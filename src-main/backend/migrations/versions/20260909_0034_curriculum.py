"""Frozen curriculum and diagnostic history tables."""

from importlib import import_module

import sqlalchemy as sa
from alembic import op

revision = "20260909_0034"
down_revision = "20260908_0033"
branch_labels = None
depends_on = None

TABLES = [
    "curriculum_pathway_versions",
    "curriculum_diagnostic_sessions",
    "curriculum_diagnostic_responses",
    "curriculum_diagnostic_confirmations",
]
STATEMENTS = [
    "CREATE TABLE curriculum_pathway_versions (\n\tid VARCHAR(36) NOT NULL, \n\toutcome_id VARCHAR(36) NOT NULL, \n\tcourse_id VARCHAR(36) NOT NULL, \n\tversion INTEGER NOT NULL, \n\trequest_key VARCHAR(100) NOT NULL, \n\tapproved_by INTEGER NOT NULL, \n\tpayload JSON NOT NULL, \n\tbindings JSON NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_curriculum_pathway_versions PRIMARY KEY (id), \n\tCONSTRAINT uq_curriculum_version UNIQUE (outcome_id, version), \n\tCONSTRAINT uq_curriculum_request UNIQUE (outcome_id, request_key), \n\tCONSTRAINT ck_curriculum_pathway_versions_curriculum_version_positive CHECK (version > 0), \n\tCONSTRAINT fk_curriculum_pathway_versions_outcome_id_learning_outcomes FOREIGN KEY(outcome_id) REFERENCES learning_outcomes (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_curriculum_pathway_versions_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_curriculum_pathway_versions_approved_by_users FOREIGN KEY(approved_by) REFERENCES users (id) ON DELETE RESTRICT\n)",
    "CREATE TRIGGER IF NOT EXISTS curriculum_pathway_versions_no_update BEFORE UPDATE ON curriculum_pathway_versions BEGIN SELECT RAISE(ABORT, 'Curriculum history is protected'); END",
    "CREATE TRIGGER IF NOT EXISTS curriculum_pathway_versions_no_delete BEFORE DELETE ON curriculum_pathway_versions BEGIN SELECT RAISE(ABORT, 'Curriculum history is protected'); END",
    "CREATE TRIGGER IF NOT EXISTS curriculum_pathway_versions_no_insert BEFORE INSERT ON curriculum_pathway_versions WHEN EXISTS (SELECT 1 FROM curriculum_pathway_versions WHERE id=NEW.id OR (outcome_id=NEW.outcome_id AND (version=NEW.version OR request_key=NEW.request_key))) BEGIN SELECT RAISE(ABORT, 'Curriculum history is protected'); END",
    "CREATE TABLE curriculum_diagnostic_sessions (\n\tid VARCHAR(36) NOT NULL, \n\tpathway_id VARCHAR(36) NOT NULL, \n\tlearner_id INTEGER NOT NULL, \n\trequest_key VARCHAR(100) NOT NULL, \n\tpayload JSON NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_curriculum_diagnostic_sessions PRIMARY KEY (id), \n\tCONSTRAINT uq_diagnostic_start_request UNIQUE (learner_id, request_key), \n\tCONSTRAINT fk_curriculum_diagnostic_sessions_pathway_id_curriculum_pathway_versions FOREIGN KEY(pathway_id) REFERENCES curriculum_pathway_versions (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_curriculum_diagnostic_sessions_learner_id_users FOREIGN KEY(learner_id) REFERENCES users (id) ON DELETE RESTRICT\n)",
    "CREATE TRIGGER IF NOT EXISTS curriculum_diagnostic_sessions_no_update BEFORE UPDATE ON curriculum_diagnostic_sessions BEGIN SELECT RAISE(ABORT, 'Curriculum history is protected'); END",
    "CREATE TRIGGER IF NOT EXISTS curriculum_diagnostic_sessions_no_delete BEFORE DELETE ON curriculum_diagnostic_sessions BEGIN SELECT RAISE(ABORT, 'Curriculum history is protected'); END",
    "CREATE TRIGGER IF NOT EXISTS curriculum_diagnostic_sessions_no_insert BEFORE INSERT ON curriculum_diagnostic_sessions WHEN EXISTS (SELECT 1 FROM curriculum_diagnostic_sessions WHERE id=NEW.id OR (learner_id=NEW.learner_id AND request_key=NEW.request_key)) BEGIN SELECT RAISE(ABORT, 'Curriculum history is protected'); END",
    "CREATE TABLE curriculum_diagnostic_responses (\n\tid VARCHAR(36) NOT NULL, \n\tsession_id VARCHAR(36) NOT NULL, \n\tevidence_id VARCHAR(36) NOT NULL, \n\tpayload JSON NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_curriculum_diagnostic_responses PRIMARY KEY (id), \n\tCONSTRAINT uq_curriculum_diagnostic_responses_session_id UNIQUE (session_id), \n\tCONSTRAINT fk_curriculum_diagnostic_responses_session_id_curriculum_diagnostic_sessions FOREIGN KEY(session_id) REFERENCES curriculum_diagnostic_sessions (id) ON DELETE RESTRICT, \n\tCONSTRAINT uq_curriculum_diagnostic_responses_evidence_id UNIQUE (evidence_id), \n\tCONSTRAINT fk_curriculum_diagnostic_responses_evidence_id_learning_evidence FOREIGN KEY(evidence_id) REFERENCES learning_evidence (id) ON DELETE RESTRICT\n)",
    "CREATE TRIGGER IF NOT EXISTS curriculum_diagnostic_responses_no_update BEFORE UPDATE ON curriculum_diagnostic_responses BEGIN SELECT RAISE(ABORT, 'Curriculum history is protected'); END",
    "CREATE TRIGGER IF NOT EXISTS curriculum_diagnostic_responses_no_delete BEFORE DELETE ON curriculum_diagnostic_responses BEGIN SELECT RAISE(ABORT, 'Curriculum history is protected'); END",
    "CREATE TRIGGER IF NOT EXISTS curriculum_diagnostic_responses_no_insert BEFORE INSERT ON curriculum_diagnostic_responses WHEN EXISTS (SELECT 1 FROM curriculum_diagnostic_responses WHERE id=NEW.id OR (session_id=NEW.session_id OR evidence_id=NEW.evidence_id)) BEGIN SELECT RAISE(ABORT, 'Curriculum history is protected'); END",
    "CREATE TABLE curriculum_diagnostic_confirmations (\n\tid VARCHAR(36) NOT NULL, \n\tsession_id VARCHAR(36) NOT NULL, \n\tassessor_id INTEGER NOT NULL, \n\tassignment_id VARCHAR(36) NOT NULL, \n\tpayload JSON NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_curriculum_diagnostic_confirmations PRIMARY KEY (id), \n\tCONSTRAINT uq_curriculum_diagnostic_confirmations_session_id UNIQUE (session_id), \n\tCONSTRAINT fk_curriculum_diagnostic_confirmations_session_id_curriculum_diagnostic_sessions FOREIGN KEY(session_id) REFERENCES curriculum_diagnostic_sessions (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_curriculum_diagnostic_confirmations_assessor_id_users FOREIGN KEY(assessor_id) REFERENCES users (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_curriculum_diagnostic_confirmations_assignment_id_role_assignments FOREIGN KEY(assignment_id) REFERENCES role_assignments (id) ON DELETE RESTRICT\n)",
    "CREATE TRIGGER IF NOT EXISTS curriculum_diagnostic_confirmations_no_update BEFORE UPDATE ON curriculum_diagnostic_confirmations BEGIN SELECT RAISE(ABORT, 'Curriculum history is protected'); END",
    "CREATE TRIGGER IF NOT EXISTS curriculum_diagnostic_confirmations_no_delete BEFORE DELETE ON curriculum_diagnostic_confirmations BEGIN SELECT RAISE(ABORT, 'Curriculum history is protected'); END",
    "CREATE TRIGGER IF NOT EXISTS curriculum_diagnostic_confirmations_no_insert BEFORE INSERT ON curriculum_diagnostic_confirmations WHEN EXISTS (SELECT 1 FROM curriculum_diagnostic_confirmations WHERE id=NEW.id OR (session_id=NEW.session_id)) BEGIN SELECT RAISE(ABORT, 'Curriculum history is protected'); END",
]


def upgrade():
    for statement in STATEMENTS:
        if statement.startswith("CREATE TABLE "):
            table = statement.split()[2]
            if sa.inspect(op.get_bind()).has_table(table):
                continue
        op.execute(sa.text(statement))


def downgrade():
    protected = TABLES + [
        "learner_preference_revisions",
        "learner_model_annotations",
        "learner_model_correction_reviews",
        "learner_model_correction_snapshot_links",
    ]
    for table in protected:
        if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError(
                "Curriculum or learner history is protected; restore a verified backup"
            )
    import_module("migrations.versions.20260907_0030_learning_episodes")._preflight_downgrade()
    for table in reversed(TABLES):
        op.drop_table(table)
