"""One bounded generated episode through existing review, draft and evidence stores."""

import asyncio
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from support.task_review import approve_fixture_task, approve_sourced_fixture_task
from test_assessment_definitions import _setup
from test_task_generation_api import StaticRetrieval

from app.models import LearningTask, TaskType, User
from app.models.assessment import AssessmentDefinitionVersion, TaskFormVersion
from app.models.source_history import SourcePassage
from app.schemas.multipart_generation import STAGES
from app.services.local_ai import LocalTaskGenerationClient
from app.services.multipart_generation import SOURCE_FACT, local_multipart, validate_multipart
from app.services.rag.contracts import RetrievalHit
from app.services.rag.task_generation import GenerateTasksInput, GroundedTaskGenerationService
from app.services.task_review import TaskReviewError, TaskReviewService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def generated(session):
    course_id, outcome_id, owner_id, _ = _setup(session)
    prior = session.scalar(select(LearningTask).where(LearningTask.course_id == course_id))
    approve_sourced_fixture_task(session, prior, source_text=SOURCE_FACT)
    source = session.get(SourcePassage, prior.source_references[0])
    retrieval = StaticRetrieval(
        (
            RetrievalHit(
                source.id, "material", course_id, source.chunk_text, "Synthetic source", 1.0, 0
            ),
        )
    )
    task = asyncio.run(
        GroundedTaskGenerationService(session, retrieval, LocalTaskGenerationClient()).generate(
            GenerateTasksInput(
                course_id,
                prior.module_id,
                outcome_id,
                "Apply the Hadamard transformation",
                1,
                (TaskType.QUANTUM_CIRCUIT,),
                ("beginner",),
                generation_mode="multipart",
            )
        )
    )[0]
    return task, session.get(User, owner_id)


def test_multipart_contract_rejects_missing_stages_fabricated_work_and_inconsistent_sources():
    item = local_multipart([{"chunk_id": "source", "text": SOURCE_FACT}], "Apply H")
    criteria = item["marking_criteria"]
    candidate = validate_multipart(criteria, "quantum_circuit", {"source": SOURCE_FACT})
    assert candidate.assessment_design.formal_result_eligible is False
    for edit in (
        lambda value: value["multipart_candidate"]["episode_plan"].update(
            required_responses=["prediction"]
        ),
        lambda value: value["multipart_candidate"]["assessment_design"]["task_conditions"].update(
            previous_response_version_id="fabricated"
        ),
        lambda value: value["multipart_candidate"]["assessment_design"].update(
            formal_result_eligible=True
        ),
        lambda value: value["multipart_candidate"]["assessment_design"]["pass_rule_expression"][
            "clauses"
        ].pop(),
        lambda value: value["multipart_candidate"]["criterion_sources"].update(
            transfer=["unknown"]
        ),
        lambda value: value["multipart_candidate"]["source_anchors"][0].update(
            quote="Invented fact"
        ),
        lambda value: value["multipart_candidate"]["assessment_design"]["criteria"][0].update(
            evaluator_type="rules"
        ),
        lambda value: value["episode_plan"]["transfer"].update(
            starter_circuit=value["starter_circuit"]
        ),
    ):
        invalid = deepcopy(criteria)
        edit(invalid)
        with pytest.raises(ValueError):
            validate_multipart(invalid, "quantum_circuit", {"source": SOURCE_FACT})
    with pytest.raises(ValueError, match="requires a source"):
        local_multipart(
            [{"chunk_id": "source", "text": "Unrelated or incomplete quantum material"}], "Apply H"
        )
    with pytest.raises(ValueError, match="renderer"):
        validate_multipart(criteria, "revision", {"source": SOURCE_FACT})


def test_provider_cannot_substitute_an_untyped_candidate_or_persist_invalid_output(db_session):
    from test_task_generation_api import RecordingGenerator

    task, _ = generated(db_session)
    source = db_session.get(SourcePassage, task.source_references[0])
    request = GenerateTasksInput(
        task.course_id,
        task.module_id,
        task.learning_outcome_id,
        "Apply H",
        1,
        (TaskType.QUANTUM_CIRCUIT,),
        ("beginner",),
        "multipart",
    )
    retrieval = StaticRetrieval(
        (
            RetrievalHit(
                source.id, "material", task.course_id, source.chunk_text, "Synthetic", 1.0, 0
            ),
        )
    )
    before = db_session.scalar(select(func.count()).select_from(LearningTask))
    output = {
        "title": "Invalid provider candidate",
        "prompt": "Candidate prompt",
        "instructions": "Candidate instructions",
        "task_type": "quantum_circuit",
        "difficulty": "beginner",
        "learning_outcome_id": task.learning_outcome_id,
        "source_references": task.source_references,
        "marking_criteria": deepcopy(task.marking_criteria),
    }
    del output["marking_criteria"]["multipart_candidate"]
    with pytest.raises(ValueError):
        asyncio.run(
            GroundedTaskGenerationService(
                db_session, retrieval, RecordingGenerator((output,))
            ).generate(request)
        )
    assert db_session.scalar(select(func.count()).select_from(LearningTask)) == before
    assert (
        task.marking_criteria["multipart_candidate"]["source_anchors"][0]["source_reference"]
        == source.id
    )
    task.marking_criteria = output["marking_criteria"]
    with pytest.raises(TaskReviewError, match="no typed multipart"):
        TaskReviewService(db_session).validate_ready(task)


def test_generated_candidate_bridge_preserves_all_criteria_and_never_approves(db_session):
    from app.api.dependencies.authentication import get_current_user
    from app.db.session import get_db
    from app.main import create_app
    from app.services.assessment.publication import require_learner_task_available

    task, owner = generated(db_session)
    assert task.generation_prompt_version == "task-generation-multipart-v1"
    review = TaskReviewService(db_session)
    revision = review.latest_revision(task.id)
    assert review.latest_event(revision.id) is None
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: owner
    with TestClient(app) as client:
        url = f"/api/v1/assessment/courses/{task.course_id}/tasks/{task.id}/generated-assessment-draft?expected_revision_id={revision.id}"
        assert client.get(url).status_code == 409
        approve_fixture_task(db_session, task)
        with pytest.raises(TaskReviewError, match="approved assessment form"):
            require_learner_task_available(db_session, task)
        preview = client.get(url)
        assert preview.status_code == 200, preview.text
        from app.models.user import UserRole

        outsider = User(
            email="unassigned-multipart@example.test",
            full_name="Unassigned",
            password_hash="unused",
            role=UserRole.EDUCATOR,
        )
        db_session.add(outsider)
        db_session.commit()
        app.dependency_overrides[get_current_user] = lambda: outsider
        assert client.get(url).status_code == 403
        assert client.post(url).status_code == 403
        app.dependency_overrides[get_current_user] = lambda: owner
        draft = preview.json()
        assert [row["stable_key"] for row in draft["criteria"]] == list(STAGES)
        assert draft["formal_result_eligible"] is False
        assert draft["access_conditions"] == {"review_required": True}
        assert draft["task_forms"][0]["constraints"]["elicited_bloom_processes"] == []
        assert db_session.scalar(select(func.count()).select_from(AssessmentDefinitionVersion)) == 0
        saved = client.post(url)
        assert saved.status_code == 201, saved.text
        definition = db_session.get(AssessmentDefinitionVersion, saved.json()["id"])
        assert definition.approval_state.value == "DRAFT" and not definition.formal_result_eligible
        form = db_session.scalar(
            select(TaskFormVersion).where(
                TaskFormVersion.assessment_definition_version_id == definition.id
            )
        )
        assert form.task_revision_id == revision.id
        assert form.constraints["episode_plan"] == task.marking_criteria["episode_plan"]
        from app.models.assessment import CriterionVersion, PassRuleVersion, TaskApproval

        criteria = list(
            db_session.scalars(
                select(CriterionVersion).where(
                    CriterionVersion.assessment_definition_version_id == definition.id
                )
            )
        )
        assert len(criteria) == len(STAGES)
        rule = db_session.scalar(
            select(PassRuleVersion).where(
                PassRuleVersion.assessment_definition_version_id == definition.id
            )
        )
        assert {clause["criterion_version_id"] for clause in rule.expression["clauses"]} == {
            criterion.id for criterion in criteria
        }
        assert db_session.scalar(select(func.count()).select_from(TaskApproval)) == 0
        from app.services.assessment.definitions import (
            AssessmentDefinitionService,
            AssessmentDefinitionValidationError,
        )

        with pytest.raises(AssessmentDefinitionValidationError):
            AssessmentDefinitionService(db_session).approve(
                course_id=task.course_id,
                assessment_definition_id=definition.assessment_definition_id,
                expected_version=1,
                actor_user_id=owner.id,
                approval_reason="Synthetic attempt before required design review",
            )
        assert db_session.scalar(select(func.count()).select_from(TaskApproval)) == 0
        assert client.post(url).status_code == 409
        task.instructions += " Changed after preview."
        db_session.commit()
        assert client.get(url).status_code == 409


def test_generated_episode_uses_real_runtime_references_and_keeps_transfer_separate(db_session):
    from support.task_review import bootstrap_reviewed_demo
    from test_task14_lifecycle import complete, supported

    from app.api.routes.assessment import _definition_draft
    from app.models.lms import Course, CourseState, Enrollment
    from app.models.user import UserRole
    from app.schemas.lms import DraftWrite, SubmissionCreate
    from app.services.assessment.definitions import AssessmentDefinitionService
    from app.services.assessment.generated_design import generated_assessment_draft
    from app.services.lms import LmsService

    task, owner = generated(db_session)
    approve_fixture_task(db_session, task)
    revision = TaskReviewService(db_session).latest_revision(task.id)
    _, proposal = generated_assessment_draft(
        db_session, owner, task.course_id, task.id, revision.id
    )
    # Explicit synthetic reviewer decisions, never claims of real content/access validity.
    raw = proposal.model_dump(mode="json")
    raw.update(
        formal_result_eligible=True,
        access_conditions={"modes": [{"mode": "text", "preserves_construct": True}]},
    )
    raw["task_forms"][0]["constraints"]["elicited_bloom_processes"] = ["APPLY"]
    source = LmsService(db_session).create_assessment_outcome_version(
        owner, task.course_id, task.learning_outcome_id
    )
    service = AssessmentDefinitionService(db_session)
    definition = service.create_draft(
        course_id=task.course_id,
        learning_outcome_id=task.learning_outcome_id,
        actor_user_id=owner.id,
        draft=_definition_draft(type(proposal).model_validate(raw), source.id),
    )
    service.approve(
        course_id=task.course_id,
        assessment_definition_id=definition.assessment_definition_id,
        expected_version=1,
        actor_user_id=owner.id,
        approval_reason="Synthetic generated episode lifecycle test",
    )
    form = db_session.scalar(
        select(TaskFormVersion).where(
            TaskFormVersion.assessment_definition_version_id == definition.id
        )
    )
    users, _ = bootstrap_reviewed_demo(db_session)
    student = next(user for user in users if user.role is UserRole.STUDENT)
    db_session.get(Course, task.course_id).state = CourseState.PUBLISHED
    db_session.add(Enrollment(course_id=task.course_id, student_id=student.id))
    db_session.commit()
    lms = LmsService(db_session)
    started = lms.start_assessment_work(student, task.id, form.id)
    with pytest.raises(TaskReviewError, match="prediction"):
        lms.submit(
            student,
            task.id,
            SubmissionCreate(
                assessment_work_start_id=started.assessment_work_start_id,
                episode={"supported": {}},
                idempotency_key="missing-stages",
            ),
        )
    db_session.rollback()
    invalid = supported(started).model_dump(mode="json")
    invalid["episode"]["supported"]["revision"] = {
        "previous_response_version_id": "invented",
        "reason": "Changed reasoning",
    }
    with pytest.raises(TaskReviewError, match="earlier response"):
        lms.save_draft(student, task.id, DraftWrite.model_validate(invalid))
    db_session.rollback()
    for field, value in (
        ("prediction_checkpoint_id", "invented"),
        ("simulation_references", [{"run_id": "invented", "circuit_version_id": "invented"}]),
    ):
        invalid = supported(started).model_dump(mode="json")
        invalid["episode"]["supported"][field] = value
        with pytest.raises(TaskReviewError, match="does not match"):
            lms.save_draft(student, task.id, DraftWrite.model_validate(invalid))
        db_session.rollback()
    payload = complete(lms, student, task, started)
    first = lms.submit(
        student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="first")
    )
    revised = payload.model_dump(mode="json")
    revised["episode"]["supported"]["revision"] = {
        "previous_response_version_id": first.id,
        "reason": "Clarify the probability and relative phase relationship",
    }
    second = lms.submit(student, task.id, SubmissionCreate(**revised, idempotency_key="revision"))
    assert second.episode.supported.revision.previous_response_version_id == first.id
    assert second.episode.transfer.stage_start_id == first.episode.transfer.stage_start_id
    assert second.formal_assessment.result is None
