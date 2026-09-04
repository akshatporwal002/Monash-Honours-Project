"""Add durable assessment evaluation jobs.

Revision ID: 20260821_0022
Revises: 20260816_0021
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0022"
down_revision: str | None = "20260816_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def _backfill_pending() -> None:
    op.execute(
        "INSERT OR IGNORE INTO assessment_evaluation_jobs "
        "(assessment_attempt_id, response_version_id, evaluation_idempotency_key, "
        "correlation_id, state, processing_attempts, execution_token, lease_expires_at, "
        "next_retry_at, failure_category, created_at, updated_at, completed_at) "
        "SELECT id, response_version_id, 'assessment-evaluation:' || id, id, 'pending', 0, "
        "NULL, NULL, NULL, NULL, created_at, created_at, NULL FROM assessment_attempts "
        "WHERE state = 'PENDING'"
    )


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("assessment_evaluation_jobs"):
        _backfill_pending()
        return
    op.create_table(
        "assessment_evaluation_jobs",
        sa.Column("assessment_attempt_id", sa.String(length=36), nullable=False),
        sa.Column("response_version_id", sa.String(length=36), nullable=False),
        sa.Column("evaluation_idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column(
            "state",
            _enum(
                "assessment_evaluation_job_state",
                "pending",
                "running",
                "retry_scheduled",
                "completed",
                "review_required",
            ),
            nullable=False,
        ),
        sa.Column("processing_attempts", sa.Integer(), nullable=False),
        sa.Column("execution_token", sa.String(length=36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "failure_category",
            _enum(
                "assessment_evaluation_failure_category",
                "provider_unavailable",
                "provider_fault",
                "version_conflict",
                "persistence_unavailable",
            ),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["assessment_attempt_id"], ["assessment_attempts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["response_version_id"], ["submission_attempts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("assessment_attempt_id"),
        sa.UniqueConstraint(
            "response_version_id",
            name="uq_assessment_evaluation_jobs_response",
        ),
        sa.UniqueConstraint(
            "evaluation_idempotency_key",
            name="uq_assessment_evaluation_jobs_idempotency",
        ),
        sa.CheckConstraint(
            "processing_attempts BETWEEN 0 AND 3",
            name="assessment_evaluation_job_attempts",
        ),
        sa.CheckConstraint(
            "(state = 'pending' AND processing_attempts = 0 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NULL AND failure_category IS NULL AND completed_at IS NULL) OR "
            "(state = 'running' AND processing_attempts BETWEEN 1 AND 3 "
            "AND execution_token IS NOT NULL AND lease_expires_at IS NOT NULL "
            "AND next_retry_at IS NULL AND failure_category IS NULL AND completed_at IS NULL) OR "
            "(state = 'retry_scheduled' AND processing_attempts BETWEEN 1 AND 2 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NOT NULL AND failure_category IS NOT NULL "
            "AND completed_at IS NULL) OR "
            "(state = 'completed' AND processing_attempts BETWEEN 1 AND 3 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NULL AND failure_category IS NULL "
            "AND completed_at IS NOT NULL) OR "
            "(state = 'review_required' AND processing_attempts BETWEEN 1 AND 3 "
            "AND execution_token IS NULL AND lease_expires_at IS NULL "
            "AND next_retry_at IS NULL AND failure_category IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="assessment_evaluation_job_state_shape",
        ),
    )
    op.create_index(
        "ix_assessment_evaluation_jobs_claim",
        "assessment_evaluation_jobs",
        ["state", "next_retry_at", "lease_expires_at", "created_at"],
    )
    _backfill_pending()


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if (
        inspector.has_table("assessor_reviews")
        and connection.execute(sa.text("SELECT COUNT(*) FROM assessor_reviews")).scalar_one()
    ):
        raise RuntimeError(
            "cannot downgrade populated assessor review history or protected learner-model, "
            "evidence, or assessment history; restore the verified backup instead"
        )
    if connection.execute(sa.text("SELECT COUNT(*) FROM assessment_evaluation_jobs")).scalar_one():
        raise RuntimeError(
            "cannot downgrade populated assessment evaluation jobs; "
            "restore a verified backup instead"
        )
    for table in _PROTECTED_DOWNGRADE_TABLES:
        if (
            inspector.has_table(table)
            and connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        ):
            raise RuntimeError(
                "cannot downgrade populated assessor review history or protected learner-model, "
                "evidence, or assessment history; restore the verified backup instead"
            )
    op.drop_index(
        "ix_assessment_evaluation_jobs_claim",
        table_name="assessment_evaluation_jobs",
    )
    op.drop_table("assessment_evaluation_jobs")
