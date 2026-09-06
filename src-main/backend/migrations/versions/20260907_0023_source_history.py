"""Preserve immutable source revisions and citations. Legacy snapshots are unapproved."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "20260907_0023"
down_revision = "20260821_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("source_revisions"):
        op.create_table(
            "source_revisions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("material_id", sa.String(length=36), nullable=False),
            sa.Column("course_id", sa.String(length=255), nullable=False),
            sa.Column("module_id", sa.String(length=255), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("source_label", sa.String(length=2048), nullable=False),
            sa.Column("mime_type", sa.String(length=100), nullable=False),
            sa.Column("content_hash", sa.String(length=128), nullable=False),
            sa.Column("storage_key", sa.String(length=512), nullable=True),
            sa.Column("extracted_blocks", sa.JSON(), nullable=False),
            sa.Column("extraction_version", sa.String(length=255), nullable=False),
            sa.Column("provenance", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "provenance IN ('EXTRACTED', 'LEGACY_SNAPSHOT')",
                name=op.f("ck_source_revisions_source_revision_provenance"),
            ),
            sa.CheckConstraint(
                "version > 0", name=op.f("ck_source_revisions_source_revision_positive_version")
            ),
            sa.ForeignKeyConstraint(
                ["material_id"],
                ["learning_materials.id"],
                name=op.f("fk_source_revisions_material_id_learning_materials"),
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_source_revisions")),
            sa.UniqueConstraint("id", "course_id", name="uq_source_revision_course"),
            sa.UniqueConstraint("material_id", "version", name="uq_source_revision_version"),
        )
        with op.batch_alter_table("source_revisions", schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f("ix_source_revisions_material_id"), ["material_id"], unique=False
            )

    if not inspector.has_table("source_approvals"):
        op.create_table(
            "source_approvals",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("revision_id", sa.String(length=36), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("state", sa.String(length=16), nullable=False),
            sa.Column("actor_id", sa.String(length=255), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "state IN ('APPROVED', 'REVOKED')",
                name=op.f("ck_source_approvals_source_approval_state"),
            ),
            sa.CheckConstraint(
                "sequence > 0", name=op.f("ck_source_approvals_source_approval_sequence")
            ),
            sa.ForeignKeyConstraint(
                ["revision_id"],
                ["source_revisions.id"],
                name=op.f("fk_source_approvals_revision_id_source_revisions"),
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_source_approvals")),
            sa.UniqueConstraint("revision_id", "sequence", name="uq_source_approval_sequence"),
        )

    if not inspector.has_table("source_passages"):
        op.create_table(
            "source_passages",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("revision_id", sa.String(length=36), nullable=False),
            sa.Column("course_id", sa.String(length=255), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("chunk_text", sa.Text(), nullable=False),
            sa.Column("heading", sa.String(length=500), nullable=True),
            sa.Column("location_label", sa.String(length=100), nullable=True),
            sa.Column("chunk_hash", sa.String(length=128), nullable=False),
            sa.CheckConstraint(
                "chunk_index >= 0", name=op.f("ck_source_passages_source_passage_index")
            ),
            sa.ForeignKeyConstraint(
                ["revision_id", "course_id"],
                ["source_revisions.id", "source_revisions.course_id"],
                name=op.f("fk_source_passages_revision_id_source_revisions"),
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_source_passages")),
            sa.UniqueConstraint("id", "course_id", name="uq_source_passage_course"),
            sa.UniqueConstraint("revision_id", "chunk_index", name="uq_source_passage_order"),
        )
        with op.batch_alter_table("source_passages", schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f("ix_source_passages_revision_id"), ["revision_id"], unique=False
            )

    if not inspector.has_table("source_uses"):
        op.create_table(
            "source_uses",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("course_id", sa.String(length=255), nullable=False),
            sa.Column("output_type", sa.String(length=16), nullable=False),
            sa.Column("output_id", sa.String(length=255), nullable=False),
            sa.Column("output_version", sa.String(length=128), nullable=False),
            sa.Column("source_id", sa.String(length=255), nullable=False),
            sa.Column("passage_id", sa.String(length=36), nullable=False),
            sa.Column("approval_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "output_type IN ('task', 'feedback', 'assessment')",
                name=op.f("ck_source_uses_source_use_output_type"),
            ),
            sa.ForeignKeyConstraint(
                ["approval_id"],
                ["source_approvals.id"],
                name=op.f("fk_source_uses_approval_id_source_approvals"),
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["passage_id", "course_id"],
                ["source_passages.id", "source_passages.course_id"],
                name=op.f("fk_source_uses_passage_id_source_passages"),
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_source_uses")),
            sa.UniqueConstraint(
                "output_type",
                "output_id",
                "output_version",
                "passage_id",
                name="uq_source_use_output_passage",
            ),
        )
        with op.batch_alter_table("source_uses", schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f("ix_source_uses_course_id"), ["course_id"], unique=False
            )
            batch_op.create_index(
                batch_op.f("ix_source_uses_output_id"), ["output_id"], unique=False
            )

    columns = {column["name"] for column in inspector.get_columns("learning_materials")}
    if "current_source_revision_id" not in columns:
        op.add_column(
            "learning_materials",
            sa.Column("current_source_revision_id", sa.String(36), nullable=True),
        )
    if "retired_at" not in columns:
        op.add_column(
            "learning_materials", sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True)
        )

    _backfill()
    _protect_history()


_HISTORY_TABLES = ("source_revisions", "source_passages", "source_approvals", "source_uses")


def _backfill() -> None:
    connection = op.get_bind()
    metadata = sa.MetaData()
    materials = sa.Table("learning_materials", metadata, autoload_with=connection)
    chunks = sa.Table("material_chunks", metadata, autoload_with=connection)
    revisions = sa.Table("source_revisions", metadata, autoload_with=connection)
    passages = sa.Table("source_passages", metadata, autoload_with=connection)
    uses = sa.Table("source_uses", metadata, autoload_with=connection)
    known_passages = dict(connection.execute(sa.select(passages.c.id, passages.c.course_id)).all())
    material_passages = {}
    for material in connection.execute(sa.select(materials)).mappings():
        rows = list(
            connection.execute(
                sa.select(chunks).where(chunks.c.material_id == material["id"])
            ).mappings()
        )
        if not rows:
            continue
        material_passages[material["id"]] = (material["course_id"], [chunk["id"] for chunk in rows])
        if connection.execute(
            sa.select(revisions.c.id).where(revisions.c.material_id == material["id"])
        ).first():
            continue
        revision_id = str(uuid.uuid4())
        connection.execute(
            revisions.insert().values(
                id=revision_id,
                material_id=material["id"],
                course_id=material["course_id"],
                module_id=material["module_id"],
                version=1,
                source_label=material["original_filename"] or material["source_url"] or "Material",
                mime_type=material["mime_type"],
                content_hash=material["content_hash"],
                storage_key=material["storage_key"],
                extracted_blocks=[],
                extraction_version="legacy-snapshot-v1",
                provenance="LEGACY_SNAPSHOT",
                created_at=datetime.now(UTC),
            )
        )
        for chunk in rows:
            connection.execute(
                passages.insert().values(
                    id=chunk["id"],
                    revision_id=revision_id,
                    course_id=material["course_id"],
                    chunk_index=chunk["chunk_index"],
                    chunk_text=chunk["chunk_text"],
                    heading=chunk["heading"],
                    location_label=chunk["location_label"],
                    chunk_hash=chunk["chunk_hash"],
                )
            )
            known_passages[chunk["id"]] = material["course_id"]
        connection.execute(
            materials.update()
            .where(materials.c.id == material["id"])
            .values(current_source_revision_id=revision_id)
        )
    # Freeze task aliases at migration; label their provenance unverified. Never reinterpret old feedback aliases.
    tasks = sa.Table("learning_tasks", metadata, autoload_with=connection)
    feedback = sa.Table("feedback_records", metadata, autoload_with=connection)
    workflows = sa.Table("workflow_runs", metadata, autoload_with=connection)
    for output_type, query in (
        ("task", sa.select(tasks.c.id, tasks.c.course_id, tasks.c.source_references)),
        (
            "feedback",
            sa.select(feedback.c.id, workflows.c.course_id, feedback.c.source_references).join(
                workflows, workflows.c.id == feedback.c.workflow_run_id
            ),
        ),
    ):
        for output in connection.execute(query).mappings():
            refs = output["source_references"] or []
            if not isinstance(refs, list):
                continue
            if output_type == "task":
                expanded = []
                for reference in refs:
                    material_scope = (
                        material_passages.get(reference) if isinstance(reference, str) else None
                    )
                    if material_scope and material_scope[0] == output["course_id"]:
                        expanded.extend(material_scope[1])
                    else:
                        expanded.append(reference)
                refs = list(dict.fromkeys(ref for ref in expanded if isinstance(ref, str)))
                connection.execute(
                    tasks.update().where(tasks.c.id == output["id"]).values(source_references=refs)
                )
            for reference in set(ref for ref in refs if isinstance(ref, str)):
                if (
                    known_passages.get(reference) != output["course_id"]
                    or reference not in known_passages
                ):
                    continue
                if connection.execute(
                    sa.select(uses.c.id).where(
                        uses.c.output_type == output_type,
                        uses.c.output_id == output["id"],
                        uses.c.output_version == "legacy-unverified",
                        uses.c.passage_id == reference,
                    )
                ).first():
                    continue
                connection.execute(
                    uses.insert().values(
                        id=str(uuid.uuid4()),
                        course_id=output["course_id"],
                        output_type=output_type,
                        output_id=output["id"],
                        output_version="legacy-unverified",
                        source_id=reference,
                        passage_id=reference,
                        approval_id=None,
                        created_at=datetime.now(UTC),
                    )
                )


def _protect_history() -> None:
    if op.get_bind().dialect.name == "sqlite":
        for table in _HISTORY_TABLES:
            op.execute(
                sa.text(
                    f"CREATE TRIGGER IF NOT EXISTS {table}_no_replace BEFORE INSERT ON {table} "
                    f"WHEN EXISTS (SELECT 1 FROM {table} WHERE id = NEW.id) "
                    "BEGIN SELECT RAISE(ABORT, 'Source history is append-only'); END"
                )
            )
            for action in ("UPDATE", "DELETE"):
                op.execute(
                    sa.text(
                        f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} BEFORE {action} ON {table} "
                        "BEGIN SELECT RAISE(ABORT, 'Source history is append-only'); END"
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
    for table in _HISTORY_TABLES:
        if connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError(
                "Source history is protected; restore a verified backup instead of dropping populated history"
            )
    inspector = sa.inspect(connection)
    if (
        inspector.has_table("assessor_reviews")
        and connection.execute(sa.text("SELECT COUNT(*) FROM assessor_reviews")).scalar_one()
    ):
        raise RuntimeError(
            "cannot downgrade populated assessor review history; restore the verified backup instead"
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
                "cannot downgrade populated assessor review history or protected learner-model, evidence, or assessment history; restore the verified backup instead"
            )
    for table in reversed(_HISTORY_TABLES):
        op.drop_table(table)
    # Native DROP COLUMN avoids rebuilding a parent referenced by protected history tables.
    op.drop_column("learning_materials", "retired_at")
    op.drop_column("learning_materials", "current_source_revision_id")
