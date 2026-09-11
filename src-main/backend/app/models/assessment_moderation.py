"""Durable policy, sampling, independent review and evaluator validation history."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.persistence import new_uuid, utc_now


class ModerationPolicy(Base):
    __tablename__ = "assessment_moderation_policies"
    __table_args__ = (
        UniqueConstraint("course_id", "version"),
        CheckConstraint(
            "initial_count >= 0 AND later_percent >= 0 AND later_percent <= 100 AND drift_interval > 0",
            name="sampling_bounds",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer)
    initial_count: Mapped[int] = mapped_column(Integer)
    later_percent: Mapped[int] = mapped_column(Integer)
    drift_interval: Mapped[int] = mapped_column(Integer)
    approval_reference: Mapped[str] = mapped_column(Text)
    training_reference: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ModerationSelection(Base):
    __tablename__ = "assessment_moderation_selections"
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_attempts.id", ondelete="RESTRICT"), primary_key=True
    )
    policy_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_moderation_policies.id", ondelete="RESTRICT")
    )
    task_family: Mapped[str] = mapped_column(String(100))
    sequence: Mapped[int] = mapped_column(Integer)
    selected: Mapped[bool] = mapped_column(Boolean)
    drift_check: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ModerationReview(Base):
    __tablename__ = "assessment_moderation_reviews"
    __table_args__ = (
        UniqueConstraint("attempt_id", "cycle", "stage"),
        UniqueConstraint("attempt_id", "request_key"),
        CheckConstraint("cycle > 0 AND length(request_digest) = 64", name="review_cycle_receipt"),
        CheckConstraint(
            "stage IN ('ORIGINAL', 'SECOND', 'RESOLUTION', 'DRIFT', 'DRIFT_RESOLUTION')",
            name="review_stage",
        ),
        CheckConstraint("result IN ('PASS', 'INCOMPLETE')", name="review_result"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_moderation_selections.attempt_id", ondelete="RESTRICT")
    )
    stage: Mapped[str] = mapped_column(String(20))
    cycle: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(128))
    request_digest: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    result: Mapped[str] = mapped_column(String(12))
    reason: Mapped[str] = mapped_column(Text)
    criteria: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EvaluatorValidationEvent(Base):
    __tablename__ = "evaluator_validation_events"
    __table_args__ = (
        UniqueConstraint("course_id", "revision"),
        CheckConstraint("state IN ('VALIDATED', 'INVALIDATED')", name="validation_state"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    revision: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20))
    fingerprint: Mapped[str] = mapped_column(String(64))
    dependencies: Mapped[dict[str, str]] = mapped_column(JSON)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


MODELS = (ModerationPolicy, ModerationSelection, ModerationReview, EvaluatorValidationEvent)


def history_guards():
    for model in MODELS:
        table = model.__table__
        identities = [list(table.primary_key.columns)] + [
            list(constraint.columns)
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        ]
        duplicate = " OR ".join(
            "(" + " AND ".join(f"{column.name} = NEW.{column.name}" for column in columns) + ")"
            for columns in identities
        )
        for operation in ("UPDATE", "DELETE", "INSERT"):
            condition = (
                f" WHEN EXISTS (SELECT 1 FROM {table.name} WHERE {duplicate})"
                if operation == "INSERT"
                else ""
            )
            name = f"{table.name}_no_{operation.lower()}"
            yield (
                table,
                f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {operation} ON {table.name}{condition} BEGIN SELECT RAISE(ABORT, 'Assessment governance history is append-only'); END",
            )


from sqlalchemy import DDL, event  # noqa: E402

for _table, _sql in history_guards():
    event.listen(_table, "after_create", DDL(_sql).execute_if(dialect="sqlite"))
