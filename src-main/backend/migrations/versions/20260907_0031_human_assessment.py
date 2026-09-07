"""Preserve human criterion decisions as append-only assessment history.

Revision ID: 20260907_0031
Revises: 20260907_0030
"""

import sqlalchemy as sa
from alembic import op

revision = "20260907_0031"
down_revision = "20260907_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.models.human_assessment import (
        HumanAssessmentAction,
        HumanCriterionDecision,
        human_review_guards,
    )

    connection = op.get_bind()
    for model in (HumanAssessmentAction, HumanCriterionDecision):
        model.__table__.create(connection, checkfirst=True)
    if connection.dialect.name == "sqlite":
        for _, _, statement in human_review_guards():
            op.execute(sa.text(statement))


def downgrade() -> None:
    connection = op.get_bind()
    tables = ("human_criterion_decisions", "human_assessment_actions")
    for table in tables:
        if (
            sa.inspect(connection).has_table(table)
            and connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        ):
            raise RuntimeError(
                "Human assessment history is protected; restore a verified backup instead"
            )
    for table in tables:
        if sa.inspect(connection).has_table(table):
            op.drop_table(table)
