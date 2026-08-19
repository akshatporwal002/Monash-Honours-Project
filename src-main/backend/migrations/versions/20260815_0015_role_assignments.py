"""Add explicit course-scoped role assignments.

Revision ID: 20260815_0015
Revises: 20260726_0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0015"
down_revision: str | None = "20260726_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _refuse_populated_downgrade() -> None:
    connection = op.get_bind()
    if (
        sa.inspect(connection).has_table("role_assignments")
        and connection.execute(sa.text("SELECT COUNT(*) FROM role_assignments")).scalar_one()
    ):
        raise RuntimeError(
            "cannot downgrade populated role assignment history; restore a verified backup instead"
        )


def upgrade() -> None:
    op.create_table(
        "role_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("subject_user_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "assessor",
                "research",
                name="scoped_role",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.Integer(), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column("supersedes_assignment_id", sa.String(length=36), nullable=True),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_role_assignments_role_assignment_version"),
        ),
        sa.CheckConstraint(
            "length(trim(reason)) > 0",
            name=op.f("ck_role_assignments_role_assignment_reason"),
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name=op.f("ck_role_assignments_role_assignment_valid_window"),
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revoked_by_user_id IS NULL "
            "AND revocation_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoked_by_user_id IS NOT NULL "
            "AND length(trim(revocation_reason)) > 0)",
            name=op.f("ck_role_assignments_role_assignment_revocation_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_user_id"],
            ["users.id"],
            name=op.f("fk_role_assignments_assigned_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_role_assignments_course_id_courses"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_user_id"],
            ["users.id"],
            name=op.f("fk_role_assignments_revoked_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["subject_user_id"],
            ["users.id"],
            name=op.f("fk_role_assignments_subject_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_assignment_id"],
            ["role_assignments.id"],
            name=op.f("fk_role_assignments_supersedes_assignment_id_role_assignments"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_assignments")),
        sa.UniqueConstraint(
            "subject_user_id",
            "course_id",
            "role",
            "version",
            name="uq_role_assignments_subject_course_role_version",
        ),
    )
    op.create_index(
        "ix_role_assignments_subject_course_role_active",
        "role_assignments",
        ["subject_user_id", "course_id", "role", "revoked_at"],
    )


def downgrade() -> None:
    _refuse_populated_downgrade()
    op.drop_index(
        "ix_role_assignments_subject_course_role_active",
        table_name="role_assignments",
    )
    op.drop_table("role_assignments")
