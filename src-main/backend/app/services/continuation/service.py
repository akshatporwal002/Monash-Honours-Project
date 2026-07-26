from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.schemas.continuation import (
    ContinuationAvailability,
    ContinuationResponse,
)
from app.services.continuation.contracts import (
    ContinuationClaim,
    ContinuationFailureCategory,
    ContinuationRecord,
    ContinuationRepository,
    ContinuationScheduleReceipt,
    ContinuationState,
    ContinuationWorkerOutcome,
    NextTaskRecommender,
    NextTaskRequest,
    ProgressPersistenceAdapter,
    ProgressUpdate,
    TerminalFeedbackNotice,
)

_OPAQUE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$")
_PSEUDONYM = re.compile(r"^v1_[0-9a-f]{64}$")
_UNKNOWN_WORKFLOW_ID = "00000000-0000-4000-8000-000000000000"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid4())


def _valid_uuid4(value: str) -> bool:
    try:
        parsed = UUID(value)
    except (AttributeError, TypeError, ValueError):
        return False
    return parsed.version == 4 and str(parsed) == value.lower()


def _valid_reference(value: object) -> bool:
    return isinstance(value, str) and bool(_OPAQUE_REFERENCE.fullmatch(value))


def _valid_notice(notice: TerminalFeedbackNotice) -> bool:
    return (
        _valid_uuid4(notice.workflow_run_id)
        and _valid_uuid4(notice.correlation_id)
        and _PSEUDONYM.fullmatch(notice.pseudonymous_actor_reference) is not None
        and _valid_reference(notice.course_reference)
        and _valid_reference(notice.completed_task_reference)
    )


class TerminalContinuationService:
    """Schedules continuation without allowing it to withhold released feedback."""

    def __init__(self, repository: ContinuationRepository | None) -> None:
        self._repository = repository

    def after_terminal_feedback(
        self,
        notice: TerminalFeedbackNotice,
    ) -> ContinuationScheduleReceipt:
        if not _valid_notice(notice):
            return ContinuationScheduleReceipt(
                workflow_run_id=_UNKNOWN_WORKFLOW_ID,
                accepted=False,
                state=None,
                failure_category=ContinuationFailureCategory.INVALID_NOTICE,
            )
        if self._repository is None:
            return ContinuationScheduleReceipt(
                workflow_run_id=notice.workflow_run_id,
                accepted=False,
                state=None,
                failure_category=ContinuationFailureCategory.REPOSITORY_NOT_CONFIGURED,
            )
        try:
            record = self._repository.ensure_pending(notice)
        except Exception:
            return ContinuationScheduleReceipt(
                workflow_run_id=notice.workflow_run_id,
                accepted=False,
                state=None,
                failure_category=ContinuationFailureCategory.PERSISTENCE_UNAVAILABLE,
            )
        return ContinuationScheduleReceipt(
            workflow_run_id=record.workflow_run_id,
            accepted=True,
            state=record.state,
        )


class ContinuationWorker:
    """Runs continuation work behind the durable-feedback boundary."""

    def __init__(
        self,
        repository: ContinuationRepository | None,
        progress_adapter: ProgressPersistenceAdapter | None,
        recommender: NextTaskRecommender | None,
        *,
        now: Callable[[], datetime] = _utc_now,
        uuid_factory: Callable[[], str] = _uuid,
        lease_duration: timedelta = timedelta(minutes=5),
        retry_backoff: timedelta = timedelta(seconds=5),
        maximum_attempts: int = 3,
        adapter_timeout_seconds: float = 60,
    ) -> None:
        if lease_duration <= timedelta(0):
            raise ValueError("lease_duration must be positive")
        if retry_backoff < timedelta(0):
            raise ValueError("retry_backoff cannot be negative")
        if not 1 <= maximum_attempts <= 3:
            raise ValueError("maximum_attempts must be between 1 and 3")
        if not 0 < adapter_timeout_seconds <= 60:
            raise ValueError("adapter_timeout_seconds must be between 0 and 60")
        self._repository = repository
        self._progress_adapter = progress_adapter
        self._recommender = recommender
        self._now = now
        self._uuid_factory = uuid_factory
        self._lease_duration = lease_duration
        self._retry_backoff = retry_backoff
        self._maximum_attempts = maximum_attempts
        self._adapter_timeout_seconds = adapter_timeout_seconds

    async def run_once(self) -> ContinuationWorkerOutcome:
        repository = self._repository
        if repository is None:
            return ContinuationWorkerOutcome(
                processed=False,
                state=ContinuationState.FAILED,
                failure_category=ContinuationFailureCategory.REPOSITORY_NOT_CONFIGURED,
            )
        observed_at = self._now()
        try:
            exhausted_workflow_id = repository.finalize_next_exhausted(
                observed_at=observed_at,
                maximum_attempts=self._maximum_attempts,
            )
            if exhausted_workflow_id is not None:
                return ContinuationWorkerOutcome(
                    processed=True,
                    workflow_run_id=exhausted_workflow_id,
                    state=ContinuationState.FAILED,
                    failure_category=ContinuationFailureCategory.PERSISTENCE_UNAVAILABLE,
                )
            claim = repository.claim_next(
                now=observed_at,
                lease_expires_at=observed_at + self._lease_duration,
                execution_token=self._uuid_factory(),
                maximum_attempts=self._maximum_attempts,
            )
        except Exception:
            return ContinuationWorkerOutcome(
                processed=False,
                state=ContinuationState.FAILED,
                failure_category=ContinuationFailureCategory.PERSISTENCE_UNAVAILABLE,
            )
        if claim is None:
            return ContinuationWorkerOutcome(processed=False)

        if self._progress_adapter is None:
            return self._fail_closed(
                repository,
                claim,
                ContinuationFailureCategory.PROGRESS_ADAPTER_NOT_CONFIGURED,
                retryable=False,
            )
        current_claim = claim
        if not current_claim.progress_recorded:
            try:
                await asyncio.wait_for(
                    self._progress_adapter.record_terminal_feedback(
                        ProgressUpdate(
                            workflow_run_id=current_claim.workflow_run_id,
                            pseudonymous_actor_reference=(
                                current_claim.pseudonymous_actor_reference
                            ),
                            course_reference=current_claim.course_reference,
                            completed_task_reference=(current_claim.completed_task_reference),
                            idempotency_key=current_claim.workflow_run_id,
                            correlation_id=current_claim.correlation_id,
                        )
                    ),
                    timeout=self._adapter_timeout_seconds,
                )
            except Exception:
                return self._retry_or_fail(
                    repository,
                    current_claim,
                    ContinuationFailureCategory.PROGRESS_UNAVAILABLE,
                )
            try:
                if not repository.mark_progress_recorded(current_claim):
                    return self._stale(current_claim)
            except Exception:
                return ContinuationWorkerOutcome(
                    processed=True,
                    workflow_run_id=current_claim.workflow_run_id,
                    state=ContinuationState.FAILED,
                    failure_category=ContinuationFailureCategory.PERSISTENCE_UNAVAILABLE,
                )
            current_claim = replace(current_claim, progress_recorded=True)

        if self._recommender is None:
            return self._fail_closed(
                repository,
                current_claim,
                ContinuationFailureCategory.RECOMMENDER_NOT_CONFIGURED,
                retryable=False,
            )

        try:
            next_task_reference = await asyncio.wait_for(
                self._recommender.recommend_next_task(
                    NextTaskRequest(
                        workflow_run_id=current_claim.workflow_run_id,
                        pseudonymous_actor_reference=(current_claim.pseudonymous_actor_reference),
                        course_reference=current_claim.course_reference,
                        completed_task_reference=current_claim.completed_task_reference,
                        correlation_id=current_claim.correlation_id,
                    )
                ),
                timeout=self._adapter_timeout_seconds,
            )
        except Exception:
            return self._retry_or_fail(
                repository,
                current_claim,
                ContinuationFailureCategory.RECOMMENDER_UNAVAILABLE,
            )
        if not _valid_reference(next_task_reference):
            return self._retry_or_fail(
                repository,
                current_claim,
                ContinuationFailureCategory.INVALID_RECOMMENDATION,
            )
        try:
            if not repository.complete(
                current_claim,
                next_task_reference,
                completed_at=self._now(),
            ):
                return self._stale(current_claim)
        except Exception:
            return ContinuationWorkerOutcome(
                processed=True,
                workflow_run_id=current_claim.workflow_run_id,
                state=ContinuationState.FAILED,
                failure_category=ContinuationFailureCategory.PERSISTENCE_UNAVAILABLE,
            )
        return ContinuationWorkerOutcome(
            processed=True,
            workflow_run_id=current_claim.workflow_run_id,
            state=ContinuationState.COMPLETED,
        )

    def _retry_or_fail(
        self,
        repository: ContinuationRepository,
        claim: ContinuationClaim,
        category: ContinuationFailureCategory,
    ) -> ContinuationWorkerOutcome:
        retryable = claim.processing_attempts < self._maximum_attempts
        return self._fail_closed(
            repository,
            claim,
            category,
            retryable=retryable,
        )

    def _fail_closed(
        self,
        repository: ContinuationRepository,
        claim: ContinuationClaim,
        category: ContinuationFailureCategory,
        *,
        retryable: bool,
    ) -> ContinuationWorkerOutcome:
        failed_at = self._now()
        try:
            updated = repository.fail(
                claim,
                category,
                failed_at=failed_at,
                retryable=retryable,
                next_retry_at=(failed_at + self._retry_backoff if retryable else None),
            )
        except Exception:
            return ContinuationWorkerOutcome(
                processed=True,
                workflow_run_id=claim.workflow_run_id,
                state=ContinuationState.FAILED,
                failure_category=ContinuationFailureCategory.PERSISTENCE_UNAVAILABLE,
            )
        if not updated:
            return self._stale(claim)
        return ContinuationWorkerOutcome(
            processed=True,
            workflow_run_id=claim.workflow_run_id,
            state=(ContinuationState.RETRY_SCHEDULED if retryable else ContinuationState.FAILED),
            retryable=retryable,
            failure_category=category,
        )

    @staticmethod
    def _stale(claim: ContinuationClaim) -> ContinuationWorkerOutcome:
        return ContinuationWorkerOutcome(
            processed=True,
            workflow_run_id=claim.workflow_run_id,
            stale_claim=True,
        )


class ContinuationQueryService:
    """Maps internal state to the minimal route-facing integration contract."""

    def __init__(self, repository: ContinuationRepository | None) -> None:
        self._repository = repository

    def get(self, workflow_run_id: str) -> ContinuationResponse:
        if not _valid_uuid4(workflow_run_id) or self._repository is None:
            return self._unavailable(workflow_run_id)
        try:
            record = self._repository.get(workflow_run_id)
        except Exception:
            return self._unavailable(workflow_run_id)
        if record is None:
            return self._unavailable(workflow_run_id)
        return self._response(record)

    @staticmethod
    def _response(record: ContinuationRecord) -> ContinuationResponse:
        if not _valid_uuid4(record.workflow_run_id):
            return ContinuationQueryService._unavailable(record.workflow_run_id)
        if record.state is ContinuationState.COMPLETED and _valid_reference(
            record.next_task_reference
        ):
            return ContinuationResponse(
                workflow_run_id=record.workflow_run_id,
                status=ContinuationAvailability.READY,
                next_task_reference=record.next_task_reference,
            )
        if record.state in {
            ContinuationState.PENDING,
            ContinuationState.RUNNING,
            ContinuationState.RETRY_SCHEDULED,
        }:
            return ContinuationResponse(
                workflow_run_id=record.workflow_run_id,
                status=ContinuationAvailability.PROCESSING,
            )
        return ContinuationResponse(
            workflow_run_id=record.workflow_run_id,
            status=ContinuationAvailability.UNAVAILABLE,
            retryable=record.retryable,
        )

    @staticmethod
    def _unavailable(workflow_run_id: str) -> ContinuationResponse:
        safe_workflow_id = (
            workflow_run_id if _valid_uuid4(workflow_run_id) else _UNKNOWN_WORKFLOW_ID
        )
        return ContinuationResponse(
            workflow_run_id=safe_workflow_id,
            status=ContinuationAvailability.UNAVAILABLE,
        )
