from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.models.enums import WorkflowStage
from app.schemas.feedback import FeedbackPipelineStatus, FeedbackResponseClassification
from app.schemas.feedback_api import (
    AuthenticatedActor,
    FeedbackFailureView,
    FeedbackSourceView,
    FeedbackWorkflowResponse,
    FeedbackWorkflowStatus,
    SafeFallbackView,
    ValidatedFeedbackView,
)
from app.services.audit_events import FeedbackAuditEvents
from app.services.feedback.agent import AI_GENERATED_NOTICE
from app.services.feedback.contracts import (
    FeedbackReportWrite,
    FeedbackReportWriteResult,
    WorkflowClaim,
)
from app.services.feedback.errors import (
    ContextCollectionError,
    ContextIntegrityError,
    LostWorkflowLeaseError,
    PipelinePersistenceError,
    SubmissionNotFoundError,
    TaskNotFoundError,
)
from app.services.feedback.pipeline import FeedbackPipeline
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FeedbackAccessPolicy(Protocol):
    async def can_access_submission(
        self,
        actor: AuthenticatedActor,
        submission_id: str,
    ) -> bool: ...


class FeedbackBackgroundExecutor(Protocol):
    async def execute(
        self,
        workflow_run_id: str,
        submission_id: str,
        execution_token: str | None = None,
        correlation_id: str | None = None,
    ) -> None: ...


class FeedbackWorkflowApplication:
    def __init__(
        self,
        repository: SqlAlchemyFeedbackWorkflowRepository,
        *,
        now: Callable[[], datetime] = _utc_now,
        uuid_factory: Callable[[], str] = lambda: str(uuid4()),
        lease_duration: timedelta = timedelta(minutes=5),
        audit_events: FeedbackAuditEvents | None = None,
    ) -> None:
        self._repository = repository
        self._now = now
        self._uuid_factory = uuid_factory
        self._lease_duration = lease_duration
        self._audit_events = audit_events

    def start(
        self,
        submission_id: str,
        *,
        correlation_id: str | None = None,
    ) -> WorkflowClaim:
        started_at = self._now()
        claim = self._repository.claim_workflow(
            submission_id,
            self._uuid_factory(),
            started_at=started_at,
            lease_expires_at=started_at + self._lease_duration,
        )
        if (
            claim.stage is WorkflowStage.FAILED
            and claim.failure_category == "retry_attempts_exhausted"
            and self._audit_events is not None
        ):
            try:
                self._audit_events.workflow_failed(
                    claim.workflow_run_id,
                    correlation_id or claim.workflow_run_id,
                    "retry_attempts_exhausted",
                )
            except Exception:
                # A terminal failed workflow remains authoritative when its
                # student-path audit sink is unavailable.
                pass
        return claim

    def get(self, submission_id: str) -> WorkflowClaim | None:
        return self._repository.get_workflow_claim(
            submission_id,
            observed_at=self._now(),
        )

    def released_submission_id(self, feedback_id: str) -> str | None:
        return self._repository.get_released_submission_id(feedback_id)

    def report(self, report: FeedbackReportWrite) -> FeedbackReportWriteResult:
        return self._repository.save_report(report)


PipelineFactory = Callable[
    [SqlAlchemyFeedbackWorkflowRepository],
    FeedbackPipeline,
]


class InProcessFeedbackExecutor:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        pipeline_factory: PipelineFactory,
        *,
        now: Callable[[], datetime] = _utc_now,
        retry_backoff: timedelta = timedelta(seconds=5),
        audit_events: FeedbackAuditEvents | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._pipeline_factory = pipeline_factory
        self._now = now
        self._retry_backoff = retry_backoff
        self._audit_events = audit_events

    async def execute(
        self,
        workflow_run_id: str,
        submission_id: str,
        execution_token: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        job_correlation_id = correlation_id or workflow_run_id
        try:
            with self._session_factory() as session:
                repository = SqlAlchemyFeedbackWorkflowRepository(session)
                pipeline = self._pipeline_factory(repository)
                pipeline.attach_progress_recorder(repository)
                if self._audit_events is not None:
                    pipeline.attach_audit_events(self._audit_events)
                await pipeline.run(
                    submission_id,
                    workflow_run_id,
                    execution_token=execution_token,
                    correlation_id=job_correlation_id,
                )
        except LostWorkflowLeaseError:
            return
        except Exception as error:
            failure_category, retryable = self._failure(error)
            try:
                failed_at = self._now()
                with self._session_factory() as session:
                    repository = SqlAlchemyFeedbackWorkflowRepository(session)
                    repository.mark_failed(
                        workflow_run_id,
                        failure_category,
                        failed_at,
                        execution_token=execution_token,
                        retryable=retryable,
                        next_retry_at=(failed_at + self._retry_backoff if retryable else None),
                    )
                    failed_claim = repository.get_workflow_claim(submission_id)
                terminal_failure = (
                    failed_claim is not None
                    and failed_claim.stage is WorkflowStage.FAILED
                    and not failed_claim.retryable
                )
                if terminal_failure and self._audit_events is not None:
                    try:
                        self._audit_events.workflow_failed(
                            workflow_run_id,
                            job_correlation_id,
                            failure_category,
                        )
                    except Exception:
                        pass
            except Exception:
                return

    @staticmethod
    def _failure(error: Exception) -> tuple[str, bool]:
        if isinstance(error, SubmissionNotFoundError):
            return "submission_unavailable", False
        if isinstance(error, TaskNotFoundError):
            return "task_unavailable", False
        if isinstance(error, ContextIntegrityError):
            return "context_integrity_error", False
        if isinstance(error, ContextCollectionError):
            return "context_unavailable", True
        if isinstance(error, PipelinePersistenceError):
            return "persistence_unavailable", True
        return "unexpected_infrastructure_error", True


def workflow_response(claim: WorkflowClaim) -> FeedbackWorkflowResponse:
    result = claim.terminal_result
    if result is not None and result.status is FeedbackPipelineStatus.VALIDATED:
        generated = result.validated_feedback
        if generated is None:
            raise ValueError("validated workflow is missing released feedback")
        content = generated.feedback_content
        return FeedbackWorkflowResponse(
            workflow_run_id=claim.workflow_run_id,
            submission_id=claim.submission_id,
            status=FeedbackWorkflowStatus.VALIDATED,
            feedback=ValidatedFeedbackView(
                feedback_id=result.feedback_id,
                response_classification=_classification(content.get("response_classification")),
                summary=_required_text(content, "summary"),
                identified_error=_optional_text(content, "identified_error"),
                explanation=_optional_text(content, "explanation"),
                improvement_actions=_string_list(content.get("improvement_actions")),
                recommended_next_step=_optional_text(content, "recommended_next_step"),
                sources=(
                    [
                        FeedbackSourceView(
                            source_id=attribution.source_id,
                            label=attribution.label,
                        )
                        for attribution in generated.source_attributions
                    ]
                    or [
                        FeedbackSourceView(source_id=source_id, label=source_id)
                        for source_id in generated.source_references
                    ]
                ),
                simulation_references=generated.simulation_references,
                ai_generated_notice=AI_GENERATED_NOTICE,
            ),
        )
    if result is not None and result.status is FeedbackPipelineStatus.FALLBACK:
        fallback = result.safe_fallback
        if fallback is None:
            raise ValueError("fallback workflow is missing released feedback")
        content = fallback.feedback_content
        return FeedbackWorkflowResponse(
            workflow_run_id=claim.workflow_run_id,
            submission_id=claim.submission_id,
            status=FeedbackWorkflowStatus.FALLBACK,
            feedback=SafeFallbackView(
                feedback_id=result.feedback_id,
                summary=_required_text(content, "summary"),
                explanation=_required_text(content, "explanation"),
                recommended_next_step=_required_text(content, "recommended_next_step"),
            ),
        )
    if claim.stage is WorkflowStage.FAILED:
        return FeedbackWorkflowResponse(
            workflow_run_id=claim.workflow_run_id,
            submission_id=claim.submission_id,
            status=FeedbackWorkflowStatus.FAILED,
            error=FeedbackFailureView(retryable=claim.retryable),
        )
    return FeedbackWorkflowResponse(
        workflow_run_id=claim.workflow_run_id,
        submission_id=claim.submission_id,
        status=FeedbackWorkflowStatus.PROCESSING,
        processing_stage=claim.stage,
    )


def _required_text(content: dict[str, object], key: str) -> str:
    value = content.get(key)
    if isinstance(value, str) and value.strip():
        return value
    if key == "summary":
        return "Feedback is available."
    return "Review your course material and ask an educator if you need help."


def _optional_text(content: dict[str, object], key: str) -> str | None:
    value = content.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _classification(value: object) -> FeedbackResponseClassification | None:
    try:
        return FeedbackResponseClassification(value)
    except (TypeError, ValueError):
        return None
