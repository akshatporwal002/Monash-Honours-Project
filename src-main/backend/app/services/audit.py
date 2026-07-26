from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.models.audit import AuditEvent
from app.schemas.audit import AuditEventCommand, AuditEventReceipt


class AuditError(Exception):
    """Base error for controlled audit failures."""


class AuditConflictError(AuditError):
    """A deduplication key was reused with different audit content."""


class AuditPersistenceError(AuditError):
    """An audit event could not be durably stored."""


class AuditRecorder:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, command: AuditEventCommand) -> AuditEventReceipt:
        existing = self._find(command.deduplication_key)
        if existing is not None:
            return self._replay(existing, command)

        record = AuditEvent(
            actor_reference=command.actor_reference,
            action=command.action,
            outcome=command.outcome,
            occurred_at=command.occurred_at,
            correlation_id=command.correlation_id,
            resource_type=command.resource_type,
            resource_id=command.resource_id,
            failure_category=command.failure_category,
            deduplication_key=command.deduplication_key,
        )
        self._session.add(record)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            winner = self._find(command.deduplication_key)
            if winner is None:
                raise AuditPersistenceError("audit event could not be stored") from None
            return self._replay(winner, command)
        except SQLAlchemyError:
            self._session.rollback()
            raise AuditPersistenceError("audit event could not be stored") from None
        return self._receipt(record, created=True)

    def _find(self, deduplication_key: str) -> AuditEvent | None:
        try:
            return self._session.scalar(
                select(AuditEvent).where(AuditEvent.deduplication_key == deduplication_key)
            )
        except SQLAlchemyError:
            self._session.rollback()
            raise AuditPersistenceError("audit event could not be read") from None

    @staticmethod
    def _replay(
        record: AuditEvent,
        command: AuditEventCommand,
    ) -> AuditEventReceipt:
        comparable = (
            record.actor_reference,
            record.action,
            record.outcome,
            record.correlation_id,
            record.resource_type,
            record.resource_id,
            record.failure_category,
        )
        requested = (
            command.actor_reference,
            command.action,
            command.outcome,
            command.correlation_id,
            command.resource_type,
            command.resource_id,
            command.failure_category,
        )
        if comparable != requested:
            raise AuditConflictError("audit deduplication key was reused")
        return AuditRecorder._receipt(record, created=False)

    @staticmethod
    def _receipt(record: AuditEvent, *, created: bool) -> AuditEventReceipt:
        return AuditEventReceipt(
            id=record.id,
            actor_reference=record.actor_reference,
            action=record.action,
            outcome=record.outcome,
            occurred_at=record.occurred_at,
            correlation_id=record.correlation_id,
            resource_type=record.resource_type,
            resource_id=record.resource_id,
            failure_category=record.failure_category,
            deduplication_key=record.deduplication_key,
            created=created,
        )


class IndependentAuditRecorder:
    """Store each audit event in a transaction independent of student work."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def record(self, command: AuditEventCommand) -> AuditEventReceipt:
        with self._session_factory() as session:
            return AuditRecorder(session).record(command)


class BestEffortAuditSink:
    def __init__(
        self,
        recorder_factory: Callable[[], AuditRecorder],
        on_failure: Callable[[str, str, str], None] | None = None,
    ) -> None:
        self._recorder_factory = recorder_factory
        self._on_failure = on_failure

    def record(self, command: AuditEventCommand) -> AuditEventReceipt | None:
        try:
            return self._recorder_factory().record(command)
        except Exception as error:
            if self._on_failure is not None:
                try:
                    self._on_failure(
                        command.correlation_id,
                        command.action.value,
                        type(error).__name__,
                    )
                except Exception:
                    # Student-path auditing is best effort even when its
                    # operational failure hook is unavailable.
                    pass
            return None
