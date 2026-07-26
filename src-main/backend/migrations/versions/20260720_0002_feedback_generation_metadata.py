"""Persist feedback generation metadata.

Revision ID: 20260720_0002
Revises: 20260713_0001
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0002"
down_revision: str | None = "20260713_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("feedback_records") as batch_op:
        batch_op.drop_constraint(
            "ck_feedback_records_feedback_generation_details",
            type_="check",
        )
        batch_op.add_column(sa.Column("provider", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("prompt_version", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column(
                "simulation_references",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )
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
            "UPDATE feedback_records "
            "SET provider = 'legacy', prompt_version = 'feedback-v0' "
            "WHERE status <> 'safe_fallback'"
        )
    )

    with op.batch_alter_table("feedback_records") as batch_op:
        batch_op.create_check_constraint(
            "ck_feedback_records_feedback_generation_details",
            "(status = 'safe_fallback' AND generation_attempt IS NULL AND model IS NULL "
            "AND provider IS NULL AND prompt_version IS NULL) OR "
            "(status <> 'safe_fallback' AND generation_attempt BETWEEN 1 AND 2 "
            "AND model IS NOT NULL AND provider IS NOT NULL AND prompt_version IS NOT NULL)",
        )
        batch_op.create_check_constraint(
            "ck_feedback_records_feedback_input_tokens",
            "input_tokens >= 0",
        )
        batch_op.create_check_constraint(
            "ck_feedback_records_feedback_output_tokens",
            "output_tokens >= 0",
        )
        batch_op.create_check_constraint(
            "ck_feedback_records_feedback_total_tokens",
            "total_tokens >= 0",
        )
        batch_op.create_check_constraint(
            "ck_feedback_records_feedback_token_total",
            "total_tokens = input_tokens + output_tokens",
        )
        batch_op.create_check_constraint(
            "ck_feedback_records_feedback_cost",
            "estimated_cost >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("feedback_records") as batch_op:
        batch_op.drop_constraint(
            "ck_feedback_records_feedback_generation_details",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_feedback_records_feedback_input_tokens",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_feedback_records_feedback_output_tokens",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_feedback_records_feedback_total_tokens",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_feedback_records_feedback_token_total",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_feedback_records_feedback_cost",
            type_="check",
        )
        batch_op.drop_column("estimated_cost")
        batch_op.drop_column("total_tokens")
        batch_op.drop_column("output_tokens")
        batch_op.drop_column("input_tokens")
        batch_op.drop_column("simulation_references")
        batch_op.drop_column("prompt_version")
        batch_op.drop_column("provider")
        batch_op.create_check_constraint(
            "ck_feedback_records_feedback_generation_details",
            "(status = 'safe_fallback' AND generation_attempt IS NULL AND model IS NULL) OR "
            "(status <> 'safe_fallback' AND generation_attempt BETWEEN 1 AND 2 "
            "AND model IS NOT NULL)",
        )
