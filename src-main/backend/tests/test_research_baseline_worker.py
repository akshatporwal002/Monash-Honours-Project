import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.models.enums import JudgeDecision, JudgeEvaluationStatus
from app.schemas.feedback import (
    ContextProviderStatus,
    FeedbackContext,
    FeedbackResponseClassification,
    GeneratedFeedback,
    JudgeEvaluationOutcome,
    JudgeResult,
    RetrievalContext,
    SubmissionContext,
    TaskContext,
    TokenUsage,
)
from app.services.research import (
    BaselineCompletion,
    BaselineJobExecutor,
    ResearchJobClaim,
)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


def context() -> FeedbackContext:
    return FeedbackContext(
        correlation_id=str(uuid4()),
        task=TaskContext(
            task_id="task-1",
            course_id="course-1",
            task_type="short_answer",
            prompt="Task",
            difficulty="intro",
            expected_answer="Expected",
            learning_outcome_id="lo-1",
        ),
        submission=SubmissionContext(
            submission_id="submission-1",
            task_id="task-1",
            course_id="course-1",
            student_id="student-1",
            attempt_number=1,
            submitted_answer="Answer",
            submitted_at=NOW,
        ),
        retrieval_status=ContextProviderStatus.COMPLETED,
        retrieval_request_ids=["request-1"],
        retrieval_context=[
            RetrievalContext(
                retrieval_request_id="request-1",
                task_id="task-1",
                course_id="course-1",
                source_id="source-1",
                document_id="document-1",
                chunk_id="chunk-1",
                chunk_text="Must not reach baseline",
                relevance_score=1,
                source_label="Private source",
            )
        ],
    )


class Repository:
    def __init__(self) -> None:
        self.claim = ResearchJobClaim(
            research_evaluation_id=str(uuid4()),
            case_id=str(uuid4()),
            workflow_run_id=str(uuid4()),
            correlation_id=str(uuid4()),
            execution_token=str(uuid4()),
            provider="provider",
            model="model",
            lease_expires_at=NOW + timedelta(minutes=5),
            processing_attempts=1,
        )
        self.completion: BaselineCompletion | None = None
        self.failure: str | None = None

    def finalize_next_exhausted(
        self,
        *,
        now: datetime,
        maximum_attempts: int,
    ) -> str | None:
        assert now == NOW
        assert maximum_attempts == 3
        return None

    def claim_next(
        self,
        *,
        now: datetime,
        maximum_attempts: int,
    ) -> ResearchJobClaim | None:
        assert now == NOW
        assert maximum_attempts == 3
        claim, self.claim = self.claim, None  # type: ignore[assignment]
        return claim

    def complete(
        self,
        _: ResearchJobClaim,
        completion: BaselineCompletion,
        *,
        completed_at: datetime,
    ) -> bool:
        assert completed_at == NOW
        self.completion = completion
        return True

    def fail(
        self,
        _: ResearchJobClaim,
        failure_category: str,
        *,
        completed_at: datetime,
    ) -> bool:
        assert completed_at == NOW
        self.failure = failure_category
        return True


class ContextProvider:
    async def get_context(self, _: str) -> FeedbackContext:
        return context()


class Generator:
    def __init__(self) -> None:
        self.context: FeedbackContext | None = None

    async def generate(
        self,
        context: FeedbackContext,
        *,
        expected_provider: str,
        expected_model: str,
    ) -> GeneratedFeedback:
        self.context = context
        assert expected_provider == "provider"
        assert expected_model == "model"
        return GeneratedFeedback(
            feedback_content={
                "response_classification": FeedbackResponseClassification.CORRECT.value,
                "summary": "Good",
                "identified_error": None,
                "explanation": "Good",
                "improvement_actions": [],
                "recommended_next_step": "Continue",
                "source_references": [],
                "simulation_references": [],
            },
            provider="provider",
            model="model",
            prompt_version="baseline-v1",
            token_usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            estimated_cost=Decimal("0.01"),
        )


class Judge:
    def __init__(self) -> None:
        self.calls = 0
        self.context: FeedbackContext | None = None

    async def evaluate(
        self,
        context: FeedbackContext,
        _: GeneratedFeedback,
    ) -> JudgeEvaluationOutcome:
        self.calls += 1
        self.context = context
        return JudgeEvaluationOutcome(
            evaluation_status=JudgeEvaluationStatus.VALID,
            reported_decision=JudgeDecision.PASS,
            judge_result=JudgeResult(
                decision=JudgeDecision.PASS,
                correctness_score=90,
                relevance_score=90,
                grounding_score=90,
                actionability_score=90,
                safety_score=100,
                reason="Pass",
            ),
            reason="Pass",
            provider="provider",
            model="judge",
            prompt_version="judge-v1",
            token_usage=TokenUsage(input_tokens=3, output_tokens=2, total_tokens=5),
            estimated_cost=Decimal("0.002"),
        )


def test_baseline_worker_isolates_context_and_judges_exactly_once() -> None:
    repository = Repository()
    generator = Generator()
    judge = Judge()
    clock_values = iter([1.0, 1.125, 2.0, 2.025])
    executor = BaselineJobExecutor(
        repository,
        ContextProvider(),
        generator,
        judge,
        now=lambda: NOW,
        clock=lambda: next(clock_values),
    )

    processed = asyncio.run(executor.run_once())

    assert processed is True
    assert repository.failure is None
    assert repository.completion is not None
    assert repository.completion.generation_latency_ms == 125
    assert repository.completion.evaluation_latency_ms == 24
    assert repository.completion.generation_token_usage.total_tokens == 15
    assert repository.completion.evaluation_token_usage.total_tokens == 5
    assert judge.calls == 1
    assert generator.context is not None
    assert generator.context.retrieval_context == []
    assert generator.context.retrieval_status is ContextProviderStatus.NOT_REQUESTED
    assert judge.context is generator.context
