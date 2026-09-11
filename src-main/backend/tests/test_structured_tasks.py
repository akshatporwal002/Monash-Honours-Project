import asyncio
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from support.task_review import approve_fixture_task, bootstrap_reviewed_demo
from test_assessment_definitions import _setup

from app.models import LearningTask, TaskType, UserRole
from app.models.lms import Course, CourseState, Enrollment
from app.schemas.lms import DraftWrite, SubmissionCreate
from app.schemas.structured_tasks import definition_for, response_for
from app.services.lms import LmsService, LmsServiceError
from app.services.local_ai import LocalTaskGenerationClient
from app.services.rag.contracts import TaskGenerationRequest
from app.services.structured_generation import grounded_structure
from app.services.task_review import TaskReviewError, TaskReviewService
from app.services.task_types import DEFAULT_TASK_TYPE_REGISTRY, UnsupportedTaskTypeError

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def exercise(kind, source="source"):
    return grounded_structure(
        kind,
        [
            {
                "chunk_id": source,
                "text": "A Hadamard gate changes a state. Measurement returns a classical outcome.",
            }
        ],
    )


@pytest.mark.parametrize("kind", ["matching", "sequencing"])
def test_generated_identifiers_and_display_order_do_not_encode_private_key(monkeypatch, kind):
    from uuid import UUID

    from app.services import structured_generation

    shuffled = []

    def shuffle(items):
        shuffled.append(items)
        # Independently vary prompt and option presentation, without editing the key.
        if len(shuffled) % 2:
            items.reverse()

    monkeypatch.setattr(structured_generation, "_shuffle", shuffle)
    answer, criteria = exercise(kind)
    definition = criteria["structured_task"]
    key = json.loads(answer)
    groups = (
        [definition["items"]]
        if kind == "sequencing"
        else [definition["prompts"], definition["options"]]
    )
    ids = [item["id"] for group in groups for item in group]
    assert len(set(ids)) == len(ids)
    assert all(UUID(identifier).version == 4 for identifier in ids)
    assert len(shuffled) == len(groups)
    if kind == "sequencing":
        assert key["order"] == [item["id"] for item in reversed(definition["items"])]
    else:
        options = {item["id"]: item["text"] for item in definition["options"]}
        for prompt in definition["prompts"]:
            assert options[key["pairs"][prompt["id"]]].startswith(
                prompt["text"].removeprefix("Excerpt beginning: ")
            )
    # Serialization/reload keeps the generated identifiers and private relationships stable.
    reloaded = json.loads(json.dumps(criteria))
    response_for(definition_for(kind, reloaded, ["source"]), answer, complete=True)


@pytest.mark.parametrize("kind", ["matching", "sequencing"])
def test_typed_definition_validation_and_exact_evaluation(kind):
    answer, criteria = exercise(kind)
    definition = definition_for(kind, criteria, ["source"])
    response_for(definition, answer, complete=True)
    task = SimpleNamespace(
        expected_answer=answer, marking_criteria=criteria, source_references=["source"]
    )
    assert DEFAULT_TASK_TYPE_REGISTRY.is_correct(kind, task, SimpleNamespace(answer=answer))
    raw = json.loads(answer)
    if kind == "matching":
        keys, values = list(raw["pairs"]), list(raw["pairs"].values())
        raw["pairs"] = dict(zip(keys, reversed(values), strict=True))
    else:
        raw["order"].reverse()
    assert not DEFAULT_TASK_TYPE_REGISTRY.is_correct(
        kind, task, SimpleNamespace(answer=json.dumps(raw))
    )
    with pytest.raises(ValueError):
        response_for(definition, json.dumps({**raw, "unexpected": True}), complete=True)
    with pytest.raises(ValueError, match="source"):
        definition_for(kind, criteria, ["invented"])
    with pytest.raises(UnsupportedTaskTypeError):
        DEFAULT_TASK_TYPE_REGISTRY.resolve("future_unapproved_type")


@pytest.mark.parametrize("kind", ["matching", "sequencing"])
def test_review_draft_reload_submit_and_revision_keep_structured_evidence(db_session, kind):
    course_id, _, _, _ = _setup(db_session)
    task = db_session.scalar(select(LearningTask).where(LearningTask.course_id == course_id))
    task.task_type = TaskType(kind)
    answer, criteria = exercise(kind, task.source_references[0])
    task.expected_answer, task.marking_criteria = answer, criteria
    db_session.commit()
    approve_fixture_task(db_session, task)
    users, _ = bootstrap_reviewed_demo(db_session)
    student = next(user for user in users if user.role is UserRole.STUDENT)
    db_session.get(Course, course_id).state = CourseState.PUBLISHED
    db_session.add(Enrollment(course_id=course_id, student_id=student.id))
    db_session.commit()
    lms = LmsService(db_session)
    public = lms._task_read(task, student)
    assert public.structured_task.model_dump() == criteria["structured_task"]
    assert "expected_answer" not in public.model_dump()
    partial = json.dumps(
        {
            "schema_version": f"learnlens.{kind}-response.v1",
            **({"pairs": {}} if kind == "matching" else {"order": []}),
        }
    )
    lms.save_draft(student, task.id, DraftWrite(answer=partial))
    db_session.expire_all()
    assert lms.get_draft(student, task.id).answer == partial
    with pytest.raises(LmsServiceError):
        lms.submit(student, task.id, SubmissionCreate(answer=partial))
    db_session.rollback()
    lms.save_draft(student, task.id, DraftWrite(answer=answer))
    first = lms.submit(student, task.id, SubmissionCreate(answer=answer))
    revised = json.loads(answer)
    if kind == "sequencing":
        revised["order"].reverse()
    else:
        keys, values = list(revised["pairs"]), list(revised["pairs"].values())
        revised["pairs"] = dict(zip(keys, reversed(values), strict=True))
    second = lms.submit(student, task.id, SubmissionCreate(answer=json.dumps(revised)))
    assert first.id != second.id
    assert first.answer == answer
    assert second.answer == json.dumps(revised)
    assert first.formal_assessment is None and second.formal_assessment is None
    task.expected_answer = '{"schema_version":"wrong"}'
    with pytest.raises(TaskReviewError):
        TaskReviewService(db_session).validate_ready(task)


@pytest.mark.parametrize("kind", ["matching", "sequencing"])
def test_local_generation_emits_grounded_private_keys_and_valid_definitions(kind):
    result = asyncio.run(
        LocalTaskGenerationClient().generate_structured(
            TaskGenerationRequest(
                "test",
                {
                    "learning_outcome_id": "outcome",
                    "learning_outcome_text": "Interpret source evidence",
                    "task_count": 1,
                    "allowed_task_types": [kind],
                    "difficulty_levels": ["beginner"],
                    "sources": [
                        {
                            "chunk_id": "source",
                            "text": "A Hadamard gate changes a state. Measurement returns a classical outcome.",
                        }
                    ],
                },
            )
        )
    )
    task = result.tasks[0]
    definition = definition_for(kind, task["marking_criteria"], task["source_references"])
    response_for(definition, task["expected_answer"], complete=True)


@pytest.mark.parametrize("kind", ["matching", "sequencing"])
def test_grounded_generation_persists_design_and_requires_review_before_release(db_session, kind):
    from test_task_generation_api import StaticRetrieval

    from app.models.source_history import SourcePassage
    from app.services.rag.contracts import RetrievalHit
    from app.services.rag.task_generation import GenerateTasksInput, GroundedTaskGenerationService

    course_id, outcome_id, _, _ = _setup(db_session)
    prior = db_session.scalar(select(LearningTask).where(LearningTask.course_id == course_id))
    source = db_session.get(SourcePassage, prior.source_references[0])
    retrieval = StaticRetrieval(
        (
            RetrievalHit(
                source.id,
                "material",
                course_id,
                source.chunk_text,
                "Approved fixture source",
                1.0,
                0,
            ),
        )
    )
    service = GroundedTaskGenerationService(db_session, retrieval, LocalTaskGenerationClient())
    generated = asyncio.run(
        service.generate(
            GenerateTasksInput(
                course_id,
                prior.module_id,
                outcome_id,
                "Use source evidence",
                1,
                (TaskType(kind),),
                ("beginner",),
            )
        )
    )[0]
    assert generated.generation_prompt_version == "task-generation-v2"
    assert generated.marking_criteria["generation_design"]["assessment_purpose"] == "FORMATIVE"
    assert generated.source_references == [source.id]
    review = TaskReviewService(db_session)
    assert review.latest_revision(generated.id) is not None
    assert review.latest_event(review.latest_revision(generated.id).id) is None
    approve_fixture_task(db_session, generated)
    assert review.latest_event(review.latest_revision(generated.id).id).state == "APPROVED"
    generated.marking_criteria = {
        key: value
        for key, value in generated.marking_criteria.items()
        if key != "generation_design"
    }
    with pytest.raises(TaskReviewError):
        review.validate_ready(generated)


def test_local_generator_rejects_unimplemented_generation_paths():
    from app.services.local_ai import _task_scaffold

    with pytest.raises(UnsupportedTaskTypeError, match="author a reviewed episode"):
        _task_scaffold("transfer", "Apply a concept", "Source evidence")


@pytest.mark.parametrize("kind", ["matching", "sequencing"])
def test_formal_structured_response_freezes_review_and_retains_evidence_after_edit(
    db_session, kind
):
    from dataclasses import replace

    from test_assessment_definitions import _draft, _service

    from app.domain.assessment import BloomProcess
    from app.models.assessment import TaskFormVersion

    course_id, outcome_id, owner_id, outcome_version_id = _setup(db_session)
    task = db_session.scalar(select(LearningTask).where(LearningTask.course_id == course_id))
    task.task_type = TaskType(kind)
    answer, criteria = exercise(kind, task.source_references[0])
    task.expected_answer, task.marking_criteria = answer, criteria
    db_session.commit()
    approve_fixture_task(db_session, task)
    draft = replace(
        _draft(outcome_version_id=outcome_version_id, task_id=task.id, task_processes=["REMEMBER"]),
        formal_result_eligible=True,
        bloom_process=BloomProcess.REMEMBER,
        transfer_rule={"required": False},
    )
    service = _service(db_session)
    definition = service.create_draft(
        course_id=course_id, learning_outcome_id=outcome_id, actor_user_id=owner_id, draft=draft
    )
    form = db_session.scalar(
        select(TaskFormVersion).where(
            TaskFormVersion.assessment_definition_version_id == definition.id
        )
    )
    service.approve(
        course_id=course_id,
        assessment_definition_id=definition.assessment_definition_id,
        expected_version=1,
        actor_user_id=owner_id,
        approval_reason="Synthetic typed-flow test",
    )
    users, _ = bootstrap_reviewed_demo(db_session)
    student = next(user for user in users if user.role is UserRole.STUDENT)
    db_session.get(Course, course_id).state = CourseState.PUBLISHED
    db_session.add(Enrollment(course_id=course_id, student_id=student.id))
    db_session.commit()
    lms = LmsService(db_session)
    started = lms.start_assessment_work(student, task.id, form.id)
    lms.save_draft(
        student,
        task.id,
        DraftWrite(answer=answer, assessment_work_start_id=started.assessment_work_start_id),
    )
    attempt = lms.submit(
        student,
        task.id,
        SubmissionCreate(
            answer=answer,
            assessment_work_start_id=started.assessment_work_start_id,
            idempotency_key="typed-first",
        ),
    )
    assert attempt.assessment_work_start_id == started.assessment_work_start_id
    assert attempt.answer == answer and attempt.formal_assessment.result is None
    task.instructions += " Changed after starting."
    db_session.commit()
    with pytest.raises((TaskReviewError, LmsServiceError)):
        lms.save_draft(
            student,
            task.id,
            DraftWrite(answer=answer, assessment_work_start_id=started.assessment_work_start_id),
        )
    db_session.rollback()
    assert lms.get_draft(student, task.id).answer == answer
