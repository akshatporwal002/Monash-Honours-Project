"""Append-only research governance; no approvals or learner data are backfilled."""

import sqlalchemy as sa
from alembic import op

revision = "20260910_0045"
down_revision = "20260910_0044"
branch_labels = None
depends_on = None

STATEMENTS = (
    "CREATE TABLE IF NOT EXISTS research_case_governance (\n\tid VARCHAR(36) NOT NULL, \n\tcase_id VARCHAR(36) NOT NULL, \n\tscope_id VARCHAR(36) NOT NULL, \n\tconsent_id VARCHAR(36) NOT NULL, \n\tcourse_id VARCHAR(36) NOT NULL, \n\tpseudonymous_user_id VARCHAR(67) NOT NULL, \n\trecorded_at DATETIME NOT NULL, \n\tCONSTRAINT pk_research_case_governance PRIMARY KEY (id), \n\tCONSTRAINT uq_research_case_governance_case_id UNIQUE (case_id), \n\tCONSTRAINT fk_research_case_governance_scope_id_research_governance_events FOREIGN KEY(scope_id) REFERENCES research_governance_events (id), \n\tCONSTRAINT fk_research_case_governance_consent_id_research_governance_events FOREIGN KEY(consent_id) REFERENCES research_governance_events (id), \n\tCONSTRAINT fk_research_case_governance_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE RESTRICT\n)",
    "CREATE TABLE IF NOT EXISTS research_export_eligibility (\n\tid VARCHAR(36) NOT NULL, \n\tstudy_id VARCHAR(128) NOT NULL, \n\tscope_id VARCHAR(36), \n\tactor_user_id INTEGER NOT NULL, \n\tmanifest JSON NOT NULL, \n\trecorded_at DATETIME NOT NULL, \n\tCONSTRAINT pk_research_export_eligibility PRIMARY KEY (id), \n\tCONSTRAINT fk_research_export_eligibility_scope_id_research_governance_events FOREIGN KEY(scope_id) REFERENCES research_governance_events (id), \n\tCONSTRAINT fk_research_export_eligibility_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE RESTRICT\n)",
    "CREATE TABLE IF NOT EXISTS research_governance_events (\n\tid VARCHAR(36) NOT NULL, \n\tstudy_id VARCHAR(128) NOT NULL, \n\trevision INTEGER NOT NULL, \n\tactor_user_id INTEGER NOT NULL, \n\trequest_key VARCHAR(128) NOT NULL, \n\tkind VARCHAR(24) NOT NULL, \n\tcommand JSON NOT NULL, \n\trecorded_at DATETIME NOT NULL, \n\tCONSTRAINT pk_research_governance_events PRIMARY KEY (id), \n\tCONSTRAINT uq_research_governance_revision UNIQUE (study_id, revision), \n\tCONSTRAINT uq_research_governance_request UNIQUE (actor_user_id, request_key), \n\tCONSTRAINT ck_research_governance_events_research_governance_revision CHECK (revision > 0), \n\tCONSTRAINT fk_research_governance_events_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE RESTRICT\n)",
    "CREATE INDEX IF NOT EXISTS ix_research_governance_events_study_id ON research_governance_events (study_id)",
    "CREATE TRIGGER IF NOT EXISTS research_case_governance_no_delete BEFORE DELETE ON research_case_governance BEGIN SELECT RAISE(ABORT, 'research_case_governance history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_case_governance_no_replace BEFORE INSERT ON research_case_governance WHEN EXISTS (SELECT 1 FROM research_case_governance WHERE (id = NEW.id) OR (case_id = NEW.case_id)) BEGIN SELECT RAISE(ABORT, 'research_case_governance history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_case_governance_no_update BEFORE UPDATE ON research_case_governance BEGIN SELECT RAISE(ABORT, 'research_case_governance history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_export_eligibility_no_delete BEFORE DELETE ON research_export_eligibility BEGIN SELECT RAISE(ABORT, 'research_export_eligibility history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_export_eligibility_no_replace BEFORE INSERT ON research_export_eligibility WHEN EXISTS (SELECT 1 FROM research_export_eligibility WHERE (id = NEW.id)) BEGIN SELECT RAISE(ABORT, 'research_export_eligibility history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_export_eligibility_no_update BEFORE UPDATE ON research_export_eligibility BEGIN SELECT RAISE(ABORT, 'research_export_eligibility history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_governance_events_no_delete BEFORE DELETE ON research_governance_events BEGIN SELECT RAISE(ABORT, 'research_governance_events history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_governance_events_no_replace BEFORE INSERT ON research_governance_events WHEN EXISTS (SELECT 1 FROM research_governance_events WHERE (id = NEW.id) OR (study_id = NEW.study_id AND revision = NEW.revision) OR (actor_user_id = NEW.actor_user_id AND request_key = NEW.request_key)) BEGIN SELECT RAISE(ABORT, 'research_governance_events history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_governance_events_no_update BEFORE UPDATE ON research_governance_events BEGIN SELECT RAISE(ABORT, 'research_governance_events history is immutable'); END",
)


def upgrade():
    for statement in STATEMENTS:
        op.execute(sa.text(statement))


def downgrade():
    tables = (
        "research_export_eligibility",
        "research_case_governance",
        "research_governance_events",
    )
    for table in tables:
        if op.get_bind().execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one():
            raise RuntimeError(f"cannot downgrade populated {table} history")
    for table in tables:
        op.drop_table(table)
