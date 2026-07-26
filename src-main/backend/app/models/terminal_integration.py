from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    TerminalIntegrationFailureCategory,
    TerminalIntegrationState,
    TerminalIntegrationType,
)

if TYPE_CHECKING:
    from app.models.persistence import WorkflowRun


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid4())


def _enum_column(enum_type: type[Enum], name: str) -> SqlEnum:
    return SqlEnum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


class TerminalIntegrationOutbox(Base):
    """Privacy-minimal durable handoff created with a terminal workflow commit."""

    __tablename__ = "terminal_integration_outbox"
    __table_args__ = (
        UniqueConstraint(
            "workflow_run_id",
            "integration_type",
            name="uq_terminal_integration_outbox_workflow_type",
        ),
        CheckConstraint(
            "processing_attempts BETWEEN 0 AND 3",
            name="terminal_integration_processing_attempts",
        ),
        CheckConstraint(
            "(state = 'pending' AND processing_attempts = 0 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NULL AND failure_category IS NULL "
            "AND completed_at IS NULL) OR "
            "(state = 'running' AND processing_attempts BETWEEN 1 AND 3 "
            "AND execution_token IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND next_retry_at IS NULL AND failure_category IS NULL "
            "AND completed_at IS NULL) OR "
            "(state = 'retry_scheduled' AND processing_attempts BETWEEN 1 AND 2 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NOT NULL AND failure_category IS NOT NULL "
            "AND completed_at IS NULL) OR "
            "(state = 'completed' AND processing_attempts BETWEEN 1 AND 3 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NULL AND failure_category IS NULL "
            "AND completed_at IS NOT NULL) OR "
            "(state = 'failed' AND processing_attempts BETWEEN 1 AND 3 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NULL AND failure_category IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="terminal_integration_state_shape",
        ),
        Index(
            "ix_terminal_integration_outbox_claim",
            "state",
            "next_retry_at",
            "lease_expires_at",
            "created_at",
        ),
        Index(
            "ix_terminal_integration_outbox_correlation",
            "correlation_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workflow_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    integration_type: Mapped[TerminalIntegrationType] = mapped_column(
        _enum_column(TerminalIntegrationType, "terminal_integration_type"),
        nullable=False,
    )
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    state: Mapped[TerminalIntegrationState] = mapped_column(
        _enum_column(TerminalIntegrationState, "terminal_integration_state"),
        nullable=False,
        default=TerminalIntegrationState.PENDING,
    )
    processing_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    execution_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    failure_category: Mapped[TerminalIntegrationFailureCategory | None] = mapped_column(
        _enum_column(
            TerminalIntegrationFailureCategory,
            "terminal_integration_failure_category",
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
