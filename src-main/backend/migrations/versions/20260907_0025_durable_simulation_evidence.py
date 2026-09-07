"""durable_simulation_evidence

Revision ID: 20260907_0025
Revises: 20260907_0024
Create Date: 2026-09-07 02:06:26.223325
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0025"
down_revision: str | None = "20260907_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("circuit_versions"):
        op.create_table(
            "circuit_versions",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("task_id", sa.String(length=36), nullable=True),
            sa.Column("course_id", sa.String(length=36), nullable=True),
            sa.Column("content_digest", sa.String(length=64), nullable=False),
            sa.Column("circuit", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["course_id"],
                ["courses.id"],
                name=op.f("fk_circuit_versions_course_id_courses"),
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["owner_id"],
                ["users.id"],
                name=op.f("fk_circuit_versions_owner_id_users"),
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["task_id"],
                ["learning_tasks.id"],
                name=op.f("fk_circuit_versions_task_id_learning_tasks"),
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_circuit_versions")),
        )
    if not inspector.has_table("simulation_runs"):
        op.create_table(
            "simulation_runs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("request_key", sa.String(length=128), nullable=False),
            sa.Column("circuit_version_id", sa.String(length=64), nullable=False),
            sa.Column("submission_id", sa.String(length=36), nullable=True),
            sa.Column("purpose", sa.String(length=16), nullable=False),
            sa.Column("shots", sa.Integer(), nullable=False),
            sa.Column("seed", sa.BigInteger(), nullable=False),
            sa.Column("policy_version", sa.String(length=64), nullable=False),
            sa.Column("engine_versions", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "purpose IN ('practice', 'task', 'feedback')",
                name=op.f("ck_simulation_runs_simulation_purpose"),
            ),
            sa.CheckConstraint(
                "seed BETWEEN 0 AND 4294967295", name=op.f("ck_simulation_runs_simulation_seed")
            ),
            sa.CheckConstraint(
                "shots BETWEEN 1 AND 4096", name=op.f("ck_simulation_runs_simulation_shots")
            ),
            sa.ForeignKeyConstraint(
                ["circuit_version_id"],
                ["circuit_versions.id"],
                name=op.f("fk_simulation_runs_circuit_version_id_circuit_versions"),
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["owner_id"],
                ["users.id"],
                name=op.f("fk_simulation_runs_owner_id_users"),
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["submission_id"],
                ["submission_attempts.id"],
                name=op.f("fk_simulation_runs_submission_id_submission_attempts"),
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_simulation_runs")),
            sa.UniqueConstraint("owner_id", "request_key", name="uq_simulation_request"),
        )
    if not any(
        item["name"] == "ix_simulation_runs_deadline_at"
        for item in sa.inspect(op.get_bind()).get_indexes("simulation_runs")
    ):
        with op.batch_alter_table("simulation_runs", schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f("ix_simulation_runs_deadline_at"), ["deadline_at"], unique=False
            )

    if not inspector.has_table("simulation_outcomes"):
        op.create_table(
            "simulation_outcomes",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("result", sa.JSON(none_as_null=True), nullable=True),
            sa.Column("error_code", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "(status = 'completed' AND result IS NOT NULL AND error_code IS NULL) OR (status != 'completed' AND result IS NULL AND error_code IS NOT NULL)",
                name=op.f("ck_simulation_outcomes_simulation_terminal_shape"),
            ),
            sa.CheckConstraint(
                "status IN ('completed', 'failed', 'timed_out', 'interrupted')",
                name=op.f("ck_simulation_outcomes_simulation_status"),
            ),
            sa.ForeignKeyConstraint(
                ["id"],
                ["simulation_runs.id"],
                name=op.f("fk_simulation_outcomes_id_simulation_runs"),
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_simulation_outcomes")),
        )
    if op.get_bind().dialect.name == "sqlite":
        for table in ("circuit_versions", "simulation_runs", "simulation_outcomes"):
            for action in ("UPDATE", "DELETE"):
                op.execute(
                    sa.text(
                        f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Simulation evidence is append-only'); END"
                    )
                )
            op.execute(
                sa.text(
                    f"CREATE TRIGGER IF NOT EXISTS {table}_no_replace BEFORE INSERT ON {table} WHEN EXISTS (SELECT 1 FROM {table} WHERE id = NEW.id) BEGIN SELECT RAISE(ABORT, 'Simulation evidence is append-only'); END"
                )
            )
        op.execute(
            sa.text(
                "CREATE TRIGGER IF NOT EXISTS simulation_runs_no_request_replace BEFORE INSERT ON simulation_runs WHEN EXISTS (SELECT 1 FROM simulation_runs WHERE owner_id = NEW.owner_id AND request_key = NEW.request_key) BEGIN SELECT RAISE(ABORT, 'Simulation evidence is append-only'); END"
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

    op.drop_table("simulation_outcomes")
    with op.batch_alter_table("simulation_runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_simulation_runs_deadline_at"))

    op.drop_table("simulation_runs")
    op.drop_table("circuit_versions")
