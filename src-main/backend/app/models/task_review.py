"""Immutable authored task revisions and explicit educator review events."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DDL,
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.persistence import new_uuid, utc_now


class TaskRevision(Base):
    __tablename__ = "task_revisions"
    __table_args__ = (
        UniqueConstraint("task_id", "version", name="uq_task_revision_version"),
        UniqueConstraint("id", "course_id", name="uq_task_revision_course"),
        CheckConstraint("version > 0", name="task_revision_version"),
        CheckConstraint(
            "provenance IN ('AUTHORED', 'GENERATED', 'LEGACY')", name="task_revision_provenance"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[str] = mapped_column(ForeignKey("learning_tasks.id", ondelete="RESTRICT"))
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_digest: Mapped[str] = mapped_column(String(64))
    provenance: Mapped[str] = mapped_column(String(16))
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class TaskReviewEvent(Base):
    __tablename__ = "task_review_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_revision_id", "course_id"],
            ["task_revisions.id", "task_revisions.course_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("task_revision_id", "version", name="uq_task_review_version"),
        CheckConstraint("version > 0", name="task_review_version"),
        CheckConstraint(
            "state IN ('SUBMITTED', 'APPROVED', 'REJECTED', 'WITHDRAWN')", name="task_review_state"
        ),
        CheckConstraint("length(trim(reason)) > 0", name="task_review_reason"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_revision_id: Mapped[str] = mapped_column(String(36))
    course_id: Mapped[str] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16))
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reason: Mapped[str] = mapped_column(Text)
    source_approvals: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    policy_version: Mapped[str] = mapped_column(String(64), default="educator-task-review-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CategoryQualityReview(Base):
    """Private content review, tied to its actual educator and immutable task event."""

    __tablename__ = "category_quality_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["task_revision_id", "course_id"],
            ["task_revisions.id", "task_revisions.course_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("task_review_event_id", name="uq_category_quality_event"),
        CheckConstraint("decision IN ('APPROVED', 'REJECTED')", name="category_quality_decision"),
        CheckConstraint("length(request_digest) = 64", name="category_quality_digest"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(String(36))
    task_revision_id: Mapped[str] = mapped_column(String(36))
    task_review_event_id: Mapped[str] = mapped_column(
        ForeignKey("task_review_events.id", ondelete="RESTRICT")
    )
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    request_digest: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(16))
    receipt: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


def category_quality_guards() -> tuple[str, ...]:
    table = "category_quality_reviews"
    return tuple(
        f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} BEFORE {action} ON {table} "
        "BEGIN SELECT RAISE(ABORT, 'Category review history is append-only'); END"
        for action in ("UPDATE", "DELETE")
    ) + (
        f"CREATE TRIGGER IF NOT EXISTS {table}_no_replace BEFORE INSERT ON {table} "
        f"WHEN EXISTS (SELECT 1 FROM {table} WHERE id=NEW.id OR task_review_event_id=NEW.task_review_event_id) "
        "BEGIN SELECT RAISE(ABORT, 'Category review history is append-only'); END",
        f"CREATE TRIGGER IF NOT EXISTS {table}_scope BEFORE INSERT ON {table} "
        "WHEN NOT EXISTS (SELECT 1 FROM task_review_events e WHERE e.id=NEW.task_review_event_id "
        "AND e.course_id=NEW.course_id AND e.task_revision_id=NEW.task_revision_id "
        "AND e.actor_user_id=NEW.reviewer_id AND e.state IN ('APPROVED','REJECTED') "
        "AND (e.state='REJECTED' OR NEW.decision='APPROVED')) "
        "BEGIN SELECT RAISE(ABORT, 'Category review event scope differs'); END",
    )


def _immutable(*_: Any) -> None:
    raise ValueError("Task review history is append-only")


for _model, _unique in (
    (TaskRevision, "task_id = NEW.task_id AND version = NEW.version"),
    (TaskReviewEvent, "task_revision_id = NEW.task_revision_id AND version = NEW.version"),
):
    event.listen(_model, "before_update", _immutable)
    event.listen(_model, "before_delete", _immutable)
    for _action in ("UPDATE", "DELETE"):
        event.listen(
            _model.__table__,
            "after_create",
            DDL(
                f"CREATE TRIGGER {_model.__tablename__}_no_{_action.lower()} BEFORE {_action} ON {_model.__tablename__} "
                "BEGIN SELECT RAISE(ABORT, 'Task review history is append-only'); END"
            ).execute_if(dialect="sqlite"),
        )
    event.listen(
        _model.__table__,
        "after_create",
        DDL(
            f"CREATE TRIGGER {_model.__tablename__}_no_replace BEFORE INSERT ON {_model.__tablename__} "
            f"WHEN EXISTS (SELECT 1 FROM {_model.__tablename__} WHERE id = NEW.id OR ({_unique})) "
            "BEGIN SELECT RAISE(ABORT, 'Task review history is append-only'); END"
        ).execute_if(dialect="sqlite"),
    )

event.listen(CategoryQualityReview, "before_update", _immutable)
event.listen(CategoryQualityReview, "before_delete", _immutable)
for _statement in category_quality_guards():
    event.listen(
        CategoryQualityReview.__table__,
        "after_create",
        DDL(_statement).execute_if(dialect="sqlite"),
    )
