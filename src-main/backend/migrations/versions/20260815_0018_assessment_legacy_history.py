"""Archive legacy assessment values without inferring a pass result.

Revision ID: 20260815_0018
Revises: 20260815_0017
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0018"
down_revision: str | None = "20260815_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_HISTORY_TABLE = "assessment_legacy_history"
_LEGACY_LEARNER_RESULTS = "legacy_learner_results"
_MIGRATION_ACTOR = "alembic:20260815_0018"
_AUDIT_DEDUPLICATION_PREFIX = "assessment-legacy-result:"
_MAX_AUDIT_SOURCE_ID_LENGTH = 255 - len(_AUDIT_DEDUPLICATION_PREFIX)
_MAPPED_RESULT_CHECK = (
    "mapped_result IS NULL OR (source_table = 'legacy_learner_results' "
    "AND upper(trim(source_result)) = 'FAIL' AND mapped_result = 'INCOMPLETE' "
    "AND migration_reason = 'LEGACY_PUBLIC_FAIL_TO_INCOMPLETE')"
)


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def _history_table() -> sa.Table:
    return sa.Table(
        _HISTORY_TABLE,
        sa.MetaData(),
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("source_table", sa.String(length=100), nullable=False),
        sa.Column("source_record_id", sa.String(length=255), nullable=False),
        sa.Column("response_version_id", sa.String(length=36), nullable=True),
        sa.Column("source_status", sa.String(length=100), nullable=True),
        sa.Column("source_result", sa.String(length=100), nullable=True),
        sa.Column("source_score", sa.Integer(), nullable=True),
        sa.Column("mapped_result", sa.String(length=20), nullable=True),
        sa.Column("migration_revision", sa.String(length=32), nullable=False),
        sa.Column("migration_actor", sa.String(length=255), nullable=False),
        sa.Column("migration_reason", sa.String(length=255), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
    )


def _create_history_table() -> None:
    op.create_table(
        _HISTORY_TABLE,
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("source_table", sa.String(length=100), nullable=False),
        sa.Column("source_record_id", sa.String(length=255), nullable=False),
        sa.Column("response_version_id", sa.String(length=36), nullable=True),
        sa.Column("source_status", sa.String(length=100), nullable=True),
        sa.Column("source_result", sa.String(length=100), nullable=True),
        sa.Column("source_score", sa.Integer(), nullable=True),
        sa.Column("mapped_result", sa.String(length=20), nullable=True),
        sa.Column("migration_revision", sa.String(length=32), nullable=False),
        sa.Column("migration_actor", sa.String(length=255), nullable=False),
        sa.Column("migration_reason", sa.String(length=255), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            _MAPPED_RESULT_CHECK,
            name="assessment_legacy_history_mapped_result",
        ),
        sa.ForeignKeyConstraint(
            ["response_version_id"],
            ["submission_attempts.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_table",
            "source_record_id",
            name="uq_assessment_legacy_history_source_record",
        ),
    )
    op.create_index(
        "ix_assessment_legacy_history_response",
        _HISTORY_TABLE,
        ["response_version_id"],
    )
    op.execute(
        "CREATE TRIGGER trg_assessment_legacy_history_immutable_update "
        "BEFORE UPDATE ON assessment_legacy_history BEGIN "
        "SELECT RAISE(ABORT, 'assessment legacy history is immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_assessment_legacy_history_immutable_delete "
        "BEFORE DELETE ON assessment_legacy_history BEGIN "
        "SELECT RAISE(ABORT, 'assessment legacy history is immutable'); END"
    )


def _create_history_insert_guard() -> None:
    # A rerun may inherit a crash-left or forged trigger with this name.  Archive
    # writes have completed at this point, so replacing it is safe and ensures
    # the final schema always has the migration-only guard.
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_legacy_history_migration_only_insert")
    op.execute(
        "CREATE TRIGGER trg_assessment_legacy_history_migration_only_insert "
        "BEFORE INSERT ON assessment_legacy_history BEGIN "
        "SELECT RAISE(ABORT, 'assessment legacy history is migration-only'); END"
    )


def _validate_history_table(
    connection: sa.Connection, *, require_insert_guard: bool = False
) -> None:
    """Reject a crash-left partial table before it can receive archive rows."""

    inspector = sa.inspect(connection)
    expected_columns = {
        "id": ("VARCHAR(255)", False),
        "source_table": ("VARCHAR(100)", False),
        "source_record_id": ("VARCHAR(255)", False),
        "response_version_id": ("VARCHAR(36)", True),
        "source_status": ("VARCHAR(100)", True),
        "source_result": ("VARCHAR(100)", True),
        "source_score": ("INTEGER", True),
        "mapped_result": ("VARCHAR(20)", True),
        "migration_revision": ("VARCHAR(32)", False),
        "migration_actor": ("VARCHAR(255)", False),
        "migration_reason": ("VARCHAR(255)", False),
        "archived_at": ("DATETIME", False),
    }
    actual_columns = {
        column["name"]: (str(column["type"]).upper(), column["nullable"])
        for column in inspector.get_columns(_HISTORY_TABLE)
    }
    checks = {
        constraint["name"]: " ".join(constraint["sqltext"].split())
        for constraint in inspector.get_check_constraints(_HISTORY_TABLE)
    }
    unique_constraints = {
        constraint["name"]: constraint["column_names"]
        for constraint in inspector.get_unique_constraints(_HISTORY_TABLE)
    }
    indexes = {
        index["name"]: index["column_names"] for index in inspector.get_indexes(_HISTORY_TABLE)
    }
    foreign_keys = inspector.get_foreign_keys(_HISTORY_TABLE)
    has_response_foreign_key = any(
        foreign_key["constrained_columns"] == ["response_version_id"]
        and foreign_key["referred_table"] == "submission_attempts"
        and foreign_key.get("options", {}).get("ondelete") == "RESTRICT"
        for foreign_key in foreign_keys
    )
    trigger_sql = dict(
        connection.execute(
            sa.text(
                "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' "
                "AND tbl_name = 'assessment_legacy_history'"
            )
        ).all()
    )
    required_trigger_fragments = {
        "trg_assessment_legacy_history_immutable_update": "BEFORE UPDATE ON assessment_legacy_history",
        "trg_assessment_legacy_history_immutable_delete": "BEFORE DELETE ON assessment_legacy_history",
    }
    if require_insert_guard:
        required_trigger_fragments["trg_assessment_legacy_history_migration_only_insert"] = (
            "BEFORE INSERT ON assessment_legacy_history"
        )
    expected_check = " ".join(_MAPPED_RESULT_CHECK.split())
    if (
        actual_columns != expected_columns
        or inspector.get_pk_constraint(_HISTORY_TABLE)["constrained_columns"] != ["id"]
        or checks.get("ck_assessment_legacy_history_assessment_legacy_history_mapped_result")
        != expected_check
        or unique_constraints.get("uq_assessment_legacy_history_source_record")
        != ["source_table", "source_record_id"]
        or indexes.get("ix_assessment_legacy_history_response") != ["response_version_id"]
        or not has_response_foreign_key
        or any(
            fragment not in trigger_sql.get(name, "")
            or (
                "assessment legacy history is immutable" not in trigger_sql.get(name, "")
                if name != "trg_assessment_legacy_history_migration_only_insert"
                else "assessment legacy history is migration-only" not in trigger_sql.get(name, "")
            )
            for name, fragment in required_trigger_fragments.items()
        )
    ):
        raise RuntimeError(
            "assessment_legacy_history exists but is incomplete; restore the verified backup "
            "before rerunning the migration"
        )


def _archive_submission_attempts(connection: sa.Connection) -> None:
    history = _history_table()
    attempts = sa.table(
        "submission_attempts",
        sa.column("id"),
        sa.column("status"),
        sa.column("score"),
    )
    source_id = sa.literal("submission_attempts:") + attempts.c.id
    exists = sa.exists(
        sa.select(history.c.id).where(
            history.c.source_table == "submission_attempts",
            history.c.source_record_id == attempts.c.id,
        )
    )
    connection.execute(
        sa.insert(history).from_select(
            [
                "id",
                "source_table",
                "source_record_id",
                "response_version_id",
                "source_status",
                "source_result",
                "source_score",
                "mapped_result",
                "migration_revision",
                "migration_actor",
                "migration_reason",
                "archived_at",
            ],
            sa.select(
                source_id,
                sa.literal("submission_attempts"),
                attempts.c.id,
                attempts.c.id,
                attempts.c.status,
                sa.null(),
                attempts.c.score,
                sa.null(),
                sa.literal(revision),
                sa.literal(_MIGRATION_ACTOR),
                sa.literal("LEGACY_NUMERIC_SCORE_AND_STATUS_PRESERVED_UNMAPPED"),
                sa.func.current_timestamp(),
            ).where(~exists),
        )
    )


def _validate_legacy_learner_results(connection: sa.Connection) -> None:
    """Reject compatibility data that cannot receive a unique audit key."""

    inspector = sa.inspect(connection)
    if not inspector.has_table(_LEGACY_LEARNER_RESULTS):
        return

    columns = {column["name"] for column in inspector.get_columns(_LEGACY_LEARNER_RESULTS)}
    required = {"id", "response_version_id", "result", "score"}
    missing = required - columns
    if missing:
        raise RuntimeError(
            "legacy_learner_results is missing required compatibility columns: "
            + ", ".join(sorted(missing))
        )

    legacy = sa.table(_LEGACY_LEARNER_RESULTS, sa.column("id"))
    oversized_source_id_count = connection.execute(
        sa.select(sa.func.count())
        .select_from(legacy)
        .where(sa.func.length(legacy.c.id) > _MAX_AUDIT_SOURCE_ID_LENGTH)
    ).scalar_one()
    if oversized_source_id_count:
        raise RuntimeError(
            "legacy learner result IDs exceed the maximum safe audit source ID length "
            f"({_MAX_AUDIT_SOURCE_ID_LENGTH})"
        )


def _archive_legacy_learner_results(connection: sa.Connection) -> None:
    inspector = sa.inspect(connection)
    if not inspector.has_table(_LEGACY_LEARNER_RESULTS):
        return

    columns = {column["name"] for column in inspector.get_columns(_LEGACY_LEARNER_RESULTS)}
    required = {"id", "response_version_id", "result", "score"}
    missing = required - columns
    if missing:
        raise RuntimeError(
            "legacy_learner_results is missing required compatibility columns: "
            + ", ".join(sorted(missing))
        )

    history = _history_table()
    legacy = sa.table(
        _LEGACY_LEARNER_RESULTS,
        sa.column("id"),
        sa.column("response_version_id"),
        sa.column("result"),
        sa.column("score"),
    )
    normalized_result = sa.func.upper(sa.func.trim(legacy.c.result))
    mapped_result = sa.case(
        (normalized_result == "FAIL", sa.literal("INCOMPLETE")),
        else_=sa.null(),
    )
    reason = sa.case(
        (
            normalized_result == "FAIL",
            sa.literal("LEGACY_PUBLIC_FAIL_TO_INCOMPLETE"),
        ),
        else_=sa.literal("LEGACY_PUBLIC_RESULT_UNMAPPED"),
    )
    exists = sa.exists(
        sa.select(history.c.id).where(
            history.c.source_table == _LEGACY_LEARNER_RESULTS,
            history.c.source_record_id == legacy.c.id,
        )
    )
    connection.execute(
        sa.insert(history).from_select(
            [
                "id",
                "source_table",
                "source_record_id",
                "response_version_id",
                "source_status",
                "source_result",
                "source_score",
                "mapped_result",
                "migration_revision",
                "migration_actor",
                "migration_reason",
                "archived_at",
            ],
            sa.select(
                sa.literal("legacy_learner_results:") + legacy.c.id,
                sa.literal(_LEGACY_LEARNER_RESULTS),
                legacy.c.id,
                legacy.c.response_version_id,
                sa.null(),
                legacy.c.result,
                legacy.c.score,
                mapped_result,
                sa.literal(revision),
                sa.literal(_MIGRATION_ACTOR),
                reason,
                sa.func.current_timestamp(),
            ).where(~exists),
        )
    )


def _backfill_legacy_result_audit_events(connection: sa.Connection) -> None:
    history = _history_table()
    audit_events = sa.table(
        "audit_events",
        sa.column("id"),
        sa.column("actor_reference"),
        sa.column("action"),
        sa.column("outcome"),
        sa.column("occurred_at"),
        sa.column("correlation_id"),
        sa.column("resource_type"),
        sa.column("resource_id"),
        sa.column("failure_category"),
        sa.column("deduplication_key"),
    )
    deduplication_key = sa.literal(_AUDIT_DEDUPLICATION_PREFIX) + history.c.source_record_id
    exists = sa.exists(
        sa.select(audit_events.c.id).where(audit_events.c.deduplication_key == deduplication_key)
    )
    connection.execute(
        sa.insert(audit_events).from_select(
            [
                "id",
                "actor_reference",
                "action",
                "outcome",
                "occurred_at",
                "correlation_id",
                "resource_type",
                "resource_id",
                "failure_category",
                "deduplication_key",
            ],
            sa.select(
                sa.func.lower(sa.func.hex(sa.func.randomblob(16))),
                sa.literal(_MIGRATION_ACTOR),
                sa.literal("assessment_legacy_result_migrated"),
                sa.literal("success"),
                history.c.archived_at,
                sa.func.lower(sa.func.hex(sa.func.randomblob(16))),
                sa.literal("assessment_legacy_history"),
                history.c.id,
                sa.null(),
                deduplication_key,
            ).where(
                history.c.source_table == _LEGACY_LEARNER_RESULTS,
                history.c.mapped_result == "INCOMPLETE",
                ~exists,
            ),
        )
    )


def _update_audit_action_constraint(include_legacy_action: bool) -> None:
    actions = [
        "assessment_definition_created",
        "assessment_attempt_created",
        "assessment_decision_created",
        "assessor_review_recorded",
        "appeal_or_correction_recorded",
        "feedback_generation_started",
        "feedback_generation_completed",
        "feedback_judged",
        "feedback_regenerated",
        "feedback_fallback_used",
        "feedback_viewed",
        "feedback_reported",
        "research_export_created",
        "workflow_completed",
        "workflow_failed",
    ]
    if include_legacy_action:
        actions.insert(3, "assessment_legacy_result_migrated")
    with op.batch_alter_table("audit_events") as batch:
        batch.drop_constraint("audit_action", type_="check")
        batch.alter_column(
            "action",
            existing_type=sa.String(length=100),
            type_=_enum("audit_action", *actions),
            existing_nullable=False,
        )


def upgrade() -> None:
    connection = op.get_bind()
    _validate_legacy_learner_results(connection)
    if not sa.inspect(connection).has_table(_HISTORY_TABLE):
        _create_history_table()

    _validate_history_table(connection)
    _update_audit_action_constraint(include_legacy_action=True)
    _archive_legacy_learner_results(connection)
    _archive_submission_attempts(connection)
    _backfill_legacy_result_audit_events(connection)
    _create_history_insert_guard()
    _validate_history_table(connection, require_insert_guard=True)


def downgrade() -> None:
    connection = op.get_bind()
    history_row_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM assessment_legacy_history")
    ).scalar_one()
    if history_row_count:
        raise RuntimeError(
            "cannot downgrade populated assessment legacy history; restore the verified backup instead"
        )
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_legacy_history_migration_only_insert")
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_legacy_history_immutable_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_legacy_history_immutable_update")
    op.drop_index("ix_assessment_legacy_history_response", table_name=_HISTORY_TABLE)
    op.drop_table(_HISTORY_TABLE)
    _update_audit_action_constraint(include_legacy_action=False)
