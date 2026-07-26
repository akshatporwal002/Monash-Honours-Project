from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    ExperimentalCondition,
    FeedbackStatus,
    JudgeDecision,
    JudgeEvaluationStatus,
    LearningEventType,
    MaterialIndexStatus,
    NotificationKind,
    ResearchStatus,
    SubmissionStatus,
    TaskType,
    WorkflowOutcome,
    WorkflowStage,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


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
            "(status = 'safe_fallback' AND generation_attempt IS NULL AND model IS NULL "
            "AND provider IS NULL AND prompt_version IS NULL) OR "
            "(status <> 'safe_fallback' AND generation_attempt BETWEEN 1 AND 2 "
            "AND model IS NOT NULL AND provider IS NOT NULL AND prompt_version IS NOT NULL)",
            name="feedback_generation_details",
        ),
        CheckConstraint("input_tokens >= 0", name="feedback_input_tokens"),
        CheckConstraint("output_tokens >= 0", name="feedback_output_tokens"),
        CheckConstraint("total_tokens >= 0", name="feedback_total_tokens"),
        CheckConstraint(
            "total_tokens = input_tokens + output_tokens",
            name="feedback_token_total",
        ),
        CheckConstraint("estimated_cost >= 0", name="feedback_cost"),
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
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_references: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    simulation_references: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
        default=Decimal(0),
    )
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
        default=Decimal(0),
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
    __table_args__ = (
        UniqueConstraint("slug", name="uq_learning_tasks_slug"),
        CheckConstraint("generation_input_tokens >= 0", name="learning_task_generation_input_tokens"),
        CheckConstraint("generation_output_tokens >= 0", name="learning_task_generation_output_tokens"),
        CheckConstraint("generation_total_tokens >= 0", name="learning_task_generation_total_tokens"),
        CheckConstraint("generation_estimated_cost >= 0", name="learning_task_generation_cost"),
        CheckConstraint(
            "(generation_provider IS NULL AND generation_model IS NULL "
            "AND generation_prompt_version IS NULL AND generation_input_tokens = 0 "
            "AND generation_output_tokens = 0 AND generation_total_tokens = 0 "
            "AND generation_estimated_cost = 0) OR "
            "(generation_provider IS NOT NULL AND generation_model IS NOT NULL "
            "AND generation_prompt_version IS NOT NULL "
            "AND generation_total_tokens = generation_input_tokens + generation_output_tokens)",
            name="learning_task_generation_metadata",
        ),
    )

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
    course_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    module_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    learning_outcome_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    marking_criteria: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON, nullable=True)
    source_references: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    prerequisite_task_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    generation_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generation_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    generation_prompt_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generation_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation_total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation_estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal(0)
    )

    submissions: Mapped[list[StudentSubmission]] = relationship(back_populates="task")


class LearningMaterial(Base):
    __tablename__ = "learning_materials"
    __table_args__ = (
        UniqueConstraint("course_id", "content_hash", name="uq_learning_materials_course_hash"),
        CheckConstraint(
            "(original_filename IS NOT NULL AND source_url IS NULL) OR "
            "(original_filename IS NULL AND source_url IS NOT NULL)",
            name="learning_material_source_identity",
        ),
        CheckConstraint(
            "source_url IS NULL OR source_url LIKE 'https://%'",
            name="learning_material_https_source",
        ),
        CheckConstraint("file_size_bytes IS NULL OR file_size_bytes >= 0", name="learning_material_file_size"),
        CheckConstraint("processing_revision >= 0", name="learning_material_processing_revision"),
        Index("ix_learning_materials_course_id", "course_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(String(255), nullable=False)
    module_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    indexing_status: Mapped[MaterialIndexStatus] = mapped_column(
        enum_column(MaterialIndexStatus, "material_index_status"),
        nullable=False,
        default=MaterialIndexStatus.PENDING,
    )
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_stage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    processing_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    chunks: Mapped[list[MaterialChunk]] = relationship(
        back_populates="material", cascade="all, delete-orphan", passive_deletes=True
    )


class MaterialChunk(Base):
    __tablename__ = "material_chunks"
    __table_args__ = (
        UniqueConstraint("material_id", "chunk_index", name="uq_material_chunks_material_index"),
        CheckConstraint("chunk_index >= 0", name="material_chunk_index"),
        CheckConstraint("token_count >= 0", name="material_chunk_token_count"),
        Index("ix_material_chunks_material_order", "material_id", "chunk_index"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    material_id: Mapped[str] = mapped_column(
        ForeignKey("learning_materials.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    heading: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedding_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_dimension: Mapped[int | None] = mapped_column(Integer, nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    material: Mapped[LearningMaterial] = relationship(back_populates="chunks")


class RetrievalAudit(Base):
    __tablename__ = "retrieval_audits"
    __table_args__ = (
        CheckConstraint("top_k > 0", name="retrieval_audit_top_k"),
        CheckConstraint("minimum_relevance BETWEEN 0 AND 1", name="retrieval_audit_relevance"),
        CheckConstraint("hit_count >= 0", name="retrieval_audit_hit_count"),
        CheckConstraint("latency_ms >= 0", name="retrieval_audit_latency"),
        Index("ix_retrieval_audits_course_created", "course_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(String(255), nullable=False)
    module_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_relevance: Mapped[float] = mapped_column(nullable=False)
    result_chunk_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    result_scores: Mapped[list[float]] = mapped_column(JSON, nullable=False, default=list)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


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
