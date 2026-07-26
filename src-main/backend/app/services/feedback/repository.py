from datetime import datetime, timezone
from decimal import Decimal
from math import ceil
from uuid import uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models import (
    FeedbackRecord,
    FeedbackReport,
    FeedbackStatus,
    JudgeDecision,
    JudgeEvaluation,
    JudgeEvaluationStatus,
    WorkflowOutcome,
    WorkflowRun,
    WorkflowStage,
)
from app.schemas.feedback import (
    FeedbackPipelineResult,
    FeedbackPipelineStatus,
    GeneratedFeedback,
    JudgeEvaluationOutcome,
    JudgeResult,
    SafeFallbackFeedback,
    TokenUsage,
)
from app.services.feedback.contracts import (
    FeedbackAttemptPersistence,
    FeedbackReportWrite,
    FeedbackReportWriteResult,
    PipelinePersistenceRequest,
    WorkflowClaim,
)
from app.services.feedback.errors import (
    FeedbackReportConflictError,
    LostWorkflowLeaseError,
    PipelinePersistenceError,
)
from app.services.terminal_integrations.repository import (
    SqlAlchemyTerminalIntegrationRepository,
    TerminalIntegrationPayloadError,
    outbox_record,
)

MAX_EXECUTION_ATTEMPTS = 3


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _token_usage(input_tokens: int, output_tokens: int) -> TokenUsage:
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )


def _new_execution_token() -> str:
    return str(uuid4())


class SqlAlchemyFeedbackWorkflowRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_submission(self, submission_id: str) -> FeedbackPipelineResult | None:
        statement = (
            select(WorkflowRun)
            .where(WorkflowRun.submission_id == submission_id)
            .options(
                selectinload(WorkflowRun.feedback_records).selectinload(
                    FeedbackRecord.judge_evaluation
                )
            )
        )
        try:
            workflow = self._session.scalar(statement)
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PipelinePersistenceError(submission_id) from error

        if workflow is None:
            return None
        if workflow.current_stage is not WorkflowStage.COMPLETED:
            return None
        if workflow.completed_at is None or not workflow.feedback_records:
            raise PipelinePersistenceError(submission_id)

        generated_records = sorted(
            (
                record
                for record in workflow.feedback_records
                if record.generation_attempt is not None
            ),
            key=lambda record: record.generation_attempt or 0,
        )
        released_records = [
            record
            for record in workflow.feedback_records
            if record.status in {FeedbackStatus.ACCEPTED, FeedbackStatus.SAFE_FALLBACK}
        ]
        if len(released_records) != 1:
            raise PipelinePersistenceError(submission_id)
        released = released_records[0]
        attempt_numbers = [record.generation_attempt for record in generated_records]
        if attempt_numbers != list(range(1, len(generated_records) + 1)):
            raise PipelinePersistenceError(submission_id)
        if len(generated_records) > 2:
            raise PipelinePersistenceError(submission_id)

        evaluations: list[JudgeEvaluationOutcome] = []
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = Decimal("0")
        generated_by_id: dict[str, GeneratedFeedback] = {}
        for record in generated_records:
            generated = self._generated_feedback(record, submission_id)
            generated_by_id[record.id] = generated
            total_input_tokens += generated.token_usage.input_tokens
            total_output_tokens += generated.token_usage.output_tokens
            total_cost += generated.estimated_cost

            if record.judge_evaluation is None:
                raise PipelinePersistenceError(submission_id)
            evaluation = self._judge_outcome(record.judge_evaluation, submission_id)
            evaluations.append(evaluation)
            total_input_tokens += evaluation.token_usage.input_tokens
            total_output_tokens += evaluation.token_usage.output_tokens
            total_cost += evaluation.estimated_cost

        if released.status is FeedbackStatus.ACCEPTED:
            validated_feedback = generated_by_id.get(released.id)
            if validated_feedback is None:
                raise PipelinePersistenceError(submission_id)
            pipeline_status = FeedbackPipelineStatus.VALIDATED
            safe_fallback = None
            fallback_used = False
            source_references = validated_feedback.source_references
            released_evaluation = released.judge_evaluation
            final_judge = (
                self._judge_outcome(released_evaluation, submission_id).judge_result
                if released_evaluation is not None
                else None
            )
            if final_judge is None or final_judge.decision is not JudgeDecision.PASS:
                raise PipelinePersistenceError(submission_id)
        else:
            validated_feedback = None
            pipeline_status = FeedbackPipelineStatus.FALLBACK
            try:
                safe_fallback = SafeFallbackFeedback(
                    feedback_content=released.feedback_content,
                    source_references=[],
                    simulation_references=[],
                )
            except (ArithmeticError, TypeError, ValueError):
                raise PipelinePersistenceError(submission_id) from None
            fallback_used = True
            source_references = []
            final_judge = evaluations[-1].judge_result if evaluations else None

        self._validate_terminal_shape(
            workflow,
            generated_records=generated_records,
            released=released,
        )
        latency_ms = workflow.latency_ms
        if latency_ms is None:
            latency = _as_utc(workflow.completed_at) - _as_utc(workflow.started_at)
            latency_ms = max(0, int(latency.total_seconds() * 1000))
        try:
            return FeedbackPipelineResult(
                workflow_run_id=workflow.id,
                feedback_id=released.id,
                submission_id=workflow.submission_id,
                status=pipeline_status,
                validated_feedback=validated_feedback,
                safe_fallback=safe_fallback,
                judge_result=final_judge,
                judge_evaluations=evaluations,
                regeneration_count=workflow.regeneration_count,
                fallback_used=fallback_used,
                latency_ms=latency_ms,
                token_usage=_token_usage(total_input_tokens, total_output_tokens),
                estimated_cost=total_cost,
                source_references=source_references,
                idempotent_replay=True,
            )
        except (ArithmeticError, TypeError, ValueError):
            raise PipelinePersistenceError(submission_id) from None

    def claim_workflow(
        self,
        submission_id: str,
        workflow_run_id: str,
        *,
        started_at: datetime,
        lease_expires_at: datetime,
    ) -> WorkflowClaim:
        try:
            workflow = self._session.scalar(
                select(WorkflowRun).where(WorkflowRun.submission_id == submission_id)
            )
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PipelinePersistenceError(submission_id) from error
        if workflow is None:
            execution_token = _new_execution_token()
            workflow = WorkflowRun(
                id=workflow_run_id,
                submission_id=submission_id,
                current_stage=WorkflowStage.PENDING,
                regeneration_count=0,
                started_at=started_at,
                lease_expires_at=lease_expires_at,
                execution_token=execution_token,
                execution_attempt_count=1,
            )
            self._session.add(workflow)
            try:
                self._session.commit()
            except IntegrityError:
                self._session.rollback()
                return self._claim_existing(submission_id, started_at, lease_expires_at)
            except SQLAlchemyError as error:
                self._session.rollback()
                raise PipelinePersistenceError(submission_id) from error
            return self._workflow_claim(workflow, should_start=True)
        return self._claim_existing(submission_id, started_at, lease_expires_at)

    def claim_next_recoverable(
        self,
        *,
        started_at: datetime,
        lease_expires_at: datetime,
    ) -> WorkflowClaim | None:
        """Claim due retry work or a workflow whose previous execution lease expired."""
        observed_at = _as_utc(started_at)
        try:
            candidate = self._session.scalar(
                select(WorkflowRun)
                .where(
                    WorkflowRun.execution_attempt_count < MAX_EXECUTION_ATTEMPTS,
                    or_(
                        and_(
                            WorkflowRun.current_stage.not_in(
                                [WorkflowStage.COMPLETED, WorkflowStage.FAILED]
                            ),
                            or_(
                                WorkflowRun.lease_expires_at.is_(None),
                                WorkflowRun.lease_expires_at <= observed_at,
                            ),
                        ),
                        and_(
                            WorkflowRun.current_stage == WorkflowStage.FAILED,
                            WorkflowRun.next_retry_at.is_not(None),
                            WorkflowRun.next_retry_at <= observed_at,
                        ),
                    ),
                )
                .order_by(WorkflowRun.started_at, WorkflowRun.id)
                .limit(1)
            )
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PipelinePersistenceError("feedback-worker-claim") from error
        if candidate is None:
            return None
        claim = self._claim_existing(
            candidate.submission_id,
            observed_at,
            _as_utc(lease_expires_at),
        )
        return claim if claim.should_start else None

    def finalize_next_exhausted(self, *, observed_at: datetime) -> str | None:
        """Persist a terminal failure for a crashed third execution attempt."""
        timestamp = _as_utc(observed_at)
        try:
            candidate = self._session.scalar(
                select(WorkflowRun)
                .where(
                    WorkflowRun.execution_attempt_count >= MAX_EXECUTION_ATTEMPTS,
                    WorkflowRun.current_stage.not_in(
                        [WorkflowStage.COMPLETED, WorkflowStage.FAILED]
                    ),
                    or_(
                        WorkflowRun.lease_expires_at.is_(None),
                        WorkflowRun.lease_expires_at <= timestamp,
                    ),
                )
                .order_by(WorkflowRun.started_at, WorkflowRun.id)
                .limit(1)
            )
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PipelinePersistenceError("feedback-worker-exhaustion") from error
        if candidate is None:
            return None
        return candidate.id if self._finalize_exhausted_workflow(candidate, timestamp) else None

    def _claim_existing(
        self,
        submission_id: str,
        started_at: datetime,
        lease_expires_at: datetime,
    ) -> WorkflowClaim:
        try:
            workflow = self._session.scalar(
                select(WorkflowRun).where(WorkflowRun.submission_id == submission_id)
            )
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PipelinePersistenceError(submission_id) from error
        if workflow is None:
            raise PipelinePersistenceError(submission_id)
        if workflow.current_stage is WorkflowStage.COMPLETED:
            terminal = self.get_by_submission(submission_id)
            if terminal is None:
                raise PipelinePersistenceError(submission_id)
            return self._workflow_claim(
                workflow,
                should_start=False,
                terminal_result=terminal,
            )

        lease_is_stale = workflow.current_stage not in {
            WorkflowStage.COMPLETED,
            WorkflowStage.FAILED,
        } and (
            workflow.lease_expires_at is None
            or _as_utc(workflow.lease_expires_at) <= _as_utc(started_at)
        )
        retry_is_due = (
            workflow.current_stage is WorkflowStage.FAILED
            and workflow.next_retry_at is not None
            and _as_utc(workflow.next_retry_at) <= _as_utc(started_at)
        )
        has_attempt = workflow.execution_attempt_count < MAX_EXECUTION_ATTEMPTS
        should_start = has_attempt and (retry_is_due or lease_is_stale)
        if should_start:
            previous_stage = workflow.current_stage
            previous_lease = workflow.lease_expires_at
            previous_token = workflow.execution_token
            execution_token = _new_execution_token()
            statement = update(WorkflowRun).where(
                WorkflowRun.id == workflow.id,
                WorkflowRun.current_stage == previous_stage,
            )
            if previous_lease is None:
                statement = statement.where(WorkflowRun.lease_expires_at.is_(None))
            else:
                statement = statement.where(WorkflowRun.lease_expires_at == previous_lease)
            if previous_token is None:
                statement = statement.where(WorkflowRun.execution_token.is_(None))
            else:
                statement = statement.where(WorkflowRun.execution_token == previous_token)
            try:
                result = self._session.execute(
                    statement.values(
                        current_stage=WorkflowStage.PENDING,
                        regeneration_count=0,
                        final_outcome=None,
                        started_at=started_at,
                        completed_at=None,
                        lease_expires_at=lease_expires_at,
                        execution_token=execution_token,
                        execution_attempt_count=workflow.execution_attempt_count + 1,
                        next_retry_at=None,
                        latency_ms=None,
                        failure_category=None,
                    )
                )
                self._session.commit()
            except SQLAlchemyError as error:
                self._session.rollback()
                raise PipelinePersistenceError(submission_id) from error
            should_start = result.rowcount == 1
            self._session.expire_all()
            workflow = self._session.get(WorkflowRun, workflow.id)
            if workflow is None:
                raise PipelinePersistenceError(submission_id)
        if not should_start and lease_is_stale and not has_attempt:
            self._finalize_exhausted_workflow(workflow, _as_utc(started_at))
            self._session.expire_all()
            persisted = self._session.get(WorkflowRun, workflow.id)
            if persisted is None:
                raise PipelinePersistenceError(submission_id)
            return self._workflow_claim(
                persisted,
                should_start=False,
            )
        return self._workflow_claim(workflow, should_start=should_start)

    def _finalize_exhausted_workflow(
        self,
        workflow: WorkflowRun,
        observed_at: datetime,
    ) -> bool:
        previous_stage = workflow.current_stage
        previous_token = workflow.execution_token
        previous_lease = workflow.lease_expires_at
        statement = update(WorkflowRun).where(
            WorkflowRun.id == workflow.id,
            WorkflowRun.current_stage == previous_stage,
            WorkflowRun.execution_attempt_count >= MAX_EXECUTION_ATTEMPTS,
        )
        if previous_token is None:
            statement = statement.where(WorkflowRun.execution_token.is_(None))
        else:
            statement = statement.where(WorkflowRun.execution_token == previous_token)
        if previous_lease is None:
            statement = statement.where(WorkflowRun.lease_expires_at.is_(None))
        else:
            statement = statement.where(WorkflowRun.lease_expires_at == previous_lease)
        latency_ms = max(
            workflow.latency_ms or 0,
            int((_as_utc(observed_at) - _as_utc(workflow.started_at)).total_seconds() * 1000),
        )
        try:
            result = self._session.execute(
                statement.values(
                    current_stage=WorkflowStage.FAILED,
                    final_outcome=WorkflowOutcome.WORKFLOW_FAILED,
                    completed_at=observed_at,
                    lease_expires_at=None,
                    execution_token=None,
                    next_retry_at=None,
                    latency_ms=max(0, latency_ms),
                    failure_category="retry_attempts_exhausted",
                )
            )
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PipelinePersistenceError(workflow.submission_id) from error
        return result.rowcount == 1

    def get_workflow_claim(
        self,
        submission_id: str,
        *,
        observed_at: datetime | None = None,
    ) -> WorkflowClaim | None:
        try:
            workflow = self._session.scalar(
                select(WorkflowRun).where(WorkflowRun.submission_id == submission_id)
            )
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PipelinePersistenceError(submission_id) from error
        if workflow is None:
            return None
        terminal = (
            self.get_by_submission(submission_id)
            if workflow.current_stage is WorkflowStage.COMPLETED
            else None
        )
        if (
            observed_at is not None
            and workflow.current_stage not in {WorkflowStage.COMPLETED, WorkflowStage.FAILED}
            and (
                workflow.lease_expires_at is None
                or _as_utc(workflow.lease_expires_at) <= _as_utc(observed_at)
            )
        ):
            return self._workflow_claim(
                workflow,
                should_start=False,
                stage=WorkflowStage.FAILED,
                failure_category="workflow_interrupted",
                retryable=workflow.execution_attempt_count < MAX_EXECUTION_ATTEMPTS,
            )
        return self._workflow_claim(
            workflow,
            should_start=False,
            terminal_result=terminal,
        )

    @staticmethod
    def _workflow_claim(
        workflow: WorkflowRun,
        *,
        should_start: bool,
        terminal_result: FeedbackPipelineResult | None = None,
        stage: WorkflowStage | None = None,
        failure_category: str | None = None,
        retryable: bool | None = None,
    ) -> WorkflowClaim:
        retry_after_seconds: int | None = None
        if workflow.next_retry_at is not None:
            retry_after_seconds = max(
                0,
                ceil(
                    (_as_utc(workflow.next_retry_at) - datetime.now(timezone.utc)).total_seconds()
                ),
            )
        return WorkflowClaim(
            workflow_run_id=workflow.id,
            submission_id=workflow.submission_id,
            stage=stage or workflow.current_stage,
            should_start=should_start,
            execution_token=workflow.execution_token if should_start else None,
            execution_attempt_count=workflow.execution_attempt_count,
            lease_expires_at=workflow.lease_expires_at,
            course_id=workflow.course_id,
            task_id=workflow.task_id,
            retryable=(retryable if retryable is not None else workflow.next_retry_at is not None),
            retry_after_seconds=retry_after_seconds,
            terminal_result=terminal_result,
            failure_category=(
                failure_category if failure_category is not None else workflow.failure_category
            ),
        )

    def record_stage(
        self,
        workflow_run_id: str,
        stage: WorkflowStage,
        *,
        execution_token: str | None = None,
        lease_expires_at: datetime | None = None,
    ) -> None:
        allowed_previous = {
            WorkflowStage.CONTEXT_COLLECTION: {
                WorkflowStage.PENDING,
                WorkflowStage.CONTEXT_COLLECTION,
            },
            WorkflowStage.GENERATING: {
                WorkflowStage.PENDING,
                WorkflowStage.CONTEXT_COLLECTION,
                WorkflowStage.GENERATING,
            },
            WorkflowStage.JUDGING: {
                WorkflowStage.GENERATING,
                WorkflowStage.REGENERATING,
                WorkflowStage.JUDGING,
            },
            WorkflowStage.REGENERATING: {
                WorkflowStage.JUDGING,
                WorkflowStage.REGENERATING,
            },
        }.get(stage)
        if allowed_previous is None:
            raise ValueError("record_stage accepts only nonterminal execution stages")

        statement = update(WorkflowRun).where(
            WorkflowRun.id == workflow_run_id,
            WorkflowRun.current_stage.in_(allowed_previous),
        )
        if execution_token is None:
            statement = statement.where(WorkflowRun.execution_token.is_(None))
        else:
            statement = statement.where(WorkflowRun.execution_token == execution_token)
        values: dict[str, object] = {"current_stage": stage}
        if lease_expires_at is not None:
            values["lease_expires_at"] = lease_expires_at
        try:
            result = self._session.execute(statement.values(**values))
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PipelinePersistenceError(workflow_run_id) from error
        if result.rowcount != 1:
            raise LostWorkflowLeaseError(workflow_run_id)

    def mark_failed(
        self,
        workflow_run_id: str,
        failure_category: str,
        completed_at: datetime,
        *,
        execution_token: str | None = None,
        retryable: bool = True,
        next_retry_at: datetime | None = None,
    ) -> None:
        try:
            workflow = self._session.get(WorkflowRun, workflow_run_id)
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PipelinePersistenceError(workflow_run_id) from error
        if workflow is None:
            if execution_token is not None:
                raise LostWorkflowLeaseError(workflow_run_id)
            return
        if workflow.current_stage is WorkflowStage.COMPLETED:
            if execution_token is not None:
                raise LostWorkflowLeaseError(workflow_run_id)
            return
        can_retry = retryable and workflow.execution_attempt_count < MAX_EXECUTION_ATTEMPTS
        retry_at = (next_retry_at or completed_at) if can_retry else None
        latency_ms = max(
            0,
            int((_as_utc(completed_at) - _as_utc(workflow.started_at)).total_seconds() * 1000),
        )
        statement = update(WorkflowRun).where(
            WorkflowRun.id == workflow_run_id,
            WorkflowRun.current_stage.not_in([WorkflowStage.COMPLETED, WorkflowStage.FAILED]),
        )
        if execution_token is None:
            statement = statement.where(WorkflowRun.execution_token.is_(None))
        else:
            statement = statement.where(WorkflowRun.execution_token == execution_token)
        try:
            result = self._session.execute(
                statement.values(
                    current_stage=WorkflowStage.FAILED,
                    final_outcome=WorkflowOutcome.WORKFLOW_FAILED,
                    completed_at=completed_at,
                    lease_expires_at=None,
                    execution_token=None,
                    next_retry_at=retry_at,
                    latency_ms=latency_ms,
                    failure_category=failure_category,
                )
            )
            self._session.commit()
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PipelinePersistenceError(workflow.submission_id) from error
        if result.rowcount != 1:
            raise LostWorkflowLeaseError(workflow_run_id)

    def get_released_submission_id(self, feedback_id: str) -> str | None:
        try:
            return self._session.scalar(
                select(FeedbackRecord.submission_id).where(
                    FeedbackRecord.id == feedback_id,
                    FeedbackRecord.status.in_(
                        [FeedbackStatus.ACCEPTED, FeedbackStatus.SAFE_FALLBACK]
                    ),
                )
            )
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PipelinePersistenceError(feedback_id) from error

    def save_report(self, report: FeedbackReportWrite) -> FeedbackReportWriteResult:
        try:
            existing = self._find_report(report)
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PipelinePersistenceError(report.feedback_id) from error
        if existing is not None:
            return self._existing_report_result(existing, report)

        record = FeedbackReport(
            feedback_id=report.feedback_id,
            reporter_reference=report.reporter_reference,
            category=report.category,
            note=report.note,
        )
        self._session.add(record)
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            try:
                winner = self._find_report(report)
            except SQLAlchemyError as read_error:
                self._session.rollback()
                raise PipelinePersistenceError(report.feedback_id) from read_error
            if winner is None:
                raise PipelinePersistenceError(report.feedback_id) from error
            return self._existing_report_result(winner, report)
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PipelinePersistenceError(report.feedback_id) from error
        return FeedbackReportWriteResult(report_id=record.id, created=True)

    def _find_report(self, report: FeedbackReportWrite) -> FeedbackReport | None:
        return self._session.scalar(
            select(FeedbackReport).where(
                FeedbackReport.feedback_id == report.feedback_id,
                FeedbackReport.reporter_reference == report.reporter_reference,
            )
        )

    @staticmethod
    def _existing_report_result(
        existing: FeedbackReport,
        report: FeedbackReportWrite,
    ) -> FeedbackReportWriteResult:
        if existing is not None:
            if existing.category is report.category and existing.note == report.note:
                return FeedbackReportWriteResult(report_id=existing.id, created=False)
            raise FeedbackReportConflictError()
        raise PipelinePersistenceError(report.feedback_id)

    def save_result(self, request: PipelinePersistenceRequest) -> FeedbackPipelineResult:
        result = request.result
        self._validate_persistence_request(request)
        try:
            workflow = self._session.get(WorkflowRun, result.workflow_run_id)
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PipelinePersistenceError(result.submission_id) from error
        records: list[object] = []
        if workflow is None:
            if request.execution_token is not None:
                raise LostWorkflowLeaseError(result.workflow_run_id)
            workflow = WorkflowRun(
                id=result.workflow_run_id,
                submission_id=result.submission_id,
                course_id=request.course_id,
                task_id=request.task_id,
                current_stage=WorkflowStage.COMPLETED,
                regeneration_count=result.regeneration_count,
                final_outcome=self._workflow_outcome(result),
                started_at=request.started_at,
                completed_at=request.completed_at,
                execution_attempt_count=1,
                latency_ms=result.latency_ms,
            )
            records.append(workflow)
        else:
            if workflow.submission_id != result.submission_id:
                raise PipelinePersistenceError(result.submission_id)
            statement = update(WorkflowRun).where(
                WorkflowRun.id == result.workflow_run_id,
                WorkflowRun.current_stage.not_in([WorkflowStage.COMPLETED, WorkflowStage.FAILED]),
            )
            if request.execution_token is None:
                statement = statement.where(WorkflowRun.execution_token.is_(None))
            else:
                statement = statement.where(WorkflowRun.execution_token == request.execution_token)
            try:
                update_result = self._session.execute(
                    statement.values(
                        current_stage=WorkflowStage.COMPLETED,
                        regeneration_count=result.regeneration_count,
                        final_outcome=self._workflow_outcome(result),
                        completed_at=request.completed_at,
                        lease_expires_at=None,
                        execution_token=None,
                        next_retry_at=None,
                        latency_ms=result.latency_ms,
                        course_id=request.course_id,
                        task_id=request.task_id,
                        failure_category=None,
                    )
                )
            except SQLAlchemyError as error:
                self._session.rollback()
                raise PipelinePersistenceError(result.submission_id) from error
            if update_result.rowcount != 1:
                self._session.rollback()
                existing = self.get_by_submission(result.submission_id)
                if existing is not None:
                    return existing
                raise LostWorkflowLeaseError(result.workflow_run_id)
        try:
            for attempt in request.attempts:
                accepted = (
                    result.status is FeedbackPipelineStatus.VALIDATED
                    and attempt.feedback_id == result.feedback_id
                )
                feedback = self._feedback_record(result, attempt, accepted)
                judge = self._judge_record(attempt)
                records.extend([feedback, judge])

            if result.status is FeedbackPipelineStatus.FALLBACK:
                if result.safe_fallback is None:
                    raise PipelinePersistenceError(result.submission_id)
                records.append(
                    FeedbackRecord(
                        id=result.feedback_id,
                        submission_id=result.submission_id,
                        workflow_run_id=result.workflow_run_id,
                        feedback_content=result.safe_fallback.feedback_content,
                        status=FeedbackStatus.SAFE_FALLBACK,
                        source_references=[],
                        simulation_references=[],
                    )
                )
            integration_types = set()
            for intent in request.terminal_integrations:
                if intent.integration_type in integration_types:
                    continue
                try:
                    records.append(outbox_record(result.workflow_run_id, intent))
                except TerminalIntegrationPayloadError:
                    # Optional integration metadata is never authoritative over
                    # the student-facing terminal aggregate.
                    continue
                integration_types.add(intent.integration_type)
        except PipelinePersistenceError:
            self._session.rollback()
            raise

        self._session.add_all(records)
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            existing = self.get_by_submission(result.submission_id)
            if existing is not None:
                return existing
            raise PipelinePersistenceError(result.submission_id) from error
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PipelinePersistenceError(result.submission_id) from error
        return result

    def recover_terminal_integrations(
        self,
        workflow_run_id: str,
        *,
        observed_at: datetime,
    ) -> int:
        try:
            return SqlAlchemyTerminalIntegrationRepository(self._session).recover_expired(
                workflow_run_id,
                observed_at=observed_at,
            )
        except Exception:
            self._session.rollback()
            raise PipelinePersistenceError(workflow_run_id) from None

    @staticmethod
    def _validate_persistence_request(request: PipelinePersistenceRequest) -> None:
        result = request.result
        if _as_utc(request.completed_at) < _as_utc(request.started_at):
            raise PipelinePersistenceError(result.submission_id)
        attempts = request.attempts
        attempt_numbers = [attempt.generation_attempt for attempt in attempts]
        if attempt_numbers != list(range(1, len(attempts) + 1)) or len(attempts) > 2:
            raise PipelinePersistenceError(result.submission_id)
        if len({attempt.feedback_id for attempt in attempts}) != len(attempts):
            raise PipelinePersistenceError(result.submission_id)
        if len(result.judge_evaluations) != len(attempts) or any(
            expected != attempt.judge_evaluation
            for expected, attempt in zip(
                result.judge_evaluations,
                attempts,
                strict=True,
            )
        ):
            raise PipelinePersistenceError(result.submission_id)
        passed = [
            attempt.judge_evaluation.evaluation_status is JudgeEvaluationStatus.VALID
            and attempt.judge_evaluation.judge_result is not None
            and attempt.judge_evaluation.judge_result.decision is JudgeDecision.PASS
            for attempt in attempts
        ]
        expected_input_tokens = sum(
            attempt.generated_feedback.token_usage.input_tokens
            + attempt.judge_evaluation.token_usage.input_tokens
            for attempt in attempts
        )
        expected_output_tokens = sum(
            attempt.generated_feedback.token_usage.output_tokens
            + attempt.judge_evaluation.token_usage.output_tokens
            for attempt in attempts
        )
        expected_cost = sum(
            (
                attempt.generated_feedback.estimated_cost + attempt.judge_evaluation.estimated_cost
                for attempt in attempts
            ),
            Decimal("0"),
        )
        if (
            result.token_usage != _token_usage(expected_input_tokens, expected_output_tokens)
            or result.estimated_cost != expected_cost
        ):
            raise PipelinePersistenceError(result.submission_id)
        if result.status is FeedbackPipelineStatus.VALIDATED:
            expected_attempt_count = 2 if result.regeneration_count == 1 else 1
            if len(attempts) != expected_attempt_count:
                raise PipelinePersistenceError(result.submission_id)
            matching = [
                attempt for attempt in attempts if attempt.feedback_id == result.feedback_id
            ]
            if len(matching) != 1:
                raise PipelinePersistenceError(result.submission_id)
            released = matching[0]
            judge_result = released.judge_evaluation.judge_result
            if judge_result is None or judge_result.decision is not JudgeDecision.PASS:
                raise PipelinePersistenceError(result.submission_id)
            expected_attempt = 2 if result.regeneration_count else 1
            if released.generation_attempt != expected_attempt:
                raise PipelinePersistenceError(result.submission_id)
            if not passed[-1] or (result.regeneration_count == 1 and passed[0]):
                raise PipelinePersistenceError(result.submission_id)
            if (
                result.validated_feedback != released.generated_feedback
                or result.judge_result != released.judge_evaluation.judge_result
            ):
                raise PipelinePersistenceError(result.submission_id)
        else:
            if any(attempt.feedback_id == result.feedback_id for attempt in attempts):
                raise PipelinePersistenceError(result.submission_id)
            valid_fallback_shape = (
                result.regeneration_count == 0
                and not attempts
                or result.regeneration_count == 1
                and 1 <= len(attempts) <= 2
            )
            if not valid_fallback_shape or any(passed):
                raise PipelinePersistenceError(result.submission_id)

    @staticmethod
    def _workflow_outcome(result: FeedbackPipelineResult) -> WorkflowOutcome:
        if result.status is FeedbackPipelineStatus.FALLBACK:
            return WorkflowOutcome.SAFE_FALLBACK
        if result.regeneration_count == 1:
            return WorkflowOutcome.SECOND_PASS
        return WorkflowOutcome.FIRST_PASS

    @staticmethod
    def _validate_terminal_shape(
        workflow: WorkflowRun,
        *,
        generated_records: list[FeedbackRecord],
        released: FeedbackRecord,
    ) -> None:
        passed = [
            record.judge_evaluation is not None
            and record.judge_evaluation.evaluation_status is JudgeEvaluationStatus.VALID
            and record.judge_evaluation.decision is JudgeDecision.PASS
            for record in generated_records
        ]
        if workflow.final_outcome is WorkflowOutcome.FIRST_PASS:
            valid = (
                workflow.regeneration_count == 0
                and released.status is FeedbackStatus.ACCEPTED
                and released.generation_attempt == 1
                and len(generated_records) == 1
                and passed == [True]
            )
        elif workflow.final_outcome is WorkflowOutcome.SECOND_PASS:
            valid = (
                workflow.regeneration_count == 1
                and released.status is FeedbackStatus.ACCEPTED
                and released.generation_attempt == 2
                and len(generated_records) == 2
                and passed == [False, True]
            )
        elif workflow.final_outcome is WorkflowOutcome.SAFE_FALLBACK:
            valid = (
                released.status is FeedbackStatus.SAFE_FALLBACK
                and released.generation_attempt is None
                and (
                    workflow.regeneration_count == 0
                    and len(generated_records) == 0
                    or workflow.regeneration_count == 1
                    and 1 <= len(generated_records) <= 2
                )
                and not any(passed)
            )
        else:
            valid = False
        if not valid:
            raise PipelinePersistenceError(workflow.submission_id)

    @staticmethod
    def _feedback_record(
        result: FeedbackPipelineResult,
        attempt: FeedbackAttemptPersistence,
        accepted: bool,
    ) -> FeedbackRecord:
        generated = attempt.generated_feedback
        attributed_source_ids = {
            attribution.source_id for attribution in generated.source_attributions
        }
        if attributed_source_ids != set(generated.source_references):
            raise PipelinePersistenceError(result.submission_id)
        return FeedbackRecord(
            id=attempt.feedback_id,
            submission_id=result.submission_id,
            workflow_run_id=result.workflow_run_id,
            feedback_content=generated.feedback_content,
            status=FeedbackStatus.ACCEPTED if accepted else FeedbackStatus.REJECTED,
            generation_attempt=attempt.generation_attempt,
            provider=generated.provider,
            model=generated.model,
            prompt_version=generated.prompt_version,
            source_references=generated.source_references,
            simulation_references=generated.simulation_references,
            source_attributions=[
                attribution.model_dump(mode="json") for attribution in generated.source_attributions
            ],
            input_tokens=generated.token_usage.input_tokens,
            output_tokens=generated.token_usage.output_tokens,
            total_tokens=generated.token_usage.total_tokens,
            estimated_cost=generated.estimated_cost,
            usage_complete=generated.usage_complete,
        )

    @staticmethod
    def _judge_record(attempt: FeedbackAttemptPersistence) -> JudgeEvaluation:
        evaluation = attempt.judge_evaluation
        result = evaluation.judge_result
        return JudgeEvaluation(
            feedback_id=attempt.feedback_id,
            evaluation_status=evaluation.evaluation_status,
            reported_decision=evaluation.reported_decision,
            decision=result.decision if result is not None else None,
            correctness_score=result.correctness_score if result is not None else None,
            relevance_score=result.relevance_score if result is not None else None,
            grounding_score=result.grounding_score if result is not None else None,
            actionability_score=result.actionability_score if result is not None else None,
            safety_score=result.safety_score if result is not None else None,
            reason=evaluation.reason,
            unsupported_claims=result.unsupported_claims if result is not None else [],
            regeneration_instructions=(
                result.regeneration_instructions if result is not None else []
            ),
            error_category=evaluation.error_category,
            provider=evaluation.provider,
            model=evaluation.model,
            prompt_version=evaluation.prompt_version,
            quality_policy_version=evaluation.quality_policy_version,
            input_tokens=evaluation.token_usage.input_tokens,
            output_tokens=evaluation.token_usage.output_tokens,
            total_tokens=evaluation.token_usage.total_tokens,
            estimated_cost=evaluation.estimated_cost,
            usage_complete=evaluation.usage_complete,
        )

    @staticmethod
    def _generated_feedback(record: FeedbackRecord, submission_id: str) -> GeneratedFeedback:
        if record.provider is None or record.model is None or record.prompt_version is None:
            raise PipelinePersistenceError(submission_id)
        try:
            return GeneratedFeedback(
                feedback_content=record.feedback_content,
                provider=record.provider,
                model=record.model,
                prompt_version=record.prompt_version,
                source_references=record.source_references,
                source_attributions=record.source_attributions,
                simulation_references=record.simulation_references,
                token_usage=TokenUsage(
                    input_tokens=record.input_tokens,
                    output_tokens=record.output_tokens,
                    total_tokens=record.total_tokens,
                ),
                estimated_cost=record.estimated_cost,
                usage_complete=record.usage_complete,
            )
        except (ArithmeticError, TypeError, ValueError):
            raise PipelinePersistenceError(submission_id) from None

    @staticmethod
    def _judge_outcome(
        judge: JudgeEvaluation,
        submission_id: str,
    ) -> JudgeEvaluationOutcome:
        try:
            usage = TokenUsage(
                input_tokens=judge.input_tokens,
                output_tokens=judge.output_tokens,
                total_tokens=judge.total_tokens,
            )
            if judge.evaluation_status is JudgeEvaluationStatus.VALID:
                if judge.reported_decision is None or judge.decision is None:
                    raise PipelinePersistenceError(submission_id)
                result = JudgeResult(
                    decision=judge.decision,
                    correctness_score=judge.correctness_score,
                    relevance_score=judge.relevance_score,
                    grounding_score=judge.grounding_score,
                    actionability_score=judge.actionability_score,
                    safety_score=judge.safety_score,
                    reason=judge.reason,
                    unsupported_claims=judge.unsupported_claims,
                    regeneration_instructions=judge.regeneration_instructions,
                )
                return JudgeEvaluationOutcome(
                    evaluation_status=judge.evaluation_status,
                    reported_decision=judge.reported_decision,
                    judge_result=result,
                    reason=judge.reason,
                    provider=judge.provider,
                    model=judge.model,
                    prompt_version=judge.prompt_version,
                    quality_policy_version=judge.quality_policy_version,
                    token_usage=usage,
                    estimated_cost=judge.estimated_cost,
                    usage_complete=judge.usage_complete,
                )
            return JudgeEvaluationOutcome(
                evaluation_status=judge.evaluation_status,
                reason=judge.reason,
                error_category=judge.error_category,
                provider=judge.provider,
                model=judge.model,
                prompt_version=judge.prompt_version,
                quality_policy_version=judge.quality_policy_version,
                token_usage=usage,
                estimated_cost=judge.estimated_cost,
                usage_complete=judge.usage_complete,
            )
        except PipelinePersistenceError:
            raise
        except (ArithmeticError, TypeError, ValueError):
            raise PipelinePersistenceError(submission_id) from None
