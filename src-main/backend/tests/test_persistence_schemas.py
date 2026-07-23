from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models import (
    ExperimentalCondition,
    FeedbackStatus,
    JudgeDecision,
    JudgeEvaluationStatus,
    LearningEventType,
    ResearchStatus,
    WorkflowOutcome,
    WorkflowStage,
)
from app.schemas import (
    FeedbackRecordCreate,
    JudgeEvaluationCreate,
    LearningEventCreate,
    LearningEventRead,
    ResearchEvaluationCreate,
    WorkflowRunCreate,
)


def uuid_string() -> str:
    return str(uuid4())


def test_workflow_terminal_timestamp_validation() -> None:
    started_at = datetime.now(timezone.utc)
    completed_at = started_at + timedelta(seconds=1)
    schema = WorkflowRunCreate(
        submission_id="submission-external",
        current_stage=WorkflowStage.COMPLETED,
        regeneration_count=1,
        final_outcome=WorkflowOutcome.SECOND_PASS,
        started_at=started_at,
        completed_at=completed_at,
    )
    assert schema.final_outcome is WorkflowOutcome.SECOND_PASS

    with pytest.raises(ValidationError):
        WorkflowRunCreate(
            submission_id="submission-external",
            current_stage=WorkflowStage.COMPLETED,
            started_at=started_at,
        )


def test_feedback_schema_enforces_generated_and_fallback_shapes() -> None:
    generated = FeedbackRecordCreate(
        submission_id="submission-external",
        workflow_run_id=uuid_string(),
        feedback_content={"summary": "Good start."},
        status=FeedbackStatus.PENDING_JUDGEMENT,
        generation_attempt=1,
        model="test-model",
    )
    assert generated.generation_attempt == 1

    fallback = FeedbackRecordCreate(
        submission_id="submission-external",
        workflow_run_id=uuid_string(),
        feedback_content={"summary": "Feedback is temporarily unavailable."},
        status=FeedbackStatus.SAFE_FALLBACK,
    )
    assert fallback.model is None

    with pytest.raises(ValidationError):
        FeedbackRecordCreate(
            submission_id="submission-external",
            workflow_run_id=uuid_string(),
            feedback_content={"summary": "Missing details."},
            status=FeedbackStatus.ACCEPTED,
        )


def test_judge_schema_accepts_valid_and_controlled_failure_results() -> None:
    valid = JudgeEvaluationCreate(
        feedback_id=uuid_string(),
        evaluation_status=JudgeEvaluationStatus.VALID,
        decision=JudgeDecision.PASS,
        correctness_score=90,
        relevance_score=90,
        grounding_score=90,
        actionability_score=90,
        safety_score=100,
        reason="Grounded response",
    )
    assert valid.decision is JudgeDecision.PASS

    malformed = JudgeEvaluationCreate(
        feedback_id=uuid_string(),
        evaluation_status=JudgeEvaluationStatus.MALFORMED,
        reason="Invalid JSON",
        error_category="invalid_json",
    )
    assert malformed.decision is None

    with pytest.raises(ValidationError):
        JudgeEvaluationCreate(
            feedback_id=uuid_string(),
            evaluation_status=JudgeEvaluationStatus.VALID,
            decision=JudgeDecision.FAIL,
            correctness_score=101,
            relevance_score=90,
            grounding_score=90,
            actionability_score=90,
            safety_score=100,
            reason="Invalid score",
        )


def test_learning_event_metadata_is_allow_listed_and_private() -> None:
    event = LearningEventCreate(
        pseudonymous_user_id="student-pseudonym",
        course_id="course-external",
        task_id="task-external",
        event_type=LearningEventType.SUBMISSION,
        correlation_id=uuid_string(),
        metadata={"attempt_number": 1, "score": 0.75},
    )
    assert event.metadata["attempt_number"] == 1

    with pytest.raises(ValidationError):
        LearningEventCreate(
            pseudonymous_user_id="student-pseudonym",
            course_id="course-external",
            task_id="task-external",
            event_type=LearningEventType.SUBMISSION,
            correlation_id=uuid_string(),
            metadata={"raw_answer": "secret answer"},
        )

    field_names = set(LearningEventRead.model_fields)
    assert not field_names & {
        "name",
        "email",
        "raw_answer",
        "submitted_answer",
        "api_key",
        "access_token",
    }


def test_research_schema_validates_measurements_and_completion() -> None:
    completed_at = datetime.now(timezone.utc)
    schema = ResearchEvaluationCreate(
        case_id=uuid_string(),
        pseudonymous_user_id="student-pseudonym",
        course_id="course-external",
        task_id="task-external",
        submission_reference="submission-external",
        experimental_condition=ExperimentalCondition.AGENTIC_RAG,
        prompt_version="feedback-v1",
        provider="fake-provider",
        model="test-model",
        generated_output={"summary": "Grounded feedback"},
        latency_ms=125,
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        estimated_cost=Decimal("0.001"),
        status=ResearchStatus.COMPLETED,
        completed_at=completed_at,
    )
    assert schema.total_tokens == 30

    with pytest.raises(ValidationError):
        ResearchEvaluationCreate(
            case_id=uuid_string(),
            pseudonymous_user_id="student-pseudonym",
            course_id="course-external",
            task_id="task-external",
            submission_reference="submission-external",
            experimental_condition=ExperimentalCondition.AGENTIC_RAG,
            prompt_version="feedback-v1",
            provider="fake-provider",
            model="test-model",
            input_tokens=10,
            output_tokens=20,
            total_tokens=29,
            status=ResearchStatus.PENDING,
        )


def test_external_identifiers_are_required_but_not_foreign_models() -> None:
    with pytest.raises(ValidationError):
        WorkflowRunCreate(submission_id="   ")
