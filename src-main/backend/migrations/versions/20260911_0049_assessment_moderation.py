"""Live moderation and evaluator revalidation; no approval records are seeded."""

import sqlalchemy as sa
from alembic import op

revision = "20260911_0049"
down_revision = "20260910_0046"
branch_labels = None
depends_on = None

STATEMENTS = (
    "CREATE TABLE assessment_moderation_policies (\n\tid VARCHAR(36) NOT NULL, \n\tcourse_id VARCHAR(36) NOT NULL, \n\tversion INTEGER NOT NULL, \n\tinitial_count INTEGER NOT NULL, \n\tlater_percent INTEGER NOT NULL, \n\tdrift_interval INTEGER NOT NULL, \n\tapproval_reference TEXT NOT NULL, \n\ttraining_reference TEXT NOT NULL, \n\tactor_id INTEGER NOT NULL, \n\texpires_at DATETIME NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_assessment_moderation_policies PRIMARY KEY (id), \n\tCONSTRAINT uq_assessment_moderation_policies_course_id UNIQUE (course_id, version), \n\tCONSTRAINT ck_assessment_moderation_policies_sampling_bounds CHECK (initial_count >= 0 AND later_percent >= 0 AND later_percent <= 100 AND drift_interval > 0), \n\tCONSTRAINT fk_assessment_moderation_policies_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_assessment_moderation_policies_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE RESTRICT\n)",
    "CREATE TRIGGER IF NOT EXISTS assessment_moderation_policies_no_update BEFORE UPDATE ON assessment_moderation_policies BEGIN SELECT RAISE(ABORT, 'Assessment governance history is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS assessment_moderation_policies_no_delete BEFORE DELETE ON assessment_moderation_policies BEGIN SELECT RAISE(ABORT, 'Assessment governance history is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS assessment_moderation_policies_no_insert BEFORE INSERT ON assessment_moderation_policies WHEN EXISTS (SELECT 1 FROM assessment_moderation_policies WHERE (id = NEW.id) OR (course_id = NEW.course_id AND version = NEW.version)) BEGIN SELECT RAISE(ABORT, 'Assessment governance history is append-only'); END",
    "CREATE TABLE assessment_moderation_selections (\n\tattempt_id VARCHAR(36) NOT NULL, \n\tpolicy_id VARCHAR(36) NOT NULL, \n\ttask_family VARCHAR(100) NOT NULL, \n\tsequence INTEGER NOT NULL, \n\tselected BOOLEAN NOT NULL, \n\tdrift_check BOOLEAN NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_assessment_moderation_selections PRIMARY KEY (attempt_id), \n\tCONSTRAINT fk_assessment_moderation_selections_attempt_id_assessment_attempts FOREIGN KEY(attempt_id) REFERENCES assessment_attempts (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_assessment_moderation_selections_policy_id_assessment_moderation_policies FOREIGN KEY(policy_id) REFERENCES assessment_moderation_policies (id) ON DELETE RESTRICT\n)",
    "CREATE TRIGGER IF NOT EXISTS assessment_moderation_selections_no_update BEFORE UPDATE ON assessment_moderation_selections BEGIN SELECT RAISE(ABORT, 'Assessment governance history is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS assessment_moderation_selections_no_delete BEFORE DELETE ON assessment_moderation_selections BEGIN SELECT RAISE(ABORT, 'Assessment governance history is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS assessment_moderation_selections_no_insert BEFORE INSERT ON assessment_moderation_selections WHEN EXISTS (SELECT 1 FROM assessment_moderation_selections WHERE (attempt_id = NEW.attempt_id)) BEGIN SELECT RAISE(ABORT, 'Assessment governance history is append-only'); END",
    "CREATE TABLE assessment_moderation_reviews (\n\tid VARCHAR(36) NOT NULL, \n\tattempt_id VARCHAR(36) NOT NULL, \n\tstage VARCHAR(20) NOT NULL, \n\tactor_id INTEGER NOT NULL, \n\tresult VARCHAR(12) NOT NULL, \n\treason TEXT NOT NULL, \n\tcriteria JSON NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_assessment_moderation_reviews PRIMARY KEY (id), \n\tCONSTRAINT uq_assessment_moderation_reviews_attempt_id UNIQUE (attempt_id, stage), \n\tCONSTRAINT ck_assessment_moderation_reviews_review_stage CHECK (stage IN ('ORIGINAL', 'SECOND', 'RESOLUTION', 'DRIFT', 'DRIFT_RESOLUTION')), \n\tCONSTRAINT ck_assessment_moderation_reviews_review_result CHECK (result IN ('PASS', 'INCOMPLETE')), \n\tCONSTRAINT fk_assessment_moderation_reviews_attempt_id_assessment_moderation_selections FOREIGN KEY(attempt_id) REFERENCES assessment_moderation_selections (attempt_id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_assessment_moderation_reviews_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE RESTRICT\n)",
    "CREATE TRIGGER IF NOT EXISTS assessment_moderation_reviews_no_update BEFORE UPDATE ON assessment_moderation_reviews BEGIN SELECT RAISE(ABORT, 'Assessment governance history is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS assessment_moderation_reviews_no_delete BEFORE DELETE ON assessment_moderation_reviews BEGIN SELECT RAISE(ABORT, 'Assessment governance history is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS assessment_moderation_reviews_no_insert BEFORE INSERT ON assessment_moderation_reviews WHEN EXISTS (SELECT 1 FROM assessment_moderation_reviews WHERE (id = NEW.id) OR (attempt_id = NEW.attempt_id AND stage = NEW.stage)) BEGIN SELECT RAISE(ABORT, 'Assessment governance history is append-only'); END",
    "CREATE TABLE evaluator_validation_events (\n\tid VARCHAR(36) NOT NULL, \n\tcourse_id VARCHAR(36) NOT NULL, \n\trevision INTEGER NOT NULL, \n\tstate VARCHAR(20) NOT NULL, \n\tfingerprint VARCHAR(64) NOT NULL, \n\tdependencies JSON NOT NULL, \n\tevidence JSON NOT NULL, \n\treason TEXT NOT NULL, \n\tactor_id INTEGER, \n\texpires_at DATETIME, \n\tcreated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_evaluator_validation_events PRIMARY KEY (id), \n\tCONSTRAINT uq_evaluator_validation_events_course_id UNIQUE (course_id, revision), \n\tCONSTRAINT ck_evaluator_validation_events_validation_state CHECK (state IN ('VALIDATED', 'INVALIDATED')), \n\tCONSTRAINT fk_evaluator_validation_events_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_evaluator_validation_events_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE RESTRICT\n)",
    "CREATE TRIGGER IF NOT EXISTS evaluator_validation_events_no_update BEFORE UPDATE ON evaluator_validation_events BEGIN SELECT RAISE(ABORT, 'Assessment governance history is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS evaluator_validation_events_no_delete BEFORE DELETE ON evaluator_validation_events BEGIN SELECT RAISE(ABORT, 'Assessment governance history is append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS evaluator_validation_events_no_insert BEFORE INSERT ON evaluator_validation_events WHEN EXISTS (SELECT 1 FROM evaluator_validation_events WHERE (id = NEW.id) OR (course_id = NEW.course_id AND revision = NEW.revision)) BEGIN SELECT RAISE(ABORT, 'Assessment governance history is append-only'); END",
)


def upgrade():
    for statement in STATEMENTS:
        op.execute(sa.text(statement))


def downgrade():
    tables = (
        "evaluator_validation_events",
        "assessment_moderation_reviews",
        "assessment_moderation_selections",
        "assessment_moderation_policies",
    )
    for table in tables:
        if op.get_bind().execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one():
            raise RuntimeError("Cannot remove populated assessment governance history")
    for table in tables:
        op.drop_table(table)
