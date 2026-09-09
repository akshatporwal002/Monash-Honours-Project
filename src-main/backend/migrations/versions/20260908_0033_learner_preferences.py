"""Append-only explicit learner preferences.

Revision ID: 20260908_0033
Revises: 20260908_0032
"""

from importlib import import_module

import sqlalchemy as sa
from alembic import op

revision = "20260908_0033"
down_revision = "20260908_0032"
branch_labels = None
depends_on = None
TABLE = "learner_preference_revisions"


def upgrade():
    if sa.inspect(op.get_bind()).has_table(TABLE):
        _protect_history()
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "learner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("request_key", sa.String(100), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("pace", sa.String(20), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("explanation_detail", sa.String(20), nullable=False),
        sa.Column(
            "breaks", sa.Boolean(create_constraint=True, name="preference_breaks"), nullable=False
        ),
        sa.Column(
            "repeat_practice",
            sa.Boolean(create_constraint=True, name="preference_repeat"),
            nullable=False,
        ),
        sa.Column(
            "personalisation_enabled",
            sa.Boolean(create_constraint=True, name="preference_enabled"),
            nullable=False,
        ),
        sa.Column("support_amount", sa.String(20), nullable=False),
        sa.Column("feedback_form", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("learner_id", "version", name="uq_preference_version"),
        sa.UniqueConstraint("learner_id", "request_key", name="uq_preference_request"),
        sa.CheckConstraint("version > 0", name="preference_version_positive"),
        sa.CheckConstraint("pace IN ('self_paced', 'stepwise')", name="preference_pace"),
        sa.CheckConstraint("format IN ('text', 'stepwise')", name="preference_format"),
        sa.CheckConstraint("explanation_detail IN ('brief', 'detailed')", name="preference_detail"),
        sa.CheckConstraint(
            "support_amount IN ('standard', 'on_request')", name="preference_support"
        ),
        sa.CheckConstraint("feedback_form IN ('inline', 'expandable')", name="preference_feedback"),
        sa.CheckConstraint("action IN ('save', 'reset')", name="preference_action"),
    )
    _protect_history()


def _protect_history():
    if op.get_bind().dialect.name == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(
                sa.text(
                    f"CREATE TRIGGER IF NOT EXISTS {TABLE}_no_{action.lower()} BEFORE {action} ON {TABLE} BEGIN SELECT RAISE(ABORT, 'Preference history is protected'); END"
                )
            )
        op.execute(
            sa.text(
                f"CREATE TRIGGER IF NOT EXISTS {TABLE}_append BEFORE INSERT ON {TABLE} WHEN NEW.version != COALESCE((SELECT MAX(version) FROM {TABLE} WHERE learner_id=NEW.learner_id), 0) + 1 OR EXISTS(SELECT 1 FROM {TABLE} WHERE id=NEW.id OR (learner_id=NEW.learner_id AND request_key=NEW.request_key)) BEGIN SELECT RAISE(ABORT, 'Preference history is protected'); END"
            )
        )


def downgrade():
    for protected in (
        "learner_model_annotations",
        "learner_model_correction_reviews",
        "learner_model_correction_snapshot_links",
    ):
        if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {protected}")).scalar_one():
            raise RuntimeError("Correction history is protected; restore a verified backup")
    if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {TABLE}")).scalar_one():
        raise RuntimeError(
            "Cannot downgrade populated preference history; restore a verified backup"
        )
    import_module("migrations.versions.20260907_0030_learning_episodes")._preflight_downgrade()
    op.drop_table(TABLE)
