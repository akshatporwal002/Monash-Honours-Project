"""Preserve gamification records and their scope guards.

Revision ID: 20260909_0038
Revises: 20260909_0037
"""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0038"
down_revision = "20260909_0037"
branch_labels = None
depends_on = None

STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS gamification_preferences (
    id VARCHAR(36) NOT NULL,
    student_id INTEGER NOT NULL,
    revision INTEGER NOT NULL,
    request_key VARCHAR(128) NOT NULL,
    enabled BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT pk_gamification_preferences PRIMARY KEY (id),
    CONSTRAINT uq_gamification_preference_revision UNIQUE (student_id, revision),
    CONSTRAINT uq_gamification_preference_request UNIQUE (student_id, request_key),
    CONSTRAINT ck_gamification_preferences_gamification_preference_revision CHECK (revision > 0),
    CONSTRAINT fk_gamification_preferences_student_id_users FOREIGN KEY(student_id) REFERENCES users (id) ON DELETE RESTRICT
)""",
    """CREATE TRIGGER IF NOT EXISTS gamification_preferences_no_delete BEFORE DELETE ON gamification_preferences BEGIN SELECT RAISE(ABORT, 'gamification_preferences history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS gamification_preferences_no_replace BEFORE INSERT ON gamification_preferences WHEN EXISTS (SELECT 1 FROM gamification_preferences WHERE (id = NEW.id) OR (student_id = NEW.student_id AND revision = NEW.revision) OR (student_id = NEW.student_id AND request_key = NEW.request_key)) BEGIN SELECT RAISE(ABORT, 'gamification_preferences history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS gamification_preferences_no_update BEFORE UPDATE ON gamification_preferences BEGIN SELECT RAISE(ABORT, 'gamification_preferences history is immutable'); END""",
    """CREATE TABLE IF NOT EXISTS participation_recognitions (
    id VARCHAR(36) NOT NULL,
    student_id INTEGER NOT NULL,
    task_id VARCHAR(36) NOT NULL,
    evidence_id VARCHAR(36) NOT NULL,
    kind VARCHAR(24) NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT pk_participation_recognitions PRIMARY KEY (id),
    CONSTRAINT uq_participation_recognition_kind UNIQUE (student_id, task_id, kind),
    CONSTRAINT ck_participation_recognitions_participation_recognition_kind CHECK (kind IN ('REFLECTION', 'REVISION', 'FEEDBACK_INTERACTION')),
    CONSTRAINT fk_participation_recognitions_student_id_users FOREIGN KEY(student_id) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_participation_recognitions_task_id_learning_tasks FOREIGN KEY(task_id) REFERENCES learning_tasks (id) ON DELETE RESTRICT,
    CONSTRAINT fk_participation_recognitions_evidence_id_learning_evidence FOREIGN KEY(evidence_id) REFERENCES learning_evidence (id) ON DELETE RESTRICT
)""",
    """CREATE TRIGGER IF NOT EXISTS participation_recognitions_no_delete BEFORE DELETE ON participation_recognitions BEGIN SELECT RAISE(ABORT, 'participation_recognitions history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS participation_recognitions_no_replace BEFORE INSERT ON participation_recognitions WHEN EXISTS (SELECT 1 FROM participation_recognitions WHERE (id = NEW.id) OR (student_id = NEW.student_id AND task_id = NEW.task_id AND kind = NEW.kind)) BEGIN SELECT RAISE(ABORT, 'participation_recognitions history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS participation_recognitions_no_update BEFORE UPDATE ON participation_recognitions BEGIN SELECT RAISE(ABORT, 'participation_recognitions history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS participation_recognitions_scope BEFORE INSERT ON participation_recognitions
WHEN NOT EXISTS (SELECT 1 FROM learning_evidence e WHERE e.id=NEW.evidence_id
AND e.learner_id=NEW.student_id AND e.task_id=NEW.task_id AND e.evidence_type=NEW.kind)
BEGIN SELECT RAISE(ABORT, 'Participation evidence scope mismatch'); END""",
)


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(sa.text(statement))


def downgrade() -> None:
    tables = ("participation_recognitions", "gamification_preferences")
    for table in tables:
        if op.get_bind().execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one():
            raise RuntimeError(f"cannot downgrade populated {table} history")
    for table in tables:
        op.drop_table(table)
