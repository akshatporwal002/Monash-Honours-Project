"""Optional reward preferences and the evidence behind participation recognition."""

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
from app.models.append_only import protect_history
from app.models.assessment import new_uuid, utc_now


class GamificationPreference(Base):
    __tablename__ = "gamification_preferences"
    __table_args__ = (
        UniqueConstraint("student_id", "revision", name="uq_gamification_preference_revision"),
        UniqueConstraint("student_id", "request_key", name="uq_gamification_preference_request"),
        CheckConstraint("revision > 0", name="gamification_preference_revision"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    revision: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ParticipationRecognition(Base):
    __tablename__ = "participation_recognitions"
    __table_args__ = (
        UniqueConstraint("student_id", "task_id", "kind", name="uq_participation_recognition_kind"),
        CheckConstraint(
            "kind IN ('REFLECTION', 'REVISION', 'FEEDBACK_INTERACTION')",
            name="participation_recognition_kind",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    task_id: Mapped[str] = mapped_column(ForeignKey("learning_tasks.id", ondelete="RESTRICT"))
    evidence_id: Mapped[str] = mapped_column(
        ForeignKey("learning_evidence.id", ondelete="RESTRICT")
    )
    kind: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


protect_history(
    GamificationPreference, unique_keys=(("student_id", "revision"), ("student_id", "request_key"))
)
protect_history(ParticipationRecognition, unique_keys=(("student_id", "task_id", "kind"),))
event.listen(
    ParticipationRecognition.__table__,
    "after_create",
    DDL("""
CREATE TRIGGER IF NOT EXISTS participation_recognitions_scope BEFORE INSERT ON participation_recognitions
WHEN NOT EXISTS (SELECT 1 FROM learning_evidence e WHERE e.id=NEW.evidence_id
AND e.learner_id=NEW.student_id AND e.task_id=NEW.task_id AND e.evidence_type=NEW.kind)
BEGIN SELECT RAISE(ABORT, 'Participation evidence scope mismatch'); END
""").execute_if(dialect="sqlite"),
)
