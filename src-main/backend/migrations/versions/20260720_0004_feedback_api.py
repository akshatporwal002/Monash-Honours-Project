"""Add feedback API workflow lifecycle, source attributions, and reports.

Revision ID: 20260720_0004
Revises: 20260720_0003
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0004"
down_revision: str | None = "20260720_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    op.execute("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("workflow_runs") as batch_op:
        batch_op.add_column(
            sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("failure_category", sa.String(length=100), nullable=True))
        batch_op.create_check_constraint(
            op.f("ck_workflow_runs_workflow_failure_shape"),
            "(current_stage = 'failed' AND failure_category IS NOT NULL) OR "
            "(current_stage <> 'failed' AND failure_category IS NULL)",
        )

    with op.batch_alter_table("feedback_records") as batch_op:
        batch_op.add_column(
            sa.Column(
                "source_attributions",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )

    op.create_table(
        "feedback_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("feedback_id", sa.String(length=36), nullable=False),
        sa.Column("reporter_reference", sa.String(length=255), nullable=False),
        sa.Column(
            "category",
            _enum(
                "incorrect",
                "unsafe",
                "unclear",
                "citation_issue",
                "other",
                name="feedback_report_category",
            ),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "note IS NULL OR length(note) BETWEEN 1 AND 2000",
            name=op.f("ck_feedback_reports_feedback_report_note_length"),
        ),
        sa.ForeignKeyConstraint(
            ["feedback_id"],
            ["feedback_records.id"],
            name="fk_feedback_reports_feedback_id_feedback_records",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_feedback_reports"),
        sa.UniqueConstraint(
            "feedback_id",
            "reporter_reference",
            name="uq_feedback_reports_feedback_reporter",
        ),
    )
    op.execute("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    op.execute("PRAGMA foreign_keys=OFF")
    op.drop_table("feedback_reports")
    with op.batch_alter_table("feedback_records") as batch_op:
        batch_op.drop_column("source_attributions")
    with op.batch_alter_table("workflow_runs") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_workflow_runs_workflow_failure_shape"),
            type_="check",
        )
        batch_op.drop_column("failure_category")
        batch_op.drop_column("lease_expires_at")
    op.execute("PRAGMA foreign_keys=ON")
