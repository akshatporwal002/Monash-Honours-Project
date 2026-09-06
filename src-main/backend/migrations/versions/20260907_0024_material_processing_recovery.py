"""Add durable material processing claims and recovery scheduling."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260907_0024"
down_revision = "20260907_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("learning_materials")}
    additions = (
        sa.Column("processing_token", sa.String(36), nullable=True),
        sa.Column("processing_lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "processing_attempts",
            sa.Integer(),
            sa.CheckConstraint(
                "processing_attempts BETWEEN 0 AND 3",
                name=op.f("ck_learning_materials_learning_material_processing_attempts"),
            ),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "processing_backend",
            sa.String(16),
            sa.CheckConstraint(
                "processing_backend IN ('offline', 'semantic')",
                name=op.f("ck_learning_materials_learning_material_processing_backend"),
            ),
            nullable=False,
            server_default="offline",
        ),
    )
    for column in additions:
        if column.name not in columns:
            op.add_column("learning_materials", column)
    if not any(
        index["name"] == "ix_learning_materials_recovery"
        for index in inspector.get_indexes("learning_materials")
    ):
        op.create_index(
            "ix_learning_materials_recovery",
            "learning_materials",
            ["indexing_status", "processing_retry_at", "processing_lease_expires_at"],
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
    op.drop_index("ix_learning_materials_recovery", table_name="learning_materials")
    for column in (
        "processing_backend",
        "processing_attempts",
        "processing_retry_at",
        "processing_lease_expires_at",
        "processing_token",
    ):
        op.drop_column("learning_materials", column)
