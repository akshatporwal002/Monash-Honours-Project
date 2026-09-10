"""Restricted governance ledger, separate from research analysis and teaching records."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.append_only import protect_history
from app.models.assessment import new_uuid, utc_now


class ResearchGovernanceEvent(Base):
    __tablename__ = "research_governance_events"
    __table_args__ = (
        UniqueConstraint("study_id", "revision", name="uq_research_governance_revision"),
        UniqueConstraint("actor_user_id", "request_key", name="uq_research_governance_request"),
        CheckConstraint("revision > 0", name="research_governance_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    study_id: Mapped[str] = mapped_column(String(128), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    request_key: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(24))
    command: Mapped[dict] = mapped_column(JSON)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ResearchCaseGovernance(Base):
    __tablename__ = "research_case_governance"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    case_id: Mapped[str] = mapped_column(String(36), unique=True)
    scope_id: Mapped[str] = mapped_column(ForeignKey("research_governance_events.id"))
    consent_id: Mapped[str] = mapped_column(ForeignKey("research_governance_events.id"))
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    pseudonymous_user_id: Mapped[str] = mapped_column(String(67))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ResearchExportEligibility(Base):
    __tablename__ = "research_export_eligibility"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    study_id: Mapped[str] = mapped_column(String(128))
    scope_id: Mapped[str | None] = mapped_column(ForeignKey("research_governance_events.id"))
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    manifest: Mapped[dict] = mapped_column(JSON)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


protect_history(
    ResearchGovernanceEvent,
    unique_keys=(("study_id", "revision"), ("actor_user_id", "request_key")),
)
protect_history(ResearchCaseGovernance, unique_keys=(("case_id",),))
protect_history(ResearchExportEligibility)
