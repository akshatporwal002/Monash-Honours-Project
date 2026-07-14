from collections.abc import Callable
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from app.models.enums import JudgeDecision
from app.schemas.feedback import (
    FeedbackPipelineResult,
    FeedbackPipelineStatus,
    GeneratedFeedback,
    JudgeResult,
)
from app.services.feedback.contracts import (
    FeedbackContextCollector,
    FeedbackGenerator,
    FeedbackJudge,
    FeedbackWorkflowRepository,
    PipelinePersistenceRequest,
    SubmissionProvider,
)
from app.services.feedback.errors import (
    ContextCollectionError,
    FeedbackGenerationError,
    FeedbackJudgementError,
    FeedbackPipelineError,
    SubmissionNotFoundError,
)


def _new_uuid() -> str:
    return str(uuid4())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FeedbackPipeline:
    def __init__(
        self,
        submission_provider: SubmissionProvider,
        context_collector: FeedbackContextCollector,
        generator: FeedbackGenerator,
        judge: FeedbackJudge,
        repository: FeedbackWorkflowRepository,
        *,
        clock: Callable[[], float] = perf_counter,
        now: Callable[[], datetime] = _utc_now,
        uuid_factory: Callable[[], str] = _new_uuid,
    ) -> None:
        self._submission_provider = submission_provider
        self._context_collector = context_collector
        self._generator = generator
        self._judge = judge
        self._repository = repository
        self._clock = clock
        self._now = now
        self._uuid_factory = uuid_factory

    async def run(self, submission_id: str) -> FeedbackPipelineResult:
        existing = self._repository.get_by_submission(submission_id)
        if existing is not None:
            return existing.model_copy(update={"idempotent_replay": True})

        workflow_run_id = self._uuid_factory()
        started_at = self._now()
        started_clock = self._clock()

        try:
            submission = await self._submission_provider.get_submission(submission_id)
        except Exception:
            raise ContextCollectionError() from None
        if submission is None:
            raise SubmissionNotFoundError(submission_id)

        try:
            context = await self._context_collector.collect(submission, workflow_run_id)
        except FeedbackPipelineError:
            raise
        except Exception:
            raise ContextCollectionError() from None

        try:
            generated_feedback = GeneratedFeedback.model_validate(
                await self._generator.generate(context)
            )
        except Exception:
            raise FeedbackGenerationError(workflow_run_id) from None

        try:
            judge_result = JudgeResult.model_validate(
                await self._judge.evaluate(context, generated_feedback)
            )
        except Exception:
            raise FeedbackJudgementError(workflow_run_id) from None

        completed_at = self._now()
        latency_ms = max(0, int((self._clock() - started_clock) * 1000))
        accepted = judge_result.decision is JudgeDecision.PASS
        result = FeedbackPipelineResult(
            workflow_run_id=workflow_run_id,
            feedback_id=self._uuid_factory(),
            submission_id=submission_id,
            status=(
                FeedbackPipelineStatus.VALIDATED if accepted else FeedbackPipelineStatus.REJECTED
            ),
            validated_feedback=generated_feedback if accepted else None,
            judge_result=judge_result,
            regeneration_count=0,
            fallback_used=False,
            latency_ms=latency_ms,
            token_usage=generated_feedback.token_usage,
            estimated_cost=generated_feedback.estimated_cost,
            source_references=generated_feedback.source_references,
            idempotent_replay=False,
        )
        return self._repository.save_result(
            PipelinePersistenceRequest(
                result=result,
                generated_feedback=generated_feedback,
                started_at=started_at,
                completed_at=completed_at,
            )
        )
