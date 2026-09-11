"""Append-only course revisions and malware scan receipts."""

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
from app.models.persistence import new_uuid, utc_now


class CourseRevision(Base):
    __tablename__ = "course_revisions"
    __table_args__ = (UniqueConstraint("course_id", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer)
    metadata_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    actor_id: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    restored_from_id: Mapped[str | None] = mapped_column(ForeignKey("course_revisions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MaterialScan(Base):
    __tablename__ = "material_scans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    material_id: Mapped[str] = mapped_column(
        ForeignKey("learning_materials.id", ondelete="RESTRICT")
    )
    content_hash: Mapped[str] = mapped_column(String(128))
    processing_revision: Mapped[int] = mapped_column(Integer)
    claim_token: Mapped[str] = mapped_column(String(36))
    policy_version: Mapped[str] = mapped_column(String(255))
    scanner: Mapped[str] = mapped_column(String(255))
    scanner_version: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(24))
    code: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


def _immutable(*_: Any) -> None:
    raise ValueError("Intake history is append-only")


for _model in (CourseRevision, MaterialScan):
    event.listen(_model, "before_update", _immutable)
    event.listen(_model, "before_delete", _immutable)
    _table = _model.__tablename__
    _key = "id = NEW.id"
    if _model is CourseRevision:
        _key += " OR (course_id = NEW.course_id AND version = NEW.version)"
    for _action in ("UPDATE", "DELETE", "INSERT"):
        _condition = (
            f"WHEN EXISTS (SELECT 1 FROM {_table} WHERE {_key}) " if _action == "INSERT" else ""
        )
        event.listen(
            _model.__table__,
            "after_create",
            DDL(
                f"CREATE TRIGGER {_table}_no_{_action.lower()} BEFORE {_action} ON {_table} "
                f"{_condition}BEGIN SELECT RAISE(ABORT, 'Intake history is append-only'); END"
            ).execute_if(dialect="sqlite"),
        )
