"""Preserve reassessment records and their scope guards.

Revision ID: 20260909_0036
Revises: 20260909_0035
"""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0036"
down_revision = "20260909_0035"
branch_labels = None
depends_on = None

STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS outcome_result_policies (
    id VARCHAR(36) NOT NULL,
    definition_version_id VARCHAR(36) NOT NULL,
    selection_rule VARCHAR(24) NOT NULL,
    required_form_ids JSON NOT NULL,
    approved_by_user_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT pk_outcome_result_policies PRIMARY KEY (id),
    CONSTRAINT uq_outcome_result_policy_definition UNIQUE (definition_version_id),
    CONSTRAINT ck_outcome_result_policies_outcome_policy_rule CHECK (selection_rule IN ('LATEST_VALID', 'ANY_VALID_PASS', 'ALL_REQUIRED_FORMS')),
    CONSTRAINT ck_outcome_result_policies_outcome_policy_reason CHECK (length(trim(reason)) > 0),
    CONSTRAINT fk_outcome_result_policies_definition_version_id_assessment_definition_versions FOREIGN KEY(definition_version_id) REFERENCES assessment_definition_versions (id) ON DELETE RESTRICT,
    CONSTRAINT fk_outcome_result_policies_approved_by_user_id_users FOREIGN KEY(approved_by_user_id) REFERENCES users (id) ON DELETE RESTRICT
)""",
    """CREATE TRIGGER IF NOT EXISTS outcome_result_policies_no_delete BEFORE DELETE ON outcome_result_policies BEGIN SELECT RAISE(ABORT, 'outcome_result_policies history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS outcome_result_policies_no_replace BEFORE INSERT ON outcome_result_policies WHEN EXISTS (SELECT 1 FROM outcome_result_policies WHERE (id = NEW.id) OR (definition_version_id = NEW.definition_version_id)) BEGIN SELECT RAISE(ABORT, 'outcome_result_policies history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS outcome_result_policies_no_update BEFORE UPDATE ON outcome_result_policies BEGIN SELECT RAISE(ABORT, 'outcome_result_policies history is immutable'); END""",
    """CREATE TABLE IF NOT EXISTS reassessment_authorisations (
    id VARCHAR(36) NOT NULL,
    prior_attempt_id VARCHAR(36) NOT NULL,
    prior_decision_id VARCHAR(36) NOT NULL,
    decision_revision INTEGER NOT NULL,
    revision INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    task_id VARCHAR(36) NOT NULL,
    task_form_version_id VARCHAR(36) NOT NULL,
    policy_id VARCHAR(36) NOT NULL,
    approved_by_user_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    learner_notice TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT pk_reassessment_authorisations PRIMARY KEY (id),
    CONSTRAINT uq_reassessment_authorisation_prior UNIQUE (prior_attempt_id, revision),
    CONSTRAINT uq_reassessment_authorisation_target UNIQUE (student_id, task_id),
    CONSTRAINT ck_reassessment_authorisations_reassessment_revision CHECK (decision_revision >= 0),
    CONSTRAINT ck_reassessment_authorisations_reassessment_authorisation_revision CHECK (revision > 0),
    CONSTRAINT ck_reassessment_authorisations_reassessment_reasons CHECK (length(trim(reason)) > 0 AND length(trim(learner_notice)) > 0),
    CONSTRAINT fk_reassessment_authorisations_prior_attempt_id_assessment_attempts FOREIGN KEY(prior_attempt_id) REFERENCES assessment_attempts (id) ON DELETE RESTRICT,
    CONSTRAINT fk_reassessment_authorisations_prior_decision_id_assessment_decisions FOREIGN KEY(prior_decision_id) REFERENCES assessment_decisions (id) ON DELETE RESTRICT,
    CONSTRAINT fk_reassessment_authorisations_student_id_users FOREIGN KEY(student_id) REFERENCES users (id) ON DELETE RESTRICT,
    CONSTRAINT fk_reassessment_authorisations_task_id_learning_tasks FOREIGN KEY(task_id) REFERENCES learning_tasks (id) ON DELETE RESTRICT,
    CONSTRAINT fk_reassessment_authorisations_task_form_version_id_task_form_versions FOREIGN KEY(task_form_version_id) REFERENCES task_form_versions (id) ON DELETE RESTRICT,
    CONSTRAINT fk_reassessment_authorisations_policy_id_outcome_result_policies FOREIGN KEY(policy_id) REFERENCES outcome_result_policies (id) ON DELETE RESTRICT,
    CONSTRAINT fk_reassessment_authorisations_approved_by_user_id_users FOREIGN KEY(approved_by_user_id) REFERENCES users (id) ON DELETE RESTRICT
)""",
    """CREATE TRIGGER IF NOT EXISTS reassessment_authorisations_no_delete BEFORE DELETE ON reassessment_authorisations BEGIN SELECT RAISE(ABORT, 'reassessment_authorisations history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS reassessment_authorisations_no_replace BEFORE INSERT ON reassessment_authorisations WHEN EXISTS (SELECT 1 FROM reassessment_authorisations WHERE (id = NEW.id) OR (prior_attempt_id = NEW.prior_attempt_id AND revision = NEW.revision) OR (student_id = NEW.student_id AND task_id = NEW.task_id)) BEGIN SELECT RAISE(ABORT, 'reassessment_authorisations history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS reassessment_authorisations_no_update BEFORE UPDATE ON reassessment_authorisations BEGIN SELECT RAISE(ABORT, 'reassessment_authorisations history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS reassessment_authorisations_scope BEFORE INSERT ON reassessment_authorisations
WHEN NOT EXISTS (
    SELECT 1 FROM assessment_attempts a
    JOIN assessment_decisions d ON d.assessment_attempt_id = a.id
    JOIN outcome_result_policies p ON p.definition_version_id = a.assessment_definition_version_id
    JOIN task_form_versions f ON f.assessment_definition_version_id = p.definition_version_id
    WHERE a.id = NEW.prior_attempt_id AND d.id = NEW.prior_decision_id
    AND p.id = NEW.policy_id AND a.student_id = NEW.student_id
    AND f.id = NEW.task_form_version_id AND f.learning_task_id = NEW.task_id
    AND a.task_id != NEW.task_id AND a.task_form_version_id != f.id
) BEGIN SELECT RAISE(ABORT, 'Reassessment authorisation scope mismatch'); END""",
)


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(sa.text(statement))


def downgrade() -> None:
    tables = ("reassessment_authorisations", "outcome_result_policies")
    for table in tables:
        if op.get_bind().execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one():
            raise RuntimeError(f"cannot downgrade populated {table} history")
    for table in tables:
        op.drop_table(table)
