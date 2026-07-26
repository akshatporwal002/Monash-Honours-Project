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
    ResearchEvaluationRead,
    WorkflowRunCreate,
)


def uuid_string() -> str:
    return str(uuid4())


def pseudonym(character: str) -> str:
    return f"v1_{character * 64}"


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
        provider="fake-provider",
        model="test-model",
        prompt_version="feedback-v1",
        usage_complete=True,
    )
    assert generated.generation_attempt == 1
    assert generated.usage_complete is True

    with pytest.raises(ValidationError):
        FeedbackRecordCreate(
            submission_id="submission-external",
            workflow_run_id=uuid_string(),
            feedback_content={"summary": "Invalid usage."},
            status=FeedbackStatus.ACCEPTED,
            generation_attempt=1,
            provider="fake-provider",
            model="test-model",
            prompt_version="feedback-v1",
            input_tokens=10,
            output_tokens=5,
            total_tokens=14,
        )

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
        reported_decision=JudgeDecision.PASS,
        decision=JudgeDecision.PASS,
        correctness_score=90,
        relevance_score=90,
        grounding_score=90,
        actionability_score=90,
        safety_score=100,
        reason="Grounded response",
        provider="fake-provider",
        model="fake-judge-model",
        prompt_version="quality-judge-v1",
        usage_complete=True,
    )
    assert valid.decision is JudgeDecision.PASS
    assert valid.usage_complete is True

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
            reported_decision=JudgeDecision.FAIL,
            decision=JudgeDecision.FAIL,
            correctness_score=101,
            relevance_score=90,
            grounding_score=90,
            actionability_score=90,
            safety_score=100,
            reason="Invalid score",
            provider="fake-provider",
            model="fake-judge-model",
            prompt_version="quality-judge-v1",
        )

    for invalid_policy in (
        {"reported_decision": JudgeDecision.FAIL},
        {"correctness_score": 79},
        {"safety_score": 99},
        {"unsupported_claims": ["Unsupported."]},
        {"quality_policy_version": "quality-policy-v0"},
    ):
        with pytest.raises(ValidationError):
            JudgeEvaluationCreate.model_validate(
                {
                    **valid.model_dump(mode="python"),
                    **invalid_policy,
                }
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
    workflow_id = uuid_string()
    schema = ResearchEvaluationCreate(
        case_id=workflow_id,
        workflow_run_id=workflow_id,
        correlation_id=uuid_string(),
        pseudonymous_user_id=pseudonym("a"),
        course_id="course-external",
        task_id="task-external",
        task_type="short_answer",
        submission_reference=pseudonym("b"),
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
        fallback_used=False,
        comparable=True,
        usage_complete=True,
        retrieval_request_count=1,
        retrieval_hit_count=1,
        status=ResearchStatus.COMPLETED,
        completed_at=completed_at,
    )
    assert schema.total_tokens == 30
    assert schema.workflow_run_id == schema.case_id
    assert schema.usage_complete is True

    with pytest.raises(ValidationError):
        ResearchEvaluationCreate(
            case_id=workflow_id,
            workflow_run_id=workflow_id,
            correlation_id=uuid_string(),
            pseudonymous_user_id=pseudonym("a"),
            course_id="course-external",
            task_id="task-external",
            task_type="short_answer",
            submission_reference=pseudonym("b"),
            experimental_condition=ExperimentalCondition.AGENTIC_RAG,
            prompt_version="feedback-v1",
            provider="fake-provider",
            model="test-model",
            input_tokens=10,
            output_tokens=20,
            total_tokens=29,
            status=ResearchStatus.PENDING,
        )


def test_research_schema_enforces_shared_id_cost_claim_and_baseline_contracts() -> None:
    workflow_id = uuid_string()
    values: dict[str, object] = {
        "case_id": workflow_id,
        "workflow_run_id": workflow_id,
        "correlation_id": uuid_string(),
        "pseudonymous_user_id": pseudonym("a"),
        "course_id": "course-external",
        "task_id": "task-external",
        "task_type": "short_answer",
        "submission_reference": pseudonym("b"),
        "experimental_condition": ExperimentalCondition.SINGLE_STEP_BASELINE,
        "prompt_version": "baseline-v1",
        "provider": "fake-provider",
        "model": "test-model",
    }

    pending = ResearchEvaluationCreate.model_validate(values)
    assert pending.status is ResearchStatus.PENDING

    with pytest.raises(ValidationError):
        ResearchEvaluationCreate.model_validate(
            {
                **values,
                "workflow_run_id": uuid_string(),
            }
        )
    with pytest.raises(ValidationError):
        ResearchEvaluationCreate.model_validate(
            {
                **values,
                "measurement_schema_version": "legacy-v1",
            }
        )
    with pytest.raises(ValidationError):
        ResearchEvaluationCreate.model_validate(
            {
                **values,
                "estimated_cost": Decimal("0.0000001"),
            }
        )
    with pytest.raises(ValidationError):
        ResearchEvaluationCreate.model_validate(
            {
                **values,
                "input_references": ["source-1"],
            }
        )
    with pytest.raises(ValidationError):
        ResearchEvaluationCreate.model_validate(
            {
                **values,
                "status": ResearchStatus.RUNNING,
                "processing_attempts": 1,
            }
        )

    running = ResearchEvaluationCreate.model_validate(
        {
            **values,
            "status": ResearchStatus.RUNNING,
            "execution_token": uuid_string(),
            "lease_expires_at": datetime.now(timezone.utc),
            "processing_attempts": 1,
        }
    )
    assert running.execution_token is not None


def test_research_read_preserves_explicitly_incomplete_legacy_measurements() -> None:
    legacy = ResearchEvaluationRead(
        id=uuid_string(),
        created_at=datetime.now(timezone.utc),
        case_id=uuid_string(),
        workflow_run_id=None,
        correlation_id=None,
        pseudonymous_user_id="legacy-direct-actor",
        course_id="course-external",
        task_id="task-external",
        task_type="unknown",
        submission_reference="legacy-direct-submission",
        experimental_condition=ExperimentalCondition.AGENTIC_RAG,
        prompt_version="feedback-v0",
        provider="legacy-provider",
        model="legacy-model",
        retrieved_sources=[{"source_id": "legacy-source"}],
        measurement_schema_version="legacy-v1",
        status=ResearchStatus.PENDING,
    )

    assert legacy.measurement_schema_version == "legacy-v1"
    assert legacy.workflow_run_id is None
    assert legacy.comparable is False
    assert legacy.usage_complete is False

    legacy_baseline = ResearchEvaluationRead(
        id=uuid_string(),
        created_at=datetime.now(timezone.utc),
        case_id=uuid_string(),
        workflow_run_id=None,
        correlation_id=None,
        pseudonymous_user_id="legacy-direct-actor",
        course_id="course-external",
        task_id="task-external",
        task_type="unknown",
        submission_reference="legacy-direct-submission",
        experimental_condition=ExperimentalCondition.SINGLE_STEP_BASELINE,
        prompt_version="legacy-baseline",
        provider="legacy-provider",
        model="legacy-model",
        input_references=["legacy-source"],
        retrieved_sources=[{"source_id": "legacy-source"}],
        simulation_reference="legacy-simulation",
        simulation_status="completed",
        measurement_schema_version="legacy-v1",
        status=ResearchStatus.PENDING,
    )
    assert legacy_baseline.retrieved_sources == [{"source_id": "legacy-source"}]
    assert legacy_baseline.simulation_reference == "legacy-simulation"


def test_external_identifiers_are_required_but_not_foreign_models() -> None:
    with pytest.raises(ValidationError):
        WorkflowRunCreate(submission_id="   ")
