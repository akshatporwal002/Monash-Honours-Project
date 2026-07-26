from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ContinuationFailureCategory, ContinuationState

if TYPE_CHECKING:
    from app.models.persistence import WorkflowRun


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


class ContinuationJob(Base):
    """Durable, privacy-minimal continuation work keyed by workflow ID."""

    __tablename__ = "continuation_jobs"
    __table_args__ = (
        CheckConstraint(
            "processing_attempts BETWEEN 0 AND 3",
            name="continuation_processing_attempts",
        ),
        CheckConstraint(
            "(state = 'pending' AND processing_attempts = 0 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NULL AND next_task_reference IS NULL "
            "AND failure_category IS NULL AND completed_at IS NULL) OR "
            "(state = 'running' AND processing_attempts BETWEEN 1 AND 3 "
            "AND execution_token IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND next_retry_at IS NULL AND next_task_reference IS NULL "
            "AND failure_category IS NULL AND completed_at IS NULL) OR "
            "(state = 'retry_scheduled' AND processing_attempts BETWEEN 1 AND 2 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NOT NULL AND next_task_reference IS NULL "
            "AND failure_category IS NOT NULL AND completed_at IS NULL) OR "
            "(state = 'completed' AND processing_attempts BETWEEN 1 AND 3 "
            "AND progress_recorded = 1 AND execution_token IS NULL "
            "AND lease_expires_at IS NULL AND next_retry_at IS NULL "
            "AND next_task_reference IS NOT NULL AND failure_category IS NULL "
            "AND completed_at IS NOT NULL) OR "
            "(state = 'failed' AND processing_attempts BETWEEN 1 AND 3 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NULL AND next_task_reference IS NULL "
            "AND failure_category IS NOT NULL AND completed_at IS NOT NULL)",
            name="continuation_state_shape",
        ),
        Index(
            "ix_continuation_jobs_claim",
            "state",
            "next_retry_at",
            "lease_expires_at",
            "created_at",
        ),
        Index(
            "ix_continuation_jobs_course_state",
            "course_reference",
            "state",
        ),
    )

    workflow_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    pseudonymous_actor_reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    course_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    completed_task_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    state: Mapped[ContinuationState] = mapped_column(
        _enum_column(ContinuationState, "continuation_state"),
        nullable=False,
        default=ContinuationState.PENDING,
    )
    progress_recorded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    processing_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    execution_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_task_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    failure_category: Mapped[ContinuationFailureCategory | None] = mapped_column(
        _enum_column(
            ContinuationFailureCategory,
            "continuation_failure_category",
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    workflow_run: Mapped[WorkflowRun] = relationship()
