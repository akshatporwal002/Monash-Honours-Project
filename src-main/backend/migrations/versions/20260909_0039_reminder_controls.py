"""Preserve reminder preferences and deadline arrangements; enforce rolling delivery limits."""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0039"
down_revision = "20260909_0038"
branch_labels = None
depends_on = None

STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS reminder_preferences (
	id VARCHAR(36) NOT NULL,
	student_id INTEGER NOT NULL,
	revision INTEGER NOT NULL,
	request_key VARCHAR(128) NOT NULL,
	enabled BOOLEAN NOT NULL,
	paused_until DATETIME,
	created_at DATETIME NOT NULL,
	CONSTRAINT pk_reminder_preferences PRIMARY KEY (id),
	CONSTRAINT uq_reminder_preference_revision UNIQUE (student_id, revision),
	CONSTRAINT uq_reminder_preference_request UNIQUE (student_id, request_key),
	CONSTRAINT ck_reminder_preferences_reminder_preference_revision CHECK (revision > 0),
	CONSTRAINT fk_reminder_preferences_student_id_users FOREIGN KEY(student_id) REFERENCES users (id) ON DELETE RESTRICT
)""",
    """CREATE TRIGGER IF NOT EXISTS reminder_preferences_no_update BEFORE UPDATE ON reminder_preferences BEGIN SELECT RAISE(ABORT, 'reminder_preferences history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS reminder_preferences_no_delete BEFORE DELETE ON reminder_preferences BEGIN SELECT RAISE(ABORT, 'reminder_preferences history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS reminder_preferences_no_replace BEFORE INSERT ON reminder_preferences WHEN EXISTS (SELECT 1 FROM reminder_preferences WHERE (id = NEW.id) OR (student_id = NEW.student_id AND revision = NEW.revision) OR (student_id = NEW.student_id AND request_key = NEW.request_key)) BEGIN SELECT RAISE(ABORT, 'reminder_preferences history is immutable'); END""",
    """CREATE TABLE IF NOT EXISTS deadline_arrangements (
	id VARCHAR(36) NOT NULL,
	student_id INTEGER NOT NULL,
	task_id VARCHAR(36) NOT NULL,
	actor_id INTEGER NOT NULL,
	revision INTEGER NOT NULL,
	request_key VARCHAR(128) NOT NULL,
	kind VARCHAR(16) NOT NULL,
	active BOOLEAN NOT NULL,
	due_at DATETIME,
	reminders_paused BOOLEAN NOT NULL,
	time_zone VARCHAR(64) NOT NULL,
	reason TEXT NOT NULL,
	learner_notice TEXT NOT NULL,
	created_at DATETIME NOT NULL,
	CONSTRAINT pk_deadline_arrangements PRIMARY KEY (id),
	CONSTRAINT uq_deadline_arrangement_revision UNIQUE (student_id, task_id, revision),
	CONSTRAINT uq_deadline_arrangement_request UNIQUE (student_id, task_id, request_key),
	CONSTRAINT ck_deadline_arrangements_deadline_arrangement_revision CHECK (revision > 0),
	CONSTRAINT ck_deadline_arrangements_deadline_arrangement_kind CHECK (kind IN ('EXTENSION', 'ACCESS_PLAN')),
	CONSTRAINT ck_deadline_arrangements_deadline_arrangement_reason CHECK (length(trim(reason)) > 0 AND length(trim(learner_notice)) > 0),
	CONSTRAINT ck_deadline_arrangements_deadline_arrangement_shape CHECK ((active = 1 AND (due_at IS NOT NULL OR reminders_paused = 1)) OR (active = 0 AND due_at IS NULL AND reminders_paused = 0)),
	CONSTRAINT ck_deadline_arrangements_deadline_arrangement_pause CHECK (kind = 'ACCESS_PLAN' OR reminders_paused = 0),
	CONSTRAINT fk_deadline_arrangements_student_id_users FOREIGN KEY(student_id) REFERENCES users (id) ON DELETE RESTRICT,
	CONSTRAINT fk_deadline_arrangements_task_id_learning_tasks FOREIGN KEY(task_id) REFERENCES learning_tasks (id) ON DELETE RESTRICT,
	CONSTRAINT fk_deadline_arrangements_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE RESTRICT
)""",
    """CREATE TRIGGER IF NOT EXISTS deadline_arrangements_no_update BEFORE UPDATE ON deadline_arrangements BEGIN SELECT RAISE(ABORT, 'deadline_arrangements history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS deadline_arrangements_no_delete BEFORE DELETE ON deadline_arrangements BEGIN SELECT RAISE(ABORT, 'deadline_arrangements history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS deadline_arrangements_no_replace BEFORE INSERT ON deadline_arrangements WHEN EXISTS (SELECT 1 FROM deadline_arrangements WHERE (id = NEW.id) OR (student_id = NEW.student_id AND task_id = NEW.task_id AND revision = NEW.revision) OR (student_id = NEW.student_id AND task_id = NEW.task_id AND request_key = NEW.request_key)) BEGIN SELECT RAISE(ABORT, 'deadline_arrangements history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS deadline_arrangements_scope
BEFORE INSERT ON deadline_arrangements WHEN NOT EXISTS (
 SELECT 1 FROM learning_tasks t JOIN courses c ON c.id=t.course_id
 JOIN enrollments e ON e.course_id=c.id AND e.student_id=NEW.student_id
 WHERE t.id=NEW.task_id AND c.educator_id=NEW.actor_id
) BEGIN SELECT RAISE(ABORT, 'Deadline arrangement scope mismatch'); END""",
    """CREATE INDEX IF NOT EXISTS ix_reminders_student_task_time ON reminders (student_id, task_id, created_at)""",
    """CREATE TRIGGER IF NOT EXISTS reminders_rolling_limit BEFORE INSERT ON reminders
WHEN EXISTS (SELECT 1 FROM reminders r WHERE r.student_id=NEW.student_id
AND r.task_id=NEW.task_id AND julianday(r.created_at) > julianday(NEW.created_at) - 1)
BEGIN SELECT RAISE(ABORT, 'A task reminder was already sent within 24 hours'); END""",
    """CREATE TRIGGER IF NOT EXISTS reminders_identity_immutable BEFORE UPDATE ON reminders
WHEN NEW.id != OLD.id OR NEW.student_id != OLD.student_id OR NEW.task_id != OLD.task_id
OR NEW.created_at != OLD.created_at OR NEW.dedupe_window != OLD.dedupe_window
BEGIN SELECT RAISE(ABORT, 'Reminder delivery identity is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS reminders_no_replace BEFORE INSERT ON reminders
WHEN EXISTS (SELECT 1 FROM reminders r WHERE r.id=NEW.id OR
(r.student_id=NEW.student_id AND r.task_id=NEW.task_id AND r.dedupe_window=NEW.dedupe_window))
BEGIN SELECT RAISE(ABORT, 'Reminder delivery identity is immutable'); END""",
)


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("courses")}
    if "time_zone" not in columns:
        op.add_column(
            "courses", sa.Column("time_zone", sa.String(64), nullable=False, server_default="UTC")
        )
    for statement in STATEMENTS:
        op.execute(sa.text(statement))


def downgrade():
    for table in ("deadline_arrangements", "reminder_preferences"):
        if op.get_bind().execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one():
            raise RuntimeError(f"cannot downgrade populated {table} history")
    if (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM courses WHERE time_zone != 'UTC'"))
        .scalar_one()
    ):
        raise RuntimeError("cannot downgrade configured course time zones")
    for trigger in (
        "reminders_rolling_limit",
        "reminders_identity_immutable",
        "reminders_no_replace",
    ):
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger}"))
    op.drop_index("ix_reminders_student_task_time", table_name="reminders")
    op.drop_table("deadline_arrangements")
    op.drop_table("reminder_preferences")
    # Keep the additive UTC column so rollback preserves existing course snapshots.
