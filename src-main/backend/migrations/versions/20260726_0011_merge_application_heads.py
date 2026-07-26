"""Merge RAG, feedback/research, and authentication migration heads.

Revision ID: 20260726_0011
Revises: 20260726_0005, 20260726_0010, 20260724_0001
"""

from collections.abc import Sequence

revision: str = "20260726_0011"
down_revision: tuple[str, str, str] = (
    "20260726_0005",
    "20260726_0010",
    "20260724_0001",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
