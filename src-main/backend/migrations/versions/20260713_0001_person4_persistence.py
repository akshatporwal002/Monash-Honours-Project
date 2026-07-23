"""Create Person 4 persistence tables.

Revision ID: 20260713_0001
Revises:
Create Date: 2026-07-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260713_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("submission_id", sa.String(length=255), nullable=False),
        sa.Column(
            "current_stage",
            _enum(
                "pending",
                "context_collection",
                "generating",
                "judging",
                "regenerating",
                "completed",
                "failed",
                name="workflow_stage",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("regeneration_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "final_outcome",
            _enum(
                "first_pass",
                "second_pass",
                "safe_fallback",
                "workflow_failed",
                name="workflow_outcome",
            ),
            nullable=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "regeneration_count BETWEEN 0 AND 1",
            name="ck_workflow_runs_workflow_regeneration_count",
        ),
        sa.CheckConstraint(
            "((current_stage IN ('completed', 'failed')) "
            "AND final_outcome IS NOT NULL AND completed_at IS NOT NULL) OR "
            "((current_stage NOT IN ('completed', 'failed')) "
            "AND final_outcome IS NULL AND completed_at IS NULL)",
            name="ck_workflow_runs_workflow_terminal_state",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workflow_runs"),
        sa.UniqueConstraint("submission_id", name="uq_workflow_runs_submission_id"),
    )

    op.create_table(
        "feedback_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("submission_id", sa.String(length=255), nullable=False),
        sa.Column("workflow_run_id", sa.String(length=36), nullable=False),
        sa.Column("feedback_content", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            _enum(
                "pending_judgement",
                "accepted",
                "rejected",
                "safe_fallback",
                name="feedback_status",
            ),
            nullable=False,
            server_default="pending_judgement",
        ),
        sa.Column("generation_attempt", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("source_references", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "(status = 'safe_fallback' AND generation_attempt IS NULL AND model IS NULL) OR "
            "(status <> 'safe_fallback' AND generation_attempt BETWEEN 1 AND 2 "
            "AND model IS NOT NULL)",
            name="ck_feedback_records_feedback_generation_details",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["workflow_runs.id"],
            name="fk_feedback_records_workflow_run_id_workflow_runs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_feedback_records"),
        sa.UniqueConstraint(
            "workflow_run_id",
            "generation_attempt",
            name="uq_feedback_records_workflow_attempt",
        ),
    )
    op.create_index(
        "ix_feedback_records_submission_id",
        "feedback_records",
        ["submission_id"],
        unique=False,
    )

    op.create_table(
        "judge_evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("feedback_id", sa.String(length=36), nullable=False),
        sa.Column(
            "evaluation_status",
            _enum("valid", "malformed", "provider_error", name="judge_evaluation_status"),
            nullable=False,
        ),
        sa.Column(
            "decision",
            _enum("pass", "fail", name="judge_decision"),
            nullable=True,
        ),
        sa.Column("correctness_score", sa.Integer(), nullable=True),
        sa.Column("relevance_score", sa.Integer(), nullable=True),
        sa.Column("grounding_score", sa.Integer(), nullable=True),
        sa.Column("actionability_score", sa.Integer(), nullable=True),
        sa.Column("safety_score", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("unsupported_claims", sa.JSON(), nullable=False),
        sa.Column("regeneration_instructions", sa.JSON(), nullable=False),
        sa.Column("error_category", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "correctness_score IS NULL OR correctness_score BETWEEN 0 AND 100",
            name="ck_judge_evaluations_judge_correctness_score",
        ),
        sa.CheckConstraint(
            "relevance_score IS NULL OR relevance_score BETWEEN 0 AND 100",
            name="ck_judge_evaluations_judge_relevance_score",
        ),
        sa.CheckConstraint(
            "grounding_score IS NULL OR grounding_score BETWEEN 0 AND 100",
            name="ck_judge_evaluations_judge_grounding_score",
        ),
        sa.CheckConstraint(
            "actionability_score IS NULL OR actionability_score BETWEEN 0 AND 100",
            name="ck_judge_evaluations_judge_actionability_score",
        ),
        sa.CheckConstraint(
            "safety_score IS NULL OR safety_score BETWEEN 0 AND 100",
            name="ck_judge_evaluations_judge_safety_score",
        ),
        sa.CheckConstraint(
            "(evaluation_status = 'valid' AND decision IS NOT NULL "
            "AND correctness_score IS NOT NULL AND relevance_score IS NOT NULL "
            "AND grounding_score IS NOT NULL AND actionability_score IS NOT NULL "
            "AND safety_score IS NOT NULL AND error_category IS NULL) OR "
            "(evaluation_status <> 'valid' AND decision IS NULL "
            "AND correctness_score IS NULL AND relevance_score IS NULL "
            "AND grounding_score IS NULL AND actionability_score IS NULL "
            "AND safety_score IS NULL AND error_category IS NOT NULL)",
            name="ck_judge_evaluations_judge_result_shape",
        ),
        sa.ForeignKeyConstraint(
            ["feedback_id"],
            ["feedback_records.id"],
            name="fk_judge_evaluations_feedback_id_feedback_records",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_judge_evaluations"),
        sa.UniqueConstraint("feedback_id", name="uq_judge_evaluations_feedback_id"),
    )

    op.create_table(
        "learning_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("pseudonymous_user_id", sa.String(length=255), nullable=False),
        sa.Column("course_id", sa.String(length=255), nullable=False),
        sa.Column("task_id", sa.String(length=255), nullable=False),
        sa.Column(
            "event_type",
            _enum(
                "task_view",
                "draft_save",
                "submission",
                "feedback_view",
                "completion",
                name="learning_event_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("deduplication_key", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_learning_events"),
        sa.UniqueConstraint(
            "deduplication_key",
            name="uq_learning_events_deduplication_key",
        ),
    )
    op.create_index(
        "ix_learning_events_course_task",
        "learning_events",
        ["course_id", "task_id"],
        unique=False,
    )
    op.create_index(
        "ix_learning_events_user_occurred",
        "learning_events",
        ["pseudonymous_user_id", "occurred_at"],
        unique=False,
    )

    op.create_table(
        "research_evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_run_id", sa.String(length=36), nullable=True),
        sa.Column("pseudonymous_user_id", sa.String(length=255), nullable=False),
        sa.Column("course_id", sa.String(length=255), nullable=False),
        sa.Column("task_id", sa.String(length=255), nullable=False),
        sa.Column("submission_reference", sa.String(length=255), nullable=False),
        sa.Column(
            "experimental_condition",
            _enum("agentic_rag", "single_step_baseline", name="experimental_condition"),
            nullable=False,
        ),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("input_references", sa.JSON(), nullable=False),
        sa.Column("retrieved_sources", sa.JSON(), nullable=False),
        sa.Column("simulation_reference", sa.String(length=255), nullable=True),
        sa.Column("generated_output", sa.JSON(), nullable=False),
        sa.Column("judge_result", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "estimated_cost",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
            server_default="0",
        ),
        sa.Column("regeneration_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            _enum("pending", "completed", "failed", name="research_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("latency_ms >= 0", name="ck_research_evaluations_research_latency"),
        sa.CheckConstraint(
            "input_tokens >= 0",
            name="ck_research_evaluations_research_input_tokens",
        ),
        sa.CheckConstraint(
            "output_tokens >= 0",
            name="ck_research_evaluations_research_output_tokens",
        ),
        sa.CheckConstraint(
            "total_tokens >= 0",
            name="ck_research_evaluations_research_total_tokens",
        ),
        sa.CheckConstraint(
            "total_tokens = input_tokens + output_tokens",
            name="ck_research_evaluations_research_token_total",
        ),
        sa.CheckConstraint("estimated_cost >= 0", name="ck_research_evaluations_research_cost"),
        sa.CheckConstraint(
            "regeneration_count BETWEEN 0 AND 1",
            name="ck_research_evaluations_research_regeneration_count",
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND completed_at IS NULL) OR "
            "(status IN ('completed', 'failed') AND completed_at IS NOT NULL)",
            name="ck_research_evaluations_research_completion_state",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["workflow_runs.id"],
            name="fk_research_evaluations_workflow_run_id_workflow_runs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_research_evaluations"),
        sa.UniqueConstraint(
            "case_id",
            "experimental_condition",
            name="uq_research_evaluations_case_condition",
        ),
    )
    op.create_index(
        "ix_research_evaluations_course_created",
        "research_evaluations",
        ["course_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_research_evaluations_submission",
        "research_evaluations",
        ["submission_reference"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_research_evaluations_submission", table_name="research_evaluations")
    op.drop_index("ix_research_evaluations_course_created", table_name="research_evaluations")
    op.drop_table("research_evaluations")
    op.drop_index("ix_learning_events_user_occurred", table_name="learning_events")
    op.drop_index("ix_learning_events_course_task", table_name="learning_events")
    op.drop_table("learning_events")
    op.drop_table("judge_evaluations")
    op.drop_index("ix_feedback_records_submission_id", table_name="feedback_records")
    op.drop_table("feedback_records")
    op.drop_table("workflow_runs")
