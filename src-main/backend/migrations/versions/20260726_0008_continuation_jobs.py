"""Add durable fenced continuation jobs.

Revision ID: 20260726_0008
Revises: 20260725_0007
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260726_0008"
down_revision: str | None = "20260725_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    op.create_table(
        "worker_heartbeats",
        sa.Column("slot", sa.String(length=32), nullable=False),
        sa.Column("worker_id", sa.String(length=36), nullable=False),
        sa.Column(
            "last_heartbeat_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "slot = 'primary'",
            name="worker_heartbeat_singleton",
        ),
        sa.PrimaryKeyConstraint("slot", name="pk_worker_heartbeats"),
    )
    op.create_table(
        "continuation_jobs",
        sa.Column("workflow_run_id", sa.String(length=36), nullable=False),
        sa.Column(
            "pseudonymous_actor_reference",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column("course_reference", sa.String(length=255), nullable=False),
        sa.Column(
            "completed_task_reference",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column(
            "state",
            _enum(
                "pending",
                "running",
                "retry_scheduled",
                "completed",
                "failed",
                name="continuation_state",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "progress_recorded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "processing_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("execution_token", sa.String(length=36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_task_reference", sa.String(length=255), nullable=True),
        sa.Column(
            "failure_category",
            _enum(
                "invalid_continuation_notice",
                "continuation_repository_not_configured",
                "progress_adapter_not_configured",
                "next_task_recommender_not_configured",
                "progress_adapter_unavailable",
                "next_task_recommender_unavailable",
                "invalid_next_task_reference",
                "continuation_persistence_unavailable",
                name="continuation_failure_category",
            ),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "processing_attempts BETWEEN 0 AND 3",
            name="continuation_processing_attempts",
        ),
        sa.CheckConstraint(
            "(state = 'pending' AND processing_attempts = 0 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NULL AND next_task_reference IS NULL "
            "AND failure_category IS NULL AND completed_at IS NULL) OR "
            "(state = 'running' AND processing_attempts BETWEEN 1 AND 3 "
            "AND execution_token IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND next_retry_at IS NULL AND next_task_reference IS NULL "
            "AND failure_category IS NULL AND completed_at IS NULL) OR "
            "(state = 'retry_scheduled' AND processing_attempts BETWEEN 1 AND 2 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NOT NULL AND next_task_reference IS NULL "
            "AND failure_category IS NOT NULL AND completed_at IS NULL) OR "
            "(state = 'completed' AND processing_attempts BETWEEN 1 AND 3 "
            "AND progress_recorded = 1 AND execution_token IS NULL "
            "AND lease_expires_at IS NULL AND next_retry_at IS NULL "
            "AND next_task_reference IS NOT NULL AND failure_category IS NULL "
            "AND completed_at IS NOT NULL) OR "
            "(state = 'failed' AND processing_attempts BETWEEN 1 AND 3 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NULL AND next_task_reference IS NULL "
            "AND failure_category IS NOT NULL AND completed_at IS NOT NULL)",
            name="continuation_state_shape",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["workflow_runs.id"],
            name="fk_continuation_jobs_workflow_run_id_workflow_runs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "workflow_run_id",
            name="pk_continuation_jobs",
        ),
    )
    op.create_index(
        "ix_continuation_jobs_claim",
        "continuation_jobs",
        [
            "state",
            "next_retry_at",
            "lease_expires_at",
            "created_at",
        ],
    )
    op.create_index(
        "ix_continuation_jobs_course_state",
        "continuation_jobs",
        ["course_reference", "state"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_continuation_jobs_course_state",
        table_name="continuation_jobs",
    )
    op.drop_index(
        "ix_continuation_jobs_claim",
        table_name="continuation_jobs",
    )
    op.drop_table("continuation_jobs")
    op.drop_table("worker_heartbeats")
