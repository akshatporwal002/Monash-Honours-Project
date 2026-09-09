"""Preserve escalation records and their scope guards.

Revision ID: 20260909_0037
Revises: 20260909_0036
"""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0037"
down_revision = "20260909_0036"
branch_labels = None
depends_on = None

STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS escalation_queue_revisions (
    id VARCHAR(36) NOT NULL, 
    course_id VARCHAR(36) NOT NULL, 
    kind VARCHAR(16) NOT NULL, 
    revision INTEGER NOT NULL, 
    primary_user_id INTEGER NOT NULL, 
    backup_user_id INTEGER NOT NULL, 
    acknowledgement_target VARCHAR(500) NOT NULL, 
    resolution_target VARCHAR(500) NOT NULL, 
    reason TEXT NOT NULL, 
    approved_by_user_id INTEGER NOT NULL, 
    created_at DATETIME NOT NULL, 
    CONSTRAINT pk_escalation_queue_revisions PRIMARY KEY (id), 
    CONSTRAINT uq_escalation_queue_revision UNIQUE (course_id, kind, revision), 
    CONSTRAINT ck_escalation_queue_revisions_escalation_queue_kind CHECK (kind IN ('ASSESSOR', 'TECHNICAL')), 
    CONSTRAINT ck_escalation_queue_revisions_escalation_queue_owners CHECK (revision > 0 AND primary_user_id != backup_user_id), 
    CONSTRAINT fk_escalation_queue_revisions_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_escalation_queue_revisions_primary_user_id_users FOREIGN KEY(primary_user_id) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_escalation_queue_revisions_backup_user_id_users FOREIGN KEY(backup_user_id) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_escalation_queue_revisions_approved_by_user_id_users FOREIGN KEY(approved_by_user_id) REFERENCES users (id) ON DELETE RESTRICT
)""",
    """CREATE TRIGGER IF NOT EXISTS escalation_queue_revisions_no_delete BEFORE DELETE ON escalation_queue_revisions BEGIN SELECT RAISE(ABORT, 'escalation_queue_revisions history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS escalation_queue_revisions_no_replace BEFORE INSERT ON escalation_queue_revisions WHEN EXISTS (SELECT 1 FROM escalation_queue_revisions WHERE (id = NEW.id) OR (course_id = NEW.course_id AND kind = NEW.kind AND revision = NEW.revision)) BEGIN SELECT RAISE(ABORT, 'escalation_queue_revisions history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS escalation_queue_revisions_no_update BEFORE UPDATE ON escalation_queue_revisions BEGIN SELECT RAISE(ABORT, 'escalation_queue_revisions history is immutable'); END""",
    """CREATE TABLE IF NOT EXISTS escalation_cases (
    id VARCHAR(36) NOT NULL, 
    course_id VARCHAR(36) NOT NULL, 
    student_id INTEGER NOT NULL, 
    task_id VARCHAR(36) NOT NULL, 
    source_kind VARCHAR(16) NOT NULL, 
    source_id VARCHAR(36) NOT NULL, 
    queue_kind VARCHAR(16) NOT NULL, 
    "trigger" VARCHAR(40) NOT NULL, 
    severity VARCHAR(16) NOT NULL, 
    reason TEXT NOT NULL, 
    request_key VARCHAR(255) NOT NULL, 
    created_at DATETIME NOT NULL, 
    CONSTRAINT pk_escalation_cases PRIMARY KEY (id), 
    CONSTRAINT uq_escalation_case_request UNIQUE (request_key), 
    CONSTRAINT ck_escalation_cases_escalation_case_queue CHECK (queue_kind IN ('ASSESSOR', 'TECHNICAL')), 
    CONSTRAINT ck_escalation_cases_escalation_case_source CHECK (source_kind IN ('FEEDBACK', 'TUTOR', 'ASSESSMENT')), 
    CONSTRAINT ck_escalation_cases_escalation_case_severity CHECK (severity IN ('NORMAL', 'HIGH', 'CRITICAL')), 
    CONSTRAINT fk_escalation_cases_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_escalation_cases_student_id_users FOREIGN KEY(student_id) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_escalation_cases_task_id_learning_tasks FOREIGN KEY(task_id) REFERENCES learning_tasks (id) ON DELETE RESTRICT
)""",
    """CREATE TRIGGER IF NOT EXISTS escalation_cases_no_delete BEFORE DELETE ON escalation_cases BEGIN SELECT RAISE(ABORT, 'escalation_cases history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS escalation_cases_no_replace BEFORE INSERT ON escalation_cases WHEN EXISTS (SELECT 1 FROM escalation_cases WHERE (id = NEW.id) OR (request_key = NEW.request_key)) BEGIN SELECT RAISE(ABORT, 'escalation_cases history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS escalation_cases_no_update BEFORE UPDATE ON escalation_cases BEGIN SELECT RAISE(ABORT, 'escalation_cases history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS escalation_cases_source_scope BEFORE INSERT ON escalation_cases
WHEN NOT EXISTS (SELECT 1 FROM learning_tasks t WHERE t.id=NEW.task_id AND t.course_id=NEW.course_id)
OR NOT (
 (NEW.source_kind='TUTOR' AND EXISTS (SELECT 1 FROM tutor_turns t WHERE t.id=NEW.source_id AND t.task_id=NEW.task_id AND t.student_id=NEW.student_id)) OR
 (NEW.source_kind='ASSESSMENT' AND EXISTS (SELECT 1 FROM assessment_attempts a WHERE a.id=NEW.source_id AND a.task_id=NEW.task_id AND a.student_id=NEW.student_id)) OR
 (NEW.source_kind='FEEDBACK' AND EXISTS (SELECT 1 FROM feedback_records f JOIN submission_attempts s ON s.id=f.submission_id WHERE f.id=NEW.source_id AND s.task_id=NEW.task_id AND s.student_id=NEW.student_id))
) BEGIN SELECT RAISE(ABORT, 'Escalation source scope mismatch'); END""",
    """CREATE TABLE IF NOT EXISTS escalation_events (
    id VARCHAR(36) NOT NULL, 
    case_id VARCHAR(36) NOT NULL, 
    queue_revision_id VARCHAR(36) NOT NULL, 
    revision INTEGER NOT NULL, 
    request_key VARCHAR(128) NOT NULL, 
    actor_user_id INTEGER NOT NULL, 
    owner_user_id INTEGER NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    severity VARCHAR(16) NOT NULL, 
    acknowledgement_due_at DATETIME NOT NULL, 
    resolution_due_at DATETIME NOT NULL, 
    reason TEXT NOT NULL, 
    learner_notice TEXT NOT NULL, 
    created_at DATETIME NOT NULL, 
    CONSTRAINT pk_escalation_events PRIMARY KEY (id), 
    CONSTRAINT uq_escalation_event_revision UNIQUE (case_id, revision), 
    CONSTRAINT uq_escalation_event_request UNIQUE (case_id, request_key), 
    CONSTRAINT ck_escalation_events_escalation_event_revision CHECK (revision > 0), 
    CONSTRAINT ck_escalation_events_escalation_event_status CHECK (status IN ('OPEN', 'ACKNOWLEDGED', 'ACTIONED', 'RESOLVED', 'CLOSED')), 
    CONSTRAINT ck_escalation_events_escalation_event_severity CHECK (severity IN ('NORMAL', 'HIGH', 'CRITICAL')), 
    CONSTRAINT ck_escalation_events_escalation_event_reasons CHECK (length(trim(reason)) > 0 AND length(trim(learner_notice)) > 0), 
    CONSTRAINT ck_escalation_events_escalation_event_deadlines CHECK (resolution_due_at >= acknowledgement_due_at), 
    CONSTRAINT fk_escalation_events_case_id_escalation_cases FOREIGN KEY(case_id) REFERENCES escalation_cases (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_escalation_events_queue_revision_id_escalation_queue_revisions FOREIGN KEY(queue_revision_id) REFERENCES escalation_queue_revisions (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_escalation_events_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE RESTRICT, 
    CONSTRAINT fk_escalation_events_owner_user_id_users FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE RESTRICT
)""",
    """CREATE TRIGGER IF NOT EXISTS escalation_events_no_delete BEFORE DELETE ON escalation_events BEGIN SELECT RAISE(ABORT, 'escalation_events history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS escalation_events_no_replace BEFORE INSERT ON escalation_events WHEN EXISTS (SELECT 1 FROM escalation_events WHERE (id = NEW.id) OR (case_id = NEW.case_id AND revision = NEW.revision) OR (case_id = NEW.case_id AND request_key = NEW.request_key)) BEGIN SELECT RAISE(ABORT, 'escalation_events history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS escalation_events_no_update BEFORE UPDATE ON escalation_events BEGIN SELECT RAISE(ABORT, 'escalation_events history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS escalation_events_queue_scope BEFORE INSERT ON escalation_events
WHEN NOT EXISTS (SELECT 1 FROM escalation_cases c JOIN escalation_queue_revisions q ON q.course_id=c.course_id AND q.kind=c.queue_kind
WHERE c.id=NEW.case_id AND q.id=NEW.queue_revision_id AND NEW.owner_user_id IN (q.primary_user_id,q.backup_user_id))
BEGIN SELECT RAISE(ABORT, 'Escalation queue scope mismatch'); END""",
)


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(sa.text(statement))


def downgrade() -> None:
    tables = ("escalation_events", "escalation_cases", "escalation_queue_revisions")
    for table in tables:
        if op.get_bind().execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one():
            raise RuntimeError(f"cannot downgrade populated {table} history")
    for table in tables:
        op.drop_table(table)
