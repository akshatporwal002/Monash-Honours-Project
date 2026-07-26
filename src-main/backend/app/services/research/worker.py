from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Protocol

from app.models.enums import JudgeEvaluationStatus
from app.schemas.feedback import (
    ContextProviderStatus,
    FeedbackContext,
    GeneratedFeedback,
    JudgeEvaluationOutcome,
    TokenUsage,
)


@dataclass(frozen=True, slots=True)
class ResearchJobClaim:
    research_evaluation_id: str
    case_id: str
    workflow_run_id: str
    correlation_id: str
    execution_token: str
    provider: str
    model: str
    lease_expires_at: datetime
    processing_attempts: int


@dataclass(frozen=True, slots=True)
class BaselineCompletion:
    generated_feedback: GeneratedFeedback
    judge_evaluation: JudgeEvaluationOutcome
    generation_latency_ms: int
    generation_token_usage: TokenUsage
    generation_cost: Decimal
    evaluation_latency_ms: int
    evaluation_token_usage: TokenUsage
    evaluation_cost: Decimal
    usage_complete: bool
    comparable: bool


class BaselineFeedbackGenerator(Protocol):
    async def generate(
        self,
        context: FeedbackContext,
        *,
        expected_provider: str,
        expected_model: str,
    ) -> GeneratedFeedback: ...


class BaselineMeasurementJudge(Protocol):
    async def evaluate(
        self,
        context: FeedbackContext,
        feedback: GeneratedFeedback,
    ) -> JudgeEvaluationOutcome: ...


class BaselineContextProvider(Protocol):
    async def get_context(self, workflow_run_id: str) -> FeedbackContext | None: ...


class ResearchBaselineJobRepository(Protocol):
    def claim_next(
        self,
        *,
        now: datetime,
        maximum_attempts: int,
    ) -> ResearchJobClaim | None: ...

    def finalize_next_exhausted(
        self,
        *,
        now: datetime,
        maximum_attempts: int,
    ) -> str | None: ...

    def complete(
        self,
        claim: ResearchJobClaim,
        completion: BaselineCompletion,
        *,
        completed_at: datetime,
    ) -> bool: ...

    def fail(
        self,
        claim: ResearchJobClaim,
        failure_category: str,
        *,
        completed_at: datetime,
    ) -> bool: ...


class BaselineJobExecutor:
    """Executes exactly one generation and one measurement-only judgement."""

    def __init__(
        self,
        repository: ResearchBaselineJobRepository,
        context_provider: BaselineContextProvider,
        generator: BaselineFeedbackGenerator,
        judge: BaselineMeasurementJudge,
        *,
        provider_timeout_seconds: float = 60,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        clock: Callable[[], float] = perf_counter,
        maximum_attempts: int = 3,
    ) -> None:
        if not 0 < provider_timeout_seconds <= 60:
            raise ValueError("provider_timeout_seconds must be between 0 and 60")
        if not 1 <= maximum_attempts <= 3:
            raise ValueError("maximum_attempts must be between 1 and 3")
        self._repository = repository
        self._context_provider = context_provider
        self._generator = generator
        self._judge = judge
        self._provider_timeout_seconds = provider_timeout_seconds
        self._now = now
        self._clock = clock
        self._maximum_attempts = maximum_attempts

    async def run_once(self) -> bool:
        observed_at = self._now()
        exhausted = self._repository.finalize_next_exhausted(
            now=observed_at,
            maximum_attempts=self._maximum_attempts,
        )
        if exhausted is not None:
            return True
        claim = self._repository.claim_next(
            now=observed_at,
            maximum_attempts=self._maximum_attempts,
        )
        if claim is None:
            return False
        try:
            context = await asyncio.wait_for(
                self._context_provider.get_context(claim.workflow_run_id),
                timeout=self._provider_timeout_seconds,
            )
            if context is None:
                self._repository.fail(
                    claim,
                    "baseline_context_unavailable",
                    completed_at=self._now(),
                )
                return True

            isolated_context = context.model_copy(
                update={
                    "correlation_id": claim.correlation_id,
                    "retrieval_context": [],
                    "retrieval_status": ContextProviderStatus.NOT_REQUESTED,
                    "retrieval_request_ids": [],
                    "simulation_context": None,
                    "simulation_status": ContextProviderStatus.NOT_REQUESTED,
                }
            )
            generation_started = self._clock()
            feedback = await asyncio.wait_for(
                self._generator.generate(
                    isolated_context,
                    expected_provider=claim.provider,
                    expected_model=claim.model,
                ),
                timeout=self._provider_timeout_seconds,
            )
            generation_latency_ms = max(
                0,
                int((self._clock() - generation_started) * 1000),
            )
            evaluation_started = self._clock()
            evaluation = await asyncio.wait_for(
                self._judge.evaluate(isolated_context, feedback),
                timeout=self._provider_timeout_seconds,
            )
            evaluation_latency_ms = max(
                0,
                int((self._clock() - evaluation_started) * 1000),
            )
            self._repository.complete(
                claim,
                BaselineCompletion(
                    generated_feedback=feedback,
                    judge_evaluation=evaluation,
                    generation_latency_ms=generation_latency_ms,
                    generation_token_usage=feedback.token_usage,
                    generation_cost=feedback.estimated_cost,
                    evaluation_latency_ms=evaluation_latency_ms,
                    evaluation_token_usage=evaluation.token_usage,
                    evaluation_cost=evaluation.estimated_cost,
                    usage_complete=feedback.usage_complete,
                    comparable=(
                        feedback.provider == claim.provider
                        and feedback.model == claim.model
                        and evaluation.evaluation_status is JudgeEvaluationStatus.VALID
                    ),
                ),
                completed_at=self._now(),
            )
        except TimeoutError:
            self._repository.fail(
                claim,
                "provider_timeout",
                completed_at=self._now(),
            )
        except Exception:
            self._repository.fail(
                claim,
                "baseline_processing_failed",
                completed_at=self._now(),
            )
        return True
