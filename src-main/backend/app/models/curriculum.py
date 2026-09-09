"""Append-only curriculum approvals and diagnostic receipts."""

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


class PathwayVersion(Base):
    __tablename__ = "curriculum_pathway_versions"
    __table_args__ = (
        UniqueConstraint("outcome_id", "version", name="uq_curriculum_version"),
        UniqueConstraint("outcome_id", "request_key", name="uq_curriculum_request"),
        CheckConstraint("version > 0", name="curriculum_version_positive"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    outcome_id: Mapped[str] = mapped_column(ForeignKey("learning_outcomes.id", ondelete="RESTRICT"))
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(100))
    approved_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    payload: Mapped[dict] = mapped_column(JSON)
    bindings: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DiagnosticSession(Base):
    __tablename__ = "curriculum_diagnostic_sessions"
    __table_args__ = (
        UniqueConstraint("learner_id", "request_key", name="uq_diagnostic_start_request"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    pathway_id: Mapped[str] = mapped_column(
        ForeignKey("curriculum_pathway_versions.id", ondelete="RESTRICT")
    )
    learner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    request_key: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DiagnosticResponse(Base):
    __tablename__ = "curriculum_diagnostic_responses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("curriculum_diagnostic_sessions.id", ondelete="RESTRICT"), unique=True
    )
    evidence_id: Mapped[str] = mapped_column(
        ForeignKey("learning_evidence.id", ondelete="RESTRICT"), unique=True
    )
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DiagnosticConfirmation(Base):
    __tablename__ = "curriculum_diagnostic_confirmations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("curriculum_diagnostic_sessions.id", ondelete="RESTRICT"), unique=True
    )
    assessor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assignment_id: Mapped[str] = mapped_column(
        ForeignKey("role_assignments.id", ondelete="RESTRICT")
    )
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


def _immutable(*_):
    raise ValueError("Curriculum history is protected")


for model in (PathwayVersion, DiagnosticSession, DiagnosticResponse, DiagnosticConfirmation):
    event.listen(model, "before_update", _immutable)
    event.listen(model, "before_delete", _immutable)
    table = model.__tablename__
    unique = {
        PathwayVersion: "outcome_id=NEW.outcome_id AND (version=NEW.version OR request_key=NEW.request_key)",
        DiagnosticSession: "learner_id=NEW.learner_id AND request_key=NEW.request_key",
        DiagnosticResponse: "session_id=NEW.session_id OR evidence_id=NEW.evidence_id",
        DiagnosticConfirmation: "session_id=NEW.session_id",
    }[model]
    for action in ("UPDATE", "DELETE", "INSERT"):
        condition = (
            f"WHEN EXISTS (SELECT 1 FROM {table} WHERE id=NEW.id OR ({unique})) "
            if action == "INSERT"
            else ""
        )
        event.listen(
            model.__table__,
            "after_create",
            DDL(
                f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} BEFORE {action} ON {table} "
                f"{condition}BEGIN SELECT RAISE(ABORT, 'Curriculum history is protected'); END"
            ).execute_if(dialect="sqlite"),
        )
