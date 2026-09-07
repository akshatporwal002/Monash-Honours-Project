"""Immutable source content, review events, and output-to-passage references."""

from __future__ import annotations

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


class SourceRevision(Base):
    __tablename__ = "source_revisions"
    __table_args__ = (
        UniqueConstraint("material_id", "version", name="uq_source_revision_version"),
        UniqueConstraint("id", "course_id", name="uq_source_revision_course"),
        CheckConstraint("version > 0", name="source_revision_positive_version"),
        CheckConstraint(
            "provenance IN ('EXTRACTED', 'LEGACY_SNAPSHOT')", name="source_revision_provenance"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    material_id: Mapped[str] = mapped_column(
        ForeignKey("learning_materials.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    course_id: Mapped[str] = mapped_column(String(255), nullable=False)
    module_id: Mapped[str | None] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_label: Mapped[str] = mapped_column(String(2048), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(512))
    extracted_blocks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(255), nullable=False)
    provenance: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class SourcePassage(Base):
    __tablename__ = "source_passages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["revision_id", "course_id"],
            ["source_revisions.id", "source_revisions.course_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("revision_id", "chunk_index", name="uq_source_passage_order"),
        UniqueConstraint("id", "course_id", name="uq_source_passage_course"),
        CheckConstraint("chunk_index >= 0", name="source_passage_index"),
    )

    # Preserve the exact original chunk identifier even after the search index changes.
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    revision_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    course_id: Mapped[str] = mapped_column(String(255), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    heading: Mapped[str | None] = mapped_column(String(500))
    location_label: Mapped[str | None] = mapped_column(String(100))
    chunk_hash: Mapped[str] = mapped_column(String(128), nullable=False)


class SourceApproval(Base):
    __tablename__ = "source_approvals"
    __table_args__ = (
        UniqueConstraint("revision_id", "sequence", name="uq_source_approval_sequence"),
        CheckConstraint("state IN ('APPROVED', 'REVOKED')", name="source_approval_state"),
        CheckConstraint("sequence > 0", name="source_approval_sequence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    revision_id: Mapped[str] = mapped_column(
        ForeignKey("source_revisions.id", ondelete="RESTRICT"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class SourceUse(Base):
    __tablename__ = "source_uses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["passage_id", "course_id"],
            ["source_passages.id", "source_passages.course_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "output_type",
            "output_id",
            "output_version",
            "passage_id",
            name="uq_source_use_output_passage",
        ),
        CheckConstraint(
            "output_type IN ('task', 'feedback', 'assessment')", name="source_use_output_type"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    output_type: Mapped[str] = mapped_column(String(16), nullable=False)
    output_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    output_version: Mapped[str] = mapped_column(String(128), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    passage_id: Mapped[str] = mapped_column(String(36), nullable=False)
    approval_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_approvals.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


def _immutable(*_: Any) -> None:
    raise ValueError("Source history is append-only")


for _model in (SourceRevision, SourcePassage, SourceApproval, SourceUse):
    event.listen(_model, "before_update", _immutable)
    event.listen(_model, "before_delete", _immutable)
    event.listen(
        _model.__table__,
        "after_create",
        DDL(
            f"CREATE TRIGGER {_model.__tablename__}_no_replace BEFORE INSERT ON {_model.__tablename__} "
            f"WHEN EXISTS (SELECT 1 FROM {_model.__tablename__} WHERE id = NEW.id) "
            "BEGIN SELECT RAISE(ABORT, 'Source history is append-only'); END"
        ).execute_if(dialect="sqlite"),
    )
    for _action in ("UPDATE", "DELETE"):
        event.listen(
            _model.__table__,
            "after_create",
            DDL(
                f"CREATE TRIGGER {_model.__tablename__}_no_{_action.lower()} "
                f"BEFORE {_action} ON {_model.__tablename__} "
                "BEGIN SELECT RAISE(ABORT, 'Source history is append-only'); END"
            ).execute_if(dialect="sqlite"),
        )
