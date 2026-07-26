"""Add append-only audit events before research exports.

Revision ID: 20260725_0007
Revises: 20260725_0006
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260725_0007"
down_revision: str | None = "20260725_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor_reference", sa.String(length=255), nullable=False),
        sa.Column(
            "action",
            _enum(
                "feedback_generation_started",
                "feedback_generation_completed",
                "feedback_judged",
                "feedback_regenerated",
                "feedback_fallback_used",
                "feedback_viewed",
                "feedback_reported",
                "research_export_created",
                "workflow_completed",
                "workflow_failed",
                name="audit_action",
            ),
            nullable=False,
        ),
        sa.Column(
            "outcome",
            _enum("success", "failure", name="audit_outcome"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=False),
        sa.Column("failure_category", sa.String(length=100), nullable=True),
        sa.Column("deduplication_key", sa.String(length=255), nullable=False),
        sa.CheckConstraint(
            "(outcome = 'failure' AND failure_category IS NOT NULL) OR "
            "(outcome = 'success' AND failure_category IS NULL)",
            name="ck_audit_events_audit_failure_shape",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
        sa.UniqueConstraint(
            "deduplication_key",
            name="uq_audit_events_deduplication_key",
        ),
    )
    op.create_index(
        "ix_audit_events_correlation_time",
        "audit_events",
        ["correlation_id", "occurred_at"],
    )
    op.create_index(
        "ix_audit_events_action_time",
        "audit_events",
        ["action", "occurred_at"],
    )
    op.create_index(
        "ix_audit_events_actor_time",
        "audit_events",
        ["actor_reference", "occurred_at"],
    )

    # SQLite is the locked deployment target. These triggers make append-only
    # semantics hold even when SQL is executed outside SQLAlchemy.
    op.execute(
        "CREATE TRIGGER audit_events_prevent_update "
        "BEFORE UPDATE ON audit_events "
        "BEGIN SELECT RAISE(ABORT, 'audit_events_append_only'); END"
    )
    op.execute(
        "CREATE TRIGGER audit_events_prevent_delete "
        "BEFORE DELETE ON audit_events "
        "BEGIN SELECT RAISE(ABORT, 'audit_events_append_only'); END"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_prevent_delete")
    op.execute("DROP TRIGGER IF EXISTS audit_events_prevent_update")
    op.drop_index("ix_audit_events_actor_time", table_name="audit_events")
    op.drop_index("ix_audit_events_action_time", table_name="audit_events")
    op.drop_index("ix_audit_events_correlation_time", table_name="audit_events")
    op.drop_table("audit_events")
