"""Add generated-task context and learning material persistence.

Revision ID: 20260726_0003
Revises: 20260720_0002, 20260722_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260726_0003"
down_revision: tuple[str, str] = ("20260720_0002", "20260722_0002")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    with op.batch_alter_table("learning_tasks") as batch_op:
        batch_op.add_column(sa.Column("course_id", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("module_id", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("learning_outcome_id", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("marking_criteria", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("source_references", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("prerequisite_task_ids", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("generation_provider", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("generation_model", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("generation_prompt_version", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("generation_input_tokens", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("generation_output_tokens", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("generation_total_tokens", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("generation_estimated_cost", sa.Numeric(12, 6), nullable=False, server_default="0"))
        batch_op.create_check_constraint("learning_task_generation_input_tokens", "generation_input_tokens >= 0")
        batch_op.create_check_constraint("learning_task_generation_output_tokens", "generation_output_tokens >= 0")
        batch_op.create_check_constraint("learning_task_generation_total_tokens", "generation_total_tokens >= 0")
        batch_op.create_check_constraint("learning_task_generation_cost", "generation_estimated_cost >= 0")
        batch_op.create_check_constraint(
            "learning_task_generation_metadata",
            "(generation_provider IS NULL AND generation_model IS NULL "
            "AND generation_prompt_version IS NULL AND generation_input_tokens = 0 "
            "AND generation_output_tokens = 0 AND generation_total_tokens = 0 "
            "AND generation_estimated_cost = 0) OR "
            "(generation_provider IS NOT NULL AND generation_model IS NOT NULL "
            "AND generation_prompt_version IS NOT NULL "
            "AND generation_total_tokens = generation_input_tokens + generation_output_tokens)",
        )

    op.create_table(
        "learning_materials",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("course_id", sa.String(255), nullable=False),
        sa.Column("module_id", sa.String(255), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column("indexing_status", _enum("pending", "extracted", "indexed", "failed", name="material_index_status"), nullable=False),
        sa.Column("extraction_error", sa.Text(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("(original_filename IS NOT NULL AND source_url IS NULL) OR (original_filename IS NULL AND source_url IS NOT NULL)", name="ck_learning_materials_learning_material_source_identity"),
        sa.CheckConstraint("source_url IS NULL OR source_url LIKE 'https://%'", name="ck_learning_materials_learning_material_https_source"),
        sa.PrimaryKeyConstraint("id", name="pk_learning_materials"),
        sa.UniqueConstraint("course_id", "content_hash", name="uq_learning_materials_course_hash"),
    )
    op.create_index("ix_learning_materials_course_id", "learning_materials", ["course_id"])
    op.create_table(
        "material_chunks",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("material_id", sa.String(36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("heading", sa.String(500), nullable=True),
        sa.Column("location_label", sa.String(100), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding_model", sa.String(255), nullable=True),
        sa.Column("embedding_version", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("chunk_index >= 0", name="ck_material_chunks_material_chunk_index"),
        sa.CheckConstraint("token_count >= 0", name="ck_material_chunks_material_chunk_token_count"),
        sa.ForeignKeyConstraint(["material_id"], ["learning_materials.id"], ondelete="CASCADE", name="fk_material_chunks_material_id_learning_materials"),
        sa.PrimaryKeyConstraint("id", name="pk_material_chunks"),
        sa.UniqueConstraint("material_id", "chunk_index", name="uq_material_chunks_material_index"),
    )
    op.create_index("ix_material_chunks_material_order", "material_chunks", ["material_id", "chunk_index"])


def downgrade() -> None:
    op.drop_index("ix_material_chunks_material_order", table_name="material_chunks")
    op.drop_table("material_chunks")
    op.drop_index("ix_learning_materials_course_id", table_name="learning_materials")
    op.drop_table("learning_materials")
    with op.batch_alter_table("learning_tasks") as batch_op:
        batch_op.drop_constraint("learning_task_generation_metadata", type_="check")
        batch_op.drop_constraint("learning_task_generation_cost", type_="check")
        batch_op.drop_constraint("learning_task_generation_total_tokens", type_="check")
        batch_op.drop_constraint("learning_task_generation_output_tokens", type_="check")
        batch_op.drop_constraint("learning_task_generation_input_tokens", type_="check")
        batch_op.drop_column("generation_estimated_cost")
        batch_op.drop_column("generation_total_tokens")
        batch_op.drop_column("generation_output_tokens")
        batch_op.drop_column("generation_input_tokens")
        batch_op.drop_column("generation_prompt_version")
        batch_op.drop_column("generation_model")
        batch_op.drop_column("generation_provider")
        batch_op.drop_column("prerequisite_task_ids")
        batch_op.drop_column("source_references")
        batch_op.drop_column("marking_criteria")
        batch_op.drop_column("learning_outcome_id")
        batch_op.drop_column("module_id")
        batch_op.drop_column("course_id")
