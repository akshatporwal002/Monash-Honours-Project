"""Preserve assessor resolution reasons and learner notices.

Revision ID: 20260909_0034
Revises: 20260908_0033
"""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0034"
down_revision = "20260908_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("appeal_resolutions"):
        op.create_table(
            "appeal_resolutions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "appeal_id",
                sa.String(36),
                sa.ForeignKey("appeals_or_corrections.id", ondelete="RESTRICT"),
                nullable=False,
                unique=True,
            ),
            sa.Column(
                "assessor_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("decision_revision", sa.Integer(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("learner_notice", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    for operation in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER IF NOT EXISTS appeal_resolutions_no_{operation.lower()} BEFORE {operation} ON appeal_resolutions BEGIN SELECT RAISE(ABORT, 'Appeal resolutions are immutable'); END"
        )
    op.execute(
        "CREATE TRIGGER IF NOT EXISTS appeal_resolutions_no_replace BEFORE INSERT ON appeal_resolutions WHEN EXISTS (SELECT 1 FROM appeal_resolutions WHERE id=NEW.id OR appeal_id=NEW.appeal_id) BEGIN SELECT RAISE(ABORT, 'Appeal resolutions are immutable'); END"
    )


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT count(*) FROM appeal_resolutions")).scalar_one():
        raise RuntimeError("cannot downgrade populated appeal resolution history")
    op.drop_table("appeal_resolutions")
