from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import JudgeDecision
from app.schemas.feedback import (
    FeedbackContext,
    FeedbackPipelineResult,
    FeedbackPipelineStatus,
    GeneratedFeedback,
    JudgeResult,
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
            status=FeedbackPipelineStatus.REJECTED,
            validated_feedback=generated,
            judge_result=judge,
            latency_ms=0,
            token_usage=generated.token_usage,
            estimated_cost=generated.estimated_cost,
        )
