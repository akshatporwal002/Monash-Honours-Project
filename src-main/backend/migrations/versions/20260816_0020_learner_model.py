"""Add append-only Person B learner-model snapshot storage.

Revision ID: 20260816_0020
Revises: 20260816_0019
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_0020"
down_revision: str | None = "20260816_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SNAPSHOTS = "learner_model_snapshots"
_ESTIMATES = "learner_outcome_estimates"
_LINKS = "learner_model_evidence_links"
_TABLES = (_SNAPSHOTS, _ESTIMATES, _LINKS)


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def _create_index_if_missing(name: str, table: str, columns: list[str]) -> None:
    index_names = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}
    if name not in index_names:
        op.create_index(name, table, columns)


def _add_append_only_triggers(table: str) -> None:
    op.execute(
        f"CREATE TRIGGER trg_{table}_append_only_update BEFORE UPDATE ON {table} BEGIN "
        "SELECT RAISE(ABORT, 'learner-model records are append-only'); END"
    )
    op.execute(
        f"CREATE TRIGGER trg_{table}_append_only_delete BEFORE DELETE ON {table} BEGIN "
        "SELECT RAISE(ABORT, 'learner-model records are append-only'); END"
    )


def _drop_append_only_triggers(table: str) -> None:
    op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only_delete")
    op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only_update")


def _create_snapshots_table() -> None:
    op.create_table(
        _SNAPSHOTS,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("outcome_id", sa.String(length=36), nullable=False),
        sa.Column("prior_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column(
            "model_source",
            _enum("learner_model_source", "RULE_BASED", "ADVISORY_MODEL", "EDUCATOR", "LEARNER"),
            nullable=False,
        ),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("rule_version", sa.String(length=100), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("actor_reference", sa.String(length=255), nullable=False),
        sa.Column("agent_reference", sa.String(length=255), nullable=True),
        sa.Column("correlation_id", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("record_version > 0", name="learner_model_snapshot_record_version"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["learner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["outcome_id"], ["learning_outcomes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_id",
            "learner_id",
            "outcome_id",
            "idempotency_key",
            name="uq_learner_model_snapshot_idempotency",
        ),
    )


def _create_estimates_table() -> None:
    op.create_table(
        _ESTIMATES,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_id", sa.String(length=36), nullable=False),
        sa.Column(
            "dimension",
            _enum(
                "learner_model_dimension",
                "PRIOR_KNOWLEDGE",
                "REASONING_STRENGTH",
                "REASONING_GAP",
                "POSSIBLE_MISCONCEPTION",
                "CONFIDENCE_CALIBRATION",
                "FEEDBACK_USE",
                "SCAFFOLD_DEPENDENCE",
                "INDEPENDENCE",
                "TRANSFER",
                "EXPLICIT_PREFERENCE",
            ),
            nullable=False,
        ),
        sa.Column(
            "inference_status",
            _enum(
                "learner_model_inference_status",
                "UNCERTAIN",
                "SUPPORTED",
                "CONTRADICTED",
                "NEEDS_REVIEW",
            ),
            nullable=False,
        ),
        sa.Column("uncertainty", sa.Float(), nullable=False),
        sa.Column("reason_code", sa.String(length=100), nullable=False),
        sa.Column("evidence_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "uncertainty >= 0 AND uncertainty <= 1",
            name="learner_outcome_estimate_uncertainty",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["learner_model_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "dimension",
            name="uq_learner_outcome_estimate_dimension",
        ),
    )


def _create_links_table() -> None:
    op.create_table(
        _LINKS,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("estimate_id", sa.String(length=36), nullable=False),
        sa.Column("evidence_id", sa.String(length=36), nullable=False),
        sa.Column(
            "relation",
            _enum(
                "learner_model_evidence_relation_type",
                "SUPPORTS",
                "CONTRADICTS",
                "DERIVES_FROM",
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "relation IN ('SUPPORTS', 'CONTRADICTS')",
            name="learner_model_evidence_relation",
        ),
        sa.ForeignKeyConstraint(
            ["estimate_id"], ["learner_outcome_estimates.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["evidence_id"], ["learning_evidence.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "estimate_id",
            "evidence_id",
            name="uq_learner_model_evidence_link",
        ),
    )


def upgrade() -> None:
    if not _has_table(_SNAPSHOTS):
        _create_snapshots_table()
    if not _has_table(_ESTIMATES):
        _create_estimates_table()
    if not _has_table(_LINKS):
        _create_links_table()

    _create_index_if_missing(
        "ix_learner_model_snapshots_timeline",
        _SNAPSHOTS,
        ["course_id", "learner_id", "outcome_id", "occurred_at", "created_at", "id"],
    )
    _create_index_if_missing(
        "ix_learner_model_snapshots_prior",
        _SNAPSHOTS,
        ["prior_snapshot_id"],
    )
    _create_index_if_missing(
        "ix_learner_model_snapshots_correlation",
        _SNAPSHOTS,
        ["correlation_id"],
    )
    _create_index_if_missing(
        "ix_learner_outcome_estimates_dimension",
        _ESTIMATES,
        ["dimension", "evidence_observed_at"],
    )
    _create_index_if_missing(
        "ix_learner_model_evidence_links_evidence",
        _LINKS,
        ["evidence_id"],
    )
    for table in _TABLES:
        _drop_append_only_triggers(table)
        _add_append_only_triggers(table)


def downgrade() -> None:
    connection = op.get_bind()
    protected_tables = (
        *_TABLES,
        "evidence_artifacts",
        "learning_evidence",
        "evidence_links",
        "assessment_legacy_history",
    )
    for table in protected_tables:
        if (
            _has_table(table)
            and connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        ):
            raise RuntimeError(
                "cannot downgrade populated learner-model, evidence, or assessment history; "
                "restore the verified backup instead"
            )
    for table in reversed(_TABLES):
        if _has_table(table):
            _drop_append_only_triggers(table)
            op.drop_table(table)
