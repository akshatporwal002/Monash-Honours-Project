"""Learner notification choices and approved individual deadline history."""

from datetime import datetime

from sqlalchemy import (
    DDL,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.append_only import protect_history
from app.models.assessment import new_uuid, utc_now
from app.models.lms import Reminder


class ReminderPreference(Base):
    __tablename__ = "reminder_preferences"
    __table_args__ = (
        UniqueConstraint("student_id", "revision", name="uq_reminder_preference_revision"),
        UniqueConstraint("student_id", "request_key", name="uq_reminder_preference_request"),
        CheckConstraint("revision > 0", name="reminder_preference_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    revision: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean)
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DeadlineArrangement(Base):
    __tablename__ = "deadline_arrangements"
    __table_args__ = (
        UniqueConstraint(
            "student_id", "task_id", "revision", name="uq_deadline_arrangement_revision"
        ),
        UniqueConstraint(
            "student_id", "task_id", "request_key", name="uq_deadline_arrangement_request"
        ),
        CheckConstraint("revision > 0", name="deadline_arrangement_revision"),
        CheckConstraint("kind IN ('EXTENSION', 'ACCESS_PLAN')", name="deadline_arrangement_kind"),
        CheckConstraint(
            "length(trim(reason)) > 0 AND length(trim(learner_notice)) > 0",
            name="deadline_arrangement_reason",
        ),
        CheckConstraint(
            "(active = 1 AND (due_at IS NOT NULL OR reminders_paused = 1)) OR (active = 0 AND due_at IS NULL AND reminders_paused = 0)",
            name="deadline_arrangement_shape",
        ),
        CheckConstraint(
            "kind = 'ACCESS_PLAN' OR reminders_paused = 0", name="deadline_arrangement_pause"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    task_id: Mapped[str] = mapped_column(ForeignKey("learning_tasks.id", ondelete="RESTRICT"))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    revision: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(Boolean)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminders_paused: Mapped[bool] = mapped_column(Boolean)
    time_zone: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)
    learner_notice: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


protect_history(
    ReminderPreference, unique_keys=(("student_id", "revision"), ("student_id", "request_key"))
)
protect_history(
    DeadlineArrangement,
    unique_keys=(("student_id", "task_id", "revision"), ("student_id", "task_id", "request_key")),
)

DEADLINE_SCOPE = """CREATE TRIGGER IF NOT EXISTS deadline_arrangements_scope
BEFORE INSERT ON deadline_arrangements WHEN NOT EXISTS (
 SELECT 1 FROM learning_tasks t JOIN courses c ON c.id=t.course_id
 JOIN enrollments e ON e.course_id=c.id AND e.student_id=NEW.student_id
 WHERE t.id=NEW.task_id AND c.educator_id=NEW.actor_id
) BEGIN SELECT RAISE(ABORT, 'Deadline arrangement scope mismatch'); END"""
event.listen(
    DeadlineArrangement.__table__, "after_create", DDL(DEADLINE_SCOPE).execute_if(dialect="sqlite")
)

REMINDER_GUARDS = (
    """CREATE TRIGGER IF NOT EXISTS reminders_rolling_limit BEFORE INSERT ON reminders
WHEN EXISTS (SELECT 1 FROM reminders r WHERE r.student_id=NEW.student_id
AND r.task_id=NEW.task_id AND julianday(r.created_at) > julianday(NEW.created_at) - 1)
BEGIN SELECT RAISE(ABORT, 'A task reminder was already sent within 24 hours'); END""",
    """CREATE TRIGGER IF NOT EXISTS reminders_identity_immutable BEFORE UPDATE ON reminders
WHEN NEW.id != OLD.id OR NEW.student_id != OLD.student_id OR NEW.task_id != OLD.task_id
OR NEW.created_at != OLD.created_at OR NEW.dedupe_window != OLD.dedupe_window
BEGIN SELECT RAISE(ABORT, 'Reminder delivery identity is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS reminders_no_replace BEFORE INSERT ON reminders
WHEN EXISTS (SELECT 1 FROM reminders r WHERE r.id=NEW.id OR
(r.student_id=NEW.student_id AND r.task_id=NEW.task_id AND r.dedupe_window=NEW.dedupe_window))
BEGIN SELECT RAISE(ABORT, 'Reminder delivery identity is immutable'); END""",
)
for statement in REMINDER_GUARDS:
    event.listen(Reminder.__table__, "after_create", DDL(statement).execute_if(dialect="sqlite"))
