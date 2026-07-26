"""Enforce canonical task and material scope relationships in SQLite.

Revision ID: 20260726_0014
Revises: 20260726_0013
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260726_0014"
down_revision: str | None = "20260726_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TASK_SCOPE_CHECK = """
SELECT CASE WHEN
    NEW.course_id IS NULL
    OR NEW.module_id IS NULL
    OR NEW.learning_outcome_id IS NULL
    OR NOT EXISTS (
        SELECT 1
        FROM courses AS course
        JOIN course_modules AS module ON module.course_id = course.id
        JOIN learning_outcomes AS outcome ON outcome.module_id = module.id
        WHERE course.id = NEW.course_id
          AND module.id = NEW.module_id
          AND outcome.id = NEW.learning_outcome_id
    )
THEN RAISE(ABORT, 'invalid learning task scope') END;
"""

_MATERIAL_SCOPE_CHECK = """
SELECT CASE WHEN
    NOT EXISTS (
        SELECT 1 FROM courses WHERE id = NEW.course_id
    )
    OR (
        NEW.module_id IS NOT NULL
        AND NOT EXISTS (
            SELECT 1
            FROM course_modules
            WHERE id = NEW.module_id
              AND course_id = NEW.course_id
        )
    )
THEN RAISE(ABORT, 'invalid learning material scope') END;
"""


def _create_trigger(name: str, event: str, table: str, check: str) -> None:
    op.execute(
        f"""
        CREATE TRIGGER {name}
        BEFORE {event} ON {table}
        BEGIN
            {check}
        END
        """
    )


def upgrade() -> None:
    _create_trigger(
        "trg_learning_tasks_scope_insert",
        "INSERT",
        "learning_tasks",
        _TASK_SCOPE_CHECK,
    )
    _create_trigger(
        "trg_learning_tasks_scope_update",
        "UPDATE OF course_id, module_id, learning_outcome_id",
        "learning_tasks",
        _TASK_SCOPE_CHECK,
    )
    _create_trigger(
        "trg_learning_materials_scope_insert",
        "INSERT",
        "learning_materials",
        _MATERIAL_SCOPE_CHECK,
    )
    _create_trigger(
        "trg_learning_materials_scope_update",
        "UPDATE OF course_id, module_id",
        "learning_materials",
        _MATERIAL_SCOPE_CHECK,
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_learning_materials_scope_update")
    op.execute("DROP TRIGGER IF EXISTS trg_learning_materials_scope_insert")
    op.execute("DROP TRIGGER IF EXISTS trg_learning_tasks_scope_update")
    op.execute("DROP TRIGGER IF EXISTS trg_learning_tasks_scope_insert")
