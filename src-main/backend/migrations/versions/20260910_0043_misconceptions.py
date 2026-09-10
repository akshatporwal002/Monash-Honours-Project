"""Preserve reviewed misconception cycles without changing formal assessment history."""

from importlib import import_module

import sqlalchemy as sa
from alembic import op

revision = "20260910_0043"
down_revision = "20260909_0042"
branch_labels = None
depends_on = None

TABLES = (
    "misconception_closures",
    "misconception_reviews",
    "misconception_responses",
    "misconception_hypotheses",
)
STATEMENTS = (
    "\nCREATE TABLE IF NOT EXISTS misconception_hypotheses (\n\tid VARCHAR(36) NOT NULL, \n\tcourse_id VARCHAR(36) NOT NULL, \n\toutcome_id VARCHAR(36) NOT NULL, \n\ttask_id VARCHAR(36) NOT NULL, \n\tstudent_id INTEGER NOT NULL, \n\tactor_id INTEGER NOT NULL, \n\tfeedback_id VARCHAR(36) NOT NULL, \n\ttask_revision_id VARCHAR(36) NOT NULL, \n\trequest_key VARCHAR(100) NOT NULL, \n\tpayload JSON NOT NULL, \n\tsource_approvals JSON NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_misconception_hypotheses PRIMARY KEY (id), \n\tCONSTRAINT uq_misconception_hypothesis_request UNIQUE (actor_id, request_key), \n\tCONSTRAINT fk_misconception_hypotheses_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_misconception_hypotheses_outcome_id_learning_outcomes FOREIGN KEY(outcome_id) REFERENCES learning_outcomes (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_misconception_hypotheses_task_id_learning_tasks FOREIGN KEY(task_id) REFERENCES learning_tasks (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_misconception_hypotheses_student_id_users FOREIGN KEY(student_id) REFERENCES users (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_misconception_hypotheses_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_misconception_hypotheses_feedback_id_feedback_records FOREIGN KEY(feedback_id) REFERENCES feedback_records (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_misconception_hypotheses_task_revision_id_task_revisions FOREIGN KEY(task_revision_id) REFERENCES task_revisions (id) ON DELETE RESTRICT\n)\n\n",
    "CREATE TRIGGER IF NOT EXISTS misconception_hypotheses_no_update BEFORE UPDATE ON misconception_hypotheses BEGIN SELECT RAISE(ABORT, 'misconception_hypotheses history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS misconception_hypotheses_no_delete BEFORE DELETE ON misconception_hypotheses BEGIN SELECT RAISE(ABORT, 'misconception_hypotheses history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS misconception_hypotheses_no_replace BEFORE INSERT ON misconception_hypotheses WHEN EXISTS (SELECT 1 FROM misconception_hypotheses WHERE (id = NEW.id) OR (actor_id = NEW.actor_id AND request_key = NEW.request_key)) BEGIN SELECT RAISE(ABORT, 'misconception_hypotheses history is immutable'); END",
    "\nCREATE TABLE IF NOT EXISTS misconception_responses (\n\tid VARCHAR(36) NOT NULL, \n\thypothesis_id VARCHAR(36) NOT NULL, \n\tactor_id INTEGER NOT NULL, \n\tversion INTEGER NOT NULL, \n\tstage VARCHAR(16) NOT NULL, \n\trequest_key VARCHAR(100) NOT NULL, \n\tpayload JSON NOT NULL, \n\tevidence_id VARCHAR(36) NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_misconception_responses PRIMARY KEY (id), \n\tCONSTRAINT uq_misconception_response_version UNIQUE (hypothesis_id, version), \n\tCONSTRAINT uq_misconception_response_request UNIQUE (hypothesis_id, request_key), \n\tCONSTRAINT uq_misconception_response_stage UNIQUE (hypothesis_id, stage), \n\tCONSTRAINT ck_misconception_responses_misconception_response_version CHECK (version BETWEEN 1 AND 3), \n\tCONSTRAINT ck_misconception_responses_misconception_response_stage CHECK (stage IN ('PROBE', 'REVISION', 'TRANSFER')), \n\tCONSTRAINT fk_misconception_responses_hypothesis_id_misconception_hypotheses FOREIGN KEY(hypothesis_id) REFERENCES misconception_hypotheses (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_misconception_responses_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_misconception_responses_evidence_id_learning_evidence FOREIGN KEY(evidence_id) REFERENCES learning_evidence (id) ON DELETE RESTRICT\n)\n\n",
    "CREATE TRIGGER IF NOT EXISTS misconception_responses_no_update BEFORE UPDATE ON misconception_responses BEGIN SELECT RAISE(ABORT, 'misconception_responses history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS misconception_responses_no_delete BEFORE DELETE ON misconception_responses BEGIN SELECT RAISE(ABORT, 'misconception_responses history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS misconception_responses_no_replace BEFORE INSERT ON misconception_responses WHEN EXISTS (SELECT 1 FROM misconception_responses WHERE (id = NEW.id) OR (hypothesis_id = NEW.hypothesis_id AND version = NEW.version) OR (hypothesis_id = NEW.hypothesis_id AND request_key = NEW.request_key) OR (hypothesis_id = NEW.hypothesis_id AND stage = NEW.stage)) BEGIN SELECT RAISE(ABORT, 'misconception_responses history is immutable'); END",
    "\nCREATE TABLE IF NOT EXISTS misconception_reviews (\n\tid VARCHAR(36) NOT NULL, \n\thypothesis_id VARCHAR(36) NOT NULL, \n\tactor_id INTEGER NOT NULL, \n\tversion INTEGER NOT NULL, \n\tstate VARCHAR(16) NOT NULL, \n\trequest_key VARCHAR(100) NOT NULL, \n\tpayload JSON NOT NULL, \n\tevidence_id VARCHAR(36) NOT NULL, \n\tsnapshot_id VARCHAR(36) NOT NULL, \n\tescalation_id VARCHAR(36), \n\tcreated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_misconception_reviews PRIMARY KEY (id), \n\tCONSTRAINT uq_misconception_review_version UNIQUE (hypothesis_id, version), \n\tCONSTRAINT uq_misconception_review_request UNIQUE (hypothesis_id, request_key), \n\tCONSTRAINT ck_misconception_reviews_misconception_review_version CHECK (version > 3), \n\tCONSTRAINT ck_misconception_reviews_misconception_review_state CHECK (state IN ('UNCERTAIN', 'PERSISTED', 'WEAKENED', 'CORRECTED')), \n\tCONSTRAINT fk_misconception_reviews_hypothesis_id_misconception_hypotheses FOREIGN KEY(hypothesis_id) REFERENCES misconception_hypotheses (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_misconception_reviews_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_misconception_reviews_evidence_id_learning_evidence FOREIGN KEY(evidence_id) REFERENCES learning_evidence (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_misconception_reviews_snapshot_id_learner_model_snapshots FOREIGN KEY(snapshot_id) REFERENCES learner_model_snapshots (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_misconception_reviews_escalation_id_escalation_cases FOREIGN KEY(escalation_id) REFERENCES escalation_cases (id) ON DELETE RESTRICT\n)\n\n",
    "CREATE TRIGGER IF NOT EXISTS misconception_reviews_no_update BEFORE UPDATE ON misconception_reviews BEGIN SELECT RAISE(ABORT, 'misconception_reviews history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS misconception_reviews_no_delete BEFORE DELETE ON misconception_reviews BEGIN SELECT RAISE(ABORT, 'misconception_reviews history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS misconception_reviews_no_replace BEFORE INSERT ON misconception_reviews WHEN EXISTS (SELECT 1 FROM misconception_reviews WHERE (id = NEW.id) OR (hypothesis_id = NEW.hypothesis_id AND version = NEW.version) OR (hypothesis_id = NEW.hypothesis_id AND request_key = NEW.request_key)) BEGIN SELECT RAISE(ABORT, 'misconception_reviews history is immutable'); END",
    "\nCREATE TABLE IF NOT EXISTS misconception_closures (\n\tid VARCHAR(36) NOT NULL, \n\thypothesis_id VARCHAR(36) NOT NULL, \n\tactor_id INTEGER NOT NULL, \n\tdisposition VARCHAR(16) NOT NULL, \n\tpayload JSON NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_misconception_closures PRIMARY KEY (id), \n\tCONSTRAINT uq_misconception_closure UNIQUE (hypothesis_id), \n\tCONSTRAINT ck_misconception_closures_misconception_closure_disposition CHECK (disposition IN ('DEFERRED', 'INVALIDATED')), \n\tCONSTRAINT fk_misconception_closures_hypothesis_id_misconception_hypotheses FOREIGN KEY(hypothesis_id) REFERENCES misconception_hypotheses (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_misconception_closures_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE RESTRICT\n)\n\n",
    "CREATE TRIGGER IF NOT EXISTS misconception_closures_no_update BEFORE UPDATE ON misconception_closures BEGIN SELECT RAISE(ABORT, 'misconception_closures history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS misconception_closures_no_delete BEFORE DELETE ON misconception_closures BEGIN SELECT RAISE(ABORT, 'misconception_closures history is immutable'); END",
    "CREATE TRIGGER IF NOT EXISTS misconception_closures_no_replace BEFORE INSERT ON misconception_closures WHEN EXISTS (SELECT 1 FROM misconception_closures WHERE (id = NEW.id) OR (hypothesis_id = NEW.hypothesis_id)) BEGIN SELECT RAISE(ABORT, 'misconception_closures history is immutable'); END",
)


def upgrade():
    for statement in STATEMENTS:
        op.execute(sa.text(statement))


def downgrade():
    for table in TABLES:
        if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError(f"cannot downgrade populated {table} history")
    # Preserve the prior head's refusal before this migration makes any DDL change.
    for table in (
        "participation_recognitions",
        "gamification_preferences",
        "deadline_arrangements",
        "reminder_preferences",
        "escalation_events",
        "escalation_cases",
        "escalation_queue_revisions",
        "reassessment_authorisations",
        "outcome_result_policies",
        "tutor_turns",
        "appeal_resolutions",
    ):
        if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError(f"cannot downgrade populated {table} history")
    import_module("migrations.versions.20260907_0030_learning_episodes")._preflight_downgrade()
    for table in (
        "activity_progress_receipts",
        "activity_suggestions",
        "activity_choices",
        "curriculum_pathway_versions",
        "curriculum_diagnostic_sessions",
        "curriculum_diagnostic_responses",
        "curriculum_diagnostic_confirmations",
        "learner_preference_revisions",
        "learner_model_annotations",
        "learner_model_correction_reviews",
        "learner_model_correction_snapshot_links",
    ):
        if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError("Activity history is protected; restore a verified backup")
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM continuation_jobs WHERE state='completed' AND next_task_reference IS NULL"
            )
        )
        .scalar_one()
    ):
        raise RuntimeError("Completed no-next decisions require a verified backup")
    for table in TABLES:
        op.drop_table(table)
