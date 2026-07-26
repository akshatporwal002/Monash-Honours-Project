from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    String,
    UniqueConstraint,
    event,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditAction(str, Enum):
    FEEDBACK_GENERATION_STARTED = "feedback_generation_started"
    FEEDBACK_GENERATION_COMPLETED = "feedback_generation_completed"
    FEEDBACK_JUDGED = "feedback_judged"
    FEEDBACK_REGENERATED = "feedback_regenerated"
    FEEDBACK_FALLBACK_USED = "feedback_fallback_used"
    FEEDBACK_VIEWED = "feedback_viewed"
    FEEDBACK_REPORTED = "feedback_reported"
    RESEARCH_EXPORT_CREATED = "research_export_created"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"


class AuditOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"


class AuditAppendOnlyError(RuntimeError):
    """Raised when application code attempts to mutate an audit event."""


def _new_uuid() -> str:
    return str(uuid4())


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _enum_column(enum_type: type[Enum], name: str) -> SqlEnum:
    return SqlEnum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("deduplication_key", name="uq_audit_events_deduplication_key"),
        CheckConstraint(
            "(outcome = 'failure' AND failure_category IS NOT NULL) OR "
            "(outcome = 'success' AND failure_category IS NULL)",
            name="audit_failure_shape",
        ),
        Index("ix_audit_events_correlation_time", "correlation_id", "occurred_at"),
        Index("ix_audit_events_action_time", "action", "occurred_at"),
        Index("ix_audit_events_actor_time", "actor_reference", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    actor_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[AuditAction] = mapped_column(
        _enum_column(AuditAction, "audit_action"),
        nullable=False,
    )
    outcome: Mapped[AuditOutcome] = mapped_column(
        _enum_column(AuditOutcome, "audit_outcome"),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    failure_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    deduplication_key: Mapped[str] = mapped_column(String(255), nullable=False)


@event.listens_for(AuditEvent, "before_update", propagate=True)
@event.listens_for(AuditEvent, "before_delete", propagate=True)
def _prevent_audit_mutation(*_: object) -> None:
    raise AuditAppendOnlyError("audit events are append-only")
