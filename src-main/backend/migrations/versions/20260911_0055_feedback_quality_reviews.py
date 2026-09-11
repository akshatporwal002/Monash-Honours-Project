"""Retain complete feedback reviews; historical v1 judgements remain unchanged."""

import sqlalchemy as sa
from alembic import op

from app.models.feedback_review_history import feedback_review_guards

revision = "20260911_0055"
down_revision = "20260911_0054"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "judge_evaluations", sa.Column("quality_review", sa.JSON(none_as_null=True), nullable=True)
    )
    for statement in feedback_review_guards():
        op.execute(statement)


def downgrade():
    raise RuntimeError("Feedback review history is protected; restore a verified backup instead")
