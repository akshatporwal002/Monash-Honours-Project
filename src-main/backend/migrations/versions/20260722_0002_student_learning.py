"""Add student learning experience tables.

Revision ID: 20260722_0002
Revises: 20260713_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260722_0002"
down_revision: str | None = "20260713_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    op.create_table(
        "student_profiles",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("streak_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_student_profiles"),
    )
    op.create_table(
        "learning_tasks",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("module", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("task_type", _enum("quiz", "code", "circuit", name="task_type"), nullable=False),
        sa.Column("difficulty", sa.String(30), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("starter_code", sa.Text(), nullable=True),
        sa.Column("expected_answer", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_learning_tasks"),
        sa.UniqueConstraint("slug", name="uq_learning_tasks_slug"),
    )
    op.create_table(
        "achievements",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("icon", sa.String(20), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_achievements"),
        sa.UniqueConstraint("code", name="uq_achievements_code"),
    )
    op.create_table(
        "student_submissions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False, server_default=""),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("circuit", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            _enum("draft", "submitted", "completed", name="submission_status"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "score BETWEEN 0 AND 100", name="ck_student_submissions_student_submission_score"
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["student_profiles.id"],
            ondelete="CASCADE",
            name="fk_student_submissions_student_id_student_profiles",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["learning_tasks.id"],
            ondelete="CASCADE",
            name="fk_student_submissions_task_id_learning_tasks",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_student_submissions"),
        sa.UniqueConstraint("student_id", "task_id", name="uq_student_submissions_student_task"),
    )
    op.create_table(
        "student_achievements",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("achievement_id", sa.String(36), nullable=False),
        sa.Column(
            "earned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["student_profiles.id"],
            ondelete="CASCADE",
            name="fk_student_achievements_student_id_student_profiles",
        ),
        sa.ForeignKeyConstraint(
            ["achievement_id"],
            ["achievements.id"],
            ondelete="CASCADE",
            name="fk_student_achievements_achievement_id_achievements",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_student_achievements"),
        sa.UniqueConstraint("student_id", "achievement_id", name="uq_student_achievement"),
    )
    op.create_table(
        "student_notifications",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column(
            "kind",
            _enum("reminder", "achievement", "feedback", name="notification_kind"),
            nullable=False,
        ),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["student_profiles.id"],
            ondelete="CASCADE",
            name="fk_student_notifications_student_id_student_profiles",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_student_notifications"),
    )


def downgrade() -> None:
    op.drop_table("student_notifications")
    op.drop_table("student_achievements")
    op.drop_table("student_submissions")
    op.drop_table("achievements")
    op.drop_table("learning_tasks")
    op.drop_table("student_profiles")
