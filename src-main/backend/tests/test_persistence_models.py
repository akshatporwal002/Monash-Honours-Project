from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ExperimentalCondition,
    FeedbackRecord,
    FeedbackStatus,
    JudgeDecision,
    JudgeEvaluation,
    JudgeEvaluationStatus,
    LearningEvent,
    LearningEventType,
    ResearchEvaluation,
    ResearchStatus,
    WorkflowRun,
)
from app.schemas import (
    FeedbackRecordRead,
    JudgeEvaluationRead,
    LearningEventRead,
    ResearchEvaluationRead,
    WorkflowRunRead,
)


def create_workflow(db_session: Session, submission_id: str = "submission-1") -> WorkflowRun:
    workflow = WorkflowRun(submission_id=submission_id)
    db_session.add(workflow)
    db_session.commit()
    return workflow


def create_feedback(
    db_session: Session,
    workflow: WorkflowRun,
    attempt: int = 1,
) -> FeedbackRecord:
    feedback = FeedbackRecord(
        submission_id=workflow.submission_id,
        workflow_run_id=workflow.id,
        feedback_content={"summary": "Review the measurement result."},
        status=FeedbackStatus.PENDING_JUDGEMENT,
        generation_attempt=attempt,
        provider="fake-provider",
        model="test-model",
        prompt_version="feedback-v1",
        source_references=["source-1"],
        simulation_references=["simulation-1"],
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        estimated_cost=Decimal("0.001000"),
    )
    db_session.add(feedback)
    db_session.commit()
    return feedback


def test_create_serialize_and_retrieve_all_records(db_session: Session) -> None:
    workflow = create_workflow(db_session)
    feedback = create_feedback(db_session, workflow)
    judge = JudgeEvaluation(
        feedback_id=feedback.id,
        evaluation_status=JudgeEvaluationStatus.VALID,
        decision=JudgeDecision.PASS,
        correctness_score=90,
        relevance_score=91,
        grounding_score=92,
        actionability_score=93,
        safety_score=100,
        reason="The feedback is grounded and actionable.",
        unsupported_claims=[],
        regeneration_instructions=[],
    )
    learning_event = LearningEvent(
        pseudonymous_user_id="student-pseudonym",
        course_id="course-external",
        task_id="task-external",
        event_type=LearningEventType.SUBMISSION,
        correlation_id=workflow.id,
        metadata_payload={"attempt_number": 1},
    )
    research = ResearchEvaluation(
        case_id=str(uuid4()),
        workflow_run_id=workflow.id,
        pseudonymous_user_id="student-pseudonym",
        course_id="course-external",
        task_id="task-external",
        submission_reference=workflow.submission_id,
        experimental_condition=ExperimentalCondition.AGENTIC_RAG,
        prompt_version="feedback-v1",
        provider="fake-provider",
        model="test-model",
        input_references=["task-external", workflow.submission_id],
        retrieved_sources=[{"source_id": "source-1"}],
        generated_output={"summary": "Review the measurement result."},
        judge_result={"decision": "pass"},
        latency_ms=125,
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        estimated_cost=Decimal("0.001000"),
        regeneration_count=0,
        status=ResearchStatus.PENDING,
    )
    db_session.add_all([judge, learning_event, research])
    db_session.commit()
    db_session.refresh(workflow)
    db_session.refresh(feedback)
    db_session.refresh(judge)
    db_session.refresh(learning_event)
    db_session.refresh(research)

    assert db_session.get(WorkflowRun, workflow.id) is workflow
    assert WorkflowRunRead.model_validate(workflow).submission_id == "submission-1"
    assert FeedbackRecordRead.model_validate(feedback).source_references == ["source-1"]
    assert FeedbackRecordRead.model_validate(feedback).total_tokens == 30
    assert JudgeEvaluationRead.model_validate(judge).decision is JudgeDecision.PASS
    event_dump = LearningEventRead.model_validate(learning_event).model_dump(by_alias=True)
    assert event_dump["metadata"] == {"attempt_number": 1}
    assert ResearchEvaluationRead.model_validate(research).total_tokens == 30


def test_sqlite_foreign_keys_are_enforced(db_session: Session) -> None:
    feedback = FeedbackRecord(
        submission_id="submission-external",
        workflow_run_id=str(uuid4()),
        feedback_content={"summary": "Not persisted"},
        status=FeedbackStatus.PENDING_JUDGEMENT,
        generation_attempt=1,
        provider="fake-provider",
        model="test-model",
        prompt_version="feedback-v1",
        source_references=[],
    )
    db_session.add(feedback)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unique_submission_and_attempt_constraints(db_session: Session) -> None:
    workflow = create_workflow(db_session)
    create_feedback(db_session, workflow)

    db_session.add(WorkflowRun(submission_id=workflow.submission_id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    duplicate_attempt = FeedbackRecord(
        submission_id=workflow.submission_id,
        workflow_run_id=workflow.id,
        feedback_content={"summary": "Duplicate"},
        status=FeedbackStatus.REJECTED,
        generation_attempt=1,
        provider="fake-provider",
        model="test-model",
        prompt_version="feedback-v1",
        source_references=[],
    )
    db_session.add(duplicate_attempt)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unique_judge_and_research_condition_constraints(db_session: Session) -> None:
    workflow = create_workflow(db_session)
    feedback = create_feedback(db_session, workflow)
    first_judge = JudgeEvaluation(
        feedback_id=feedback.id,
        evaluation_status=JudgeEvaluationStatus.MALFORMED,
        reason="Malformed output",
        error_category="invalid_json",
        unsupported_claims=[],
        regeneration_instructions=[],
    )
    db_session.add(first_judge)
    db_session.commit()

    duplicate_judge = JudgeEvaluation(
        feedback_id=feedback.id,
        evaluation_status=JudgeEvaluationStatus.PROVIDER_ERROR,
        reason="Provider unavailable",
        error_category="timeout",
        unsupported_claims=[],
        regeneration_instructions=[],
    )
    db_session.add(duplicate_judge)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    case_id = str(uuid4())
    base_values = {
        "case_id": case_id,
        "pseudonymous_user_id": "student-pseudonym",
        "course_id": "course-external",
        "task_id": "task-external",
        "submission_reference": workflow.submission_id,
        "experimental_condition": ExperimentalCondition.AGENTIC_RAG,
        "prompt_version": "feedback-v1",
        "provider": "fake-provider",
        "model": "test-model",
        "input_references": [],
        "retrieved_sources": [],
        "generated_output": {},
        "latency_ms": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_cost": Decimal("0"),
        "regeneration_count": 0,
        "status": ResearchStatus.PENDING,
    }
    db_session.add(ResearchEvaluation(**base_values))
    db_session.commit()
    db_session.add(ResearchEvaluation(**base_values))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize(
    ("record"),
    [
        WorkflowRun(submission_id="submission-constraint", regeneration_count=2),
        ResearchEvaluation(
            case_id=str(uuid4()),
            pseudonymous_user_id="student-pseudonym",
            course_id="course-external",
            task_id="task-external",
            submission_reference="submission-external",
            experimental_condition=ExperimentalCondition.SINGLE_STEP_BASELINE,
            prompt_version="baseline-v1",
            provider="fake-provider",
            model="test-model",
            input_references=[],
            retrieved_sources=[],
            generated_output={},
            latency_ms=-1,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            estimated_cost=Decimal("0"),
            regeneration_count=0,
            status=ResearchStatus.PENDING,
        ),
    ],
)
def test_database_numeric_constraints(db_session: Session, record: object) -> None:
    db_session.add(record)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_database_rejects_out_of_range_judge_score(db_session: Session) -> None:
    workflow = create_workflow(db_session)
    feedback = create_feedback(db_session, workflow)
    judge = JudgeEvaluation(
        feedback_id=feedback.id,
        evaluation_status=JudgeEvaluationStatus.VALID,
        decision=JudgeDecision.FAIL,
        correctness_score=101,
        relevance_score=50,
        grounding_score=50,
        actionability_score=50,
        safety_score=50,
        reason="Invalid score",
        unsupported_claims=[],
        regeneration_instructions=["Regenerate"],
    )
    db_session.add(judge)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_feedback_shape_and_independent_json_defaults(db_session: Session) -> None:
    workflow = create_workflow(db_session)
    fallback = FeedbackRecord(
        submission_id=workflow.submission_id,
        workflow_run_id=workflow.id,
        feedback_content={"summary": "Feedback is temporarily unavailable."},
        status=FeedbackStatus.SAFE_FALLBACK,
    )
    db_session.add(fallback)
    db_session.commit()
    assert fallback.source_references == []
    assert fallback.simulation_references == []

    invalid_generated = FeedbackRecord(
        submission_id=workflow.submission_id,
        workflow_run_id=workflow.id,
        feedback_content={"summary": "Missing model"},
        status=FeedbackStatus.ACCEPTED,
        generation_attempt=2,
        source_references=[],
    )
    db_session.add(invalid_generated)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    second_workflow = create_workflow(db_session, "submission-2")
    second_fallback = FeedbackRecord(
        submission_id=second_workflow.submission_id,
        workflow_run_id=second_workflow.id,
        feedback_content={"summary": "Feedback is temporarily unavailable."},
        status=FeedbackStatus.SAFE_FALLBACK,
    )
    db_session.add(second_fallback)
    db_session.commit()
    fallback.source_references.append("source-local")
    assert second_fallback.source_references == []

    third_workflow = create_workflow(db_session, "submission-3")
    invalid_usage = FeedbackRecord(
        submission_id=third_workflow.submission_id,
        workflow_run_id=third_workflow.id,
        feedback_content={"summary": "Invalid token accounting"},
        status=FeedbackStatus.ACCEPTED,
        generation_attempt=1,
        provider="fake-provider",
        model="test-model",
        prompt_version="feedback-v1",
        input_tokens=10,
        output_tokens=5,
        total_tokens=14,
    )
    db_session.add(invalid_usage)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_restrictive_foreign_keys_preserve_evidence(db_session: Session) -> None:
    workflow = create_workflow(db_session)
    create_feedback(db_session, workflow)
    db_session.delete(workflow)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
