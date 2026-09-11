"""Retain complete feedback reviews; historical v1 judgements remain unchanged."""

import sqlalchemy as sa
from alembic import context, op

from app.models.feedback_review_history import feedback_review_guards

revision = "20260911_0055"
down_revision = "20260911_0054"
branch_labels = None
depends_on = None


def upgrade():
    existing = (
        None
        if context.is_offline_mode()
        else next(
            (
                column
                for column in sa.inspect(op.get_bind()).get_columns("judge_evaluations")
                if column["name"] == "quality_review"
            ),
            None,
        )
    )
    if existing is None:
        op.add_column(
            "judge_evaluations",
            sa.Column("quality_review", sa.JSON(none_as_null=True), nullable=True),
        )
    elif (
        not isinstance(existing["type"], sa.JSON)
        or not existing["nullable"]
        or existing.get("default") is not None
        or existing.get("primary_key")
        or existing.get("computed") is not None
    ):
        raise RuntimeError("Existing judge_evaluations.quality_review has incompatible shape")
    # Historical replay or a partially applied upgrade may already have the
    # column. Preserve every value and still install any missing history guards.
    for statement in feedback_review_guards():
        op.execute(statement)


def downgrade():
    raise RuntimeError("Feedback review history is protected; restore a verified backup instead")
