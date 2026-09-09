"""Immutable learner dialogue and the exact reviewed context used for each reply."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DDL,
    JSON,
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
from app.models.assessment import new_uuid, utc_now


class TutorTurn(Base):
    __tablename__ = "tutor_turns"
    __table_args__ = (
        UniqueConstraint("student_id", "task_id", "revision", name="uq_tutor_revision"),
        UniqueConstraint("student_id", "task_id", "request_key", name="uq_tutor_request"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    task_id: Mapped[str] = mapped_column(ForeignKey("learning_tasks.id", ondelete="RESTRICT"))
    assessment_work_start_id: Mapped[str | None] = mapped_column(
        ForeignKey("assessment_work_starts.id", ondelete="RESTRICT")
    )
    revision: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(128))
    context_token: Mapped[str] = mapped_column(String(64))
    learner_text: Mapped[str] = mapped_column(Text)
    reply: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(24))
    hint_index: Mapped[int | None] = mapped_column(Integer)
    context: Mapped[dict[str, Any]] = mapped_column(JSON)
    quality: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


def tutor_guards() -> tuple[str, ...]:
    return tuple(
        f"CREATE TRIGGER IF NOT EXISTS tutor_turns_no_{operation.lower()} "
        f"BEFORE {operation} ON tutor_turns BEGIN SELECT RAISE(ABORT, 'Tutor history is immutable'); END"
        for operation in ("UPDATE", "DELETE")
    ) + (
        "CREATE TRIGGER IF NOT EXISTS tutor_turns_no_replace BEFORE INSERT ON tutor_turns "
        "WHEN EXISTS (SELECT 1 FROM tutor_turns WHERE id=NEW.id OR "
        "(student_id=NEW.student_id AND task_id=NEW.task_id AND "
        "(revision=NEW.revision OR request_key=NEW.request_key))) "
        "BEGIN SELECT RAISE(ABORT, 'Tutor history is immutable'); END",
        "CREATE TRIGGER IF NOT EXISTS tutor_turns_work_scope BEFORE INSERT ON tutor_turns "
        "WHEN NEW.assessment_work_start_id IS NOT NULL AND NOT EXISTS "
        "(SELECT 1 FROM assessment_work_starts WHERE id=NEW.assessment_work_start_id "
        "AND student_id=NEW.student_id AND task_id=NEW.task_id) "
        "BEGIN SELECT RAISE(ABORT, 'Tutor work scope differs'); END",
    )


def _immutable(*_: object) -> None:
    raise ValueError("Tutor history is immutable")


event.listen(TutorTurn, "before_update", _immutable)
event.listen(TutorTurn, "before_delete", _immutable)
for _statement in tutor_guards():
    event.listen(TutorTurn.__table__, "after_create", DDL(_statement).execute_if(dialect="sqlite"))
