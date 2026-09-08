"""Add append-only learner annotations and educator correction reviews.

Revision ID: 20260908_0032
Revises: 20260907_0031
"""

from __future__ import annotations

from collections.abc import Sequence
from importlib import import_module

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0032"
down_revision: str | None = "20260907_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ANNOTATIONS = "learner_model_annotations"
REVIEWS = "learner_model_correction_reviews"
SNAPSHOT_LINKS = "learner_model_correction_snapshot_links"
TABLES = (ANNOTATIONS, REVIEWS, SNAPSHOT_LINKS)


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def _sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def _append_only(table: str) -> None:
    for operation in ("UPDATE", "DELETE"):
        op.execute(
            sa.text(
                f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} "
                "BEGIN SELECT RAISE(ABORT, 'learner-model correction records are append-only'); END"
            )
        )


def _scope_guards() -> None:
    op.execute(
        sa.text(
            "CREATE TRIGGER learner_model_annotation_target_scope BEFORE INSERT ON "
            "learner_model_annotations WHEN NOT ((NEW.target_kind = 'EVIDENCE' AND EXISTS "
            "(SELECT 1 FROM learning_evidence WHERE id = NEW.evidence_id AND course_id = NEW.course_id "
            "AND learner_id = NEW.learner_id AND outcome_id = NEW.outcome_id)) OR "
            "(NEW.target_kind = 'ESTIMATE' AND EXISTS (SELECT 1 FROM learner_outcome_estimates estimate "
            "JOIN learner_model_snapshots snapshot ON snapshot.id = estimate.snapshot_id "
            "WHERE estimate.id = NEW.estimate_id AND snapshot.course_id = NEW.course_id "
            "AND snapshot.learner_id = NEW.learner_id AND snapshot.outcome_id = NEW.outcome_id))) "
            "BEGIN SELECT RAISE(ABORT, 'invalid learner-model correction target scope'); END"
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER learner_model_review_ancestry BEFORE INSERT ON learner_model_correction_reviews "
            "WHEN NEW.review_version > 1 AND NOT EXISTS (SELECT 1 FROM learner_model_correction_reviews prior "
            "WHERE prior.id = NEW.prior_review_id AND prior.annotation_id = NEW.annotation_id "
            "AND prior.review_version = NEW.expected_latest_review_version) "
            "BEGIN SELECT RAISE(ABORT, 'invalid learner-model correction review ancestry'); END"
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER learner_model_snapshot_link_scope BEFORE INSERT ON "
            "learner_model_correction_snapshot_links WHEN NOT EXISTS (SELECT 1 FROM "
            "learner_model_correction_reviews review JOIN learner_model_snapshots snapshot "
            "ON snapshot.id = NEW.snapshot_id WHERE review.id = NEW.review_id AND review.action = 'ACCEPTED' "
            "AND review.course_id = NEW.course_id AND review.learner_id = NEW.learner_id "
            "AND review.outcome_id = NEW.outcome_id AND snapshot.course_id = NEW.course_id "
            "AND snapshot.learner_id = NEW.learner_id AND snapshot.outcome_id = NEW.outcome_id "
            "AND julianday(snapshot.occurred_at) >= julianday(review.occurred_at)) "
            "BEGIN SELECT RAISE(ABORT, 'invalid learner-model correction snapshot scope or ordering'); END"
        )
    )


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = tuple(table for table in TABLES if inspector.has_table(table))
    if existing:
        if existing != TABLES:
            raise RuntimeError("partial learner-model correction schema")
        required = {
            ANNOTATIONS: {"id", "target_kind", "evidence_id", "estimate_id", "note"},
            REVIEWS: {"id", "annotation_id", "review_version", "reason"},
            SNAPSHOT_LINKS: {"id", "review_id", "snapshot_id"},
        }
        for table, columns in required.items():
            available = {column["name"] for column in inspector.get_columns(table)}
            if not columns <= available:
                raise RuntimeError(f"partial learner-model correction schema for {table}")
        if _sqlite():
            for trigger in (
                "learner_model_annotation_target_scope",
                "learner_model_review_ancestry",
                "learner_model_snapshot_link_scope",
            ):
                op.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger}"))
            for table in TABLES:
                for operation in ("update", "delete"):
                    op.execute(sa.text(f"DROP TRIGGER IF EXISTS {table}_no_{operation}"))
            _scope_guards()
            for table in TABLES:
                _append_only(table)
        return
    op.create_table(
        ANNOTATIONS,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "course_id",
            sa.String(36),
            sa.ForeignKey("courses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "learner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "outcome_id",
            sa.String(36),
            sa.ForeignKey("learning_outcomes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "target_kind",
            _enum("learner_model_correction_target_kind", "EVIDENCE", "ESTIMATE"),
            nullable=False,
        ),
        sa.Column(
            "evidence_id", sa.String(36), sa.ForeignKey("learning_evidence.id", ondelete="RESTRICT")
        ),
        sa.Column(
            "estimate_id",
            sa.String(36),
            sa.ForeignKey("learner_outcome_estimates.id", ondelete="RESTRICT"),
        ),
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
        sa.Column("schema_version", sa.String(100), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("actor_reference", sa.String(255), nullable=False),
        sa.Column("correlation_id", sa.String(255), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
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
            "(target_kind = 'EVIDENCE' AND evidence_id IS NOT NULL AND estimate_id IS NULL) OR (target_kind = 'ESTIMATE' AND estimate_id IS NOT NULL AND evidence_id IS NULL)",
            name="learner_model_annotation_target",
        ),
        sa.CheckConstraint(
            "length(trim(note)) BETWEEN 1 AND 2000", name="learner_model_annotation_note"
        ),
        sa.UniqueConstraint(
            "id", "course_id", "learner_id", "outcome_id", name="uq_learner_model_annotation_scope"
        ),
        sa.Index(
            "ix_learner_model_annotations_timeline",
            "course_id",
            "learner_id",
            "outcome_id",
            "occurred_at",
            "created_at",
            "id",
        ),
        sa.Index(
            "ix_learner_model_annotations_target", "target_kind", "evidence_id", "estimate_id"
        ),
        sa.Index("ix_learner_model_annotations_correlation", "correlation_id"),
        sa.Index(
            "ix_learner_model_annotations_idempotency",
            "course_id",
            "learner_id",
            "idempotency_key",
            unique=True,
        ),
    )
    op.create_table(
        REVIEWS,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("annotation_id", sa.String(36), nullable=False),
        sa.Column(
            "course_id",
            sa.String(36),
            sa.ForeignKey("courses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "learner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "outcome_id",
            sa.String(36),
            sa.ForeignKey("learning_outcomes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("prior_review_id", sa.String(36)),
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
        sa.Column("schema_version", sa.String(100), nullable=False),
        sa.Column("actor_reference", sa.String(255), nullable=False),
        sa.Column("correlation_id", sa.String(255), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("review_version > 0", name="learner_model_correction_review_version"),
        sa.CheckConstraint(
            "expected_latest_review_version >= 0", name="learner_model_correction_expected_version"
        ),
        sa.CheckConstraint(
            "(review_version = 1 AND expected_latest_review_version = 0 AND prior_review_id IS NULL) OR (review_version > 1 AND expected_latest_review_version = review_version - 1 AND prior_review_id IS NOT NULL)",
            name="learner_model_correction_review_ancestry",
        ),
        sa.CheckConstraint(
            "action IN ('ACCEPTED', 'REJECTED', 'NEEDS_REVIEW')",
            name="learner_model_correction_review_action",
        ),
        sa.CheckConstraint(
            "length(trim(reason)) BETWEEN 1 AND 2000", name="learner_model_correction_review_reason"
        ),
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
            "annotation_id", "review_version", name="uq_learner_model_correction_review_version"
        ),
        sa.Index(
            "ix_learner_model_correction_reviews_history",
            "annotation_id",
            "review_version",
            "occurred_at",
            "id",
        ),
        sa.Index("ix_learner_model_correction_reviews_correlation", "correlation_id"),
        sa.Index(
            "ix_learner_model_correction_reviews_idempotency",
            "course_id",
            "learner_id",
            "idempotency_key",
            unique=True,
        ),
    )
    op.create_table(
        SNAPSHOT_LINKS,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_id", sa.String(36), nullable=False),
        sa.Column(
            "snapshot_id",
            sa.String(36),
            sa.ForeignKey("learner_model_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "course_id",
            sa.String(36),
            sa.ForeignKey("courses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "learner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "outcome_id",
            sa.String(36),
            sa.ForeignKey("learning_outcomes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("schema_version", sa.String(100), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("actor_reference", sa.String(255), nullable=False),
        sa.Column("correlation_id", sa.String(255), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
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
        sa.UniqueConstraint("review_id", name="uq_learner_model_correction_snapshot_review"),
        sa.Index(
            "ix_learner_model_correction_snapshot_links_snapshot", "snapshot_id", "occurred_at"
        ),
        sa.Index("ix_learner_model_correction_snapshot_links_correlation", "correlation_id"),
        sa.Index(
            "ix_learner_model_correction_snapshot_links_idempotency",
            "course_id",
            "learner_id",
            "idempotency_key",
            unique=True,
        ),
    )
    if _sqlite():
        _scope_guards()
        for table in TABLES:
            _append_only(table)


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    for table in TABLES:
        if (
            inspector.has_table(table)
            and connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        ):
            raise RuntimeError(
                "cannot downgrade populated learner-model correction history; restore a verified backup instead"
            )
    # Do not partially downgrade an otherwise protected predecessor history.
    import_module("migrations.versions.20260907_0030_learning_episodes")._preflight_downgrade()
    if _sqlite():
        for trigger in (
            "learner_model_annotation_target_scope",
            "learner_model_review_ancestry",
            "learner_model_snapshot_link_scope",
        ):
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger}"))
        for table in TABLES:
            for operation in ("update", "delete"):
                op.execute(sa.text(f"DROP TRIGGER IF EXISTS {table}_no_{operation}"))
    for table in reversed(TABLES):
        if inspector.has_table(table):
            op.drop_table(table)
