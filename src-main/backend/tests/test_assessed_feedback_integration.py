import asyncio
from decimal import Decimal

from sqlalchemy.orm import Session
from support.assessment import build_assessment_attempt

from app.models import JudgeDecision, SubmissionAttempt
from app.schemas.feedback import (
    FeedbackPipelineStatus,
    GeneratedFeedback,
    JudgeResult,
    TaskContext,
    TokenUsage,
)
from app.services.feedback.context import DefaultFeedbackContextCollector
from app.services.feedback.fakes import (
    FakeFeedbackGenerator,
    FakeFeedbackJudge,
    InMemoryTaskProvider,
)
from app.services.feedback.pipeline import FeedbackPipeline
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository
from app.services.feedback.runtime import LmsSubmissionProvider


def _generated_feedback() -> GeneratedFeedback:
    return GeneratedFeedback(
        feedback_content={
            "summary": "The response was accepted for evidence-based feedback.",
            "recommended_next_step": "Review the criterion evidence when it is available.",
        },
        provider="test-provider",
        model="test-feedback-model",
        prompt_version="feedback-test-v1",
        token_usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        estimated_cost=Decimal("0.001"),
    )


def _approved_judgement() -> JudgeResult:
    return JudgeResult(
        decision=JudgeDecision.PASS,
        correctness_score=90,
        relevance_score=90,
        grounding_score=90,
        actionability_score=90,
        safety_score=100,
        reason="The test feedback is safe and actionable.",
    )


def test_production_adapter_preserves_null_assessment_score(db_session: Session) -> None:
    _, response, _, _, _ = build_assessment_attempt(db_session)

    context = asyncio.run(LmsSubmissionProvider(db_session).get_submission(response.id))

    assert context is not None
    assert context.submission_id == response.id
    assert context.score is None


def test_assessed_attempt_reaches_terminal_feedback_through_production_adapter(
    db_session: Session,
) -> None:
    assessment_attempt, response, _, _, _ = build_assessment_attempt(db_session)
    generator = FakeFeedbackGenerator(_generated_feedback())
    judge = FakeFeedbackJudge(_approved_judgement())
    repository = SqlAlchemyFeedbackWorkflowRepository(db_session)
    task = TaskContext(
        task_id=response.task_id,
        course_id=assessment_attempt.course_id,
        task_type="quiz",
        prompt="Explain the observed interference pattern.",
        difficulty="intermediate",
        marking_criteria="Connect the observation to the claim.",
        learning_outcome_id="assessment-outcome",
    )
    pipeline = FeedbackPipeline(
        LmsSubmissionProvider(db_session),
        DefaultFeedbackContextCollector(InMemoryTaskProvider({response.task_id: task})),
        generator,
        judge,
        repository,
    )

    result = asyncio.run(pipeline.run(response.id))

    assert result.status is FeedbackPipelineStatus.VALIDATED
    assert generator.contexts[0].submission.score is None
    stored_response = db_session.get(SubmissionAttempt, response.id)
    assert stored_response is not None
    assert stored_response.score is None
    assert stored_response.answer == "The response links the observation to the claim."


def test_assessed_response_survives_feedback_generation_failure(db_session: Session) -> None:
    assessment_attempt, response, _, _, _ = build_assessment_attempt(db_session)
    generator = FakeFeedbackGenerator(
        _generated_feedback(),
        error=RuntimeError("feedback provider unavailable"),
    )
    judge = FakeFeedbackJudge(_approved_judgement())
    task = TaskContext(
        task_id=response.task_id,
        course_id=assessment_attempt.course_id,
        task_type="quiz",
        prompt="Explain the observed interference pattern.",
        difficulty="intermediate",
        marking_criteria="Connect the observation to the claim.",
        learning_outcome_id="assessment-outcome",
    )
    pipeline = FeedbackPipeline(
        LmsSubmissionProvider(db_session),
        DefaultFeedbackContextCollector(InMemoryTaskProvider({response.task_id: task})),
        generator,
        judge,
        SqlAlchemyFeedbackWorkflowRepository(db_session),
    )

    result = asyncio.run(pipeline.run(response.id))

    assert result.status is FeedbackPipelineStatus.FALLBACK
    assert judge.call_count == 0
    stored_response = db_session.get(SubmissionAttempt, response.id)
    assert stored_response is not None
    assert stored_response.score is None
    assert stored_response.answer == "The response links the observation to the claim."
