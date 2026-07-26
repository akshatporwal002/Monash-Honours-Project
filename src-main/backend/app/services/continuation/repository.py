from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.continuation import ContinuationJob
from app.models.enums import (
    ContinuationFailureCategory,
    ContinuationState,
    WorkflowOutcome,
    WorkflowStage,
)
from app.models.persistence import WorkflowRun
from app.services.continuation.contracts import (
    ContinuationClaim,
    ContinuationRecord,
    TerminalFeedbackNotice,
)

_OPAQUE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$")
_PSEUDONYM = re.compile(r"^v1_[0-9a-f]{64}$")
_MAXIMUM_ATTEMPTS = 3
_RELEASED_OUTCOMES = {
    WorkflowOutcome.FIRST_PASS,
    WorkflowOutcome.SECOND_PASS,
    WorkflowOutcome.SAFE_FALLBACK,
}


class ContinuationPersistenceError(Exception):
    """A sanitized continuation persistence failure."""


class ContinuationConflictError(ContinuationPersistenceError):
    """A workflow ID was reused for different immutable continuation input."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _valid_uuid4(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = UUID(value)
    except ValueError:
        return False
    return parsed.version == 4 and str(parsed) == value.lower()


def _valid_reference(value: object) -> bool:
    return isinstance(value, str) and _OPAQUE_REFERENCE.fullmatch(value) is not None


def _validate_notice(notice: TerminalFeedbackNotice) -> None:
    if not (
        _valid_uuid4(notice.workflow_run_id)
        and _valid_uuid4(notice.correlation_id)
        and _PSEUDONYM.fullmatch(notice.pseudonymous_actor_reference) is not None
        and _valid_reference(notice.course_reference)
        and _valid_reference(notice.completed_task_reference)
    ):
        raise ContinuationPersistenceError("continuation notice is invalid")


def _validate_claim(claim: ContinuationClaim) -> None:
    if not (
        _valid_uuid4(claim.workflow_run_id)
        and _valid_uuid4(claim.execution_token)
        and _valid_uuid4(claim.correlation_id)
        and _PSEUDONYM.fullmatch(claim.pseudonymous_actor_reference) is not None
        and _valid_reference(claim.course_reference)
        and _valid_reference(claim.completed_task_reference)
        and 1 <= claim.processing_attempts <= _MAXIMUM_ATTEMPTS
    ):
        raise ContinuationPersistenceError("continuation claim is invalid")


class SqlAlchemyContinuationRepository:
    """SQLite-safe durable continuation jobs with token-fenced mutations."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_pending(self, notice: TerminalFeedbackNotice) -> ContinuationRecord:
        _validate_notice(notice)
        existing = self._get_job(notice.workflow_run_id)
        if existing is not None:
            self._validate_exact_replay(existing, notice)
            return self._record(existing)

        workflow = self._get_workflow(notice.workflow_run_id)
        if (
            workflow is None
            or workflow.current_stage is not WorkflowStage.COMPLETED
            or workflow.final_outcome not in _RELEASED_OUTCOMES
        ):
            raise ContinuationPersistenceError("released workflow is unavailable")

        job = ContinuationJob(
            workflow_run_id=notice.workflow_run_id,
            pseudonymous_actor_reference=notice.pseudonymous_actor_reference,
            course_reference=notice.course_reference,
            completed_task_reference=notice.completed_task_reference,
            correlation_id=notice.correlation_id,
            state=ContinuationState.PENDING,
        )
        self._session.add(job)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            winner = self._get_job(notice.workflow_run_id)
            if winner is None:
                raise ContinuationPersistenceError("continuation job could not be stored") from None
            self._validate_exact_replay(winner, notice)
            return self._record(winner)
        except SQLAlchemyError:
            self._session.rollback()
            raise ContinuationPersistenceError("continuation job could not be stored") from None
        return self._record(job)

    def claim_next(
        self,
        *,
        now: datetime,
        lease_expires_at: datetime,
        execution_token: str,
        maximum_attempts: int,
    ) -> ContinuationClaim | None:
        observed_at = _utc(now)
        lease_until = _utc(lease_expires_at)
        if (
            not _valid_uuid4(execution_token)
            or not 1 <= maximum_attempts <= _MAXIMUM_ATTEMPTS
            or lease_until <= observed_at
        ):
            raise ContinuationPersistenceError("continuation claim request is invalid")

        try:
            candidate = self._session.scalar(
                select(ContinuationJob)
                .where(
                    ContinuationJob.processing_attempts < maximum_attempts,
                    or_(
                        ContinuationJob.state == ContinuationState.PENDING,
                        and_(
                            ContinuationJob.state == ContinuationState.RETRY_SCHEDULED,
                            ContinuationJob.next_retry_at <= observed_at,
                        ),
                        and_(
                            ContinuationJob.state == ContinuationState.RUNNING,
                            ContinuationJob.lease_expires_at <= observed_at,
                        ),
                    ),
                )
                .order_by(ContinuationJob.created_at, ContinuationJob.workflow_run_id)
                .limit(1)
            )
        except (LookupError, SQLAlchemyError):
            self._session.rollback()
            raise ContinuationPersistenceError("continuation job could not be claimed") from None
        if candidate is None:
            return None

        previous_state = candidate.state
        previous_token = candidate.execution_token
        previous_lease = candidate.lease_expires_at
        previous_retry = candidate.next_retry_at
        previous_attempts = candidate.processing_attempts
        next_attempt = previous_attempts + 1
        claim_values = {
            "workflow_run_id": candidate.workflow_run_id,
            "pseudonymous_actor_reference": candidate.pseudonymous_actor_reference,
            "course_reference": candidate.course_reference,
            "completed_task_reference": candidate.completed_task_reference,
            "correlation_id": candidate.correlation_id,
            "progress_recorded": candidate.progress_recorded,
        }

        statement = update(ContinuationJob).where(
            ContinuationJob.workflow_run_id == candidate.workflow_run_id,
            ContinuationJob.state == previous_state,
            ContinuationJob.processing_attempts == previous_attempts,
        )
        statement = self._match_nullable(
            statement,
            ContinuationJob.execution_token,
            previous_token,
        )
        statement = self._match_nullable(
            statement,
            ContinuationJob.lease_expires_at,
            previous_lease,
        )
        statement = self._match_nullable(
            statement,
            ContinuationJob.next_retry_at,
            previous_retry,
        )
        try:
            result = self._session.execute(
                statement.values(
                    state=ContinuationState.RUNNING,
                    processing_attempts=next_attempt,
                    execution_token=execution_token,
                    lease_expires_at=lease_until,
                    next_retry_at=None,
                    next_task_reference=None,
                    failure_category=None,
                    completed_at=None,
                    updated_at=observed_at,
                )
            )
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise ContinuationPersistenceError("continuation job could not be claimed") from None
        if result.rowcount != 1:
            return None

        return ContinuationClaim(
            **claim_values,
            execution_token=execution_token,
            processing_attempts=next_attempt,
            lease_expires_at=lease_until,
        )

    def finalize_next_exhausted(
        self,
        *,
        observed_at: datetime,
        maximum_attempts: int,
    ) -> str | None:
        """Finalize one expired last-attempt claim without reviving its worker."""
        observed = _utc(observed_at)
        if not 1 <= maximum_attempts <= _MAXIMUM_ATTEMPTS:
            raise ContinuationPersistenceError("continuation exhaustion request is invalid")
        try:
            candidate = self._session.scalar(
                select(ContinuationJob)
                .where(
                    ContinuationJob.state == ContinuationState.RUNNING,
                    ContinuationJob.processing_attempts >= maximum_attempts,
                    ContinuationJob.execution_token.is_not(None),
                    ContinuationJob.lease_expires_at.is_not(None),
                    ContinuationJob.lease_expires_at <= observed,
                )
                .order_by(ContinuationJob.created_at, ContinuationJob.workflow_run_id)
                .limit(1)
            )
        except (LookupError, SQLAlchemyError):
            self._session.rollback()
            raise ContinuationPersistenceError(
                "continuation exhaustion could not be finalized"
            ) from None
        if candidate is None:
            return None
        return (
            candidate.workflow_run_id if self._finalize_exhausted_job(candidate, observed) else None
        )

    def mark_progress_recorded(self, claim: ContinuationClaim) -> bool:
        _validate_claim(claim)
        return self._fenced_update(
            claim,
            {
                "progress_recorded": True,
                "updated_at": datetime.now(UTC),
            },
        )

    def complete(
        self,
        claim: ContinuationClaim,
        next_task_reference: str,
        *,
        completed_at: datetime,
    ) -> bool:
        _validate_claim(claim)
        if not _valid_reference(next_task_reference):
            raise ContinuationPersistenceError("next-task reference is invalid")
        terminal_at = _utc(completed_at)
        return self._fenced_update(
            claim,
            {
                "state": ContinuationState.COMPLETED,
                "execution_token": None,
                "lease_expires_at": None,
                "next_retry_at": None,
                "next_task_reference": next_task_reference,
                "failure_category": None,
                "completed_at": terminal_at,
                "updated_at": terminal_at,
            },
            require_progress=True,
        )

    def fail(
        self,
        claim: ContinuationClaim,
        category: ContinuationFailureCategory,
        *,
        failed_at: datetime,
        retryable: bool,
        next_retry_at: datetime | None,
    ) -> bool:
        _validate_claim(claim)
        if not isinstance(category, ContinuationFailureCategory):
            raise ContinuationPersistenceError("continuation failure category is invalid")
        observed_at = _utc(failed_at)
        retry_at = _utc(next_retry_at) if next_retry_at is not None else None
        if retryable:
            if (
                claim.processing_attempts >= _MAXIMUM_ATTEMPTS
                or retry_at is None
                or retry_at < observed_at
            ):
                raise ContinuationPersistenceError("continuation retry schedule is invalid")
        elif retry_at is not None:
            raise ContinuationPersistenceError("terminal continuation cannot be retried")

        return self._fenced_update(
            claim,
            {
                "state": (
                    ContinuationState.RETRY_SCHEDULED if retryable else ContinuationState.FAILED
                ),
                "execution_token": None,
                "lease_expires_at": None,
                "next_retry_at": retry_at,
                "next_task_reference": None,
                "failure_category": category,
                "completed_at": None if retryable else observed_at,
                "updated_at": observed_at,
            },
        )

    def get(self, workflow_run_id: str) -> ContinuationRecord | None:
        if not _valid_uuid4(workflow_run_id):
            raise ContinuationPersistenceError("workflow reference is invalid")
        job = self._get_job(workflow_run_id)
        return self._record(job) if job is not None else None

    def _finalize_exhausted_job(
        self,
        job: ContinuationJob,
        observed_at: datetime,
    ) -> bool:
        statement = update(ContinuationJob).where(
            ContinuationJob.workflow_run_id == job.workflow_run_id,
            ContinuationJob.state == ContinuationState.RUNNING,
            ContinuationJob.execution_token == job.execution_token,
            ContinuationJob.processing_attempts == job.processing_attempts,
            ContinuationJob.lease_expires_at == job.lease_expires_at,
        )
        try:
            result = self._session.execute(
                statement.values(
                    state=ContinuationState.FAILED,
                    execution_token=None,
                    lease_expires_at=None,
                    next_retry_at=None,
                    next_task_reference=None,
                    failure_category=ContinuationFailureCategory.PERSISTENCE_UNAVAILABLE,
                    completed_at=observed_at,
                    updated_at=observed_at,
                )
            )
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise ContinuationPersistenceError(
                "continuation exhaustion could not be finalized"
            ) from None
        return result.rowcount == 1

    def _fenced_update(
        self,
        claim: ContinuationClaim,
        values: dict[str, object],
        *,
        require_progress: bool = False,
    ) -> bool:
        statement = update(ContinuationJob).where(
            ContinuationJob.workflow_run_id == claim.workflow_run_id,
            ContinuationJob.state == ContinuationState.RUNNING,
            ContinuationJob.execution_token == claim.execution_token,
            ContinuationJob.processing_attempts == claim.processing_attempts,
        )
        if require_progress:
            statement = statement.where(ContinuationJob.progress_recorded.is_(True))
        try:
            result = self._session.execute(statement.values(**values))
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise ContinuationPersistenceError("continuation job could not be updated") from None
        return result.rowcount == 1

    def _get_job(self, workflow_run_id: str) -> ContinuationJob | None:
        try:
            return self._session.get(ContinuationJob, workflow_run_id)
        except (LookupError, SQLAlchemyError):
            self._session.rollback()
            raise ContinuationPersistenceError("continuation job could not be read") from None

    def _get_workflow(self, workflow_run_id: str) -> WorkflowRun | None:
        try:
            return self._session.get(WorkflowRun, workflow_run_id)
        except (LookupError, SQLAlchemyError):
            self._session.rollback()
            raise ContinuationPersistenceError("released workflow could not be read") from None

    @staticmethod
    def _validate_exact_replay(
        job: ContinuationJob,
        notice: TerminalFeedbackNotice,
    ) -> None:
        stored = (
            job.pseudonymous_actor_reference,
            job.course_reference,
            job.completed_task_reference,
            job.correlation_id,
        )
        replay = (
            notice.pseudonymous_actor_reference,
            notice.course_reference,
            notice.completed_task_reference,
            notice.correlation_id,
        )
        if stored != replay:
            raise ContinuationConflictError("continuation workflow ID was reused")

    @staticmethod
    def _record(job: ContinuationJob) -> ContinuationRecord:
        return ContinuationRecord(
            workflow_run_id=job.workflow_run_id,
            pseudonymous_actor_reference=job.pseudonymous_actor_reference,
            course_reference=job.course_reference,
            completed_task_reference=job.completed_task_reference,
            correlation_id=job.correlation_id,
            state=job.state,
            progress_recorded=job.progress_recorded,
            processing_attempts=job.processing_attempts,
            next_task_reference=job.next_task_reference,
            failure_category=job.failure_category,
            retryable=job.state is ContinuationState.RETRY_SCHEDULED,
            next_retry_at=(_utc(job.next_retry_at) if job.next_retry_at is not None else None),
        )

    @staticmethod
    def _match_nullable(statement: object, column: object, value: object) -> object:
        if value is None:
            return statement.where(column.is_(None))
        return statement.where(column == value)
