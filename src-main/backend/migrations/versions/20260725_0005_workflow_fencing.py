"""Add fenced workflow execution and versioned quality policy.

Revision ID: 20260725_0005
Revises: 20260720_0004
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260725_0005"
down_revision: str | None = "20260720_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("workflow_runs") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_workflow_runs_ck_workflow_runs_workflow_terminal_state"),
            type_="check",
        )
        batch_op.drop_constraint(
            op.f("ck_workflow_runs_workflow_failure_shape"),
            type_="check",
        )
        batch_op.add_column(sa.Column("execution_token", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column(
                "execution_attempt_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("latency_ms", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("course_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("task_id", sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint(
            "uq_workflow_runs_id_submission",
            ["id", "submission_id"],
        )
        batch_op.create_check_constraint(
            op.f("ck_workflow_runs_workflow_terminal_state"),
            "(current_stage = 'completed' "
            "AND final_outcome IN ('first_pass', 'second_pass', 'safe_fallback') "
            "AND completed_at IS NOT NULL) OR "
            "(current_stage = 'failed' AND final_outcome = 'workflow_failed' "
            "AND completed_at IS NOT NULL) OR "
            "(current_stage NOT IN ('completed', 'failed') "
            "AND final_outcome IS NULL AND completed_at IS NULL)",
        )
        batch_op.create_check_constraint(
            op.f("ck_workflow_runs_workflow_failure_shape"),
            "(current_stage = 'failed' AND failure_category IS NOT NULL) OR "
            "(current_stage <> 'failed' AND failure_category IS NULL)",
        )
        batch_op.create_check_constraint(
            op.f("ck_workflow_runs_workflow_execution_attempt_count"),
            "execution_attempt_count BETWEEN 0 AND 3",
        )
        batch_op.create_check_constraint(
            op.f("ck_workflow_runs_workflow_latency"),
            "latency_ms IS NULL OR latency_ms >= 0",
        )
        batch_op.create_check_constraint(
            op.f("ck_workflow_runs_workflow_retry_shape"),
            "next_retry_at IS NULL OR current_stage = 'failed'",
        )

    op.execute(
        sa.text(
            "UPDATE workflow_runs SET "
            "execution_attempt_count = CASE "
            "WHEN current_stage IN ('completed', 'failed') THEN 1 ELSE 0 END, "
            "latency_ms = CASE "
            "WHEN completed_at IS NULL THEN NULL "
            "WHEN julianday(completed_at) <= julianday(started_at) THEN 0 "
            "ELSE CAST((julianday(completed_at) - julianday(started_at)) "
            "* 86400000 AS INTEGER) END"
        )
    )

    with op.batch_alter_table("feedback_records") as batch_op:
        batch_op.drop_constraint(
            "fk_feedback_records_workflow_run_id_workflow_runs",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_feedback_records_workflow_submission",
            "workflow_runs",
            ["workflow_run_id", "submission_id"],
            ["id", "submission_id"],
            ondelete="RESTRICT",
        )
    op.create_index(
        "uq_feedback_records_workflow_released",
        "feedback_records",
        ["workflow_run_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('accepted', 'safe_fallback')"),
        postgresql_where=sa.text("status IN ('accepted', 'safe_fallback')"),
    )

    with op.batch_alter_table("judge_evaluations") as batch_op:
        batch_op.add_column(
            sa.Column("quality_policy_version", sa.String(length=100), nullable=True)
        )
    op.execute("UPDATE judge_evaluations SET quality_policy_version = 'quality-policy-v0'")
    with op.batch_alter_table("judge_evaluations") as batch_op:
        batch_op.alter_column(
            "quality_policy_version",
            existing_type=sa.String(length=100),
            nullable=False,
            server_default="quality-policy-v1",
        )
    op.execute("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    op.execute("PRAGMA foreign_keys=OFF")
    op.drop_index(
        "uq_feedback_records_workflow_released",
        table_name="feedback_records",
    )
    with op.batch_alter_table("feedback_records") as batch_op:
        batch_op.drop_constraint(
            "fk_feedback_records_workflow_submission",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_feedback_records_workflow_run_id_workflow_runs",
            "workflow_runs",
            ["workflow_run_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    with op.batch_alter_table("judge_evaluations") as batch_op:
        batch_op.drop_column("quality_policy_version")

    with op.batch_alter_table("workflow_runs") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_workflow_runs_workflow_retry_shape"),
            type_="check",
        )
        batch_op.drop_constraint(
            op.f("ck_workflow_runs_workflow_latency"),
            type_="check",
        )
        batch_op.drop_constraint(
            op.f("ck_workflow_runs_workflow_execution_attempt_count"),
            type_="check",
        )
        batch_op.drop_constraint(
            op.f("ck_workflow_runs_workflow_failure_shape"),
            type_="check",
        )
        batch_op.drop_constraint(
            op.f("ck_workflow_runs_workflow_terminal_state"),
            type_="check",
        )
        batch_op.drop_constraint(
            "uq_workflow_runs_id_submission",
            type_="unique",
        )
        batch_op.drop_column("task_id")
        batch_op.drop_column("course_id")
        batch_op.drop_column("latency_ms")
        batch_op.drop_column("next_retry_at")
        batch_op.drop_column("execution_attempt_count")
        batch_op.drop_column("execution_token")
        batch_op.create_check_constraint(
            op.f("ck_workflow_runs_workflow_terminal_state"),
            "((current_stage IN ('completed', 'failed')) "
            "AND final_outcome IS NOT NULL AND completed_at IS NOT NULL) OR "
            "((current_stage NOT IN ('completed', 'failed')) "
            "AND final_outcome IS NULL AND completed_at IS NULL)",
        )
        batch_op.create_check_constraint(
            op.f("ck_workflow_runs_workflow_failure_shape"),
            "(current_stage = 'failed' AND failure_category IS NOT NULL) OR "
            "(current_stage <> 'failed' AND failure_category IS NULL)",
        )
    op.execute("PRAGMA foreign_keys=ON")
