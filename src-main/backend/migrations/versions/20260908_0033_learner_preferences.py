"""Add append-only learner preference revisions.

Revision ID: 20260908_0033
Revises: 20260908_0032
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0033"
down_revision: str | None = "20260908_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "learner_preference_revisions"


def upgrade() -> None:
    # Several protected-history tests deliberately re-stamp older revisions on
    # a database created from current metadata.  Treat that complete table as
    # an already-applied additive migration, as earlier append-only revisions
    # do, rather than attempting a destructive rebuild.
    if sa.inspect(op.get_bind()).has_table(TABLE):
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "learner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("prior_revision_id", sa.String(36), nullable=True),
        sa.Column("pace", sa.String(20), nullable=False),
        sa.Column("format", sa.String(30), nullable=False),
        sa.Column("explanation_detail", sa.String(20), nullable=False),
        sa.Column("optional_breaks_enabled", sa.Boolean(), nullable=False),
        sa.Column("repeat_practice_enabled", sa.Boolean(), nullable=False),
        sa.Column("personalisation_enabled", sa.Boolean(), nullable=False),
        sa.Column("schema_version", sa.String(100), nullable=False),
        sa.Column("actor_reference", sa.String(255), nullable=False),
        sa.Column("correlation_id", sa.String(255), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("revision > 0", name="preference_revision_positive"),
        sa.CheckConstraint("pace IN ('DEFAULT', 'SLOWER', 'FASTER')", name="preference_pace"),
        sa.CheckConstraint(
            "format IN ('NO_PREFERENCE', 'TEXT', 'VISUAL', 'WORKED_EXAMPLE', 'CIRCUIT', 'STEPWISE')",
            name="preference_format",
        ),
        sa.CheckConstraint(
            "explanation_detail IN ('BRIEF', 'STANDARD', 'DETAILED')", name="preference_detail"
        ),
        sa.UniqueConstraint("learner_id", "revision", name="uq_preference_learner_revision"),
        sa.UniqueConstraint(
            "learner_id", "idempotency_key", name="uq_preference_learner_idempotency"
        ),
    )
    op.create_index("ix_preference_current", TABLE, ["learner_id", "revision"])
    op.create_index("ix_preference_history", TABLE, ["learner_id", "occurred_at", "id"])
    op.create_index("ix_preference_correlation", TABLE, ["correlation_id"])
    for operation in ("UPDATE", "DELETE"):
        op.execute(
            sa.text(
                f"CREATE TRIGGER {TABLE}_no_{operation.lower()} BEFORE {operation} ON {TABLE} BEGIN SELECT RAISE(ABORT, 'learner preference revisions are append-only'); END"
            )
        )


def downgrade() -> None:
    count = op.get_bind().execute(sa.text(f"SELECT count(*) FROM {TABLE}")).scalar_one()
    if count:
        raise RuntimeError("cannot downgrade populated learner preference history")
    op.drop_table(TABLE)
