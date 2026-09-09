"""Append-only global learner choices, never inferred model estimates."""

from datetime import datetime

from sqlalchemy import (
    DDL,
    Boolean,
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
from app.models.persistence import utc_now


class LearnerPreferenceRevision(Base):
    __tablename__ = "learner_preference_revisions"
    __table_args__ = (
        UniqueConstraint("learner_id", "version", name="uq_preference_version"),
        UniqueConstraint("learner_id", "request_key", name="uq_preference_request"),
        CheckConstraint("version > 0", name="preference_version_positive"),
        CheckConstraint("pace IN ('self_paced', 'stepwise')", name="preference_pace"),
        CheckConstraint("format IN ('text', 'stepwise')", name="preference_format"),
        CheckConstraint("explanation_detail IN ('brief', 'detailed')", name="preference_detail"),
        CheckConstraint("support_amount IN ('standard', 'on_request')", name="preference_support"),
        CheckConstraint("feedback_form IN ('inline', 'expandable')", name="preference_feedback"),
        CheckConstraint("action IN ('save', 'reset')", name="preference_action"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    learner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(10))
    pace: Mapped[str] = mapped_column(String(20))
    format: Mapped[str] = mapped_column(String(20))
    explanation_detail: Mapped[str] = mapped_column(String(20))
    breaks: Mapped[bool] = mapped_column(Boolean(create_constraint=True, name="preference_breaks"))
    repeat_practice: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="preference_repeat")
    )
    personalisation_enabled: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="preference_enabled")
    )
    support_amount: Mapped[str] = mapped_column(String(20))
    feedback_form: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


def history_triggers() -> list[str]:
    table = "learner_preference_revisions"
    statements = [
        f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} BEFORE {action} ON {table} "
        "BEGIN SELECT RAISE(ABORT, 'Preference history is protected'); END"
        for action in ("UPDATE", "DELETE")
    ]
    statements.append(
        f"CREATE TRIGGER IF NOT EXISTS {table}_append BEFORE INSERT ON {table} "
        f"WHEN NEW.version != COALESCE((SELECT MAX(version) FROM {table} "
        "WHERE learner_id=NEW.learner_id), 0) + 1 "
        f"OR EXISTS(SELECT 1 FROM {table} WHERE id=NEW.id OR "
        "(learner_id=NEW.learner_id AND request_key=NEW.request_key)) "
        "BEGIN SELECT RAISE(ABORT, 'Preference history is protected'); END"
    )
    return statements


def _immutable(*_):
    raise ValueError("Preference history is protected")


event.listen(LearnerPreferenceRevision, "before_update", _immutable)
event.listen(LearnerPreferenceRevision, "before_delete", _immutable)
for statement in history_triggers():
    event.listen(
        LearnerPreferenceRevision.__table__,
        "after_create",
        DDL(statement).execute_if(dialect="sqlite"),
    )
