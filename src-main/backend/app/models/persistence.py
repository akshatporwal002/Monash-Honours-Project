from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    ExperimentalCondition,
    FeedbackReportCategory,
    FeedbackStatus,
    JudgeDecision,
    JudgeEvaluationStatus,
    LearningEventType,
    ResearchStatus,
    WorkflowOutcome,
    WorkflowStage,
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
        UniqueConstraint(
            "id",
            "submission_id",
            name="uq_workflow_runs_id_submission",
        ),
        CheckConstraint(
            "regeneration_count BETWEEN 0 AND 1",
            name="workflow_regeneration_count",
        ),
        CheckConstraint(
            "(current_stage = 'completed' "
            "AND final_outcome IN ('first_pass', 'second_pass', 'safe_fallback') "
            "AND completed_at IS NOT NULL) OR "
            "(current_stage = 'failed' AND final_outcome = 'workflow_failed' "
            "AND completed_at IS NOT NULL) OR "
            "(current_stage NOT IN ('completed', 'failed') "
            "AND final_outcome IS NULL AND completed_at IS NULL)",
            name="workflow_terminal_state",
        ),
        CheckConstraint(
            "(current_stage = 'failed' AND failure_category IS NOT NULL) OR "
            "(current_stage <> 'failed' AND failure_category IS NULL)",
            name="workflow_failure_shape",
        ),
        CheckConstraint(
            "execution_attempt_count BETWEEN 0 AND 3",
            name="workflow_execution_attempt_count",
        ),
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="workflow_latency",
        ),
        CheckConstraint(
            "next_retry_at IS NULL OR current_stage = 'failed'",
            name="workflow_retry_shape",
        ),
        Index(
            "ix_workflow_runs_worker_claim",
            "current_stage",
            "next_retry_at",
            "lease_expires_at",
            "started_at",
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
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    execution_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    execution_attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    course_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failure_category: Mapped[str | None] = mapped_column(String(100), nullable=True)

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
        ForeignKeyConstraint(
            ["workflow_run_id", "submission_id"],
            ["workflow_runs.id", "workflow_runs.submission_id"],
            name="fk_feedback_records_workflow_submission",
            ondelete="RESTRICT",
        ),
        Index("ix_feedback_records_submission_id", "submission_id"),
        Index(
            "uq_feedback_records_workflow_released",
            "workflow_run_id",
            unique=True,
            sqlite_where=text("status IN ('accepted', 'safe_fallback')"),
            postgresql_where=text("status IN ('accepted', 'safe_fallback')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    submission_id: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_run_id: Mapped[str] = mapped_column(String(36), nullable=False)
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
    source_attributions: Mapped[list[dict[str, str]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
        default=Decimal("0"),
    )
    usage_complete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
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
    reports: Mapped[list[FeedbackReport]] = relationship(
        back_populates="feedback_record",
        passive_deletes=True,
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
            "(evaluation_status = 'valid' AND reported_decision IS NOT NULL "
            "AND decision IS NOT NULL "
            "AND correctness_score IS NOT NULL AND relevance_score IS NOT NULL "
            "AND grounding_score IS NOT NULL AND actionability_score IS NOT NULL "
            "AND safety_score IS NOT NULL AND error_category IS NULL "
            "AND provider IS NOT NULL AND model IS NOT NULL AND prompt_version IS NOT NULL) OR "
            "(evaluation_status <> 'valid' AND reported_decision IS NULL AND decision IS NULL "
            "AND correctness_score IS NULL AND relevance_score IS NULL "
            "AND grounding_score IS NULL AND actionability_score IS NULL "
            "AND safety_score IS NULL AND error_category IS NOT NULL)",
            name="judge_result_shape",
        ),
        CheckConstraint("input_tokens >= 0", name="judge_input_tokens"),
        CheckConstraint("output_tokens >= 0", name="judge_output_tokens"),
        CheckConstraint("total_tokens >= 0", name="judge_total_tokens"),
        CheckConstraint(
            "total_tokens = input_tokens + output_tokens",
            name="judge_token_total",
        ),
        CheckConstraint("estimated_cost >= 0", name="judge_cost"),
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
    reported_decision: Mapped[JudgeDecision | None] = mapped_column(
        enum_column(JudgeDecision, "judge_reported_decision"),
        nullable=True,
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
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quality_policy_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="quality-policy-v1",
    )
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
        default=Decimal("0"),
    )
    usage_complete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    feedback_record: Mapped[FeedbackRecord] = relationship(back_populates="judge_evaluation")


class FeedbackReport(Base):
    __tablename__ = "feedback_reports"
    __table_args__ = (
        UniqueConstraint(
            "feedback_id",
            "reporter_reference",
            name="uq_feedback_reports_feedback_reporter",
        ),
        CheckConstraint(
            "note IS NULL OR length(note) BETWEEN 1 AND 2000",
            name="feedback_report_note_length",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    feedback_id: Mapped[str] = mapped_column(
        ForeignKey("feedback_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reporter_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[FeedbackReportCategory] = mapped_column(
        enum_column(FeedbackReportCategory, "feedback_report_category"),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    feedback_record: Mapped[FeedbackRecord] = relationship(back_populates="reports")


class LearningEvent(Base):
    __tablename__ = "learning_events"
    __table_args__ = (
        UniqueConstraint("deduplication_key", name="uq_learning_events_deduplication_key"),
        Index("ix_learning_events_course_task", "course_id", "task_id"),
        Index("ix_learning_events_user_occurred", "pseudonymous_user_id", "occurred_at"),
        Index("ix_learning_events_event_workflow", "event_type", "workflow_reference"),
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
    workflow_reference: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
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
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="research_latency",
        ),
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
            "(status = 'pending' AND completed_at IS NULL "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND failure_category IS NULL) OR "
            "(status = 'running' AND completed_at IS NULL "
            "AND execution_token IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND failure_category IS NULL) OR "
            "(status = 'completed' AND completed_at IS NOT NULL "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND failure_category IS NULL) OR "
            "(status = 'failed' AND completed_at IS NOT NULL "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND failure_category IS NOT NULL)",
            name="research_completion_state",
        ),
        CheckConstraint(
            "processing_attempts BETWEEN 0 AND 3",
            name="research_processing_attempts",
        ),
        CheckConstraint(
            "retrieval_request_count >= 0 "
            "AND retrieval_hit_count >= 0 "
            "AND retrieval_hit_count <= retrieval_request_count",
            name="research_retrieval_counts",
        ),
        CheckConstraint(
            "evaluation_latency_ms IS NULL OR evaluation_latency_ms >= 0",
            name="research_evaluation_latency",
        ),
        CheckConstraint(
            "evaluation_input_tokens >= 0 AND evaluation_output_tokens >= 0 "
            "AND evaluation_total_tokens >= 0 "
            "AND evaluation_total_tokens = "
            "evaluation_input_tokens + evaluation_output_tokens",
            name="research_evaluation_tokens",
        ),
        CheckConstraint(
            "evaluation_estimated_cost >= 0",
            name="research_evaluation_cost",
        ),
        CheckConstraint(
            "(correctness_score IS NULL OR correctness_score BETWEEN 0 AND 100) "
            "AND (relevance_score IS NULL OR relevance_score BETWEEN 0 AND 100) "
            "AND (grounding_score IS NULL OR grounding_score BETWEEN 0 AND 100) "
            "AND (actionability_score IS NULL OR actionability_score BETWEEN 0 AND 100) "
            "AND (safety_score IS NULL OR safety_score BETWEEN 0 AND 100)",
            name="research_scores",
        ),
        CheckConstraint(
            "unsupported_claim_count IS NULL OR unsupported_claim_count >= 0",
            name="research_unsupported_claims",
        ),
        Index("ix_research_evaluations_course_created", "course_id", "created_at"),
        Index(
            "ix_research_evaluations_course_condition_created",
            "course_id",
            "experimental_condition",
            "created_at",
        ),
        Index("ix_research_evaluations_task_type", "task_type"),
        Index("ix_research_evaluations_provider_model", "provider", "model"),
        Index("ix_research_evaluations_decision", "final_judge_decision"),
        Index("ix_research_evaluations_submission", "submission_reference"),
        Index("ix_research_evaluations_correlation", "correlation_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    case_id: Mapped[str] = mapped_column(String(36), nullable=False)
    workflow_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"),
        nullable=True,
    )
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    pseudonymous_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    course_id: Mapped[str] = mapped_column(String(255), nullable=False)
    task_id: Mapped[str] = mapped_column(String(255), nullable=False)
    task_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="unknown",
    )
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
    simulation_status: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="not_requested",
    )
    generated_output: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    judge_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    measurement_schema_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="research-v1",
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
        default=Decimal("0"),
    )
    regeneration_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    comparable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    usage_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retrieval_request_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    retrieval_hit_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    first_judge_status: Mapped[JudgeEvaluationStatus | None] = mapped_column(
        enum_column(JudgeEvaluationStatus, "research_first_judge_status"),
        nullable=True,
    )
    first_judge_decision: Mapped[JudgeDecision | None] = mapped_column(
        enum_column(JudgeDecision, "research_first_judge_decision"),
        nullable=True,
    )
    final_judge_status: Mapped[JudgeEvaluationStatus | None] = mapped_column(
        enum_column(JudgeEvaluationStatus, "research_final_judge_status"),
        nullable=True,
    )
    final_judge_decision: Mapped[JudgeDecision | None] = mapped_column(
        enum_column(JudgeDecision, "research_final_judge_decision"),
        nullable=True,
    )
    correctness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relevance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grounding_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actionability_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    safety_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unsupported_claim_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_policy_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    evaluation_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evaluation_input_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    evaluation_output_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    evaluation_total_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    evaluation_estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
        default=Decimal("0"),
    )
    evaluation_usage_complete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    status: Mapped[ResearchStatus] = mapped_column(
        enum_column(ResearchStatus, "research_status"),
        nullable=False,
        default=ResearchStatus.PENDING,
    )
    execution_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    processing_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    failure_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workflow_run: Mapped[WorkflowRun | None] = relationship(back_populates="research_evaluations")
