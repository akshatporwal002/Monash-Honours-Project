"""Add durable terminal integration outbox and measurement links.

Revision ID: 20260726_0010
Revises: 20260726_0009
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260726_0010"
down_revision: str | None = "20260726_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    # Legacy usage rows remain explicitly incomplete. New writes populate these
    # fields from provider response presence rather than token values.
    op.add_column(
        "feedback_records",
        sa.Column(
            "usage_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "judge_evaluations",
        sa.Column(
            "usage_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    with op.batch_alter_table("learning_events") as batch:
        batch.add_column(sa.Column("workflow_reference", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_learning_events_workflow_reference_workflow_runs",
            "workflow_runs",
            ["workflow_reference"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_index(
            "ix_learning_events_event_workflow",
            ["event_type", "workflow_reference"],
        )

    # Earlier stale-lease recovery was not bounded. Preserve terminal evidence,
    # but terminally sanitize any legacy nonterminal row already over the cap.
    op.execute(
        "UPDATE research_evaluations "
        "SET status = 'failed', processing_attempts = 3, "
        "execution_token = NULL, lease_expires_at = NULL, "
        "failure_category = 'baseline_worker_lease_expired', "
        "usage_complete = 0, comparable = 0, "
        "completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP) "
        "WHERE processing_attempts > 3 AND status IN ('pending', 'running')"
    )
    op.execute(
        "UPDATE research_evaluations SET processing_attempts = 3 WHERE processing_attempts > 3"
    )

    with op.batch_alter_table("research_evaluations") as batch:
        batch.drop_constraint(
            op.f("ck_research_evaluations_ck_research_evaluations_research_processing_attempts"),
            type_="check",
        )
        batch.create_check_constraint(
            op.f("ck_research_evaluations_research_processing_attempts"),
            "processing_attempts BETWEEN 0 AND 3",
        )
        batch.add_column(sa.Column("correlation_id", sa.String(length=36), nullable=True))
        batch.create_index(
            "ix_research_evaluations_correlation",
            ["correlation_id"],
        )

    op.create_table(
        "terminal_integration_outbox",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workflow_run_id", sa.String(length=36), nullable=False),
        sa.Column(
            "integration_type",
            _enum(
                "research_pair",
                "continuation",
                name="terminal_integration_type",
            ),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "state",
            _enum(
                "pending",
                "running",
                "retry_scheduled",
                "completed",
                "failed",
                name="terminal_integration_state",
            ),
            nullable=False,
            server_default="pending",
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
        sa.Column(
            "failure_category",
            _enum(
                "invalid_terminal_integration_payload",
                "terminal_integration_unavailable",
                "terminal_integration_persistence_unavailable",
                name="terminal_integration_failure_category",
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
            name="terminal_integration_processing_attempts",
        ),
        sa.CheckConstraint(
            "(state = 'pending' AND processing_attempts = 0 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NULL AND failure_category IS NULL "
            "AND completed_at IS NULL) OR "
            "(state = 'running' AND processing_attempts BETWEEN 1 AND 3 "
            "AND execution_token IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND next_retry_at IS NULL AND failure_category IS NULL "
            "AND completed_at IS NULL) OR "
            "(state = 'retry_scheduled' AND processing_attempts BETWEEN 1 AND 2 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NOT NULL AND failure_category IS NOT NULL "
            "AND completed_at IS NULL) OR "
            "(state = 'completed' AND processing_attempts BETWEEN 1 AND 3 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NULL AND failure_category IS NULL "
            "AND completed_at IS NOT NULL) OR "
            "(state = 'failed' AND processing_attempts BETWEEN 1 AND 3 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NULL AND failure_category IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="terminal_integration_state_shape",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["workflow_runs.id"],
            name="fk_terminal_integration_outbox_workflow_run_id_workflow_runs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_terminal_integration_outbox"),
        sa.UniqueConstraint(
            "workflow_run_id",
            "integration_type",
            name="uq_terminal_integration_outbox_workflow_type",
        ),
    )
    op.create_index(
        "ix_terminal_integration_outbox_claim",
        "terminal_integration_outbox",
        ["state", "next_retry_at", "lease_expires_at", "created_at"],
    )
    op.create_index(
        "ix_terminal_integration_outbox_correlation",
        "terminal_integration_outbox",
        ["correlation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_terminal_integration_outbox_correlation",
        table_name="terminal_integration_outbox",
    )
    op.drop_index(
        "ix_terminal_integration_outbox_claim",
        table_name="terminal_integration_outbox",
    )
    op.drop_table("terminal_integration_outbox")

    with op.batch_alter_table("research_evaluations") as batch:
        batch.drop_index("ix_research_evaluations_correlation")
        batch.drop_column("correlation_id")
        batch.drop_constraint(
            op.f("ck_research_evaluations_research_processing_attempts"),
            type_="check",
        )
        batch.create_check_constraint(
            op.f("ck_research_evaluations_ck_research_evaluations_research_processing_attempts"),
            "processing_attempts >= 0",
        )

    with op.batch_alter_table("learning_events") as batch:
        batch.drop_index("ix_learning_events_event_workflow")
        batch.drop_constraint(
            "fk_learning_events_workflow_reference_workflow_runs",
            type_="foreignkey",
        )
        batch.drop_column("workflow_reference")

    op.drop_column("judge_evaluations", "usage_complete")
    op.drop_column("feedback_records", "usage_complete")
