"""Immutable study workflow history; separate from teaching and assessment."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.append_only import protect_history
from app.models.assessment import new_uuid, utc_now


class ResearchStudyEvent(Base):
    __tablename__ = "research_study_events"
    __table_args__ = (
        UniqueConstraint("actor_user_id", "request_key"),
        UniqueConstraint("scope_id", "course_id", "slot", "revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    scope_id: Mapped[str] = mapped_column(ForeignKey("research_governance_events.id"))
    study_id: Mapped[str] = mapped_column(String(128))
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"))
    kind: Mapped[str] = mapped_column(String(24))
    slot: Mapped[str] = mapped_column(String(256))
    revision: Mapped[int] = mapped_column(Integer)
    subject_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    consent_id: Mapped[str | None] = mapped_column(ForeignKey("research_governance_events.id"))
    data: Mapped[dict] = mapped_column(JSON)
    content_digest: Mapped[str] = mapped_column(String(71))
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    request_key: Mapped[str] = mapped_column(String(128))
    request_digest: Mapped[str] = mapped_column(String(71))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


protect_history(
    ResearchStudyEvent,
    unique_keys=(
        ("actor_user_id", "request_key"),
        ("scope_id", "course_id", "slot", "revision"),
    ),
)
