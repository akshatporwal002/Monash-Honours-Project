"""Add append-only learner-model annotation and correction history.

Revision ID: 20260824_0022
Revises: 20260816_0021
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0022"
down_revision: str | None = "20260816_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANNOTATIONS = "learner_model_annotations"
_REVIEWS = "learner_model_correction_reviews"
_SNAPSHOT_LINKS = "learner_model_correction_snapshot_links"
_TABLES = (_ANNOTATIONS, _REVIEWS, _SNAPSHOT_LINKS)
_PROTECTED_DOWNGRADE_TABLES = (
    *_TABLES,
    "assessor_reviews",
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

_REQUIRED_COLUMNS = {
    _ANNOTATIONS: {
        "id",
        "course_id",
        "learner_id",
        "outcome_id",
        "target_kind",
        "evidence_id",
        "estimate_id",
        "action",
        "note",
        "schema_version",
        "record_version",
        "actor_reference",
        "correlation_id",
        "idempotency_key",
        "occurred_at",
        "created_at",
    },
    _REVIEWS: {
        "id",
        "annotation_id",
        "course_id",
        "learner_id",
        "outcome_id",
        "prior_review_id",
        "review_version",
        "expected_latest_review_version",
        "action",
        "reason",
        "schema_version",
        "actor_reference",
        "correlation_id",
        "idempotency_key",
        "occurred_at",
        "created_at",
    },
    _SNAPSHOT_LINKS: {
        "id",
        "review_id",
        "snapshot_id",
        "course_id",
        "learner_id",
        "outcome_id",
        "schema_version",
        "record_version",
        "actor_reference",
        "correlation_id",
        "idempotency_key",
        "occurred_at",
        "created_at",
    },
}


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def _validate_existing_table(table: str) -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}
    missing = _REQUIRED_COLUMNS[table] - columns
    if missing:
        raise RuntimeError(
            f"partial learner-model correction schema for {table}; missing {sorted(missing)}"
        )


def _create_index_if_missing(
    name: str,
    table: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    index_names = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}
    if name not in index_names:
        op.create_index(name, table, columns, unique=unique)


def _drop_triggers(table: str) -> None:
    op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only_delete")
    op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only_update")


def _add_append_only_triggers(table: str) -> None:
    op.execute(
        f"CREATE TRIGGER trg_{table}_append_only_update BEFORE UPDATE ON {table} BEGIN "
        "SELECT RAISE(ABORT, 'learner-model correction records are append-only'); END"
    )
    op.execute(
        f"CREATE TRIGGER trg_{table}_append_only_delete BEFORE DELETE ON {table} BEGIN "
        "SELECT RAISE(ABORT, 'learner-model correction records are append-only'); END"
    )


def _drop_scope_triggers() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_learner_model_annotations_target_scope")
    op.execute("DROP TRIGGER IF EXISTS trg_learner_model_correction_reviews_ancestry")
    op.execute("DROP TRIGGER IF EXISTS trg_learner_model_correction_snapshot_links_scope")


def _add_scope_triggers() -> None:
    op.execute(
        "CREATE TRIGGER trg_learner_model_annotations_target_scope BEFORE INSERT ON "
        "learner_model_annotations WHEN NOT ((NEW.target_kind = 'EVIDENCE' AND EXISTS "
        "(SELECT 1 FROM learning_evidence WHERE id = NEW.evidence_id AND course_id = "
        "NEW.course_id AND learner_id = NEW.learner_id AND outcome_id = NEW.outcome_id)) OR "
        "(NEW.target_kind = 'ESTIMATE' AND EXISTS (SELECT 1 FROM learner_outcome_estimates "
        "AS estimate JOIN learner_model_snapshots AS snapshot ON snapshot.id = "
        "estimate.snapshot_id WHERE estimate.id = NEW.estimate_id AND snapshot.course_id = "
        "NEW.course_id AND snapshot.learner_id = NEW.learner_id AND snapshot.outcome_id = "
        "NEW.outcome_id))) BEGIN SELECT RAISE(ABORT, 'invalid learner-model correction target "
        "scope'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_learner_model_correction_reviews_ancestry BEFORE INSERT ON "
        "learner_model_correction_reviews WHEN NEW.review_version > 1 AND NOT EXISTS "
        "(SELECT 1 FROM learner_model_correction_reviews AS prior WHERE prior.id = "
        "NEW.prior_review_id AND prior.annotation_id = NEW.annotation_id AND "
        "prior.review_version = NEW.expected_latest_review_version) BEGIN SELECT "
        "RAISE(ABORT, 'invalid learner-model correction review ancestry'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_learner_model_correction_snapshot_links_scope BEFORE INSERT ON "
        "learner_model_correction_snapshot_links WHEN NOT EXISTS (SELECT 1 FROM "
        "learner_model_correction_reviews AS review JOIN learner_model_snapshots AS snapshot "
        "ON snapshot.id = NEW.snapshot_id WHERE review.id = NEW.review_id AND review.action = "
        "'ACCEPTED' AND review.course_id = NEW.course_id AND review.learner_id = NEW.learner_id "
        "AND review.outcome_id = NEW.outcome_id AND snapshot.course_id = NEW.course_id AND "
        "snapshot.learner_id = NEW.learner_id AND snapshot.outcome_id = NEW.outcome_id AND "
        "julianday(snapshot.occurred_at) >= julianday(review.occurred_at)) BEGIN SELECT "
        "RAISE(ABORT, 'invalid learner-model correction snapshot scope or ordering'); END"
    )


def _create_annotations_table() -> None:
    op.create_table(
        _ANNOTATIONS,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("outcome_id", sa.String(length=36), nullable=False),
        sa.Column(
            "target_kind",
            _enum("learner_model_correction_target_kind", "EVIDENCE", "ESTIMATE"),
            nullable=False,
        ),
        sa.Column("evidence_id", sa.String(length=36), nullable=True),
        sa.Column("estimate_id", sa.String(length=36), nullable=True),
        sa.Column(
            "action",
            _enum(
                "learner_model_annotation_action_type",
                "ANNOTATED",
                "ACCEPTED",
                "REJECTED",
                "NEEDS_REVIEW",
            ),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("actor_reference", sa.String(length=255), nullable=False),
        sa.Column("correlation_id", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("record_version > 0", name="learner_model_annotation_record_version"),
        sa.CheckConstraint("action = 'ANNOTATED'", name="learner_model_annotation_action"),
        sa.CheckConstraint(
            "(target_kind = 'EVIDENCE' AND evidence_id IS NOT NULL AND estimate_id IS NULL) OR "
            "(target_kind = 'ESTIMATE' AND estimate_id IS NOT NULL AND evidence_id IS NULL)",
            name="learner_model_annotation_target",
        ),
        sa.CheckConstraint(
            "length(trim(note)) BETWEEN 1 AND 2000",
            name="learner_model_annotation_note",
        ),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["learner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["outcome_id"], ["learning_outcomes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evidence_id"], ["learning_evidence.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["estimate_id"], ["learner_outcome_estimates.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "course_id",
            "learner_id",
            "outcome_id",
            name="uq_learner_model_annotation_scope",
        ),
    )


def _create_reviews_table() -> None:
    op.create_table(
        _REVIEWS,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("annotation_id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("outcome_id", sa.String(length=36), nullable=False),
        sa.Column("prior_review_id", sa.String(length=36), nullable=True),
        sa.Column("review_version", sa.Integer(), nullable=False),
        sa.Column("expected_latest_review_version", sa.Integer(), nullable=False),
        sa.Column(
            "action",
            _enum(
                "learner_model_correction_review_action_type",
                "ANNOTATED",
                "ACCEPTED",
                "REJECTED",
                "NEEDS_REVIEW",
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("actor_reference", sa.String(length=255), nullable=False),
        sa.Column("correlation_id", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("review_version > 0", name="learner_model_correction_review_version"),
        sa.CheckConstraint(
            "expected_latest_review_version >= 0",
            name="learner_model_correction_expected_version",
        ),
        sa.CheckConstraint(
            "(review_version = 1 AND expected_latest_review_version = 0 "
            "AND prior_review_id IS NULL) OR "
            "(review_version > 1 AND expected_latest_review_version = review_version - 1 "
            "AND prior_review_id IS NOT NULL)",
            name="learner_model_correction_review_ancestry",
        ),
        sa.CheckConstraint(
            "action IN ('ACCEPTED', 'REJECTED', 'NEEDS_REVIEW')",
            name="learner_model_correction_review_action",
        ),
        sa.CheckConstraint(
            "length(trim(reason)) BETWEEN 1 AND 2000",
            name="learner_model_correction_review_reason",
        ),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["learner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["outcome_id"], ["learning_outcomes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["annotation_id", "course_id", "learner_id", "outcome_id"],
            [
                "learner_model_annotations.id",
                "learner_model_annotations.course_id",
                "learner_model_annotations.learner_id",
                "learner_model_annotations.outcome_id",
            ],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "annotation_id",
            "review_version",
            name="uq_learner_model_correction_review_ancestry",
        ),
        sa.UniqueConstraint(
            "id",
            "course_id",
            "learner_id",
            "outcome_id",
            name="uq_learner_model_correction_review_scope",
        ),
        sa.UniqueConstraint(
            "annotation_id",
            "review_version",
            name="uq_learner_model_correction_review_version",
        ),
    )


def _create_snapshot_links_table() -> None:
    op.create_table(
        _SNAPSHOT_LINKS,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("outcome_id", sa.String(length=36), nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("actor_reference", sa.String(length=255), nullable=False),
        sa.Column("correlation_id", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "record_version > 0", name="learner_model_correction_snapshot_link_version"
        ),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["learner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["outcome_id"], ["learning_outcomes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["learner_model_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "course_id", "learner_id", "outcome_id"],
            [
                "learner_model_correction_reviews.id",
                "learner_model_correction_reviews.course_id",
                "learner_model_correction_reviews.learner_id",
                "learner_model_correction_reviews.outcome_id",
            ],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_id", name="uq_learner_model_correction_snapshot_review"),
    )


def _create_indexes() -> None:
    _create_index_if_missing(
        "ix_learner_model_annotations_timeline",
        _ANNOTATIONS,
        ["course_id", "learner_id", "outcome_id", "occurred_at", "created_at", "id"],
    )
    _create_index_if_missing(
        "ix_learner_model_annotations_target",
        _ANNOTATIONS,
        ["target_kind", "evidence_id", "estimate_id"],
    )
    _create_index_if_missing(
        "ix_learner_model_annotations_correlation", _ANNOTATIONS, ["correlation_id"]
    )
    _create_index_if_missing(
        "ix_learner_model_annotations_idempotency",
        _ANNOTATIONS,
        ["course_id", "learner_id", "idempotency_key"],
        unique=True,
    )
    _create_index_if_missing(
        "ix_learner_model_correction_reviews_history",
        _REVIEWS,
        ["annotation_id", "review_version", "occurred_at", "id"],
    )
    _create_index_if_missing(
        "ix_learner_model_correction_reviews_correlation", _REVIEWS, ["correlation_id"]
    )
    _create_index_if_missing(
        "ix_learner_model_correction_reviews_idempotency",
        _REVIEWS,
        ["course_id", "learner_id", "idempotency_key"],
        unique=True,
    )
    _create_index_if_missing(
        "ix_learner_model_correction_snapshot_links_snapshot",
        _SNAPSHOT_LINKS,
        ["snapshot_id", "occurred_at"],
    )
    _create_index_if_missing(
        "ix_learner_model_correction_snapshot_links_correlation",
        _SNAPSHOT_LINKS,
        ["correlation_id"],
    )
    _create_index_if_missing(
        "ix_learner_model_correction_snapshot_links_idempotency",
        _SNAPSHOT_LINKS,
        ["course_id", "learner_id", "idempotency_key"],
        unique=True,
    )


def upgrade() -> None:
    creators = {
        _ANNOTATIONS: _create_annotations_table,
        _REVIEWS: _create_reviews_table,
        _SNAPSHOT_LINKS: _create_snapshot_links_table,
    }
    for table in _TABLES:
        if _has_table(table):
            _validate_existing_table(table)
        else:
            creators[table]()
    _create_indexes()
    _drop_scope_triggers()
    _add_scope_triggers()
    for table in _TABLES:
        _drop_triggers(table)
        _add_append_only_triggers(table)


def downgrade() -> None:
    connection = op.get_bind()
    for table in _PROTECTED_DOWNGRADE_TABLES:
        if (
            _has_table(table)
            and connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        ):
            if table == "assessor_reviews":
                raise RuntimeError(
                    "cannot downgrade populated assessor review history; "
                    "restore the verified backup instead"
                )
            raise RuntimeError(
                "cannot downgrade populated correction, learner-model, evidence, or assessment "
                "history; "
                "restore the verified backup instead"
            )
    _drop_scope_triggers()
    for table in reversed(_TABLES):
        if _has_table(table):
            _drop_triggers(table)
            op.drop_table(table)
