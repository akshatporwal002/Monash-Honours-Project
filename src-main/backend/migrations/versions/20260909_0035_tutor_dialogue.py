"""Preserve scoped tutor dialogue and quality decisions.

Revision ID: 20260909_0035
Revises: 20260909_0034
"""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0035"
down_revision = "20260909_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("tutor_turns"):
        op.create_table(
            "tutor_turns",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "student_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "task_id",
                sa.String(36),
                sa.ForeignKey("learning_tasks.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "assessment_work_start_id",
                sa.String(36),
                sa.ForeignKey("assessment_work_starts.id", ondelete="RESTRICT"),
            ),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("request_key", sa.String(128), nullable=False),
            sa.Column("context_token", sa.String(64), nullable=False),
            sa.Column("learner_text", sa.Text(), nullable=False),
            sa.Column("reply", sa.Text(), nullable=False),
            sa.Column("kind", sa.String(24), nullable=False),
            sa.Column("hint_index", sa.Integer()),
            sa.Column("context", sa.JSON(), nullable=False),
            sa.Column("quality", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("student_id", "task_id", "revision", name="uq_tutor_revision"),
            sa.UniqueConstraint("student_id", "task_id", "request_key", name="uq_tutor_request"),
        )
    for operation in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER IF NOT EXISTS tutor_turns_no_{operation.lower()} BEFORE {operation} ON tutor_turns BEGIN SELECT RAISE(ABORT, 'Tutor history is immutable'); END"
        )
    op.execute(
        "CREATE TRIGGER IF NOT EXISTS tutor_turns_no_replace BEFORE INSERT ON tutor_turns WHEN EXISTS (SELECT 1 FROM tutor_turns WHERE id=NEW.id OR (student_id=NEW.student_id AND task_id=NEW.task_id AND (revision=NEW.revision OR request_key=NEW.request_key))) BEGIN SELECT RAISE(ABORT, 'Tutor history is immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER IF NOT EXISTS tutor_turns_work_scope BEFORE INSERT ON tutor_turns WHEN NEW.assessment_work_start_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM assessment_work_starts WHERE id=NEW.assessment_work_start_id AND student_id=NEW.student_id AND task_id=NEW.task_id) BEGIN SELECT RAISE(ABORT, 'Tutor work scope differs'); END"
    )


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT count(*) FROM tutor_turns")).scalar_one():
        raise RuntimeError("cannot downgrade populated tutor history")
    op.drop_table("tutor_turns")
