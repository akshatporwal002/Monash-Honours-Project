"""Durable, lease-fenced orchestration for assessment evaluation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.domain.assessment import AssessmentAttemptState
from app.models.assessment import (
    AssessmentAttempt,
    AssessmentEvaluationFailureCategory,
    AssessmentEvaluationJob,
    AssessmentEvaluationJobState,
)
from app.services.assessment.evaluation import (
    AssessmentEvaluationConflictError,
    AssessmentEvaluationFaultError,
    AssessmentEvaluationService,
)

_MAXIMUM_ATTEMPTS = 3


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _valid_uuid4(value: str) -> bool:
    try:
        parsed = UUID(value)
    except (TypeError, ValueError):
        return False
    return parsed.version == 4 and str(parsed) == value.lower()


class AssessmentEvaluationJobError(RuntimeError):
    """A sanitized assessment-evaluation persistence failure."""


@dataclass(frozen=True, slots=True)
class AssessmentEvaluationJobClaim:
    assessment_attempt_id: str
    response_version_id: str
    evaluation_idempotency_key: str
    correlation_id: str
    execution_token: str
    processing_attempts: int
    lease_expires_at: datetime


class SqlAlchemyAssessmentEvaluationJobRepository:
    """Store and claim assessment work with compare-and-swap fencing."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_pending(self, attempt: AssessmentAttempt) -> AssessmentEvaluationJob:
        if attempt.state is not AssessmentAttemptState.PENDING:
            raise AssessmentEvaluationJobError("only pending assessment work can be queued")
        existing = self._session.get(AssessmentEvaluationJob, attempt.id)
        if existing is not None:
            self._validate_exact(existing, attempt)
            return existing
        job = AssessmentEvaluationJob(
            assessment_attempt_id=attempt.id,
            response_version_id=attempt.response_version_id,
            evaluation_idempotency_key=f"assessment-evaluation:{attempt.id}",
            correlation_id=attempt.id,
            state=AssessmentEvaluationJobState.PENDING,
        )
        self._session.add(job)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            winner = self._session.get(AssessmentEvaluationJob, attempt.id)
            if winner is None:
                raise AssessmentEvaluationJobError("evaluation job could not be stored") from None
            self._validate_exact(winner, attempt)
            return winner
        except SQLAlchemyError:
            self._session.rollback()
            raise AssessmentEvaluationJobError("evaluation job could not be stored") from None
        return job

    def claim_for_response(
        self,
        response_version_id: str,
        *,
        now: datetime,
        lease_expires_at: datetime,
        execution_token: str,
        maximum_attempts: int = _MAXIMUM_ATTEMPTS,
    ) -> AssessmentEvaluationJobClaim | None:
        return self._claim(
            AssessmentEvaluationJob.response_version_id == response_version_id,
            now=now,
            lease_expires_at=lease_expires_at,
            execution_token=execution_token,
            maximum_attempts=maximum_attempts,
        )

    def claim_next(
        self,
        *,
        now: datetime,
        lease_expires_at: datetime,
        execution_token: str,
        maximum_attempts: int = _MAXIMUM_ATTEMPTS,
    ) -> AssessmentEvaluationJobClaim | None:
        return self._claim(
            None,
            now=now,
            lease_expires_at=lease_expires_at,
            execution_token=execution_token,
            maximum_attempts=maximum_attempts,
        )

    def complete(
        self,
        claim: AssessmentEvaluationJobClaim,
        *,
        completed_at: datetime,
    ) -> bool:
        return self._finish(
            claim,
            state=AssessmentEvaluationJobState.COMPLETED,
            category=None,
            completed_at=completed_at,
        )

    def finalize_next_exhausted(
        self,
        *,
        observed_at: datetime,
        maximum_attempts: int = _MAXIMUM_ATTEMPTS,
    ) -> str | None:
        observed = _utc(observed_at)
        if not 1 <= maximum_attempts <= _MAXIMUM_ATTEMPTS:
            raise AssessmentEvaluationJobError("evaluation exhaustion request is invalid")
        try:
            candidate = self._session.scalar(
                select(AssessmentEvaluationJob)
                .where(
                    AssessmentEvaluationJob.state == AssessmentEvaluationJobState.RUNNING,
                    AssessmentEvaluationJob.processing_attempts >= maximum_attempts,
                    AssessmentEvaluationJob.lease_expires_at <= observed,
                )
                .order_by(
                    AssessmentEvaluationJob.created_at,
                    AssessmentEvaluationJob.assessment_attempt_id,
                )
                .limit(1)
            )
        except SQLAlchemyError:
            self._session.rollback()
            raise AssessmentEvaluationJobError(
                "evaluation exhaustion could not be finalized"
            ) from None
        if candidate is None:
            return None
        try:
            result = self._session.execute(
                update(AssessmentEvaluationJob)
                .where(
                    AssessmentEvaluationJob.assessment_attempt_id
                    == candidate.assessment_attempt_id,
                    AssessmentEvaluationJob.state == AssessmentEvaluationJobState.RUNNING,
                    AssessmentEvaluationJob.execution_token == candidate.execution_token,
                    AssessmentEvaluationJob.processing_attempts == candidate.processing_attempts,
                    AssessmentEvaluationJob.lease_expires_at == candidate.lease_expires_at,
                )
                .values(
                    state=AssessmentEvaluationJobState.REVIEW_REQUIRED,
                    execution_token=None,
                    lease_expires_at=None,
                    next_retry_at=None,
                    failure_category=AssessmentEvaluationFailureCategory.PERSISTENCE_UNAVAILABLE,
                    completed_at=observed,
                    updated_at=observed,
                )
            )
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise AssessmentEvaluationJobError(
                "evaluation exhaustion could not be finalized"
            ) from None
        return candidate.assessment_attempt_id if result.rowcount == 1 else None

    def fail(
        self,
        claim: AssessmentEvaluationJobClaim,
        category: AssessmentEvaluationFailureCategory,
        *,
        failed_at: datetime,
        retryable: bool,
        retry_backoff: timedelta = timedelta(seconds=5),
    ) -> bool:
        if retry_backoff < timedelta(0):
            raise AssessmentEvaluationJobError("evaluation retry schedule is invalid")
        if retryable and claim.processing_attempts < _MAXIMUM_ATTEMPTS:
            observed = _utc(failed_at)
            return self._fenced_update(
                claim,
                {
                    "state": AssessmentEvaluationJobState.RETRY_SCHEDULED,
                    "execution_token": None,
                    "lease_expires_at": None,
                    "next_retry_at": observed + retry_backoff,
                    "failure_category": category,
                    "completed_at": None,
                    "updated_at": observed,
                },
            )
        return self._finish(
            claim,
            state=AssessmentEvaluationJobState.REVIEW_REQUIRED,
            category=category,
            completed_at=failed_at,
        )

    def get(self, assessment_attempt_id: str) -> AssessmentEvaluationJob | None:
        try:
            return self._session.get(AssessmentEvaluationJob, assessment_attempt_id)
        except SQLAlchemyError:
            self._session.rollback()
            raise AssessmentEvaluationJobError("evaluation job could not be read") from None

    def _claim(
        self,
        response_filter: object | None,
        *,
        now: datetime,
        lease_expires_at: datetime,
        execution_token: str,
        maximum_attempts: int,
    ) -> AssessmentEvaluationJobClaim | None:
        observed = _utc(now)
        lease = _utc(lease_expires_at)
        if (
            not _valid_uuid4(execution_token)
            or not 1 <= maximum_attempts <= _MAXIMUM_ATTEMPTS
            or lease <= observed
        ):
            raise AssessmentEvaluationJobError("evaluation claim request is invalid")
        due = or_(
            AssessmentEvaluationJob.state == AssessmentEvaluationJobState.PENDING,
            and_(
                AssessmentEvaluationJob.state == AssessmentEvaluationJobState.RETRY_SCHEDULED,
                AssessmentEvaluationJob.next_retry_at <= observed,
            ),
            and_(
                AssessmentEvaluationJob.state == AssessmentEvaluationJobState.RUNNING,
                AssessmentEvaluationJob.lease_expires_at <= observed,
            ),
        )
        statement = select(AssessmentEvaluationJob).where(
            AssessmentEvaluationJob.processing_attempts < maximum_attempts,
            due,
        )
        if response_filter is not None:
            statement = statement.where(response_filter)
        try:
            candidate = self._session.scalar(
                statement.order_by(
                    AssessmentEvaluationJob.created_at,
                    AssessmentEvaluationJob.assessment_attempt_id,
                ).limit(1)
            )
        except SQLAlchemyError:
            self._session.rollback()
            raise AssessmentEvaluationJobError("evaluation job could not be claimed") from None
        if candidate is None:
            return None

        previous = (
            candidate.state,
            candidate.processing_attempts,
            candidate.execution_token,
            candidate.lease_expires_at,
            candidate.next_retry_at,
        )
        claim_statement = update(AssessmentEvaluationJob).where(
            AssessmentEvaluationJob.assessment_attempt_id == candidate.assessment_attempt_id,
            AssessmentEvaluationJob.state == previous[0],
            AssessmentEvaluationJob.processing_attempts == previous[1],
        )
        claim_statement = self._match_nullable(
            claim_statement, AssessmentEvaluationJob.execution_token, previous[2]
        )
        claim_statement = self._match_nullable(
            claim_statement, AssessmentEvaluationJob.lease_expires_at, previous[3]
        )
        claim_statement = self._match_nullable(
            claim_statement, AssessmentEvaluationJob.next_retry_at, previous[4]
        )
        try:
            result = self._session.execute(
                claim_statement.values(
                    state=AssessmentEvaluationJobState.RUNNING,
                    processing_attempts=previous[1] + 1,
                    execution_token=execution_token,
                    lease_expires_at=lease,
                    next_retry_at=None,
                    failure_category=None,
                    completed_at=None,
                    updated_at=observed,
                )
            )
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise AssessmentEvaluationJobError("evaluation job could not be claimed") from None
        if result.rowcount != 1:
            return None
        return AssessmentEvaluationJobClaim(
            assessment_attempt_id=candidate.assessment_attempt_id,
            response_version_id=candidate.response_version_id,
            evaluation_idempotency_key=candidate.evaluation_idempotency_key,
            correlation_id=candidate.correlation_id,
            execution_token=execution_token,
            processing_attempts=previous[1] + 1,
            lease_expires_at=lease,
        )

    def _finish(
        self,
        claim: AssessmentEvaluationJobClaim,
        *,
        state: AssessmentEvaluationJobState,
        category: AssessmentEvaluationFailureCategory | None,
        completed_at: datetime,
    ) -> bool:
        observed = _utc(completed_at)
        return self._fenced_update(
            claim,
            {
                "state": state,
                "execution_token": None,
                "lease_expires_at": None,
                "next_retry_at": None,
                "failure_category": category,
                "completed_at": observed,
                "updated_at": observed,
            },
        )

    def _fenced_update(
        self,
        claim: AssessmentEvaluationJobClaim,
        values: dict[str, object],
    ) -> bool:
        try:
            result = self._session.execute(
                update(AssessmentEvaluationJob)
                .where(
                    AssessmentEvaluationJob.assessment_attempt_id == claim.assessment_attempt_id,
                    AssessmentEvaluationJob.state == AssessmentEvaluationJobState.RUNNING,
                    AssessmentEvaluationJob.execution_token == claim.execution_token,
                    AssessmentEvaluationJob.processing_attempts == claim.processing_attempts,
                )
                .values(**values)
            )
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise AssessmentEvaluationJobError("evaluation job could not be updated") from None
        return result.rowcount == 1

    @staticmethod
    def _match_nullable(statement, column, value):
        return (
            statement.where(column.is_(None)) if value is None else statement.where(column == value)
        )

    @staticmethod
    def _validate_exact(job: AssessmentEvaluationJob, attempt: AssessmentAttempt) -> None:
        if (
            job.response_version_id != attempt.response_version_id
            or job.evaluation_idempotency_key != f"assessment-evaluation:{attempt.id}"
        ):
            raise AssessmentEvaluationJobError("evaluation job conflicts with frozen attempt")


class AssessmentEvaluationApplication:
    def __init__(
        self,
        repository: SqlAlchemyAssessmentEvaluationJobRepository,
        *,
        now: Callable[[], datetime] = _utc_now,
        uuid_factory: Callable[[], str] = lambda: str(uuid4()),
        lease_duration: timedelta = timedelta(minutes=5),
    ) -> None:
        self._repository = repository
        self._now = now
        self._uuid_factory = uuid_factory
        self._lease_duration = lease_duration

    def start(self, response_version_id: str) -> AssessmentEvaluationJobClaim | None:
        observed = self._now()
        return self._repository.claim_for_response(
            response_version_id,
            now=observed,
            lease_expires_at=observed + self._lease_duration,
            execution_token=self._uuid_factory(),
        )


AssessmentEvaluationServiceFactory = Callable[[Session, str], AssessmentEvaluationService]


class AssessmentEvaluationExecutor:
    def __init__(
        self,
        session_factory: sessionmaker[Session] | Callable[[], Session],
        service_factory: AssessmentEvaluationServiceFactory,
        *,
        now: Callable[[], datetime] = _utc_now,
        retry_backoff: timedelta = timedelta(seconds=5),
    ) -> None:
        self._session_factory = session_factory
        self._service_factory = service_factory
        self._now = now
        self._retry_backoff = retry_backoff

    async def execute(self, claim: AssessmentEvaluationJobClaim) -> None:
        try:
            with self._session_factory() as session:
                self._service_factory(session, claim.correlation_id).evaluate(
                    assessment_attempt_id=claim.assessment_attempt_id,
                    evaluation_idempotency_key=claim.evaluation_idempotency_key,
                )
        except AssessmentEvaluationConflictError:
            self._fail(claim, AssessmentEvaluationFailureCategory.VERSION_CONFLICT, False)
            return
        except AssessmentEvaluationFaultError as error:
            category = AssessmentEvaluationFailureCategory(error.failure_category)
            self._fail(claim, category, error.retryable)
            return
        except Exception:
            self._fail(claim, AssessmentEvaluationFailureCategory.PERSISTENCE_UNAVAILABLE, True)
            return
        try:
            with self._session_factory() as session:
                SqlAlchemyAssessmentEvaluationJobRepository(session).complete(
                    claim,
                    completed_at=self._now(),
                )
        except AssessmentEvaluationJobError:
            return

    def _fail(
        self,
        claim: AssessmentEvaluationJobClaim,
        category: AssessmentEvaluationFailureCategory,
        retryable: bool,
    ) -> None:
        try:
            with self._session_factory() as session:
                SqlAlchemyAssessmentEvaluationJobRepository(session).fail(
                    claim,
                    category,
                    failed_at=self._now(),
                    retryable=retryable,
                    retry_backoff=self._retry_backoff,
                )
        except AssessmentEvaluationJobError:
            return


class AssessmentEvaluationRecoveryWorker:
    def __init__(
        self,
        session_factory: sessionmaker[Session] | Callable[[], Session],
        executor: AssessmentEvaluationExecutor,
        *,
        now: Callable[[], datetime] = _utc_now,
        lease_duration: timedelta = timedelta(minutes=5),
        maximum_attempts: int = _MAXIMUM_ATTEMPTS,
        uuid_factory: Callable[[], str] = lambda: str(uuid4()),
    ) -> None:
        self._session_factory = session_factory
        self._executor = executor
        self._now = now
        self._lease_duration = lease_duration
        self._maximum_attempts = maximum_attempts
        self._uuid_factory = uuid_factory

    async def run_once(self) -> bool:
        observed = self._now()
        with self._session_factory() as session:
            repository = SqlAlchemyAssessmentEvaluationJobRepository(session)
            exhausted = repository.finalize_next_exhausted(
                observed_at=observed,
                maximum_attempts=self._maximum_attempts,
            )
            if exhausted is not None:
                return True
            claim = repository.claim_next(
                now=observed,
                lease_expires_at=observed + self._lease_duration,
                execution_token=self._uuid_factory(),
                maximum_attempts=self._maximum_attempts,
            )
        if claim is None:
            return False
        await self._executor.execute(claim)
        return True


__all__ = [
    "AssessmentEvaluationApplication",
    "AssessmentEvaluationExecutor",
    "AssessmentEvaluationJobClaim",
    "AssessmentEvaluationJobError",
    "AssessmentEvaluationRecoveryWorker",
    "AssessmentEvaluationServiceFactory",
    "SqlAlchemyAssessmentEvaluationJobRepository",
]
