"""Required source-led types, reviewed candidates and actual generation lineage."""

import asyncio
import json
from copy import deepcopy
from dataclasses import replace

import pytest
from sqlalchemy import select
from support.task_review import approve_fixture_task, approve_sourced_fixture_task
from test_activity_continuation import context as context
from test_assessment_definitions import _setup
from test_task_generation_api import StaticRetrieval

from app.models import FeedbackRecord, LearningTask, TaskType, User
from app.models.lms import SubmissionAttempt
from app.models.source_history import SourcePassage
from app.models.task_review import CategoryQualityReview
from app.schemas.generation_context import GenerationContext
from app.schemas.lms import SubmissionCreate
from app.services.generation_context import generation_options, resolve_generation_context
from app.services.lms import LmsService
from app.services.local_ai import LocalTaskGenerationClient, _condition_drafts
from app.services.multipart_generation import validate_multipart
from app.services.rag.contracts import RetrievalHit
from app.services.rag.task_generation import GenerateTasksInput, GroundedTaskGenerationService
from app.services.source_episode_generation import EPISODE_TYPES
from app.services.task_review import TaskReviewService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")
SOURCE = "A Pauli X gate exchanges the computational basis states. Applying the gate twice restores the original state."


def setup(session):
    course, outcome, owner, _ = _setup(session)
    task = session.scalar(select(LearningTask).where(LearningTask.course_id == course))
    approve_sourced_fixture_task(session, task, source_text=SOURCE)
    return task, session.get(User, owner)


def service_for(session, task, client=None):
    source = session.get(SourcePassage, task.source_references[0])
    return GroundedTaskGenerationService(
        session,
        StaticRetrieval(
            (
                RetrievalHit(
                    source.id,
                    "material",
                    task.course_id,
                    source.chunk_text,
                    "Synthetic notes",
                    1.0,
                    0,
                ),
            )
        ),
        client or LocalTaskGenerationClient(),
    )


def request_for(task, types, **kwargs):
    return GenerateTasksInput(
        task.course_id,
        task.module_id,
        task.learning_outcome_id,
        "Apply the cited relationship",
        len(types),
        tuple(types),
        ("beginner",),
        **kwargs,
    )


def test_every_required_text_type_generates_reviewable_typed_source_evidence(db_session):
    prior, owner = setup(db_session)
    tasks = asyncio.run(
        service_for(db_session, prior).generate(
            request_for(prior, [TaskType(t) for t in sorted(EPISODE_TYPES)])
        )
    )
    assert {task.task_type.value for task in tasks} == EPISODE_TYPES
    for task in tasks:
        assert task.expected_answer is None
        assert SOURCE in task.description
        assert task.marking_criteria["response_review"] == "human"
        assert task.marking_criteria["source_episode"]["source_reference"] in task.source_references
        assert not TaskReviewService(db_session).summary(task)["available"]
        TaskReviewService(db_session).validate_ready(task)
        public = LmsService(db_session)._task_read(task).model_dump(mode="json")
        assert "Fresh application:" not in json.dumps(public)
        assert public["episode_plan"] is None
    assert len({task.description for task in tasks}) == len(tasks)


@pytest.mark.parametrize("task_type", [TaskType.QUANTUM_CIRCUIT, TaskType.EXPLANATION])
def test_non_hadamard_multipart_has_complete_unapproved_design_and_private_transfer(
    db_session, task_type
):
    prior, owner = setup(db_session)
    task = asyncio.run(
        service_for(db_session, prior).generate(
            request_for(prior, [task_type], generation_mode="multipart")
        )
    )[0]
    texts = {ref: db_session.get(SourcePassage, ref).chunk_text for ref in task.source_references}
    candidate = validate_multipart(task.marking_criteria, task_type.value, texts)
    assert candidate.family == "source_application_transfer"
    assert len(candidate.assessment_design.criteria) == 5
    assert not candidate.assessment_design.formal_result_eligible
    assert candidate.assessment_design.task_forms == []
    TaskReviewService(db_session).validate_ready(task)
    assert "Fresh application:" not in json.dumps(
        LmsService(db_session)._task_read(task).model_dump(mode="json")
    )
    invalid = deepcopy(task.marking_criteria)
    invalid["source_episode"]["quote"] = "An invented relationship with no evidence."
    with pytest.raises(ValueError, match="source anchor"):
        validate_multipart(invalid, task_type.value, texts)


def test_variant_binds_exact_revision_and_rejects_stale_or_out_of_scope_inputs(db_session):
    prior, owner = setup(db_session)
    revision = TaskReviewService(db_session).latest_revision(prior.id)
    context = GenerationContext(variant_task_id=prior.id, variant_revision_id=revision.id)
    request = request_for(prior, [TaskType.EXPLANATION], generation_context=context)
    task = asyncio.run(service_for(db_session, prior).generate(request))[0]
    assert task.marking_criteria["generation_lineage"]["task_revision_id"] == revision.id
    assert task.description != prior.description
    assert "contrasting example" in task.description
    assert not TaskReviewService(db_session).summary(task)["available"]
    with pytest.raises(ValueError, match="course and learning outcome"):
        resolve_generation_context(
            db_session, replace(request, learning_outcome_id="another-outcome")
        )
    prior.instructions += " Changed demand."
    TaskReviewService(db_session).capture(prior, owner.id)
    with pytest.raises(ValueError, match="current task revision"):
        asyncio.run(service_for(db_session, prior).generate(request))


def test_feedback_uses_real_approved_response_and_provenance_without_copying_it(
    context, db_session
):
    curriculum, workflow_id, _, _ = context
    _, teacher, learner, course, tasks, _, _ = curriculum
    prior = tasks[0]
    feedback = db_session.scalar(
        select(FeedbackRecord).where(FeedbackRecord.workflow_run_id == workflow_id)
    )
    generation_context = GenerationContext(
        response_version_id=feedback.submission_id, feedback_id=feedback.id
    )
    request = request_for(prior, [TaskType.REASONING], generation_context=generation_context)
    lineage, payload = resolve_generation_context(db_session, request)
    assert payload["prior_response"]["answer"] == "b"
    assert payload["feedback"] == feedback.feedback_content
    task = asyncio.run(service_for(db_session, prior).generate(request))[0]
    assert task.marking_criteria["generation_lineage"] == lineage
    assert "reasoning step" in task.description
    assert feedback.id not in json.dumps(
        LmsService(db_session)._task_read(task).model_dump(mode="json")
    )
    options = LmsService(db_session).task_generation_options(
        teacher, course.id, prior.learning_outcome_id
    )
    assert generation_context.model_dump(exclude_none=True) in [
        option["context"] for option in options
    ]
    with pytest.raises(Exception) as denied:
        LmsService(db_session).task_generation_options(
            learner, course.id, prior.learning_outcome_id
        )
    assert denied.value.status_code == 403
    with pytest.raises(ValueError, match="real response"):
        resolve_generation_context(
            db_session,
            replace(
                request,
                generation_context=GenerationContext(
                    response_version_id=feedback.submission_id, feedback_id="invented"
                ),
            ),
        )
    with pytest.raises(ValueError, match="course and learning outcome"):
        resolve_generation_context(
            db_session,
            replace(
                request,
                generation_context=GenerationContext(
                    response_version_id="invented", feedback_id=feedback.id
                ),
            ),
        )
    assert generation_options(db_session, "other-course", prior.learning_outcome_id) == []


def test_local_feedback_focus_depends_on_actual_response_and_feedback():
    drafts = [{"title": "Draft", "prompt": "Use the cited source", "marking_criteria": {}}]
    _condition_drafts(
        drafts,
        {
            "kind": "feedback",
            "prior_response": {"answer": "My explanation", "code": None},
            "feedback": {"improvement_actions": ["Include code for the missing step"]},
        },
    )
    assert "missing code step" in drafts[0]["prompt"]
    assert "My explanation" not in drafts[0]["prompt"]
    with pytest.raises(ValueError):
        GenerationContext(response_version_id="actual", feedback_id=None)


def test_generated_practice_types_submit_and_reload_without_assessment_work(context, db_session):
    curriculum, _, _, _ = context
    _, _, learner, _, tasks, _, _ = curriculum
    prior = tasks[0]
    service = LmsService(db_session)
    for task_type in sorted(EPISODE_TYPES):
        task = asyncio.run(
            service_for(db_session, prior).generate(request_for(prior, [TaskType(task_type)]))
        )[0]
        approve_fixture_task(db_session, task)
        review = TaskReviewService(db_session)
        revision = review.latest_revision(task.id)
        criteria = revision.snapshot["marking_criteria"]
        generation = criteria["representation_generation"]["practice"]
        assert criteria == task.marking_criteria
        assert criteria["practice_representations"] == generation["installed"]["practice"]
        assert generation["candidate"]["variants"]
        for variant in generation["candidate"]["variants"]:
            assert set(variant["source_references"]) <= set(task.source_references)
            for quote in variant["source_quotes"]:
                passage = db_session.get(SourcePassage, quote["source_reference"])
                assert passage.course_id == task.course_id
                assert quote["quote"] in passage.chunk_text
            if task_type == "transfer":
                assert variant["support_kind"] == "accessibility"
                assert variant["instructional_support_level"] == 0
        event = review.latest_event(revision.id)
        quality = db_session.scalar(
            select(CategoryQualityReview).where(
                CategoryQualityReview.task_review_event_id == event.id,
            )
        )
        assert quality.task_revision_id == revision.id and quality.course_id == task.course_id
        assert len(quality.receipt["assessment"]["findings"]) == 10
        assert all(
            "Synthetic fixture" in finding["reason"]
            for finding in quality.receipt["assessment"]["findings"]
        )
        field = "application" if task_type == "transfer" else task_type
        value = (
            {"answer": "A new example with its changed condition"}
            if field in {"application", "prediction"}
            else "A source-grounded explanation of the relationship"
        )
        payload = SubmissionCreate(
            answer="See the typed response", episode={"supported": {field: value}}
        )
        saved = service.submit(learner, task.id, payload)
        retained = db_session.get(SubmissionAttempt, saved.id)
        assert retained.assessment_work_start_id is None
        assert retained.episode["supported"][field] == (
            value
            if isinstance(value, str)
            else {"answer": value["answer"], "code": None, "circuit": None}
        )
        invalid = {"answer": ""} if isinstance(value, dict) else " "
        with pytest.raises(Exception) as empty:
            service.submit(
                learner,
                task.id,
                SubmissionCreate(
                    answer="Cannot bypass typed response", episode={"supported": {field: invalid}}
                ),
            )
        assert empty.value.status_code == 422


@pytest.mark.parametrize(
    "source,gate,qubits",
    [
        ("A Pauli X gate flips a computational basis state.", "x", 1),
        ("The CNOT gate changes the target when its control is one.", "cx", 2),
    ],
)
def test_code_and_circuit_scaffolds_use_the_gate_in_the_source(source, gate, qubits):
    from app.services.local_ai import _task_scaffold

    _, criteria, code = _task_scaffold("code_explanation", "Explain the gate", source)
    assert f"circuit.{gate}(" in code
    assert "circuit.h(" not in code
    assert criteria["response_review"] == "human"
    _, circuit_criteria, _ = _task_scaffold("quantum_circuit", "Build the gate", source)
    assert circuit_criteria["required_gates"] == [gate]
    assert circuit_criteria["starter_circuit"]["qubits"] == qubits
    with pytest.raises(ValueError, match="source naming"):
        _task_scaffold("code_completion", "Explain a concept", "This text names no gate.")
