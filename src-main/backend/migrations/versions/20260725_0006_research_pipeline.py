"""Add durable paired-research measurements and fenced baseline jobs.

Revision ID: 20260725_0006
Revises: 20260725_0005
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260725_0006"
down_revision: str | None = "20260725_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def _create_research_v2() -> None:
    op.create_table(
        "research_evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_run_id", sa.String(length=36), nullable=True),
        sa.Column("pseudonymous_user_id", sa.String(length=255), nullable=False),
        sa.Column("course_id", sa.String(length=255), nullable=False),
        sa.Column("task_id", sa.String(length=255), nullable=False),
        sa.Column(
            "task_type",
            sa.String(length=255),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("submission_reference", sa.String(length=255), nullable=False),
        sa.Column(
            "experimental_condition",
            _enum(
                "agentic_rag",
                "single_step_baseline",
                name="experimental_condition",
            ),
            nullable=False,
        ),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("input_references", sa.JSON(), nullable=False),
        sa.Column("retrieved_sources", sa.JSON(), nullable=False),
        sa.Column("simulation_reference", sa.String(length=255), nullable=True),
        sa.Column(
            "simulation_status",
            sa.String(length=100),
            nullable=False,
            server_default="not_requested",
        ),
        sa.Column("generated_output", sa.JSON(), nullable=False),
        sa.Column("judge_result", sa.JSON(), nullable=True),
        sa.Column(
            "measurement_schema_version",
            sa.String(length=100),
            nullable=False,
            server_default="research-v1",
        ),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "estimated_cost",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "regeneration_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "fallback_used",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "comparable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "usage_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "retrieval_request_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "retrieval_hit_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "first_judge_status",
            _enum(
                "valid",
                "malformed",
                "provider_error",
                name="research_first_judge_status",
            ),
            nullable=True,
        ),
        sa.Column(
            "first_judge_decision",
            _enum("pass", "fail", name="research_first_judge_decision"),
            nullable=True,
        ),
        sa.Column(
            "final_judge_status",
            _enum(
                "valid",
                "malformed",
                "provider_error",
                name="research_final_judge_status",
            ),
            nullable=True,
        ),
        sa.Column(
            "final_judge_decision",
            _enum("pass", "fail", name="research_final_judge_decision"),
            nullable=True,
        ),
        sa.Column("correctness_score", sa.Integer(), nullable=True),
        sa.Column("relevance_score", sa.Integer(), nullable=True),
        sa.Column("grounding_score", sa.Integer(), nullable=True),
        sa.Column("actionability_score", sa.Integer(), nullable=True),
        sa.Column("safety_score", sa.Integer(), nullable=True),
        sa.Column("unsupported_claim_count", sa.Integer(), nullable=True),
        sa.Column("quality_policy_version", sa.String(length=100), nullable=True),
        sa.Column("evaluation_latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "evaluation_input_tokens",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "evaluation_output_tokens",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "evaluation_total_tokens",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "evaluation_estimated_cost",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "evaluation_usage_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "status",
            _enum(
                "pending",
                "running",
                "completed",
                "failed",
                name="research_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("execution_token", sa.String(length=36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "processing_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("failure_category", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_research_evaluations_research_latency",
        ),
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
        sa.CheckConstraint(
            "estimated_cost >= 0",
            name="ck_research_evaluations_research_cost",
        ),
        sa.CheckConstraint(
            "regeneration_count BETWEEN 0 AND 1",
            name="ck_research_evaluations_research_regeneration_count",
        ),
        sa.CheckConstraint(
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
            name="ck_research_evaluations_research_completion_state",
        ),
        sa.CheckConstraint(
            "processing_attempts >= 0",
            name="ck_research_evaluations_research_processing_attempts",
        ),
        sa.CheckConstraint(
            "retrieval_request_count >= 0 AND retrieval_hit_count >= 0 "
            "AND retrieval_hit_count <= retrieval_request_count",
            name="ck_research_evaluations_research_retrieval_counts",
        ),
        sa.CheckConstraint(
            "evaluation_latency_ms IS NULL OR evaluation_latency_ms >= 0",
            name="ck_research_evaluations_research_evaluation_latency",
        ),
        sa.CheckConstraint(
            "evaluation_input_tokens >= 0 AND evaluation_output_tokens >= 0 "
            "AND evaluation_total_tokens >= 0 "
            "AND evaluation_total_tokens = "
            "evaluation_input_tokens + evaluation_output_tokens",
            name="ck_research_evaluations_research_evaluation_tokens",
        ),
        sa.CheckConstraint(
            "evaluation_estimated_cost >= 0",
            name="ck_research_evaluations_research_evaluation_cost",
        ),
        sa.CheckConstraint(
            "(correctness_score IS NULL OR correctness_score BETWEEN 0 AND 100) "
            "AND (relevance_score IS NULL OR relevance_score BETWEEN 0 AND 100) "
            "AND (grounding_score IS NULL OR grounding_score BETWEEN 0 AND 100) "
            "AND (actionability_score IS NULL OR actionability_score BETWEEN 0 AND 100) "
            "AND (safety_score IS NULL OR safety_score BETWEEN 0 AND 100)",
            name="ck_research_evaluations_research_scores",
        ),
        sa.CheckConstraint(
            "unsupported_claim_count IS NULL OR unsupported_claim_count >= 0",
            name="ck_research_evaluations_research_unsupported_claims",
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


def _create_research_v1() -> None:
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
            _enum(
                "agentic_rag",
                "single_step_baseline",
                name="experimental_condition",
            ),
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
        sa.Column(
            "latency_ms",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "estimated_cost",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "regeneration_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
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
        sa.CheckConstraint(
            "latency_ms >= 0",
            name="ck_research_evaluations_research_latency",
        ),
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
        sa.CheckConstraint(
            "estimated_cost >= 0",
            name="ck_research_evaluations_research_cost",
        ),
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


def _create_v2_indexes() -> None:
    op.create_index(
        "ix_research_evaluations_course_created",
        "research_evaluations",
        ["course_id", "created_at"],
    )
    op.create_index(
        "ix_research_evaluations_course_condition_created",
        "research_evaluations",
        ["course_id", "experimental_condition", "created_at"],
    )
    op.create_index(
        "ix_research_evaluations_task_type",
        "research_evaluations",
        ["task_type"],
    )
    op.create_index(
        "ix_research_evaluations_provider_model",
        "research_evaluations",
        ["provider", "model"],
    )
    op.create_index(
        "ix_research_evaluations_decision",
        "research_evaluations",
        ["final_judge_decision"],
    )
    op.create_index(
        "ix_research_evaluations_submission",
        "research_evaluations",
        ["submission_reference"],
    )


def _create_v1_indexes() -> None:
    op.create_index(
        "ix_research_evaluations_course_created",
        "research_evaluations",
        ["course_id", "created_at"],
    )
    op.create_index(
        "ix_research_evaluations_submission",
        "research_evaluations",
        ["submission_reference"],
    )


def upgrade() -> None:
    op.execute("PRAGMA foreign_keys=OFF")
    op.drop_index(
        "ix_research_evaluations_submission",
        table_name="research_evaluations",
    )
    op.drop_index(
        "ix_research_evaluations_course_created",
        table_name="research_evaluations",
    )
    op.rename_table("research_evaluations", "research_evaluations_legacy")
    _create_research_v2()
    op.execute(
        sa.text(
            "INSERT INTO research_evaluations ("
            "id, case_id, workflow_run_id, pseudonymous_user_id, course_id, task_id, "
            "task_type, submission_reference, experimental_condition, prompt_version, "
            "provider, model, input_references, retrieved_sources, simulation_reference, "
            "simulation_status, generated_output, judge_result, measurement_schema_version, "
            "latency_ms, input_tokens, output_tokens, total_tokens, estimated_cost, "
            "regeneration_count, fallback_used, comparable, usage_complete, "
            "retrieval_request_count, retrieval_hit_count, evaluation_input_tokens, "
            "evaluation_output_tokens, evaluation_total_tokens, evaluation_estimated_cost, "
            "evaluation_usage_complete, status, processing_attempts, failure_category, "
            "created_at, completed_at"
            ") SELECT "
            "id, case_id, workflow_run_id, pseudonymous_user_id, course_id, task_id, "
            "'unknown', submission_reference, experimental_condition, prompt_version, "
            "provider, model, input_references, retrieved_sources, simulation_reference, "
            "CASE WHEN simulation_reference IS NULL THEN 'not_requested' ELSE 'completed' END, "
            "generated_output, judge_result, 'legacy-v1', latency_ms, input_tokens, "
            "output_tokens, total_tokens, estimated_cost, regeneration_count, 0, 0, 0, "
            "0, 0, 0, 0, 0, 0, 0, status, 0, "
            "CASE WHEN status = 'failed' THEN 'legacy_failure' ELSE NULL END, "
            "created_at, completed_at FROM research_evaluations_legacy"
        )
    )
    op.drop_table("research_evaluations_legacy")
    _create_v2_indexes()
    op.execute("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    op.execute("PRAGMA foreign_keys=OFF")
    for index_name in (
        "ix_research_evaluations_submission",
        "ix_research_evaluations_decision",
        "ix_research_evaluations_provider_model",
        "ix_research_evaluations_task_type",
        "ix_research_evaluations_course_condition_created",
        "ix_research_evaluations_course_created",
    ):
        op.drop_index(index_name, table_name="research_evaluations")
    op.rename_table("research_evaluations", "research_evaluations_v2")
    _create_research_v1()
    op.execute(
        sa.text(
            "INSERT INTO research_evaluations ("
            "id, case_id, workflow_run_id, pseudonymous_user_id, course_id, task_id, "
            "submission_reference, experimental_condition, prompt_version, provider, model, "
            "input_references, retrieved_sources, simulation_reference, generated_output, "
            "judge_result, latency_ms, input_tokens, output_tokens, total_tokens, "
            "estimated_cost, regeneration_count, status, created_at, completed_at"
            ") SELECT "
            "id, case_id, workflow_run_id, pseudonymous_user_id, course_id, task_id, "
            "submission_reference, experimental_condition, prompt_version, provider, model, "
            "input_references, retrieved_sources, simulation_reference, generated_output, "
            "judge_result, COALESCE(latency_ms, 0), input_tokens, output_tokens, total_tokens, "
            "estimated_cost, regeneration_count, "
            "CASE WHEN status = 'running' THEN 'failed' ELSE status END, created_at, "
            "CASE WHEN status = 'running' THEN CURRENT_TIMESTAMP ELSE completed_at END "
            "FROM research_evaluations_v2"
        )
    )
    op.drop_table("research_evaluations_v2")
    _create_v1_indexes()
    op.execute("PRAGMA foreign_keys=ON")
