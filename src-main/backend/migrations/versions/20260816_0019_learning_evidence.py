"""Add append-only Person B learning evidence tables.

Revision ID: 20260816_0019
Revises: 20260815_0018
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_0019"
down_revision: str | None = "20260815_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ARTIFACTS = "evidence_artifacts"
_EVIDENCE = "learning_evidence"
_LINKS = "evidence_links"
_APPEND_ONLY_TABLES = (_ARTIFACTS, _EVIDENCE, _LINKS)
_DIGEST_CHECK = (
    "length(content_digest) = 71 AND content_digest GLOB 'sha256:*' "
    "AND content_digest NOT GLOB 'sha256:*[^0-9a-f]*'"
)


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def _add_append_only_triggers(table: str) -> None:
    op.execute(
        f"CREATE TRIGGER trg_{table}_append_only_update BEFORE UPDATE ON {table} BEGIN "
        "SELECT RAISE(ABORT, 'learning evidence records are append-only'); END"
    )
    op.execute(
        f"CREATE TRIGGER trg_{table}_append_only_delete BEFORE DELETE ON {table} BEGIN "
        "SELECT RAISE(ABORT, 'learning evidence records are append-only'); END"
    )


def _drop_append_only_triggers(table: str) -> None:
    op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only_delete")
    op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only_update")


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def _create_index_if_missing(name: str, table: str, columns: list[str]) -> None:
    index_names = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}
    if name not in index_names:
        op.create_index(name, table, columns)


def _ensure_safe_downgrade() -> None:
    connection = op.get_bind()
    protected_tables = (*_APPEND_ONLY_TABLES, "assessment_legacy_history")
    for table in protected_tables:
        if (
            _has_table(table)
            and connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        ):
            raise RuntimeError(
                "cannot downgrade populated evidence or assessment legacy history; "
                "restore the verified backup instead"
            )


def _create_artifacts_table() -> None:
    op.create_table(
        _ARTIFACTS,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_digest", sa.String(length=71), nullable=False),
        sa.Column("content_format", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("actor_reference", sa.String(length=255), nullable=False),
        sa.Column("agent_reference", sa.String(length=255), nullable=True),
        sa.Column("correlation_id", sa.String(length=255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("record_version > 0", name="evidence_artifact_record_version"),
        sa.CheckConstraint(_DIGEST_CHECK, name="evidence_artifact_content_digest"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["learner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_artifacts_learner_time", _ARTIFACTS, ["learner_id", "occurred_at"])


def _create_evidence_table() -> None:
    op.create_table(
        _EVIDENCE,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("artifact_id", sa.String(length=36), nullable=True),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("outcome_id", sa.String(length=36), nullable=False),
        sa.Column("activity_id", sa.String(length=255), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("response_version_id", sa.String(length=255), nullable=True),
        sa.Column("source_interaction_id", sa.String(length=255), nullable=True),
        sa.Column("source_version", sa.String(length=100), nullable=True),
        sa.Column("task_conditions_version", sa.Integer(), nullable=True),
        sa.Column(
            "evidence_type",
            _enum(
                "learning_evidence_type",
                "PREDICTION",
                "EXPLANATION",
                "REASONING",
                "RESPONSE",
                "REVISION",
                "CONFIDENCE",
                "HINT",
                "SCAFFOLD",
                "FEEDBACK_INTERACTION",
                "REFLECTION",
                "SIMULATION",
                "MISCONCEPTION_CHECK",
                "TRANSFER",
                "DIAGNOSTIC",
                "SYSTEM_FAULT",
            ),
            nullable=False,
        ),
        sa.Column(
            "provenance",
            _enum("evidence_provenance", "LEARNER", "EDUCATOR", "SYSTEM", "SIMULATOR"),
            nullable=False,
        ),
        sa.Column(
            "observation_type",
            _enum(
                "evidence_observation_type",
                "DIRECT",
                "SELF_REPORTED",
                "SYSTEM_CAPTURED",
                "EDUCATOR_RECORDED",
            ),
            nullable=False,
        ),
        sa.Column("instructional_support_level", sa.Integer(), nullable=False),
        sa.Column(
            "access_support_state",
            _enum("evidence_access_support_state", "NOT_DECLARED", "APPROVED", "PROVIDED"),
            nullable=False,
        ),
        sa.Column("content_digest", sa.String(length=71), nullable=False),
        sa.Column("actor_reference", sa.String(length=255), nullable=False),
        sa.Column("agent_reference", sa.String(length=255), nullable=True),
        sa.Column("correlation_id", sa.String(length=255), nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("record_version > 0", name="learning_evidence_record_version"),
        sa.CheckConstraint(
            "instructional_support_level BETWEEN 0 AND 5",
            name="learning_evidence_instructional_support",
        ),
        sa.CheckConstraint(_DIGEST_CHECK, name="learning_evidence_content_digest"),
        sa.ForeignKeyConstraint(["artifact_id"], ["evidence_artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["learner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["outcome_id"], ["learning_outcomes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_id"], ["learning_tasks.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_id", "learner_id", "idempotency_key", name="uq_learning_evidence_idempotency"
        ),
    )
    op.create_index(
        "ix_learning_evidence_learner_outcome_timeline",
        _EVIDENCE,
        ["learner_id", "outcome_id", "occurred_at", "created_at", "id"],
    )
    op.create_index(
        "ix_learning_evidence_course_outcome_timeline",
        _EVIDENCE,
        ["course_id", "outcome_id", "occurred_at"],
    )
    op.create_index("ix_learning_evidence_response_version", _EVIDENCE, ["response_version_id"])
    op.create_index("ix_learning_evidence_type_time", _EVIDENCE, ["evidence_type", "occurred_at"])
    op.create_index("ix_learning_evidence_correlation", _EVIDENCE, ["correlation_id"])


def _create_links_table() -> None:
    op.create_table(
        _LINKS,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("evidence_id", sa.String(length=36), nullable=False),
        sa.Column("linked_evidence_id", sa.String(length=36), nullable=False),
        sa.Column(
            "relation",
            _enum("evidence_link_relation", "SUPPORTS", "CONTRADICTS", "DERIVES_FROM"),
            nullable=False,
        ),
        sa.Column("actor_reference", sa.String(length=255), nullable=False),
        sa.Column("correlation_id", sa.String(length=255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "evidence_id <> linked_evidence_id", name="evidence_link_distinct_records"
        ),
        sa.ForeignKeyConstraint(["evidence_id"], ["learning_evidence.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["linked_evidence_id"], ["learning_evidence.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evidence_id",
            "linked_evidence_id",
            "relation",
            name="uq_evidence_links_relation",
        ),
    )
    op.create_index("ix_evidence_links_linked_evidence", _LINKS, ["linked_evidence_id"])


def upgrade() -> None:
    if not _has_table(_ARTIFACTS):
        _create_artifacts_table()
    if not _has_table(_EVIDENCE):
        _create_evidence_table()
    if not _has_table(_LINKS):
        _create_links_table()

    _create_index_if_missing(
        "ix_evidence_artifacts_learner_time", _ARTIFACTS, ["learner_id", "occurred_at"]
    )
    _create_index_if_missing(
        "ix_learning_evidence_learner_outcome_timeline",
        _EVIDENCE,
        ["learner_id", "outcome_id", "occurred_at", "created_at", "id"],
    )
    _create_index_if_missing(
        "ix_learning_evidence_course_outcome_timeline",
        _EVIDENCE,
        ["course_id", "outcome_id", "occurred_at"],
    )
    _create_index_if_missing(
        "ix_learning_evidence_response_version", _EVIDENCE, ["response_version_id"]
    )
    _create_index_if_missing(
        "ix_learning_evidence_type_time", _EVIDENCE, ["evidence_type", "occurred_at"]
    )
    _create_index_if_missing("ix_learning_evidence_correlation", _EVIDENCE, ["correlation_id"])
    _create_index_if_missing("ix_evidence_links_linked_evidence", _LINKS, ["linked_evidence_id"])

    for table in _APPEND_ONLY_TABLES:
        _drop_append_only_triggers(table)
        _add_append_only_triggers(table)


def downgrade() -> None:
    _ensure_safe_downgrade()
    for table in reversed(_APPEND_ONLY_TABLES):
        _drop_append_only_triggers(table)
    for table in (_LINKS, _EVIDENCE, _ARTIFACTS):
        if _has_table(table):
            op.drop_table(table)
