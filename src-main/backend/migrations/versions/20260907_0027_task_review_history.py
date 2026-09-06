"""task_review_history

Revision ID: 20260907_0027
Revises: 20260907_0026
Create Date: 2026-09-07 03:18:27.051724
"""

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0027"
down_revision: str | None = "20260907_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("task_revisions"):
        op.create_table(
            "task_revisions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("task_id", sa.String(length=36), nullable=False),
            sa.Column("course_id", sa.String(length=36), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("snapshot", sa.JSON(), nullable=False),
            sa.Column("content_digest", sa.String(length=64), nullable=False),
            sa.Column("provenance", sa.String(length=16), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "provenance IN ('AUTHORED', 'GENERATED', 'LEGACY')",
                name=op.f("ck_task_revisions_task_revision_provenance"),
            ),
            sa.CheckConstraint("version > 0", name=op.f("ck_task_revisions_task_revision_version")),
            sa.ForeignKeyConstraint(
                ["actor_user_id"],
                ["users.id"],
                name=op.f("fk_task_revisions_actor_user_id_users"),
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["course_id"],
                ["courses.id"],
                name=op.f("fk_task_revisions_course_id_courses"),
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["task_id"],
                ["learning_tasks.id"],
                name=op.f("fk_task_revisions_task_id_learning_tasks"),
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_task_revisions")),
            sa.UniqueConstraint("id", "course_id", name="uq_task_revision_course"),
            sa.UniqueConstraint("task_id", "version", name="uq_task_revision_version"),
        )
    if not inspector.has_table("task_review_events"):
        op.create_table(
            "task_review_events",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("task_revision_id", sa.String(length=36), nullable=False),
            sa.Column("course_id", sa.String(length=36), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("state", sa.String(length=16), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("source_approvals", sa.JSON(), nullable=False),
            sa.Column("policy_version", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "state IN ('SUBMITTED', 'APPROVED', 'REJECTED', 'WITHDRAWN')",
                name=op.f("ck_task_review_events_task_review_state"),
            ),
            sa.CheckConstraint(
                "length(trim(reason)) > 0", name=op.f("ck_task_review_events_task_review_reason")
            ),
            sa.CheckConstraint(
                "version > 0", name=op.f("ck_task_review_events_task_review_version")
            ),
            sa.ForeignKeyConstraint(
                ["actor_user_id"],
                ["users.id"],
                name=op.f("fk_task_review_events_actor_user_id_users"),
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["task_revision_id", "course_id"],
                ["task_revisions.id", "task_revisions.course_id"],
                name=op.f("fk_task_review_events_task_revision_id_task_revisions"),
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_task_review_events")),
            sa.UniqueConstraint("task_revision_id", "version", name="uq_task_review_version"),
        )
    _backfill()
    _guards()


def _guards() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    for table, unique in (
        ("task_revisions", "task_id = NEW.task_id AND version = NEW.version"),
        ("task_review_events", "task_revision_id = NEW.task_revision_id AND version = NEW.version"),
    ):
        for action in ("UPDATE", "DELETE"):
            op.execute(
                sa.text(
                    f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} BEFORE {action} ON {table} "
                    "BEGIN SELECT RAISE(ABORT, 'Task review history is append-only'); END"
                )
            )
        op.execute(
            sa.text(
                f"CREATE TRIGGER IF NOT EXISTS {table}_no_replace BEFORE INSERT ON {table} "
                f"WHEN EXISTS (SELECT 1 FROM {table} WHERE id = NEW.id OR ({unique})) "
                "BEGIN SELECT RAISE(ABORT, 'Task review history is append-only'); END"
            )
        )


# Keep the migration snapshot contract independent of future application changes.
_CONTENT_FIELDS = (
    "id",
    "slug",
    "title",
    "module",
    "description",
    "instructions",
    "task_type",
    "difficulty",
    "points",
    "position",
    "starter_code",
    "expected_answer",
    "due_at",
    "course_id",
    "module_id",
    "learning_outcome_id",
    "marking_criteria",
    "source_references",
    "prerequisite_task_ids",
    "generation_provider",
    "generation_model",
    "generation_prompt_version",
)


def _json_value(value):
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        ).isoformat()
    raise TypeError("Unsupported legacy task snapshot value")


def _backfill() -> None:
    connection = op.get_bind()
    metadata = sa.MetaData()
    tasks = sa.Table("learning_tasks", metadata, autoload_with=connection)
    courses = sa.Table("courses", metadata, autoload_with=connection)
    outcomes = sa.Table("learning_outcomes", metadata, autoload_with=connection)
    revisions = sa.Table("task_revisions", metadata, autoload_with=connection)
    statement = (
        sa.select(tasks)
        .join(courses, courses.c.id == tasks.c.course_id)
        .where(~sa.exists(sa.select(revisions.c.id).where(revisions.c.task_id == tasks.c.id)))
    )
    for task in connection.execute(statement).mappings():
        snapshot = {name: task[name] for name in _CONTENT_FIELDS}
        outcome = (
            connection.execute(
                sa.select(outcomes).where(outcomes.c.id == task["learning_outcome_id"])
            )
            .mappings()
            .first()
        )
        snapshot["outcome"] = (
            {name: outcome[name] for name in ("id", "module_id", "title", "statement", "kind")}
            if outcome
            else None
        )
        snapshot = json.loads(json.dumps(snapshot, default=_json_value, allow_nan=False))
        digest = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
        connection.execute(
            revisions.insert().values(
                id=str(uuid4()),
                task_id=task["id"],
                course_id=task["course_id"],
                version=1,
                snapshot=snapshot,
                content_digest=digest,
                provenance="LEGACY",
                actor_user_id=None,
                created_at=datetime.now(UTC),
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

    for table in ("task_revisions", "task_review_events"):
        if connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError(
                "Task review history is protected; restore a verified backup instead"
            )
    op.drop_table("task_review_events")
    op.drop_table("task_revisions")
