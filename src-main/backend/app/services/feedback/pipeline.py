import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from time import perf_counter
from uuid import uuid4

from app.models.enums import JudgeDecision, JudgeEvaluationStatus, WorkflowStage
from app.schemas.feedback import (
    FeedbackContext,
    FeedbackPipelineResult,
    FeedbackPipelineStatus,
    FeedbackRegenerationContext,
    GeneratedFeedback,
    JudgeEvaluationOutcome,
    TokenUsage,
    quality_policy_passes,
)
from app.services.audit_events import FeedbackAuditEvents
from app.services.feedback.contracts import (
    FeedbackAttemptPersistence,
    FeedbackContextCollector,
    FeedbackGenerator,
    FeedbackJudge,
    FeedbackWorkflowRepository,
    PipelinePersistenceRequest,
    SubmissionProvider,
    TerminalFeedbackObserver,
    TerminalIntegrationPlanner,
    WorkflowProgressRecorder,
)
from app.services.feedback.errors import (
    ContextCollectionError,
    ContextIntegrityError,
    FeedbackPipelineError,
    SubmissionNotFoundError,
)
from app.services.feedback.fallback import safe_fallback_feedback
from app.services.feedback.judge import provider_error_outcome


def _new_uuid() -> str:
    return str(uuid4())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aggregate_usage(
    attempts: list[FeedbackAttemptPersistence],
) -> tuple[TokenUsage, Decimal]:
    input_tokens = 0
    output_tokens = 0
    estimated_cost = Decimal("0")
    for attempt in attempts:
        input_tokens += attempt.generated_feedback.token_usage.input_tokens
        output_tokens += attempt.generated_feedback.token_usage.output_tokens
        estimated_cost += attempt.generated_feedback.estimated_cost
        input_tokens += attempt.judge_evaluation.token_usage.input_tokens
        output_tokens += attempt.judge_evaluation.token_usage.output_tokens
        estimated_cost += attempt.judge_evaluation.estimated_cost
    return (
        TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
        estimated_cost,
    )


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
        progress_recorder: WorkflowProgressRecorder | None = None,
        terminal_observer: TerminalFeedbackObserver | None = None,
        terminal_integration_planner: TerminalIntegrationPlanner | None = None,
        audit_events: FeedbackAuditEvents | None = None,
        provider_timeout_seconds: float = 60,
        lease_duration: timedelta = timedelta(minutes=5),
    ) -> None:
        if not 0 < provider_timeout_seconds <= 60:
            raise ValueError("provider_timeout_seconds must be between 0 and 60")
        self._submission_provider = submission_provider
        self._context_collector = context_collector
        self._generator = generator
        self._judge = judge
        self._repository = repository
        self._clock = clock
        self._now = now
        self._uuid_factory = uuid_factory
        self._progress_recorder = progress_recorder
        self._terminal_observer = terminal_observer
        self._terminal_integration_planner = terminal_integration_planner
        self._audit_events = audit_events
        self._provider_timeout_seconds = provider_timeout_seconds
        self._lease_duration = lease_duration

    async def run(
        self,
        submission_id: str,
        workflow_run_id: str | None = None,
        execution_token: str | None = None,
        correlation_id: str | None = None,
    ) -> FeedbackPipelineResult:
        existing = self._repository.get_by_submission(submission_id)
        if existing is not None:
            self._recover_terminal_integrations(existing.workflow_run_id)
            return existing.model_copy(update={"idempotent_replay": True})

        workflow_run_id = workflow_run_id or self._uuid_factory()
        correlation_id = correlation_id or workflow_run_id
        started_at = self._now()
        started_clock = self._clock()
        self._audit(
            "generation_started",
            workflow_run_id,
            correlation_id,
            execution_token=execution_token,
        )

        try:
            submission = await asyncio.wait_for(
                self._submission_provider.get_submission(submission_id),
                timeout=self._provider_timeout_seconds,
            )
        except Exception:
            raise ContextCollectionError() from None
        if submission is None:
            raise SubmissionNotFoundError(submission_id)
        if submission.submission_id != submission_id:
            raise ContextIntegrityError()

        self._record_stage(
            workflow_run_id,
            WorkflowStage.CONTEXT_COLLECTION,
            execution_token,
        )
        try:
            context = await asyncio.wait_for(
                self._context_collector.collect(submission, correlation_id),
                timeout=self._provider_timeout_seconds,
            )
        except FeedbackPipelineError:
            raise
        except Exception:
            raise ContextCollectionError() from None

        attempts: list[FeedbackAttemptPersistence] = []
        self._record_stage(workflow_run_id, WorkflowStage.GENERATING, execution_token)
        first_feedback = await self._generate(context)
        self._audit(
            "generation_completed",
            workflow_run_id,
            correlation_id,
            attempt=1,
            succeeded=first_feedback is not None,
            execution_token=execution_token,
        )
        if first_feedback is None:
            return await self._store_fallback(
                submission_id,
                workflow_run_id,
                correlation_id,
                attempts,
                regeneration_count=0,
                started_at=started_at,
                started_clock=started_clock,
                context=context,
                execution_token=execution_token,
            )

        self._record_stage(workflow_run_id, WorkflowStage.JUDGING, execution_token)
        first_evaluation = await self._evaluate(context, first_feedback)
        self._audit(
            "judged",
            workflow_run_id,
            correlation_id,
            attempt=1,
            succeeded=first_evaluation.evaluation_status is JudgeEvaluationStatus.VALID,
            failure_category=first_evaluation.error_category or "judge_unavailable",
            execution_token=execution_token,
        )
        first_attempt = FeedbackAttemptPersistence(
            feedback_id=self._uuid_factory(),
            generation_attempt=1,
            generated_feedback=first_feedback,
            judge_evaluation=first_evaluation,
        )
        attempts.append(first_attempt)
        if self._passed(first_evaluation):
            return await self._store_validated(
                submission_id,
                workflow_run_id,
                correlation_id,
                attempts,
                first_attempt,
                regeneration_count=0,
                started_at=started_at,
                started_clock=started_clock,
                context=context,
                execution_token=execution_token,
            )

        regeneration = FeedbackRegenerationContext(
            previous_feedback=first_feedback,
            judge_evaluation=first_evaluation,
        )
        self._audit(
            "regenerated",
            workflow_run_id,
            correlation_id,
            execution_token=execution_token,
        )
        self._record_stage(
            workflow_run_id,
            WorkflowStage.REGENERATING,
            execution_token,
        )
        second_feedback = await self._generate(context, regeneration)
        self._audit(
            "generation_completed",
            workflow_run_id,
            correlation_id,
            attempt=2,
            succeeded=second_feedback is not None,
            execution_token=execution_token,
        )
        if second_feedback is None:
            return await self._store_fallback(
                submission_id,
                workflow_run_id,
                correlation_id,
                attempts,
                regeneration_count=1,
                started_at=started_at,
                started_clock=started_clock,
                context=context,
                execution_token=execution_token,
            )

        self._record_stage(workflow_run_id, WorkflowStage.JUDGING, execution_token)
        second_evaluation = await self._evaluate(context, second_feedback)
        self._audit(
            "judged",
            workflow_run_id,
            correlation_id,
            attempt=2,
            succeeded=second_evaluation.evaluation_status is JudgeEvaluationStatus.VALID,
            failure_category=second_evaluation.error_category or "judge_unavailable",
            execution_token=execution_token,
        )
        second_attempt = FeedbackAttemptPersistence(
            feedback_id=self._uuid_factory(),
            generation_attempt=2,
            generated_feedback=second_feedback,
            judge_evaluation=second_evaluation,
        )
        attempts.append(second_attempt)
        if self._passed(second_evaluation):
            return await self._store_validated(
                submission_id,
                workflow_run_id,
                correlation_id,
                attempts,
                second_attempt,
                regeneration_count=1,
                started_at=started_at,
                started_clock=started_clock,
                context=context,
                execution_token=execution_token,
            )

        return await self._store_fallback(
            submission_id,
            workflow_run_id,
            correlation_id,
            attempts,
            regeneration_count=1,
            started_at=started_at,
            started_clock=started_clock,
            context=context,
            execution_token=execution_token,
        )

    async def _generate(
        self,
        context: FeedbackContext,
        regeneration: FeedbackRegenerationContext | None = None,
    ) -> GeneratedFeedback | None:
        try:
            generated = await asyncio.wait_for(
                self._generator.generate(context, regeneration),
                timeout=self._provider_timeout_seconds,
            )
            payload = (
                generated.model_dump(mode="python")
                if isinstance(generated, GeneratedFeedback)
                else generated
            )
            return GeneratedFeedback.model_validate(payload)
        except Exception:
            return None

    async def _evaluate(
        self,
        context: FeedbackContext,
        feedback: GeneratedFeedback,
    ) -> JudgeEvaluationOutcome:
        try:
            evaluated = await asyncio.wait_for(
                self._judge.evaluate(context, feedback),
                timeout=self._provider_timeout_seconds,
            )
            payload = (
                evaluated.model_dump(mode="python")
                if isinstance(evaluated, JudgeEvaluationOutcome)
                else evaluated
            )
            return JudgeEvaluationOutcome.model_validate(payload)
        except Exception:
            return provider_error_outcome()

    @staticmethod
    def _passed(evaluation: JudgeEvaluationOutcome) -> bool:
        return (
            evaluation.evaluation_status is JudgeEvaluationStatus.VALID
            and evaluation.judge_result is not None
            and evaluation.judge_result.decision is JudgeDecision.PASS
            and quality_policy_passes(
                evaluation.reported_decision,
                evaluation.judge_result,
                evaluation.quality_policy_version,
            )
        )

    async def _store_validated(
        self,
        submission_id: str,
        workflow_run_id: str,
        correlation_id: str,
        attempts: list[FeedbackAttemptPersistence],
        released_attempt: FeedbackAttemptPersistence,
        *,
        regeneration_count: int,
        started_at: datetime,
        started_clock: float,
        context: FeedbackContext,
        execution_token: str | None,
    ) -> FeedbackPipelineResult:
        usage, cost = _aggregate_usage(attempts)
        result = FeedbackPipelineResult(
            workflow_run_id=workflow_run_id,
            feedback_id=released_attempt.feedback_id,
            submission_id=submission_id,
            status=FeedbackPipelineStatus.VALIDATED,
            validated_feedback=released_attempt.generated_feedback,
            judge_result=released_attempt.judge_evaluation.judge_result,
            judge_evaluations=[attempt.judge_evaluation for attempt in attempts],
            regeneration_count=regeneration_count,
            fallback_used=False,
            latency_ms=self._latency_ms(started_clock),
            token_usage=usage,
            estimated_cost=cost,
            source_references=released_attempt.generated_feedback.source_references,
        )
        return await self._save(
            result,
            attempts,
            started_at,
            context,
            execution_token,
            correlation_id,
        )

    async def _store_fallback(
        self,
        submission_id: str,
        workflow_run_id: str,
        correlation_id: str,
        attempts: list[FeedbackAttemptPersistence],
        *,
        regeneration_count: int,
        started_at: datetime,
        started_clock: float,
        context: FeedbackContext,
        execution_token: str | None,
    ) -> FeedbackPipelineResult:
        fallback = safe_fallback_feedback()
        usage, cost = _aggregate_usage(attempts)
        final_judge = attempts[-1].judge_evaluation.judge_result if attempts else None
        result = FeedbackPipelineResult(
            workflow_run_id=workflow_run_id,
            feedback_id=self._uuid_factory(),
            submission_id=submission_id,
            status=FeedbackPipelineStatus.FALLBACK,
            validated_feedback=None,
            safe_fallback=fallback,
            judge_result=final_judge,
            judge_evaluations=[attempt.judge_evaluation for attempt in attempts],
            regeneration_count=regeneration_count,
            fallback_used=True,
            latency_ms=self._latency_ms(started_clock),
            token_usage=usage,
            estimated_cost=cost,
            source_references=[],
        )
        return await self._save(
            result,
            attempts,
            started_at,
            context,
            execution_token,
            correlation_id,
        )

    async def _save(
        self,
        result: FeedbackPipelineResult,
        attempts: list[FeedbackAttemptPersistence],
        started_at: datetime,
        context: FeedbackContext,
        execution_token: str | None,
        correlation_id: str,
    ) -> FeedbackPipelineResult:
        terminal_integrations = ()
        if self._terminal_integration_planner is not None:
            try:
                terminal_integrations = await self._terminal_integration_planner.plan(
                    context,
                    result,
                    tuple(attempts),
                )
            except Exception:
                # Missing integration adapters must not withhold durable feedback.
                terminal_integrations = ()
        saved = self._repository.save_result(
            PipelinePersistenceRequest(
                result=result,
                attempts=tuple(attempts),
                started_at=started_at,
                completed_at=self._now(),
                execution_token=execution_token,
                course_id=context.task.course_id,
                task_id=context.task.task_id,
                terminal_integrations=terminal_integrations,
            )
        )
        if saved is not result:
            return saved
        if result.fallback_used:
            self._audit(
                "fallback_used",
                result.workflow_run_id,
                correlation_id,
            )
        self._audit(
            "workflow_completed",
            result.workflow_run_id,
            correlation_id,
        )
        if self._terminal_observer is not None:
            try:
                await self._terminal_observer.after_terminal_feedback(
                    context,
                    result,
                    tuple(attempts),
                )
            except Exception:
                # Research and continuation must not withhold durable feedback.
                pass
        return saved

    def _recover_terminal_integrations(self, workflow_run_id: str) -> None:
        try:
            self._repository.recover_terminal_integrations(
                workflow_run_id,
                observed_at=self._now(),
            )
        except Exception:
            # Replay remains available while the serial worker owns recovery.
            return

    def _latency_ms(self, started_clock: float) -> int:
        return max(0, int((self._clock() - started_clock) * 1000))

    def _record_stage(
        self,
        workflow_run_id: str,
        stage: WorkflowStage,
        execution_token: str | None,
    ) -> None:
        if self._progress_recorder is not None:
            self._progress_recorder.record_stage(
                workflow_run_id,
                stage,
                execution_token=execution_token,
                lease_expires_at=self._now() + self._lease_duration,
            )

    def attach_progress_recorder(self, recorder: WorkflowProgressRecorder) -> None:
        self._progress_recorder = recorder

    def attach_audit_events(self, events: FeedbackAuditEvents) -> None:
        self._audit_events = events

    def _audit(self, method: str, *args: object, **kwargs: object) -> None:
        if self._audit_events is None:
            return
        try:
            callback = getattr(self._audit_events, method)
            callback(*args, **kwargs)
        except Exception:
            # Student-facing work remains authoritative if auditing is unavailable.
            return
