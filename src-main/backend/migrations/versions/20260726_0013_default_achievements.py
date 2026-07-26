"""Seed canonical production achievement definitions.

Revision ID: 20260726_0013
Revises: 20260726_0012
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql.selectable import TableClause

revision: str = "20260726_0013"
down_revision: str | None = "20260726_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_ACHIEVEMENTS: tuple[dict[str, str], ...] = (
    {
        "id": "00000000-0000-4000-9000-000000000101",
        "code": "first-step",
        "name": "First Step",
        "description": "Complete your first learning activity.",
        "icon": "✦",
    },
    {
        "id": "00000000-0000-4000-9000-000000000102",
        "code": "circuit-maker",
        "name": "Circuit Maker",
        "description": "Complete a circuit activity.",
        "icon": "⌁",
    },
    {
        "id": "00000000-0000-4000-9000-000000000103",
        "code": "perfect-score",
        "name": "Quantum Ace",
        "description": "Earn a perfect task score.",
        "icon": "★",
    },
)


def _achievement_table() -> TableClause:
    return sa.table(
        "achievements",
        sa.column("id", sa.String(length=36)),
        sa.column("code", sa.String(length=50)),
        sa.column("name", sa.String(length=100)),
        sa.column("description", sa.String(length=255)),
        sa.column("icon", sa.String(length=20)),
    )


def upgrade() -> None:
    achievements = _achievement_table()
    connection = op.get_bind()
    for definition in DEFAULT_ACHIEVEMENTS:
        existing_id = connection.scalar(
            sa.select(achievements.c.id).where(
                achievements.c.code == definition["code"],
            )
        )
        if existing_id is None:
            connection.execute(achievements.insert().values(**definition))


def downgrade() -> None:
    achievements = _achievement_table()
    op.get_bind().execute(
        achievements.delete().where(
            achievements.c.id.in_([definition["id"] for definition in DEFAULT_ACHIEVEMENTS])
        )
    )
