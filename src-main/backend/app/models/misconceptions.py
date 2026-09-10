"""Immutable, scoped misconception hypotheses, observations and educator reviews."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.append_only import protect_history
from app.models.assessment import new_uuid, utc_now


class MisconceptionHypothesis(Base):
    __tablename__ = "misconception_hypotheses"
    __table_args__ = (
        UniqueConstraint("actor_id", "request_key", name="uq_misconception_hypothesis_request"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    outcome_id: Mapped[str] = mapped_column(ForeignKey("learning_outcomes.id", ondelete="RESTRICT"))
    task_id: Mapped[str] = mapped_column(ForeignKey("learning_tasks.id", ondelete="RESTRICT"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    feedback_id: Mapped[str] = mapped_column(ForeignKey("feedback_records.id", ondelete="RESTRICT"))
    task_revision_id: Mapped[str] = mapped_column(
        ForeignKey("task_revisions.id", ondelete="RESTRICT")
    )
    request_key: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON)
    source_approvals: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MisconceptionResponse(Base):
    __tablename__ = "misconception_responses"
    __table_args__ = (
        UniqueConstraint("hypothesis_id", "version", name="uq_misconception_response_version"),
        UniqueConstraint("hypothesis_id", "request_key", name="uq_misconception_response_request"),
        UniqueConstraint("hypothesis_id", "stage", name="uq_misconception_response_stage"),
        CheckConstraint("version BETWEEN 1 AND 3", name="misconception_response_version"),
        CheckConstraint(
            "stage IN ('PROBE', 'REVISION', 'TRANSFER')", name="misconception_response_stage"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    hypothesis_id: Mapped[str] = mapped_column(
        ForeignKey("misconception_hypotheses.id", ondelete="RESTRICT")
    )
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(16))
    request_key: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON)
    evidence_id: Mapped[str] = mapped_column(
        ForeignKey("learning_evidence.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MisconceptionReviewRecord(Base):
    __tablename__ = "misconception_reviews"
    __table_args__ = (
        UniqueConstraint("hypothesis_id", "version", name="uq_misconception_review_version"),
        UniqueConstraint("hypothesis_id", "request_key", name="uq_misconception_review_request"),
        CheckConstraint("version > 3", name="misconception_review_version"),
        CheckConstraint(
            "state IN ('UNCERTAIN', 'PERSISTED', 'WEAKENED', 'CORRECTED')",
            name="misconception_review_state",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    hypothesis_id: Mapped[str] = mapped_column(
        ForeignKey("misconception_hypotheses.id", ondelete="RESTRICT")
    )
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16))
    request_key: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON)
    evidence_id: Mapped[str] = mapped_column(
        ForeignKey("learning_evidence.id", ondelete="RESTRICT")
    )
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("learner_model_snapshots.id", ondelete="RESTRICT")
    )
    escalation_id: Mapped[str | None] = mapped_column(
        ForeignKey("escalation_cases.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MisconceptionClosure(Base):
    __tablename__ = "misconception_closures"
    __table_args__ = (
        UniqueConstraint("hypothesis_id", name="uq_misconception_closure"),
        CheckConstraint(
            "disposition IN ('DEFERRED', 'INVALIDATED')", name="misconception_closure_disposition"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    hypothesis_id: Mapped[str] = mapped_column(
        ForeignKey("misconception_hypotheses.id", ondelete="RESTRICT")
    )
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    disposition: Mapped[str] = mapped_column(String(16))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


protect_history(MisconceptionClosure, unique_keys=(("hypothesis_id",),))
protect_history(MisconceptionHypothesis, unique_keys=(("actor_id", "request_key"),))
protect_history(
    MisconceptionResponse,
    unique_keys=(
        ("hypothesis_id", "version"),
        ("hypothesis_id", "request_key"),
        ("hypothesis_id", "stage"),
    ),
)
protect_history(
    MisconceptionReviewRecord,
    unique_keys=(("hypothesis_id", "version"), ("hypothesis_id", "request_key")),
)
