"""Preserved reports, queue ownership and human response history."""

from datetime import datetime

from sqlalchemy import (
    DDL,
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


class EscalationQueueRevision(Base):
    __tablename__ = "escalation_queue_revisions"
    __table_args__ = (
        UniqueConstraint("course_id", "kind", "revision", name="uq_escalation_queue_revision"),
        CheckConstraint("kind IN ('ASSESSOR', 'TECHNICAL')", name="escalation_queue_kind"),
        CheckConstraint(
            "revision > 0 AND primary_user_id != backup_user_id", name="escalation_queue_owners"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(16))
    revision: Mapped[int] = mapped_column(Integer)
    primary_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    backup_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    acknowledgement_target: Mapped[str] = mapped_column(String(500))
    resolution_target: Mapped[str] = mapped_column(String(500))
    reason: Mapped[str] = mapped_column(Text)
    approved_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EscalationCase(Base):
    __tablename__ = "escalation_cases"
    __table_args__ = (
        UniqueConstraint("request_key", name="uq_escalation_case_request"),
        CheckConstraint("queue_kind IN ('ASSESSOR', 'TECHNICAL')", name="escalation_case_queue"),
        CheckConstraint(
            "source_kind IN ('FEEDBACK', 'TUTOR', 'ASSESSMENT')", name="escalation_case_source"
        ),
        CheckConstraint(
            "severity IN ('NORMAL', 'HIGH', 'CRITICAL')", name="escalation_case_severity"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    task_id: Mapped[str] = mapped_column(ForeignKey("learning_tasks.id", ondelete="RESTRICT"))
    source_kind: Mapped[str] = mapped_column(String(16))
    source_id: Mapped[str] = mapped_column(String(36))
    queue_kind: Mapped[str] = mapped_column(String(16))
    trigger: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(Text)
    request_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EscalationEvent(Base):
    __tablename__ = "escalation_events"
    __table_args__ = (
        UniqueConstraint("case_id", "revision", name="uq_escalation_event_revision"),
        UniqueConstraint("case_id", "request_key", name="uq_escalation_event_request"),
        CheckConstraint("revision > 0", name="escalation_event_revision"),
        CheckConstraint(
            "status IN ('OPEN', 'ACKNOWLEDGED', 'ACTIONED', 'RESOLVED', 'CLOSED')",
            name="escalation_event_status",
        ),
        CheckConstraint(
            "severity IN ('NORMAL', 'HIGH', 'CRITICAL')", name="escalation_event_severity"
        ),
        CheckConstraint(
            "length(trim(reason)) > 0 AND length(trim(learner_notice)) > 0",
            name="escalation_event_reasons",
        ),
        CheckConstraint(
            "resolution_due_at >= acknowledgement_due_at", name="escalation_event_deadlines"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("escalation_cases.id", ondelete="RESTRICT"))
    queue_revision_id: Mapped[str] = mapped_column(
        ForeignKey("escalation_queue_revisions.id", ondelete="RESTRICT")
    )
    revision: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(128))
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16))
    severity: Mapped[str] = mapped_column(String(16))
    acknowledgement_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolution_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(Text)
    learner_notice: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


protect_history(EscalationQueueRevision, unique_keys=(("course_id", "kind", "revision"),))
protect_history(EscalationCase, unique_keys=(("request_key",),))
protect_history(EscalationEvent, unique_keys=(("case_id", "revision"), ("case_id", "request_key")))

event.listen(
    EscalationCase.__table__,
    "after_create",
    DDL("""
CREATE TRIGGER IF NOT EXISTS escalation_cases_source_scope BEFORE INSERT ON escalation_cases
WHEN NOT EXISTS (SELECT 1 FROM learning_tasks t WHERE t.id=NEW.task_id AND t.course_id=NEW.course_id)
OR NOT (
 (NEW.source_kind='TUTOR' AND EXISTS (SELECT 1 FROM tutor_turns t WHERE t.id=NEW.source_id AND t.task_id=NEW.task_id AND t.student_id=NEW.student_id)) OR
 (NEW.source_kind='ASSESSMENT' AND EXISTS (SELECT 1 FROM assessment_attempts a WHERE a.id=NEW.source_id AND a.task_id=NEW.task_id AND a.student_id=NEW.student_id)) OR
 (NEW.source_kind='FEEDBACK' AND EXISTS (SELECT 1 FROM feedback_records f JOIN submission_attempts s ON s.id=f.submission_id WHERE f.id=NEW.source_id AND s.task_id=NEW.task_id AND s.student_id=NEW.student_id))
) BEGIN SELECT RAISE(ABORT, 'Escalation source scope mismatch'); END
""").execute_if(dialect="sqlite"),
)
event.listen(
    EscalationEvent.__table__,
    "after_create",
    DDL("""
CREATE TRIGGER IF NOT EXISTS escalation_events_queue_scope BEFORE INSERT ON escalation_events
WHEN NOT EXISTS (SELECT 1 FROM escalation_cases c JOIN escalation_queue_revisions q ON q.course_id=c.course_id AND q.kind=c.queue_kind
WHERE c.id=NEW.case_id AND q.id=NEW.queue_revision_id AND NEW.owner_user_id IN (q.primary_user_id,q.backup_user_id))
BEGIN SELECT RAISE(ABORT, 'Escalation queue scope mismatch'); END
""").execute_if(dialect="sqlite"),
)
