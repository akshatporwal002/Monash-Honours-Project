from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import JudgeDecision, JudgeEvaluationStatus
from app.schemas.feedback import (
    FeedbackContext,
    FeedbackPipelineResult,
    FeedbackPipelineStatus,
    GeneratedFeedback,
    JudgeEvaluationOutcome,
    JudgeResult,
    RetrievalContext,
    SimulationContext,
    SubmissionContext,
    TaskContext,
    TokenUsage,
)


def test_task_requires_expected_answer_or_marking_criteria() -> None:
    with pytest.raises(ValidationError):
        TaskContext(
            task_id="task-1",
            course_id="course-1",
            task_type="short_answer",
            prompt="Explain a qubit.",
            difficulty="introductory",
            learning_outcome_id="outcome-1",
        )


def test_feedback_context_requires_matching_task_reference() -> None:
    task = TaskContext(
        task_id="task-1",
        course_id="course-1",
        task_type="short_answer",
        prompt="Explain a qubit.",
        difficulty="introductory",
        marking_criteria="Describe a two-state quantum system.",
        learning_outcome_id="outcome-1",
    )
    submission = SubmissionContext(
        submission_id="submission-1",
        task_id="task-2",
        student_id="student-pseudonym",
        attempt_number=1,
        submitted_answer="A quantum bit.",
        submitted_at=datetime.now(timezone.utc),
    )

    with pytest.raises(ValidationError):
        FeedbackContext(
            correlation_id=str(uuid4()),
            task=task,
            submission=submission,
        )


@pytest.mark.parametrize("missing_scope", ["submission", "retrieval", "simulation"])
def test_feedback_context_rejects_missing_provider_scope(missing_scope: str) -> None:
    task = TaskContext(
        task_id="task-1",
        course_id="course-1",
        task_type="short_answer",
        prompt="Explain a qubit.",
        difficulty="introductory",
        marking_criteria="Describe superposition.",
        learning_outcome_id="outcome-1",
    )
    submission = SubmissionContext(
        submission_id="submission-1",
        task_id="task-1",
        course_id=None if missing_scope == "submission" else "course-1",
        student_id="student-private",
        attempt_number=1,
        submitted_answer="A quantum bit.",
        submitted_at=datetime.now(timezone.utc),
    )
    retrieval = RetrievalContext(
        retrieval_request_id="request-1",
        task_id=None if missing_scope == "retrieval" else "task-1",
        course_id=None if missing_scope == "retrieval" else "course-1",
        source_id="source-1",
        document_id="document-1",
        chunk_id="chunk-1",
        chunk_text="A scoped source.",
        relevance_score=0.9,
        source_label="Course notes",
    )
    simulation = SimulationContext(
        simulation_id="simulation-1",
        task_id=None if missing_scope == "simulation" else "task-1",
        course_id=None if missing_scope == "simulation" else "course-1",
        status="completed",
    )

    with pytest.raises(ValidationError):
        FeedbackContext(
            correlation_id=str(uuid4()),
            task=task,
            submission=submission,
            retrieval_context=[retrieval],
            simulation_context=simulation,
        )


def test_token_usage_and_feedback_content_are_validated() -> None:
    with pytest.raises(ValidationError):
        TokenUsage(input_tokens=10, output_tokens=5, total_tokens=14)

    with pytest.raises(ValidationError):
        GeneratedFeedback(
            feedback_content={},
            provider="fake-provider",
            model="fake-model",
            prompt_version="feedback-v1",
            token_usage=TokenUsage(),
            estimated_cost=Decimal("0"),
        )


def test_rejected_pipeline_result_cannot_release_feedback() -> None:
    generated = GeneratedFeedback(
        feedback_content={"summary": "Structured feedback"},
        provider="fake-provider",
        model="fake-model",
        prompt_version="feedback-v1",
        token_usage=TokenUsage(),
        estimated_cost=Decimal("0"),
    )
    judge = JudgeResult(
        decision=JudgeDecision.FAIL,
        correctness_score=40,
        relevance_score=50,
        grounding_score=50,
        actionability_score=50,
        safety_score=100,
        reason="Feedback needs revision.",
    )

    with pytest.raises(ValidationError):
        FeedbackPipelineResult(
            workflow_run_id=str(uuid4()),
            feedback_id=str(uuid4()),
            submission_id="submission-1",
            status=FeedbackPipelineStatus.FALLBACK,
            validated_feedback=generated,
            judge_result=judge,
            latency_ms=0,
            token_usage=generated.token_usage,
            estimated_cost=generated.estimated_cost,
        )


def _passing_judge_payload() -> dict[str, object]:
    return {
        "evaluation_status": JudgeEvaluationStatus.VALID,
        "reported_decision": JudgeDecision.PASS,
        "judge_result": JudgeResult(
            decision=JudgeDecision.PASS,
            correctness_score=80,
            relevance_score=80,
            grounding_score=80,
            actionability_score=80,
            safety_score=100,
            reason="Policy threshold met.",
        ),
        "reason": "Policy threshold met.",
        "provider": "provider",
        "model": "judge-model",
        "prompt_version": "quality-judge-v1",
        "quality_policy_version": "quality-policy-v1",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reported_decision", JudgeDecision.FAIL),
        ("correctness_score", 79),
        ("relevance_score", 79),
        ("grounding_score", 79),
        ("actionability_score", 79),
        ("safety_score", 99),
        ("unsupported_claims", ["Unsupported statement."]),
        ("quality_policy_version", "quality-policy-v0"),
    ],
)
def test_effective_pass_cannot_bypass_quality_policy(
    field: str,
    value: object,
) -> None:
    payload = _passing_judge_payload()
    if field in {
        "correctness_score",
        "relevance_score",
        "grounding_score",
        "actionability_score",
        "safety_score",
        "unsupported_claims",
    }:
        result = payload["judge_result"]
        assert isinstance(result, JudgeResult)
        payload["judge_result"] = result.model_copy(update={field: value})
    else:
        payload[field] = value

    with pytest.raises(ValidationError):
        JudgeEvaluationOutcome.model_validate(payload)


def test_nested_simulation_and_judge_values_are_bounded() -> None:
    with pytest.raises(ValidationError):
        SimulationContext(
            simulation_id="simulation-1",
            status="completed",
            measurement_counts={"x" * 256: 1},
        )

    payload = _passing_judge_payload()
    result = payload["judge_result"]
    assert isinstance(result, JudgeResult)
    payload["judge_result"] = result.model_copy(
        update={"unsupported_claims": ["x" * 4_001]},
    )
    with pytest.raises(ValidationError):
        JudgeEvaluationOutcome.model_validate(payload)
