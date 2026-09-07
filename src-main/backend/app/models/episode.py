"""Immutable pre-submit prediction checkpoints and authorised transfer starts."""

from datetime import datetime
from typing import Any

from sqlalchemy import DDL, JSON, DateTime, ForeignKey, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.persistence import new_uuid, utc_now


class EpisodeCheckpoint(Base):
    __tablename__ = "episode_checkpoints"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    task_id: Mapped[str] = mapped_column(ForeignKey("learning_tasks.id", ondelete="RESTRICT"))
    assessment_work_start_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_work_starts.id", ondelete="RESTRICT")
    )
    task_form_version_id: Mapped[str] = mapped_column(
        ForeignKey("task_form_versions.id", ondelete="RESTRICT")
    )
    stage_start_id: Mapped[str | None] = mapped_column(
        ForeignKey("episode_stage_starts.id", ondelete="RESTRICT")
    )
    part_id: Mapped[str] = mapped_column(String(255))
    prediction: Mapped[dict[str, Any]] = mapped_column(JSON)
    input_content: Mapped[dict[str, Any]] = mapped_column(JSON)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EpisodeStageStart(Base):
    __tablename__ = "episode_stage_starts"
    __table_args__ = (
        UniqueConstraint("assessment_work_start_id", "part_id", name="uq_episode_transfer_start"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    task_id: Mapped[str] = mapped_column(ForeignKey("learning_tasks.id", ondelete="RESTRICT"))
    assessment_work_start_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_work_starts.id", ondelete="RESTRICT")
    )
    task_form_version_id: Mapped[str] = mapped_column(
        ForeignKey("task_form_versions.id", ondelete="RESTRICT")
    )
    part_id: Mapped[str] = mapped_column(String(255))
    supported_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


def episode_guards():
    clauses = []
    for table in ("episode_checkpoints", "episode_stage_starts"):
        for action in ("UPDATE", "DELETE"):
            clauses.append((table, f"{table}_no_{action.lower()}", action, "1"))
        clauses.append(
            (
                table,
                f"{table}_no_replace",
                "INSERT",
                f"EXISTS(SELECT 1 FROM {table} WHERE id=NEW.id)",
            )
        )
        clauses.append(
            (
                table,
                f"{table}_scope",
                "INSERT",
                "NOT EXISTS(SELECT 1 FROM assessment_work_starts w WHERE w.id=NEW.assessment_work_start_id AND w.task_id=NEW.task_id AND w.student_id=NEW.student_id AND w.task_form_version_id=NEW.task_form_version_id)",
            )
        )
    clauses.append(
        (
            "episode_checkpoints",
            "episode_checkpoint_stage_scope",
            "INSERT",
            "NEW.stage_start_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM episode_stage_starts s WHERE s.id=NEW.stage_start_id AND s.assessment_work_start_id=NEW.assessment_work_start_id AND s.part_id=NEW.part_id)",
        )
    )
    clauses.append(
        (
            "episode_stage_starts",
            "episode_stage_no_scope_replace",
            "INSERT",
            "EXISTS(SELECT 1 FROM episode_stage_starts WHERE assessment_work_start_id=NEW.assessment_work_start_id AND part_id=NEW.part_id)",
        )
    )
    return [
        (
            table,
            name,
            f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {table} WHEN {condition} BEGIN SELECT RAISE(ABORT, 'Episode history or scope is protected'); END",
        )
        for table, name, action, condition in clauses
    ]


def _immutable(*_: Any) -> None:
    raise ValueError("Episode history is immutable")


for _model in (EpisodeCheckpoint, EpisodeStageStart):
    event.listen(_model, "before_update", _immutable)
    event.listen(_model, "before_delete", _immutable)
for _table, _name, _statement in episode_guards():
    event.listen(
        Base.metadata.tables[_table], "after_create", DDL(_statement).execute_if(dialect="sqlite")
    )
