from __future__ import annotations

from datetime import timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.persistence import LearningEvent
from app.schemas.learning_events import LearningEventReceipt
from app.services.learning_events.contracts import (
    LearningEventRecordResult,
    LearningEventWrite,
)
from app.services.learning_events.errors import (
    LearningEventConflictError,
    LearningEventPersistenceError,
)


class SqlAlchemyLearningEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, write: LearningEventWrite) -> LearningEventRecordResult:
        try:
            existing = self._by_deduplication_key(write.deduplication_key)
            if existing is not None:
                return self._replay(existing, write)

            event = LearningEvent(
                id=write.id,
                pseudonymous_user_id=write.pseudonymous_user_id,
                course_id=write.course_id,
                task_id=write.task_id,
                event_type=write.event_type,
                occurred_at=write.occurred_at,
                correlation_id=write.correlation_id,
                workflow_reference=write.workflow_reference,
                metadata_payload=write.metadata,
                deduplication_key=write.deduplication_key,
            )
            self._session.add(event)
            try:
                self._session.commit()
            except IntegrityError:
                # A concurrent writer may have won the unique-key race. Re-read once
                # and return only if it wrote the exact same logical event.
                self._session.rollback()
                winner = self._by_deduplication_key(write.deduplication_key)
                if winner is None:
                    raise LearningEventPersistenceError(
                        "learning-event persistence failed"
                    ) from None
                return self._replay(winner, write)
            self._session.refresh(event)
            return LearningEventRecordResult(
                receipt=self._receipt(event),
                created=True,
            )
        except (LearningEventConflictError, LearningEventPersistenceError):
            raise
        except SQLAlchemyError:
            self._session.rollback()
            raise LearningEventPersistenceError("learning-event persistence failed") from None

    def _by_deduplication_key(self, key: str) -> LearningEvent | None:
        return self._session.scalar(
            select(LearningEvent).where(LearningEvent.deduplication_key == key)
        )

    def _replay(
        self,
        existing: LearningEvent,
        write: LearningEventWrite,
    ) -> LearningEventRecordResult:
        same_content = (
            existing.pseudonymous_user_id == write.pseudonymous_user_id
            and existing.course_id == write.course_id
            and existing.task_id == write.task_id
            and existing.event_type == write.event_type
            and existing.workflow_reference == write.workflow_reference
            and existing.metadata_payload == write.metadata
        )
        if not same_content:
            raise LearningEventConflictError(
                "the learning-event identifier was reused with different content"
            )
        return LearningEventRecordResult(
            receipt=self._receipt(existing),
            created=False,
        )

    @staticmethod
    def _receipt(event: LearningEvent) -> LearningEventReceipt:
        occurred_at = event.occurred_at
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        else:
            occurred_at = occurred_at.astimezone(timezone.utc)
        return LearningEventReceipt(
            learning_event_id=event.id,
            occurred_at=occurred_at,
        )
