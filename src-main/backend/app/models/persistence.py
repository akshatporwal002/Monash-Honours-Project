from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    ExperimentalCondition,
    FeedbackStatus,
    JudgeDecision,
    JudgeEvaluationStatus,
    LearningEventType,
    ResearchStatus,
    WorkflowOutcome,
    WorkflowStage,
    NotificationKind,
    SubmissionStatus,
    TaskType,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid4())


def enum_column(enum_type: type[Any], name: str) -> SqlEnum[Any]:
    return SqlEnum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint("submission_id", name="uq_workflow_runs_submission_id"),
        CheckConstraint(
            "regeneration_count BETWEEN 0 AND 1",
            name="workflow_regeneration_count",
        ),
        CheckConstraint(
            "((current_stage IN ('completed', 'failed')) "
            "AND final_outcome IS NOT NULL AND completed_at IS NOT NULL) OR "
            "((current_stage NOT IN ('completed', 'failed')) "
            "AND final_outcome IS NULL AND completed_at IS NULL)",
            name="workflow_terminal_state",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    submission_id: Mapped[str] = mapped_column(String(255), nullable=False)
    current_stage: Mapped[WorkflowStage] = mapped_column(
        enum_column(WorkflowStage, "workflow_stage"),
        nullable=False,
        default=WorkflowStage.PENDING,
    )
    regeneration_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    final_outcome: Mapped[WorkflowOutcome | None] = mapped_column(
        enum_column(WorkflowOutcome, "workflow_outcome"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    feedback_records: Mapped[list[FeedbackRecord]] = relationship(
        back_populates="workflow_run",
        passive_deletes=True,
    )
    research_evaluations: Mapped[list[ResearchEvaluation]] = relationship(
        back_populates="workflow_run",
        passive_deletes=True,
    )


class FeedbackRecord(Base):
    __tablename__ = "feedback_records"
    __table_args__ = (
        UniqueConstraint(
            "workflow_run_id",
            "generation_attempt",
            name="uq_feedback_records_workflow_attempt",
        ),
        CheckConstraint(
            "(status = 'safe_fallback' AND generation_attempt IS NULL AND model IS NULL) OR "
            "(status <> 'safe_fallback' AND generation_attempt BETWEEN 1 AND 2 "
            "AND model IS NOT NULL)",
            name="feedback_generation_details",
        ),
        Index("ix_feedback_records_submission_id", "submission_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    submission_id: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    feedback_content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[FeedbackStatus] = mapped_column(
        enum_column(FeedbackStatus, "feedback_status"),
        nullable=False,
        default=FeedbackStatus.PENDING_JUDGEMENT,
    )
    generation_attempt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_references: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    workflow_run: Mapped[WorkflowRun] = relationship(back_populates="feedback_records")
    judge_evaluation: Mapped[JudgeEvaluation | None] = relationship(
        back_populates="feedback_record",
        passive_deletes=True,
        uselist=False,
    )


class JudgeEvaluation(Base):
    __tablename__ = "judge_evaluations"
    __table_args__ = (
        UniqueConstraint("feedback_id", name="uq_judge_evaluations_feedback_id"),
        CheckConstraint(
            "correctness_score IS NULL OR correctness_score BETWEEN 0 AND 100",
            name="judge_correctness_score",
        ),
        CheckConstraint(
            "relevance_score IS NULL OR relevance_score BETWEEN 0 AND 100",
            name="judge_relevance_score",
        ),
        CheckConstraint(
            "grounding_score IS NULL OR grounding_score BETWEEN 0 AND 100",
            name="judge_grounding_score",
        ),
        CheckConstraint(
            "actionability_score IS NULL OR actionability_score BETWEEN 0 AND 100",
            name="judge_actionability_score",
        ),
        CheckConstraint(
            "safety_score IS NULL OR safety_score BETWEEN 0 AND 100",
            name="judge_safety_score",
        ),
        CheckConstraint(
            "(evaluation_status = 'valid' AND decision IS NOT NULL "
            "AND correctness_score IS NOT NULL AND relevance_score IS NOT NULL "
            "AND grounding_score IS NOT NULL AND actionability_score IS NOT NULL "
            "AND safety_score IS NOT NULL AND error_category IS NULL) OR "
            "(evaluation_status <> 'valid' AND decision IS NULL "
            "AND correctness_score IS NULL AND relevance_score IS NULL "
            "AND grounding_score IS NULL AND actionability_score IS NULL "
            "AND safety_score IS NULL AND error_category IS NOT NULL)",
            name="judge_result_shape",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    feedback_id: Mapped[str] = mapped_column(
        ForeignKey("feedback_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    evaluation_status: Mapped[JudgeEvaluationStatus] = mapped_column(
        enum_column(JudgeEvaluationStatus, "judge_evaluation_status"),
        nullable=False,
    )
    decision: Mapped[JudgeDecision | None] = mapped_column(
        enum_column(JudgeDecision, "judge_decision"),
        nullable=True,
    )
    correctness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relevance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grounding_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actionability_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    safety_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    unsupported_claims: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    regeneration_instructions: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    error_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    feedback_record: Mapped[FeedbackRecord] = relationship(back_populates="judge_evaluation")


class LearningEvent(Base):
    __tablename__ = "learning_events"
    __table_args__ = (
        UniqueConstraint("deduplication_key", name="uq_learning_events_deduplication_key"),
        Index("ix_learning_events_course_task", "course_id", "task_id"),
        Index("ix_learning_events_user_occurred", "pseudonymous_user_id", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    pseudonymous_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    course_id: Mapped[str] = mapped_column(String(255), nullable=False)
    task_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[LearningEventType] = mapped_column(
        enum_column(LearningEventType, "learning_event_type"),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )
    deduplication_key: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ResearchEvaluation(Base):
    __tablename__ = "research_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "case_id",
            "experimental_condition",
            name="uq_research_evaluations_case_condition",
        ),
        CheckConstraint("latency_ms >= 0", name="research_latency"),
        CheckConstraint("input_tokens >= 0", name="research_input_tokens"),
        CheckConstraint("output_tokens >= 0", name="research_output_tokens"),
        CheckConstraint("total_tokens >= 0", name="research_total_tokens"),
        CheckConstraint(
            "total_tokens = input_tokens + output_tokens",
            name="research_token_total",
        ),
        CheckConstraint("estimated_cost >= 0", name="research_cost"),
        CheckConstraint(
            "regeneration_count BETWEEN 0 AND 1",
            name="research_regeneration_count",
        ),
        CheckConstraint(
            "(status = 'pending' AND completed_at IS NULL) OR "
            "(status IN ('completed', 'failed') AND completed_at IS NOT NULL)",
            name="research_completion_state",
        ),
        Index("ix_research_evaluations_course_created", "course_id", "created_at"),
        Index("ix_research_evaluations_submission", "submission_reference"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    case_id: Mapped[str] = mapped_column(String(36), nullable=False)
    workflow_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    pseudonymous_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    course_id: Mapped[str] = mapped_column(String(255), nullable=False)
    task_id: Mapped[str] = mapped_column(String(255), nullable=False)
    submission_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    experimental_condition: Mapped[ExperimentalCondition] = mapped_column(
        enum_column(ExperimentalCondition, "experimental_condition"),
        nullable=False,
    )
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    input_references: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    retrieved_sources: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    simulation_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    generated_output: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    judge_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
        default=Decimal("0"),
    )
    regeneration_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[ResearchStatus] = mapped_column(
        enum_column(ResearchStatus, "research_status"),
        nullable=False,
        default=ResearchStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workflow_run: Mapped[WorkflowRun | None] = relationship(back_populates="research_evaluations")


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    streak_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    submissions: Mapped[list[StudentSubmission]] = relationship(back_populates="student")
    notifications: Mapped[list[StudentNotification]] = relationship(back_populates="student")
    achievements: Mapped[list[StudentAchievement]] = relationship(back_populates="student")


class LearningTask(Base):
    __tablename__ = "learning_tasks"
    __table_args__ = (UniqueConstraint("slug", name="uq_learning_tasks_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    module: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[TaskType] = mapped_column(enum_column(TaskType, "task_type"), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(30), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    starter_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    submissions: Mapped[list[StudentSubmission]] = relationship(back_populates="task")


class StudentSubmission(Base):
    __tablename__ = "student_submissions"
    __table_args__ = (
        UniqueConstraint("student_id", "task_id", name="uq_student_submissions_student_task"),
        CheckConstraint("score BETWEEN 0 AND 100", name="student_submission_score"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    student_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[str] = mapped_column(ForeignKey("learning_tasks.id", ondelete="CASCADE"), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    code: Mapped[str | None] = mapped_column(Text, nullable=True)
    circuit: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[SubmissionStatus] = mapped_column(enum_column(SubmissionStatus, "submission_status"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    student: Mapped[StudentProfile] = relationship(back_populates="submissions")
    task: Mapped[LearningTask] = relationship(back_populates="submissions")


class Achievement(Base):
    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("code", name="uq_achievements_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    icon: Mapped[str] = mapped_column(String(20), nullable=False)


class StudentAchievement(Base):
    __tablename__ = "student_achievements"
    __table_args__ = (UniqueConstraint("student_id", "achievement_id", name="uq_student_achievement"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    student_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False)
    achievement_id: Mapped[str] = mapped_column(ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False)
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    student: Mapped[StudentProfile] = relationship(back_populates="achievements")
    achievement: Mapped[Achievement] = relationship()


class StudentNotification(Base):
    __tablename__ = "student_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    student_id: Mapped[str] = mapped_column(ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[NotificationKind] = mapped_column(enum_column(NotificationKind, "notification_kind"), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    student: Mapped[StudentProfile] = relationship(back_populates="notifications")
