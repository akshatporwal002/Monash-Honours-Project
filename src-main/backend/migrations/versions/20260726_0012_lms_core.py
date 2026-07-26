"""Add the canonical minimal LMS domain.

Revision ID: 20260726_0012
Revises: 20260726_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260726_0012"
down_revision: str | None = "20260726_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(
        *values,
        name=name,
        native_enum=False,
        create_constraint=True,
    )


def upgrade() -> None:
    with op.batch_alter_table("learning_tasks") as batch_op:
        batch_op.drop_constraint("task_type", type_="check")
        batch_op.alter_column(
            "task_type",
            existing_type=_enum("quiz", "code", "circuit", name="task_type"),
            type_=_enum(
                "multiple_choice",
                "multiple_answer",
                "short_answer",
                "code_explanation",
                "code_completion",
                "quantum_circuit",
                "quiz",
                "code",
                "circuit",
                name="task_type",
            ),
            existing_nullable=False,
        )

    with op.batch_alter_table("student_profiles") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_student_profiles_user_id",
            ["user_id"],
        )
        batch_op.create_foreign_key(
            "fk_student_profiles_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.create_table(
        "courses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("educator_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "state",
            _enum("draft", "published", "archived", name="course_state"),
            nullable=False,
        ),
        sa.Column("enrollment_open", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["educator_id"],
            ["users.id"],
            name=op.f("fk_courses_educator_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_courses")),
        sa.UniqueConstraint("code", name="uq_courses_code"),
    )
    op.create_index(
        "ix_courses_educator_state",
        "courses",
        ["educator_id", "state"],
    )

    op.create_table(
        "course_modules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "position > 0",
            name=op.f("ck_course_modules_course_module_position"),
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_course_modules_course_id_courses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_modules")),
        sa.UniqueConstraint(
            "course_id",
            "position",
            name="uq_course_modules_course_position",
        ),
    )

    op.create_table(
        "learning_outcomes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("module_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column(
            "kind",
            _enum("weekly", "topic", name="outcome_kind"),
            nullable=False,
        ),
        sa.Column("week_number", sa.Integer(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "position > 0",
            name=op.f("ck_learning_outcomes_learning_outcome_position"),
        ),
        sa.CheckConstraint(
            "(kind = 'weekly' AND week_number IS NOT NULL AND week_number > 0) OR "
            "(kind = 'topic' AND week_number IS NULL)",
            name=op.f("ck_learning_outcomes_learning_outcome_kind_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["module_id"],
            ["course_modules.id"],
            name=op.f("fk_learning_outcomes_module_id_course_modules"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_outcomes")),
        sa.UniqueConstraint(
            "module_id",
            "position",
            name="uq_learning_outcomes_module_position",
        ),
    )

    op.create_table(
        "enrollments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            _enum("active", "completed", "withdrawn", name="enrollment_status"),
            nullable=False,
        ),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_enrollments_course_id_courses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.id"],
            name=op.f("fk_enrollments_student_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_enrollments")),
        sa.UniqueConstraint(
            "course_id",
            "student_id",
            name="uq_enrollments_course_student",
        ),
    )
    op.create_index(
        "ix_enrollments_student_status",
        "enrollments",
        ["student_id", "status"],
    )

    op.create_table(
        "submission_drafts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("circuit", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.id"],
            name=op.f("fk_submission_drafts_student_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["learning_tasks.id"],
            name=op.f("fk_submission_drafts_task_id_learning_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submission_drafts")),
        sa.UniqueConstraint(
            "student_id",
            "task_id",
            name="uq_submission_drafts_student_task",
        ),
    )

    op.create_table(
        "submission_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("draft_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            _enum("submitted", "completed", name="attempt_status"),
            nullable=False,
        ),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("circuit", sa.JSON(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("feedback_reference", sa.String(length=255), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "attempt_number > 0",
            name=op.f("ck_submission_attempts_submission_attempt_number"),
        ),
        sa.CheckConstraint(
            "score BETWEEN 0 AND 100",
            name=op.f("ck_submission_attempts_submission_attempt_score"),
        ),
        sa.ForeignKeyConstraint(
            ["draft_id"],
            ["submission_drafts.id"],
            name=op.f("fk_submission_attempts_draft_id_submission_drafts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.id"],
            name=op.f("fk_submission_attempts_student_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["learning_tasks.id"],
            name=op.f("fk_submission_attempts_task_id_learning_tasks"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submission_attempts")),
        sa.UniqueConstraint(
            "student_id",
            "task_id",
            "attempt_number",
            name="uq_submission_attempts_student_task_number",
        ),
    )
    op.create_index(
        "ix_submission_attempts_student_time",
        "submission_attempts",
        ["student_id", "submitted_at"],
    )
    op.create_index(
        "ix_submission_attempts_task_status",
        "submission_attempts",
        ["task_id", "status"],
    )

    op.create_table(
        "task_point_awards",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_id", sa.String(length=36), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "points >= 0",
            name=op.f("ck_task_point_awards_task_point_award_points"),
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["submission_attempts.id"],
            name=op.f("fk_task_point_awards_attempt_id_submission_attempts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.id"],
            name=op.f("fk_task_point_awards_student_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["learning_tasks.id"],
            name=op.f("fk_task_point_awards_task_id_learning_tasks"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_point_awards")),
        sa.UniqueConstraint(
            "student_id",
            "task_id",
            name="uq_task_point_awards_student_task",
        ),
        sa.UniqueConstraint(
            "attempt_id",
            name="uq_task_point_awards_attempt",
        ),
    )

    op.create_table(
        "reminders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("dedupe_window", sa.String(length=40), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.id"],
            name=op.f("fk_reminders_student_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["learning_tasks.id"],
            name=op.f("fk_reminders_task_id_learning_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reminders")),
        sa.UniqueConstraint(
            "student_id",
            "task_id",
            "dedupe_window",
            name="uq_reminders_student_task_window",
        ),
    )
    op.create_index(
        "ix_reminders_student_time",
        "reminders",
        ["student_id", "created_at"],
    )

    op.create_table(
        "system_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_system_settings_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_system_settings")),
        sa.UniqueConstraint("key", name="uq_system_settings_key"),
    )

    op.create_table(
        "recommendations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "rank BETWEEN 1 AND 3",
            name=op.f("ck_recommendations_recommendation_rank"),
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.id"],
            name=op.f("fk_recommendations_student_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["learning_tasks.id"],
            name=op.f("fk_recommendations_task_id_learning_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendations")),
        sa.UniqueConstraint(
            "student_id",
            "task_id",
            name="uq_recommendations_student_task",
        ),
    )
    op.create_index(
        "ix_recommendations_student_active",
        "recommendations",
        ["student_id", "is_active", "rank"],
    )

    op.create_table(
        "platform_audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_platform_audit_events_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_audit_events")),
    )
    op.create_index(
        "ix_platform_audit_events_actor_time",
        "platform_audit_events",
        ["actor_id", "occurred_at"],
    )
    op.create_index(
        "ix_platform_audit_events_resource",
        "platform_audit_events",
        ["resource_type", "resource_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_platform_audit_events_resource",
        table_name="platform_audit_events",
    )
    op.drop_index(
        "ix_platform_audit_events_actor_time",
        table_name="platform_audit_events",
    )
    op.drop_table("platform_audit_events")
    op.drop_index(
        "ix_recommendations_student_active",
        table_name="recommendations",
    )
    op.drop_table("recommendations")
    op.drop_table("system_settings")
    op.drop_index("ix_reminders_student_time", table_name="reminders")
    op.drop_table("reminders")
    op.drop_table("task_point_awards")
    op.drop_index(
        "ix_submission_attempts_task_status",
        table_name="submission_attempts",
    )
    op.drop_index(
        "ix_submission_attempts_student_time",
        table_name="submission_attempts",
    )
    op.drop_table("submission_attempts")
    op.drop_table("submission_drafts")
    op.drop_index("ix_enrollments_student_status", table_name="enrollments")
    op.drop_table("enrollments")
    op.drop_table("learning_outcomes")
    op.drop_table("course_modules")
    op.drop_index("ix_courses_educator_state", table_name="courses")
    op.drop_table("courses")

    with op.batch_alter_table("student_profiles") as batch_op:
        batch_op.drop_constraint(
            "fk_student_profiles_user_id_users",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "uq_student_profiles_user_id",
            type_="unique",
        )
        batch_op.drop_column("user_id")

    with op.batch_alter_table("learning_tasks") as batch_op:
        batch_op.drop_constraint("task_type", type_="check")
        batch_op.alter_column(
            "task_type",
            existing_type=_enum(
                "multiple_choice",
                "multiple_answer",
                "short_answer",
                "code_explanation",
                "code_completion",
                "quantum_circuit",
                "quiz",
                "code",
                "circuit",
                name="task_type",
            ),
            type_=_enum("quiz", "code", "circuit", name="task_type"),
            existing_nullable=False,
        )
