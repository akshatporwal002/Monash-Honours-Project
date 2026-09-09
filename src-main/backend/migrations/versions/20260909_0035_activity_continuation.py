"""Protected approved-activity continuation and nullable no-next decisions."""

from importlib import import_module

import sqlalchemy as sa
from alembic import op

revision = "20260909_0035"
down_revision = "20260909_0034"
branch_labels = None
depends_on = None

TABLES = ["activity_progress_receipts", "activity_suggestions", "activity_choices"]
STATEMENTS = [
    "CREATE TABLE activity_progress_receipts (\n\tworkflow_id VARCHAR(36) NOT NULL, \n\tlearner_id INTEGER NOT NULL, \n\tcourse_id VARCHAR(36) NOT NULL, \n\toutcome_id VARCHAR(36), \n\tsnapshot_id VARCHAR(36), \n\tstate VARCHAR(50) NOT NULL, \n\tevidence_ids JSON NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_activity_progress_receipts PRIMARY KEY (workflow_id), \n\tCONSTRAINT fk_activity_progress_receipts_workflow_id_workflow_runs FOREIGN KEY(workflow_id) REFERENCES workflow_runs (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_activity_progress_receipts_learner_id_users FOREIGN KEY(learner_id) REFERENCES users (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_activity_progress_receipts_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_activity_progress_receipts_outcome_id_learning_outcomes FOREIGN KEY(outcome_id) REFERENCES learning_outcomes (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_activity_progress_receipts_snapshot_id_learner_model_snapshots FOREIGN KEY(snapshot_id) REFERENCES learner_model_snapshots (id) ON DELETE RESTRICT\n)",
    "CREATE TRIGGER IF NOT EXISTS activity_progress_receipts_no_update BEFORE UPDATE ON activity_progress_receipts BEGIN SELECT RAISE(ABORT, 'Activity continuation history is protected'); END",
    "CREATE TRIGGER IF NOT EXISTS activity_progress_receipts_no_delete BEFORE DELETE ON activity_progress_receipts BEGIN SELECT RAISE(ABORT, 'Activity continuation history is protected'); END",
    "CREATE TRIGGER IF NOT EXISTS activity_progress_receipts_no_insert BEFORE INSERT ON activity_progress_receipts WHEN EXISTS (SELECT 1 FROM activity_progress_receipts WHERE workflow_id=NEW.workflow_id) BEGIN SELECT RAISE(ABORT, 'Activity continuation history is protected'); END",
    "CREATE TABLE activity_suggestions (\n\tworkflow_id VARCHAR(36) NOT NULL, \n\tpathway_id VARCHAR(36), \n\ttask_id VARCHAR(36), \n\tdecision JSON NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_activity_suggestions PRIMARY KEY (workflow_id), \n\tCONSTRAINT fk_activity_suggestions_workflow_id_activity_progress_receipts FOREIGN KEY(workflow_id) REFERENCES activity_progress_receipts (workflow_id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_activity_suggestions_pathway_id_curriculum_pathway_versions FOREIGN KEY(pathway_id) REFERENCES curriculum_pathway_versions (id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_activity_suggestions_task_id_learning_tasks FOREIGN KEY(task_id) REFERENCES learning_tasks (id) ON DELETE RESTRICT\n)",
    "CREATE TRIGGER IF NOT EXISTS activity_suggestions_no_update BEFORE UPDATE ON activity_suggestions BEGIN SELECT RAISE(ABORT, 'Activity continuation history is protected'); END",
    "CREATE TRIGGER IF NOT EXISTS activity_suggestions_no_delete BEFORE DELETE ON activity_suggestions BEGIN SELECT RAISE(ABORT, 'Activity continuation history is protected'); END",
    "CREATE TRIGGER IF NOT EXISTS activity_suggestions_no_insert BEFORE INSERT ON activity_suggestions WHEN EXISTS (SELECT 1 FROM activity_suggestions WHERE workflow_id=NEW.workflow_id) BEGIN SELECT RAISE(ABORT, 'Activity continuation history is protected'); END",
    "CREATE TABLE activity_choices (\n\tid VARCHAR(36) NOT NULL, \n\tworkflow_id VARCHAR(36) NOT NULL, \n\tactor_id INTEGER NOT NULL, \n\tversion INTEGER NOT NULL, \n\trequest_key VARCHAR(100) NOT NULL, \n\tpayload JSON NOT NULL, \n\tcreated_at DATETIME NOT NULL, \n\tCONSTRAINT pk_activity_choices PRIMARY KEY (id), \n\tCONSTRAINT uq_activity_choice_version UNIQUE (workflow_id, version), \n\tCONSTRAINT uq_activity_choice_request UNIQUE (workflow_id, actor_id, request_key), \n\tCONSTRAINT ck_activity_choices_activity_choice_positive_version CHECK (version > 0), \n\tCONSTRAINT fk_activity_choices_workflow_id_activity_suggestions FOREIGN KEY(workflow_id) REFERENCES activity_suggestions (workflow_id) ON DELETE RESTRICT, \n\tCONSTRAINT fk_activity_choices_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE RESTRICT\n)",
    "CREATE TRIGGER IF NOT EXISTS activity_choices_no_update BEFORE UPDATE ON activity_choices BEGIN SELECT RAISE(ABORT, 'Activity continuation history is protected'); END",
    "CREATE TRIGGER IF NOT EXISTS activity_choices_no_delete BEFORE DELETE ON activity_choices BEGIN SELECT RAISE(ABORT, 'Activity continuation history is protected'); END",
    "CREATE TRIGGER IF NOT EXISTS activity_choices_no_insert BEFORE INSERT ON activity_choices WHEN EXISTS (SELECT 1 FROM activity_choices WHERE id=NEW.id OR (workflow_id=NEW.workflow_id AND (version=NEW.version OR (actor_id=NEW.actor_id AND request_key=NEW.request_key)))) BEGIN SELECT RAISE(ABORT, 'Activity continuation history is protected'); END",
]
SHAPE = "(state = 'pending' AND processing_attempts = 0 AND execution_token IS NULL AND lease_expires_at IS NULL AND next_retry_at IS NULL AND next_task_reference IS NULL AND failure_category IS NULL AND completed_at IS NULL) OR (state = 'running' AND processing_attempts BETWEEN 1 AND 3 AND execution_token IS NOT NULL AND lease_expires_at IS NOT NULL AND next_retry_at IS NULL AND next_task_reference IS NULL AND failure_category IS NULL AND completed_at IS NULL) OR (state = 'retry_scheduled' AND processing_attempts BETWEEN 1 AND 2 AND execution_token IS NULL AND lease_expires_at IS NULL AND next_retry_at IS NOT NULL AND next_task_reference IS NULL AND failure_category IS NOT NULL AND completed_at IS NULL) OR (state = 'completed' AND processing_attempts BETWEEN 1 AND 3 AND progress_recorded = 1 AND execution_token IS NULL AND lease_expires_at IS NULL AND next_retry_at IS NULL AND failure_category IS NULL AND completed_at IS NOT NULL) OR (state = 'failed' AND processing_attempts BETWEEN 1 AND 3 AND execution_token IS NULL AND lease_expires_at IS NULL AND next_retry_at IS NULL AND next_task_reference IS NULL AND failure_category IS NOT NULL AND completed_at IS NOT NULL)"


def _shape(value):
    with op.batch_alter_table("continuation_jobs") as batch:
        batch.drop_constraint(op.f("ck_continuation_jobs_continuation_state_shape"), type_="check")
        batch.create_check_constraint(op.f("ck_continuation_jobs_continuation_state_shape"), value)


def upgrade():
    current = next(
        c["sqltext"]
        for c in sa.inspect(op.get_bind()).get_check_constraints("continuation_jobs")
        if c["name"].endswith("continuation_state_shape")
    )
    if "next_task_reference IS NOT NULL" in current:
        _shape(SHAPE)
    for statement in STATEMENTS:
        if statement.startswith("CREATE TABLE ") and sa.inspect(op.get_bind()).has_table(
            statement.split()[2]
        ):
            continue
        op.execute(sa.text(statement))


def downgrade():
    import_module("migrations.versions.20260907_0030_learning_episodes")._preflight_downgrade()
    protected = TABLES + [
        "curriculum_pathway_versions",
        "curriculum_diagnostic_sessions",
        "curriculum_diagnostic_responses",
        "curriculum_diagnostic_confirmations",
        "learner_preference_revisions",
        "learner_model_annotations",
        "learner_model_correction_reviews",
        "learner_model_correction_snapshot_links",
    ]
    for table in protected:
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
    for table in reversed(TABLES):
        op.drop_table(table)
    _shape(
        SHAPE.replace(
            "AND failure_category IS NULL AND completed_at IS NOT NULL) OR (state = 'failed'",
            "AND next_task_reference IS NOT NULL AND failure_category IS NULL AND completed_at IS NOT NULL) OR (state = 'failed'",
        )
    )
