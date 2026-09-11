"""Study workflow history; no approvals, participant backfill or activation."""

import sqlalchemy as sa
from alembic import op

revision = "20260911_0048"
down_revision = "20260910_0046"
branch_labels = None
depends_on = None

STATEMENTS = (
    "CREATE TABLE IF NOT EXISTS research_study_events (\n\tid VARCHAR(36) NOT NULL, \n\tscope_id VARCHAR(36) NOT NULL, \n\tstudy_id VARCHAR(128) NOT NULL, \n\tcourse_id VARCHAR(36) NOT NULL, \n\tkind VARCHAR(24) NOT NULL, \n\tslot VARCHAR(256) NOT NULL, \n\trevision INTEGER NOT NULL, \n\tsubject_user_id INTEGER, \n\tconsent_id VARCHAR(36), \n\tdata JSON NOT NULL, \n\tcontent_digest VARCHAR(71) NOT NULL, \n\tactor_user_id INTEGER NOT NULL, \n\trequest_key VARCHAR(128) NOT NULL, \n\trequest_digest VARCHAR(71) NOT NULL, \n\trecorded_at DATETIME NOT NULL, \n\tCONSTRAINT pk_research_study_events PRIMARY KEY (id), \n\tCONSTRAINT uq_research_study_events_actor_user_id UNIQUE (actor_user_id, request_key), \n\tCONSTRAINT uq_research_study_events_scope_id UNIQUE (scope_id, course_id, slot, revision), \n\tCONSTRAINT fk_research_study_events_scope_id_research_governance_events FOREIGN KEY(scope_id) REFERENCES research_governance_events (id), \n\tCONSTRAINT fk_research_study_events_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id), \n\tCONSTRAINT fk_research_study_events_subject_user_id_users FOREIGN KEY(subject_user_id) REFERENCES users (id), \n\tCONSTRAINT fk_research_study_events_consent_id_research_governance_events FOREIGN KEY(consent_id) REFERENCES research_governance_events (id), \n\tCONSTRAINT fk_research_study_events_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (id)\n)",
    "CREATE TRIGGER IF NOT EXISTS research_study_events_no_update BEFORE UPDATE ON research_study_events BEGIN SELECT RAISE(ABORT, 'research_study_events history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_study_events_no_delete BEFORE DELETE ON research_study_events BEGIN SELECT RAISE(ABORT, 'research_study_events history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_study_events_no_replace BEFORE INSERT ON research_study_events WHEN EXISTS (SELECT 1 FROM research_study_events WHERE id = NEW.id OR (actor_user_id = NEW.actor_user_id AND request_key = NEW.request_key) OR (scope_id = NEW.scope_id AND course_id = NEW.course_id AND slot = NEW.slot AND revision = NEW.revision)) BEGIN SELECT RAISE(ABORT, 'research_study_events history is immutable'); END",
)


def upgrade():
    for statement in STATEMENTS:
        op.execute(sa.text(statement))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM research_study_events")).scalar_one():
        raise RuntimeError("cannot downgrade populated study history")
    op.drop_table("research_study_events")
