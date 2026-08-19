from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.assessment import AssessmentAttempt, AssessmentDefinition, TaskFormVersion


def new_uuid() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


def enum_column(enum_type: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


class CourseState(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class EnrollmentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"


class OutcomeKind(StrEnum):
    WEEKLY = "weekly"
    TOPIC = "topic"


class AttemptStatus(StrEnum):
    SUBMITTED = "submitted"
    COMPLETED = "completed"


class ImmutableAttemptError(RuntimeError):
    """Raised when application code tries to change an accepted attempt."""


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("code", name="uq_courses_code"),
        Index("ix_courses_educator_state", "educator_id", "state"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    educator_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    state: Mapped[CourseState] = mapped_column(
        enum_column(CourseState, "course_state"),
        nullable=False,
        default=CourseState.DRAFT,
    )
    enrollment_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    educator: Mapped[Any] = relationship("User", foreign_keys=[educator_id])
    modules: Mapped[list[CourseModule]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="CourseModule.position",
    )
    enrollments: Mapped[list[Enrollment]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )


class CourseModule(Base):
    __tablename__ = "course_modules"
    __table_args__ = (
        UniqueConstraint("course_id", "position", name="uq_course_modules_course_position"),
        CheckConstraint("position > 0", name="course_module_position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    course: Mapped[Course] = relationship(back_populates="modules")
    outcomes: Mapped[list[LearningOutcome]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="LearningOutcome.position",
    )


class LearningOutcome(Base):
    __tablename__ = "learning_outcomes"
    __table_args__ = (
        UniqueConstraint(
            "module_id",
            "position",
            name="uq_learning_outcomes_module_position",
        ),
        CheckConstraint("position > 0", name="learning_outcome_position"),
        CheckConstraint(
            "(kind = 'weekly' AND week_number IS NOT NULL AND week_number > 0) OR "
            "(kind = 'topic' AND week_number IS NULL)",
            name="learning_outcome_kind_shape",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    module_id: Mapped[str] = mapped_column(
        ForeignKey("course_modules.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[OutcomeKind] = mapped_column(
        enum_column(OutcomeKind, "outcome_kind"),
        nullable=False,
    )
    week_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    module: Mapped[CourseModule] = relationship(back_populates="outcomes")
    assessment_definitions: Mapped[list["AssessmentDefinition"]] = relationship(
        "AssessmentDefinition",
        back_populates="learning_outcome",
    )


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("course_id", "student_id", name="uq_enrollments_course_student"),
        Index("ix_enrollments_student_status", "student_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[EnrollmentStatus] = mapped_column(
        enum_column(EnrollmentStatus, "enrollment_status"),
        nullable=False,
        default=EnrollmentStatus.ACTIVE,
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    course: Mapped[Course] = relationship(back_populates="enrollments")
    student: Mapped[Any] = relationship("User", foreign_keys=[student_id])


class SubmissionDraft(Base):
    __tablename__ = "submission_drafts"
    __table_args__ = (
        UniqueConstraint("student_id", "task_id", name="uq_submission_drafts_student_task"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("learning_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    code: Mapped[str | None] = mapped_column(Text, nullable=True)
    circuit: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    attempts: Mapped[list[SubmissionAttempt]] = relationship(
        back_populates="draft",
        order_by="SubmissionAttempt.attempt_number",
    )


class SubmissionAttempt(Base):
    __tablename__ = "submission_attempts"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "task_id",
            "attempt_number",
            name="uq_submission_attempts_student_task_number",
        ),
        CheckConstraint("attempt_number > 0", name="submission_attempt_number"),
        CheckConstraint(
            "score IS NULL OR score BETWEEN 0 AND 100", name="submission_attempt_legacy_score"
        ),
        CheckConstraint(
            "content_digest IS NULL OR (length(content_digest) = 71 AND "
            "content_digest GLOB 'sha256:*' AND content_digest NOT GLOB 'sha256:*[^0-9a-f]*')",
            name="submission_attempt_content_digest",
        ),
        Index("ix_submission_attempts_student_time", "student_id", "submitted_at"),
        Index("ix_submission_attempts_task_status", "task_id", "status"),
        UniqueConstraint(
            "student_id", "task_id", "idempotency_key", name="uq_submission_attempts_idempotency"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("submission_drafts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("learning_tasks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[AttemptStatus] = mapped_column(
        enum_column(AttemptStatus, "attempt_status"),
        nullable=False,
    )
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    code: Mapped[str | None] = mapped_column(Text, nullable=True)
    circuit: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Legacy numeric value. Formal assessment results never read this column.",
    )
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    feedback_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    task_form_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("task_form_versions.id", ondelete="RESTRICT"), nullable=True
    )
    response_schema_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content_digest: Mapped[str | None] = mapped_column(String(71), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    declared_conditions: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    draft: Mapped[SubmissionDraft] = relationship(back_populates="attempts")
    point_award: Mapped[TaskPointAward | None] = relationship(
        back_populates="attempt",
        uselist=False,
    )
    assessment_attempt: Mapped["AssessmentAttempt | None"] = relationship(
        "AssessmentAttempt", back_populates="response_version", uselist=False
    )
    task_form_version: Mapped["TaskFormVersion | None"] = relationship()


@event.listens_for(SubmissionAttempt, "before_update", propagate=True)
@event.listens_for(SubmissionAttempt, "before_delete", propagate=True)
def _prevent_attempt_mutation(*_: object) -> None:
    raise ImmutableAttemptError("submission attempts are immutable")


class TaskPointAward(Base):
    __tablename__ = "task_point_awards"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "task_id",
            name="uq_task_point_awards_student_task",
        ),
        UniqueConstraint("attempt_id", name="uq_task_point_awards_attempt"),
        CheckConstraint("points >= 0", name="task_point_award_points"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("learning_tasks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("submission_attempts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    attempt: Mapped[SubmissionAttempt] = relationship(back_populates="point_award")


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "task_id",
            "dedupe_window",
            name="uq_reminders_student_task_window",
        ),
        Index("ix_reminders_student_time", "student_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("learning_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    dedupe_window: Mapped[str] = mapped_column(String(40), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "task_id",
            name="uq_recommendations_student_task",
        ),
        CheckConstraint("rank BETWEEN 1 AND 3", name="recommendation_rank"),
        Index("ix_recommendations_student_active", "student_id", "is_active", "rank"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("learning_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"
    __table_args__ = (UniqueConstraint("key", name="uq_system_settings_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class PlatformAuditEvent(Base):
    __tablename__ = "platform_audit_events"
    __table_args__ = (
        Index("ix_platform_audit_events_actor_time", "actor_id", "occurred_at"),
        Index("ix_platform_audit_events_resource", "resource_type", "resource_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
