"""Synthetic instrument foundation; no study approval or participant backfill."""

import sqlalchemy as sa
from alembic import op

revision = "20260910_0046"
down_revision = "20260910_0045"
branch_labels = None
depends_on = None

STATEMENTS = (
    "CREATE TABLE IF NOT EXISTS research_instrument_forms (\n\tid VARCHAR(36) NOT NULL, \n\tstudy_id VARCHAR(128) NOT NULL, \n\tcourse_id VARCHAR(36) NOT NULL, \n\tscope_id VARCHAR(36) NOT NULL, \n\tinstrument_key VARCHAR(128) NOT NULL, \n\tversion INTEGER NOT NULL, \n\tdefinition JSON NOT NULL, \n\tcontent_digest VARCHAR(71) NOT NULL, \n\tactor_user_id INTEGER NOT NULL, \n\trequest_key VARCHAR(128) NOT NULL, \n\trequest_digest VARCHAR(71) NOT NULL, \n\trecorded_at DATETIME NOT NULL, \n\tCONSTRAINT pk_research_instrument_forms PRIMARY KEY (id), \n\tCONSTRAINT uq_research_instrument_forms_study_id UNIQUE (study_id, course_id, instrument_key, version), \n\tCONSTRAINT uq_research_instrument_forms_actor_user_id UNIQUE (actor_user_id, request_key), \n\tCONSTRAINT ck_research_instrument_forms_instrument_form_version CHECK (version > 0), \n\tCONSTRAINT fk_research_instrument_forms_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_research_instrument_forms_scope_id_research_governance_events FOREIGN KEY(scope_id) REFERENCES research_governance_events (id), \n\tCONSTRAINT fk_research_instrument_forms_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE RESTRICT\n)",
    "CREATE TRIGGER IF NOT EXISTS research_instrument_forms_no_update BEFORE UPDATE ON research_instrument_forms BEGIN SELECT RAISE(ABORT, 'research_instrument_forms history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_instrument_forms_no_delete BEFORE DELETE ON research_instrument_forms BEGIN SELECT RAISE(ABORT, 'research_instrument_forms history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_instrument_forms_no_replace BEFORE INSERT ON research_instrument_forms WHEN EXISTS (SELECT 1 FROM research_instrument_forms WHERE (id = NEW.id) OR (study_id = NEW.study_id AND course_id = NEW.course_id AND instrument_key = NEW.instrument_key AND version = NEW.version) OR (actor_user_id = NEW.actor_user_id AND request_key = NEW.request_key)) BEGIN SELECT RAISE(ABORT, 'research_instrument_forms history is immutable'); END",
    "CREATE TABLE IF NOT EXISTS research_instrument_freezes (\n\tid VARCHAR(36) NOT NULL, \n\tform_id VARCHAR(36) NOT NULL, \n\tactor_user_id INTEGER NOT NULL, \n\trequest_key VARCHAR(128) NOT NULL, \n\trequest_digest VARCHAR(71) NOT NULL, \n\tsynthetic_review_reference VARCHAR(128) NOT NULL, \n\trecorded_at DATETIME NOT NULL, \n\tCONSTRAINT pk_research_instrument_freezes PRIMARY KEY (id), \n\tCONSTRAINT uq_research_instrument_freezes_form_id UNIQUE (form_id), \n\tCONSTRAINT uq_research_instrument_freezes_actor_user_id UNIQUE (actor_user_id, request_key), \n\tCONSTRAINT fk_research_instrument_freezes_form_id_research_instrument_forms FOREIGN KEY(form_id) REFERENCES research_instrument_forms (id), \n\tCONSTRAINT fk_research_instrument_freezes_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE RESTRICT\n)",
    "CREATE TRIGGER IF NOT EXISTS research_instrument_freezes_no_update BEFORE UPDATE ON research_instrument_freezes BEGIN SELECT RAISE(ABORT, 'research_instrument_freezes history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_instrument_freezes_no_delete BEFORE DELETE ON research_instrument_freezes BEGIN SELECT RAISE(ABORT, 'research_instrument_freezes history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_instrument_freezes_no_replace BEFORE INSERT ON research_instrument_freezes WHEN EXISTS (SELECT 1 FROM research_instrument_freezes WHERE (id = NEW.id) OR (form_id = NEW.form_id) OR (actor_user_id = NEW.actor_user_id AND request_key = NEW.request_key)) BEGIN SELECT RAISE(ABORT, 'research_instrument_freezes history is immutable'); END",
    "CREATE TABLE IF NOT EXISTS research_instrument_bindings (\n\tid VARCHAR(36) NOT NULL, \n\tscope_id VARCHAR(36) NOT NULL, \n\tcourse_id VARCHAR(36) NOT NULL, \n\tsubject_user_id INTEGER NOT NULL, \n\tparticipant_id VARCHAR(67) NOT NULL, \n\tCONSTRAINT pk_research_instrument_bindings PRIMARY KEY (id), \n\tCONSTRAINT uq_research_instrument_bindings_scope_id UNIQUE (scope_id, course_id, subject_user_id), \n\tCONSTRAINT fk_research_instrument_bindings_scope_id_research_governance_events FOREIGN KEY(scope_id) REFERENCES research_governance_events (id), \n\tCONSTRAINT fk_research_instrument_bindings_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_research_instrument_bindings_subject_user_id_users FOREIGN KEY(subject_user_id) REFERENCES users (id) ON DELETE RESTRICT\n)",
    "CREATE TRIGGER IF NOT EXISTS research_instrument_bindings_no_update BEFORE UPDATE ON research_instrument_bindings BEGIN SELECT RAISE(ABORT, 'research_instrument_bindings history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_instrument_bindings_no_delete BEFORE DELETE ON research_instrument_bindings BEGIN SELECT RAISE(ABORT, 'research_instrument_bindings history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_instrument_bindings_no_replace BEFORE INSERT ON research_instrument_bindings WHEN EXISTS (SELECT 1 FROM research_instrument_bindings WHERE (id = NEW.id) OR (scope_id = NEW.scope_id AND course_id = NEW.course_id AND subject_user_id = NEW.subject_user_id)) BEGIN SELECT RAISE(ABORT, 'research_instrument_bindings history is immutable'); END",
    "CREATE TABLE IF NOT EXISTS research_instrument_records (\n\tid VARCHAR(36) NOT NULL, \n\tform_id VARCHAR(36) NOT NULL, \n\tbinding_id VARCHAR(36) NOT NULL, \n\tconsent_id VARCHAR(36) NOT NULL, \n\tseries_id VARCHAR(36) NOT NULL, \n\trevision INTEGER NOT NULL, \n\tsupersedes_id VARCHAR(36), \n\tcorrection_reason_code VARCHAR(48), \n\tsequence_id VARCHAR(67) NOT NULL, \n\tstage VARCHAR(32) NOT NULL, \n\tkind VARCHAR(24) NOT NULL, \n\tlinks JSON NOT NULL, \n\tdata JSON NOT NULL, \n\tcontent_digest VARCHAR(71) NOT NULL, \n\tactor_user_id INTEGER NOT NULL, \n\trequest_key VARCHAR(128) NOT NULL, \n\trequest_digest VARCHAR(71) NOT NULL, \n\trecorded_at DATETIME NOT NULL, \n\tCONSTRAINT pk_research_instrument_records PRIMARY KEY (id), \n\tCONSTRAINT uq_research_instrument_records_actor_user_id UNIQUE (actor_user_id, request_key), \n\tCONSTRAINT uq_research_instrument_records_series_id UNIQUE (series_id, revision), \n\tCONSTRAINT uq_research_instrument_records_supersedes_id UNIQUE (supersedes_id), \n\tCONSTRAINT ck_research_instrument_records_instrument_record_revision CHECK (revision > 0), \n\tCONSTRAINT ck_research_instrument_records_instrument_record_kind CHECK (kind IN ('response','missingness','attrition','deviation')), \n\tCONSTRAINT fk_research_instrument_records_form_id_research_instrument_forms FOREIGN KEY(form_id) REFERENCES research_instrument_forms (id), \n\tCONSTRAINT fk_research_instrument_records_binding_id_research_instrument_bindings FOREIGN KEY(binding_id) REFERENCES research_instrument_bindings (id), \n\tCONSTRAINT fk_research_instrument_records_consent_id_research_governance_events FOREIGN KEY(consent_id) REFERENCES research_governance_events (id), \n\tCONSTRAINT fk_research_instrument_records_supersedes_id_research_instrument_records FOREIGN KEY(supersedes_id) REFERENCES research_instrument_records (id), \n\tCONSTRAINT fk_research_instrument_records_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE RESTRICT\n)",
    "CREATE TRIGGER IF NOT EXISTS research_instrument_records_no_update BEFORE UPDATE ON research_instrument_records BEGIN SELECT RAISE(ABORT, 'research_instrument_records history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_instrument_records_no_delete BEFORE DELETE ON research_instrument_records BEGIN SELECT RAISE(ABORT, 'research_instrument_records history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS research_instrument_records_no_replace BEFORE INSERT ON research_instrument_records WHEN EXISTS (SELECT 1 FROM research_instrument_records WHERE (id = NEW.id) OR (series_id = NEW.series_id AND revision = NEW.revision) OR (actor_user_id = NEW.actor_user_id AND request_key = NEW.request_key) OR (supersedes_id = NEW.supersedes_id)) BEGIN SELECT RAISE(ABORT, 'research_instrument_records history is immutable'); END",
    "CREATE TABLE IF NOT EXISTS restricted_instrument_evidence (\n\tid VARCHAR(36) NOT NULL, \n\trecord_id VARCHAR(36) NOT NULL, \n\tresponse_text JSON NOT NULL, \n\tcontent_digest VARCHAR(71) NOT NULL, \n\tCONSTRAINT pk_restricted_instrument_evidence PRIMARY KEY (id), \n\tCONSTRAINT uq_restricted_instrument_evidence_record_id UNIQUE (record_id), \n\tCONSTRAINT fk_restricted_instrument_evidence_record_id_research_instrument_records FOREIGN KEY(record_id) REFERENCES research_instrument_records (id)\n)",
    "CREATE TRIGGER IF NOT EXISTS restricted_instrument_evidence_no_update BEFORE UPDATE ON restricted_instrument_evidence BEGIN SELECT RAISE(ABORT, 'restricted_instrument_evidence history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS restricted_instrument_evidence_no_delete BEFORE DELETE ON restricted_instrument_evidence BEGIN SELECT RAISE(ABORT, 'restricted_instrument_evidence history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS restricted_instrument_evidence_no_replace BEFORE INSERT ON restricted_instrument_evidence WHEN EXISTS (SELECT 1 FROM restricted_instrument_evidence WHERE (id = NEW.id) OR (record_id = NEW.record_id)) BEGIN SELECT RAISE(ABORT, 'restricted_instrument_evidence history is immutable'); END",
)


def upgrade():
    for statement in STATEMENTS:
        op.execute(sa.text(statement))


def downgrade():
    tables = (
        "restricted_instrument_evidence",
        "research_instrument_records",
        "research_instrument_bindings",
        "research_instrument_freezes",
        "research_instrument_forms",
    )
    for table in tables:
        if op.get_bind().execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one():
            raise RuntimeError(f"cannot downgrade populated {table} history")
    for table in tables:
        op.drop_table(table)
