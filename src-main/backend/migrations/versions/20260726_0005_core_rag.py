"""Add persisted chunks, indexing metadata, and retrieval audits.

Revision ID: 20260726_0005
Revises: 20260726_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260726_0005"
down_revision: str | None = "20260726_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("material_chunks") as batch_op:
        batch_op.add_column(sa.Column("chunk_hash", sa.String(128), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("embedding_dimension", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "retrieval_audits",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("course_id", sa.String(255), nullable=False),
        sa.Column("module_id", sa.String(255), nullable=True),
        sa.Column("task_id", sa.String(255), nullable=True),
        sa.Column("purpose", sa.String(50), nullable=False),
        sa.Column("query_hash", sa.String(64), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("minimum_relevance", sa.Float(), nullable=False),
        sa.Column("result_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("result_scores", sa.JSON(), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("top_k > 0", name="ck_retrieval_audits_retrieval_audit_top_k"),
        sa.CheckConstraint("minimum_relevance BETWEEN 0 AND 1", name="ck_retrieval_audits_retrieval_audit_relevance"),
        sa.CheckConstraint("hit_count >= 0", name="ck_retrieval_audits_retrieval_audit_hit_count"),
        sa.CheckConstraint("latency_ms >= 0", name="ck_retrieval_audits_retrieval_audit_latency"),
        sa.PrimaryKeyConstraint("id", name="pk_retrieval_audits"),
    )
    op.create_index("ix_retrieval_audits_course_created", "retrieval_audits", ["course_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_retrieval_audits_course_created", table_name="retrieval_audits")
    op.drop_table("retrieval_audits")
    with op.batch_alter_table("material_chunks") as batch_op:
        batch_op.drop_column("indexed_at")
        batch_op.drop_column("embedding_dimension")
        batch_op.drop_column("chunk_hash")
