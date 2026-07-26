"""Add material lifecycle storage metadata.

Revision ID: 20260726_0004
Revises: 20260726_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260726_0004"
down_revision: str | None = "20260726_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _material_status_enum() -> sa.Enum:
    return sa.Enum(
        "pending",
        "processing",
        "extracted",
        "indexed",
        "failed",
        name="material_index_status",
        native_enum=False,
        create_constraint=True,
    )


def upgrade() -> None:
    with op.batch_alter_table("learning_materials") as batch_op:
        batch_op.add_column(sa.Column("storage_key", sa.String(512), nullable=True))
        batch_op.add_column(sa.Column("file_size_bytes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("failure_stage", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("error_code", sa.String(100), nullable=True))
        batch_op.add_column(
            sa.Column("processing_revision", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.create_check_constraint(
            "learning_material_file_size", "file_size_bytes IS NULL OR file_size_bytes >= 0"
        )
        batch_op.create_check_constraint(
            "learning_material_processing_revision", "processing_revision >= 0"
        )

    with op.batch_alter_table("learning_materials") as batch_op:
        batch_op.drop_constraint("material_index_status", type_="check")
        batch_op.alter_column(
            "indexing_status",
            existing_type=sa.String(9),
            type_=_material_status_enum(),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("learning_materials") as batch_op:
        batch_op.drop_constraint("material_index_status", type_="check")
        batch_op.alter_column(
            "indexing_status",
            existing_type=_material_status_enum(),
            type_=sa.Enum(
                "pending",
                "extracted",
                "indexed",
                "failed",
                name="material_index_status",
                native_enum=False,
                create_constraint=True,
            ),
            existing_nullable=False,
        )
    with op.batch_alter_table("learning_materials") as batch_op:
        batch_op.drop_constraint("learning_material_processing_revision", type_="check")
        batch_op.drop_constraint("learning_material_file_size", type_="check")
        batch_op.drop_column("processing_revision")
        batch_op.drop_column("error_code")
        batch_op.drop_column("failure_stage")
        batch_op.drop_column("file_size_bytes")
        batch_op.drop_column("storage_key")
