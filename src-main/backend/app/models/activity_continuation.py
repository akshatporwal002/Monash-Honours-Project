"""Protected receipts and choices for approved activity continuation."""

from datetime import datetime

from sqlalchemy import (
    DDL,
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.lms import new_uuid, utc_now


class ActivityProgress(Base):
    __tablename__ = "activity_progress_receipts"
    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"), primary_key=True
    )
    learner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    outcome_id: Mapped[str | None] = mapped_column(
        ForeignKey("learning_outcomes.id", ondelete="RESTRICT")
    )
    snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("learner_model_snapshots.id", ondelete="RESTRICT")
    )
    state: Mapped[str] = mapped_column(String(50))
    evidence_ids: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ActivitySuggestion(Base):
    __tablename__ = "activity_suggestions"
    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("activity_progress_receipts.workflow_id", ondelete="RESTRICT"), primary_key=True
    )
    pathway_id: Mapped[str | None] = mapped_column(
        ForeignKey("curriculum_pathway_versions.id", ondelete="RESTRICT")
    )
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("learning_tasks.id", ondelete="RESTRICT")
    )
    decision: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ActivityChoice(Base):
    __tablename__ = "activity_choices"
    __table_args__ = (
        UniqueConstraint("workflow_id", "version", name="uq_activity_choice_version"),
        UniqueConstraint(
            "workflow_id", "actor_id", "request_key", name="uq_activity_choice_request"
        ),
        CheckConstraint("version > 0", name="activity_choice_positive_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("activity_suggestions.workflow_id", ondelete="RESTRICT")
    )
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


def _immutable(*_):
    raise ValueError("Activity continuation history is protected")


for model in (ActivityProgress, ActivitySuggestion, ActivityChoice):
    event.listen(model, "before_update", _immutable)
    event.listen(model, "before_delete", _immutable)
    table = model.__tablename__
    condition = "workflow_id=NEW.workflow_id"
    if model is ActivityChoice:
        condition = "id=NEW.id OR (workflow_id=NEW.workflow_id AND (version=NEW.version OR (actor_id=NEW.actor_id AND request_key=NEW.request_key)))"
    for action in ("UPDATE", "DELETE", "INSERT"):
        when = (
            f"WHEN EXISTS (SELECT 1 FROM {table} WHERE {condition}) " if action == "INSERT" else ""
        )
        event.listen(
            model.__table__,
            "after_create",
            DDL(
                f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} BEFORE {action} ON {table} "
                f"{when}BEGIN SELECT RAISE(ABORT, 'Activity continuation history is protected'); END"
            ).execute_if(dialect="sqlite"),
        )
