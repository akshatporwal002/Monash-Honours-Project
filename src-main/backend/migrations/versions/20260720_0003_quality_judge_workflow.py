"""Add quality-judge metadata and normalize legacy rejected workflows.

Revision ID: 20260720_0003
Revises: 20260720_0002
Create Date: 2026-07-20
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0003"
down_revision: str | None = "20260720_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("judge_evaluations") as batch_op:
        batch_op.drop_constraint(
            "ck_judge_evaluations_judge_result_shape",
            type_="check",
        )
        batch_op.add_column(
            sa.Column(
                "reported_decision",
                sa.String(length=4),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("provider", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("model", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("prompt_version", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column(
                "estimated_cost",
                sa.Numeric(precision=12, scale=6),
                nullable=False,
                server_default="0",
            )
        )

    op.execute(
        sa.text(
            "UPDATE judge_evaluations SET "
            "reported_decision = decision, provider = 'legacy', "
            "model = COALESCE((SELECT feedback_records.model FROM feedback_records "
            "WHERE feedback_records.id = judge_evaluations.feedback_id), 'legacy-judge'), "
            "prompt_version = 'quality-judge-v0'"
        )
    )

    with op.batch_alter_table("judge_evaluations") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_judge_evaluations_judge_reported_decision"),
            "reported_decision IS NULL OR reported_decision IN ('pass', 'fail')",
        )
        batch_op.create_check_constraint(
            "ck_judge_evaluations_judge_result_shape",
            "(evaluation_status = 'valid' AND reported_decision IS NOT NULL "
            "AND decision IS NOT NULL AND correctness_score IS NOT NULL "
            "AND relevance_score IS NOT NULL AND grounding_score IS NOT NULL "
            "AND actionability_score IS NOT NULL AND safety_score IS NOT NULL "
            "AND error_category IS NULL AND provider IS NOT NULL AND model IS NOT NULL "
            "AND prompt_version IS NOT NULL) OR "
            "(evaluation_status <> 'valid' AND reported_decision IS NULL AND decision IS NULL "
            "AND correctness_score IS NULL AND relevance_score IS NULL "
            "AND grounding_score IS NULL AND actionability_score IS NULL "
            "AND safety_score IS NULL AND error_category IS NOT NULL)",
        )
        batch_op.create_check_constraint(
            "ck_judge_evaluations_judge_input_tokens",
            "input_tokens >= 0",
        )
        batch_op.create_check_constraint(
            "ck_judge_evaluations_judge_output_tokens",
            "output_tokens >= 0",
        )
        batch_op.create_check_constraint(
            "ck_judge_evaluations_judge_total_tokens",
            "total_tokens >= 0",
        )
        batch_op.create_check_constraint(
            "ck_judge_evaluations_judge_token_total",
            "total_tokens = input_tokens + output_tokens",
        )
        batch_op.create_check_constraint(
            "ck_judge_evaluations_judge_cost",
            "estimated_cost >= 0",
        )

    _convert_legacy_rejections_to_fallbacks()


def _convert_legacy_rejections_to_fallbacks() -> None:
    connection = op.get_bind()
    workflows = list(
        connection.execute(
            sa.text(
                "SELECT id, submission_id FROM workflow_runs "
                "WHERE final_outcome = 'workflow_failed'"
            )
        ).mappings()
    )
    for workflow in workflows:
        connection.execute(
            sa.text(
                "INSERT INTO feedback_records "
                "(id, submission_id, workflow_run_id, feedback_content, status, "
                "generation_attempt, provider, model, prompt_version, source_references, "
                "simulation_references, input_tokens, output_tokens, total_tokens, "
                "estimated_cost, created_at) "
                "VALUES (:id, :submission_id, :workflow_id, :content, 'safe_fallback', "
                "NULL, NULL, NULL, NULL, :sources, :simulations, 0, 0, 0, 0, CURRENT_TIMESTAMP)"
            ),
            {
                "id": str(uuid4()),
                "submission_id": workflow["submission_id"],
                "workflow_id": workflow["id"],
                "content": (
                    '{"summary":"Personalized feedback is temporarily unavailable.",'
                    '"explanation":"Your submission was received, but no feedback passed '
                    'validation.","recommended_next_step":"Review the relevant course material '
                    'and try again, or ask your educator for help."}'
                ),
                "sources": "[]",
                "simulations": "[]",
            },
        )
        connection.execute(
            sa.text(
                "UPDATE workflow_runs SET current_stage = 'completed', "
                "final_outcome = 'safe_fallback' WHERE id = :workflow_id"
            ),
            {"workflow_id": workflow["id"]},
        )


def downgrade() -> None:
    with op.batch_alter_table("judge_evaluations") as batch_op:
        batch_op.drop_constraint(
            "ck_judge_evaluations_judge_result_shape",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_judge_evaluations_judge_input_tokens",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_judge_evaluations_judge_output_tokens",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_judge_evaluations_judge_total_tokens",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_judge_evaluations_judge_token_total",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_judge_evaluations_judge_cost",
            type_="check",
        )
        batch_op.drop_constraint(
            op.f("ck_judge_evaluations_judge_reported_decision"),
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_judge_evaluations_judge_result_shape",
            "(evaluation_status = 'valid' AND decision IS NOT NULL "
            "AND correctness_score IS NOT NULL AND relevance_score IS NOT NULL "
            "AND grounding_score IS NOT NULL AND actionability_score IS NOT NULL "
            "AND safety_score IS NOT NULL AND error_category IS NULL) OR "
            "(evaluation_status <> 'valid' AND decision IS NULL "
            "AND correctness_score IS NULL AND relevance_score IS NULL "
            "AND grounding_score IS NULL AND actionability_score IS NULL "
            "AND safety_score IS NULL AND error_category IS NOT NULL)",
        )

    with op.batch_alter_table("judge_evaluations") as batch_op:
        batch_op.drop_column("estimated_cost")
        batch_op.drop_column("total_tokens")
        batch_op.drop_column("output_tokens")
        batch_op.drop_column("input_tokens")
        batch_op.drop_column("prompt_version")
        batch_op.drop_column("model")
        batch_op.drop_column("provider")
        batch_op.drop_column("reported_decision")
