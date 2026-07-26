"""Add the feedback worker claim index.

Revision ID: 20260726_0009
Revises: 20260726_0008
Create Date: 2026-07-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260726_0009"
down_revision: str | None = "20260726_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_workflow_runs_worker_claim",
        "workflow_runs",
        [
            "current_stage",
            "next_retry_at",
            "lease_expires_at",
            "started_at",
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_runs_worker_claim",
        table_name="workflow_runs",
    )
