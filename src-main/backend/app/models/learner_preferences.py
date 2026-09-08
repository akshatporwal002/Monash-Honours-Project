"""Append-only, learner-owned choices for non-essential support."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.platform_enums import ExplanationDetail, PreferenceFormat, PreferencePace


def _now() -> datetime:
    return datetime.now(UTC)


class LearnerPreferenceRevision(Base):
    __tablename__ = "learner_preference_revisions"
    __table_args__ = (
        UniqueConstraint("learner_id", "revision", name="uq_preference_learner_revision"),
        UniqueConstraint("learner_id", "idempotency_key", name="uq_preference_learner_idempotency"),
        Index("ix_preference_current", "learner_id", "revision"),
        Index("ix_preference_history", "learner_id", "occurred_at", "id"),
        Index("ix_preference_correlation", "correlation_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    prior_revision_id: Mapped[str | None] = mapped_column(String(36))
    pace: Mapped[PreferencePace] = mapped_column(String(20), nullable=False)
    format: Mapped[PreferenceFormat] = mapped_column(String(30), nullable=False)
    explanation_detail: Mapped[ExplanationDetail] = mapped_column(String(20), nullable=False)
    optional_breaks_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    repeat_practice_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    personalisation_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
