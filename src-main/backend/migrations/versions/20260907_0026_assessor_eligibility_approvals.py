"""assessor_eligibility_approvals

Revision ID: 20260907_0026
Revises: 20260907_0025
Create Date: 2026-09-07 02:43:14.731504
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0026"
down_revision: str | None = "20260907_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("assessor_eligibility_approvals"):
        op.create_table(
            "assessor_eligibility_approvals",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("course_id", sa.String(length=36), nullable=False),
            sa.Column("subject_user_id", sa.Integer(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("state", sa.String(length=16), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("policy_version", sa.String(length=64), nullable=False),
            sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "state IN ('APPROVED', 'WITHDRAWN')",
                name=op.f("ck_assessor_eligibility_approvals_assessor_eligibility_state"),
            ),
            sa.CheckConstraint(
                "length(trim(reason)) > 0",
                name=op.f("ck_assessor_eligibility_approvals_assessor_eligibility_reason"),
            ),
            sa.CheckConstraint(
                "version > 0",
                name=op.f("ck_assessor_eligibility_approvals_assessor_eligibility_version"),
            ),
            sa.ForeignKeyConstraint(
                ["actor_user_id"],
                ["users.id"],
                name=op.f("fk_assessor_eligibility_approvals_actor_user_id_users"),
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["course_id"],
                ["courses.id"],
                name=op.f("fk_assessor_eligibility_approvals_course_id_courses"),
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["subject_user_id"],
                ["users.id"],
                name=op.f("fk_assessor_eligibility_approvals_subject_user_id_users"),
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_assessor_eligibility_approvals")),
            sa.UniqueConstraint(
                "course_id", "subject_user_id", "version", name="uq_assessor_eligibility_version"
            ),
        )
    if "eligibility_approval_id" not in {
        column["name"] for column in inspector.get_columns("role_assignments")
    }:
        if op.get_bind().dialect.name == "sqlite":
            op.execute(
                sa.text(
                    "ALTER TABLE role_assignments ADD COLUMN eligibility_approval_id VARCHAR(36) REFERENCES assessor_eligibility_approvals(id)"
                )
            )
        else:
            op.add_column(
                "role_assignments",
                sa.Column("eligibility_approval_id", sa.String(36), nullable=True),
            )
            op.create_foreign_key(
                "fk_role_assignments_eligibility_approval_id_assessor_eligibility_approvals",
                "role_assignments",
                "assessor_eligibility_approvals",
                ["eligibility_approval_id"],
                ["id"],
            )
    if op.get_bind().dialect.name == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(
                sa.text(
                    f"CREATE TRIGGER IF NOT EXISTS assessor_eligibility_no_{action.lower()} BEFORE {action} ON assessor_eligibility_approvals BEGIN SELECT RAISE(ABORT, 'Assessor eligibility history is append-only'); END"
                )
            )
        op.execute(
            sa.text(
                "CREATE TRIGGER IF NOT EXISTS assessor_eligibility_no_replace BEFORE INSERT ON assessor_eligibility_approvals WHEN EXISTS (SELECT 1 FROM assessor_eligibility_approvals WHERE id = NEW.id OR (course_id = NEW.course_id AND subject_user_id = NEW.subject_user_id AND version = NEW.version)) BEGIN SELECT RAISE(ABORT, 'Assessor eligibility history is append-only'); END"
            )
        )


_PROTECTED_DOWNGRADE_TABLES = (
    "role_assignments",
    "assessment_definitions",
    "outcome_versions",
    "assessment_definition_versions",
    "bloom_targets",
    "bloom_target_versions",
    "criteria",
    "criterion_versions",
    "pass_rules",
    "pass_rule_versions",
    "task_forms",
    "task_form_versions",
    "task_approvals",
    "assessment_attempts",
    "criterion_evaluations",
    "assessment_decisions",
    "assessor_reviews",
    "reassessment_links",
    "appeals_or_corrections",
    "learner_model_snapshots",
    "learner_outcome_estimates",
    "learner_model_evidence_links",
    "evidence_artifacts",
    "learning_evidence",
    "evidence_links",
    "assessment_legacy_history",
)


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if connection.execute(
        sa.text("SELECT COUNT(*) FROM assessor_eligibility_approvals")
    ).scalar_one():
        raise RuntimeError(
            "Assessor eligibility history is protected; restore a verified backup instead"
        )
    for table in ("circuit_versions", "simulation_runs", "simulation_outcomes"):
        if (
            inspector.has_table(table)
            and connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        ):
            raise RuntimeError(
                "Simulation evidence is protected; restore a verified backup instead"
            )
    for table in ("source_revisions", "source_passages", "source_approvals", "source_uses"):
        if connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError("Source history is protected; restore a verified backup instead")
    if connection.execute(sa.text("SELECT COUNT(*) FROM assessor_reviews")).scalar_one():
        raise RuntimeError(
            "cannot downgrade populated assessor review history; restore a verified backup instead"
        )
    if connection.execute(sa.text("SELECT COUNT(*) FROM assessment_evaluation_jobs")).scalar_one():
        raise RuntimeError(
            "cannot downgrade populated assessment evaluation jobs; restore a verified backup instead"
        )
    for table in _PROTECTED_DOWNGRADE_TABLES:
        if (
            inspector.has_table(table)
            and connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        ):
            raise RuntimeError(
                "cannot downgrade populated protected learner-model, evidence, or assessment history; restore a verified backup instead"
            )
    if connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM learning_materials WHERE processing_attempts > 0 OR indexing_status = 'processing'"
        )
    ).scalar_one():
        raise RuntimeError(
            "cannot downgrade populated material processing claims; restore a verified backup instead"
        )

    if connection.dialect.name != "sqlite":
        op.drop_constraint(
            "fk_role_assignments_eligibility_approval_id_assessor_eligibility_approvals",
            "role_assignments",
            type_="foreignkey",
        )
    op.drop_column("role_assignments", "eligibility_approval_id")
    op.drop_table("assessor_eligibility_approvals")
