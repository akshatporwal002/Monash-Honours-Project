"""Create immutable response-version assessment attempts and decisions.

Revision ID: 20260815_0017
Revises: 20260815_0016
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0017"
down_revision: str | None = "20260815_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    with op.batch_alter_table("submission_attempts") as batch:
        batch.drop_constraint("submission_attempt_score", type_="check")
        batch.alter_column("score", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("task_form_version_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("response_schema_version", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("content_digest", sa.String(length=71), nullable=True))
        batch.add_column(sa.Column("idempotency_key", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("declared_conditions", sa.JSON(), nullable=True))
        batch.create_foreign_key(
            "fk_submission_attempts_task_form_version_id_task_form_versions",
            "task_form_versions",
            ["task_form_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_check_constraint(
            "submission_attempt_legacy_score", "score IS NULL OR score BETWEEN 0 AND 100"
        )
        batch.create_check_constraint(
            "submission_attempt_content_digest",
            "content_digest IS NULL OR (length(content_digest) = 71 AND "
            "content_digest GLOB 'sha256:*' AND content_digest NOT GLOB 'sha256:*[^0-9a-f]*')",
        )
        batch.create_unique_constraint(
            "uq_submission_attempts_idempotency", ["student_id", "task_id", "idempotency_key"]
        )

    with op.batch_alter_table("audit_events") as batch:
        batch.drop_constraint("audit_action", type_="check")
        batch.alter_column(
            "action",
            existing_type=sa.String(length=100),
            type_=_enum(
                "audit_action",
                "assessment_definition_created",
                "assessment_attempt_created",
                "assessment_decision_created",
                "assessor_review_recorded",
                "appeal_or_correction_recorded",
                "feedback_generation_started",
                "feedback_generation_completed",
                "feedback_judged",
                "feedback_regenerated",
                "feedback_fallback_used",
                "feedback_viewed",
                "feedback_reported",
                "research_export_created",
                "workflow_completed",
                "workflow_failed",
            ),
            existing_nullable=False,
        )

    op.create_table(
        "assessment_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("response_version_id", sa.String(length=36), nullable=False),
        sa.Column("assessment_definition_version_id", sa.String(length=36), nullable=False),
        sa.Column("task_form_version_id", sa.String(length=36), nullable=False),
        sa.Column("bloom_target_version_id", sa.String(length=36), nullable=False),
        sa.Column("pass_rule_version_id", sa.String(length=36), nullable=False),
        sa.Column(
            "state",
            _enum("assessment_attempt_state", "PENDING", "EVALUATED", "FAULTED", "VOID"),
            nullable=False,
        ),
        sa.Column("fault_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_id"], ["learning_tasks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["response_version_id"], ["submission_attempts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["assessment_definition_version_id"],
            ["assessment_definition_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_form_version_id"], ["task_form_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["bloom_target_version_id"], ["bloom_target_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["pass_rule_version_id"], ["pass_rule_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("response_version_id", name="uq_assessment_attempts_response_version"),
        sa.CheckConstraint(
            "(state IN ('PENDING', 'EVALUATED') AND fault_reason IS NULL) OR "
            "(state IN ('FAULTED', 'VOID') AND length(trim(fault_reason)) > 0)",
            name="assessment_attempt_state_shape",
        ),
    )
    op.create_table(
        "criterion_evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assessment_attempt_id", sa.String(length=36), nullable=False),
        sa.Column("criterion_version_id", sa.String(length=36), nullable=False),
        sa.Column(
            "decision",
            _enum("criterion_decision", "MET", "NOT_MET", "NOT_EVALUABLE"),
            nullable=False,
        ),
        sa.Column("evidence_references", sa.JSON(), nullable=False),
        sa.Column("evaluator_reference", sa.String(length=255), nullable=False),
        sa.Column("model_version", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=255), nullable=True),
        sa.Column("retrieval_version", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_attempt_id"], ["assessment_attempts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["criterion_version_id"], ["criterion_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assessment_attempt_id",
            "criterion_version_id",
            name="uq_criterion_evaluations_attempt_criterion",
        ),
        sa.CheckConstraint("length(trim(reason)) > 0", name="criterion_evaluation_reason"),
    )
    result = _enum("assessment_result", "PASS", "INCOMPLETE")
    op.create_table(
        "assessment_decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assessment_attempt_id", sa.String(length=36), nullable=False),
        sa.Column("bloom_target_version_id", sa.String(length=36), nullable=False),
        sa.Column("pass_rule_version_id", sa.String(length=36), nullable=False),
        sa.Column("evaluation_idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("result", result, nullable=True),
        sa.Column(
            "result_state",
            _enum(
                "assessment_result_state",
                "NOT_ASSESSED",
                "PROVISIONAL",
                "CONFIRMED",
                "OVERRIDDEN",
                "VOID",
            ),
            nullable=False,
        ),
        sa.Column("evidence_references", sa.JSON(), nullable=False),
        sa.Column("system_reason", sa.Text(), nullable=False),
        sa.Column("assessor_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "prior_result", _enum("assessment_prior_result", "PASS", "INCOMPLETE"), nullable=True
        ),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_attempt_id"], ["assessment_attempts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["bloom_target_version_id"], ["bloom_target_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["pass_rule_version_id"], ["pass_rule_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["assessor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_attempt_id", name="uq_assessment_decisions_attempt"),
        sa.UniqueConstraint(
            "evaluation_idempotency_key", name="uq_assessment_decisions_idempotency"
        ),
        sa.CheckConstraint(
            "(result_state = 'PROVISIONAL' AND result IN ('PASS', 'INCOMPLETE') AND assessor_user_id IS NULL AND reviewed_at IS NULL AND prior_result IS NULL AND override_reason IS NULL AND length(trim(system_reason)) > 0) OR "
            "(result_state = 'CONFIRMED' AND result IN ('PASS', 'INCOMPLETE') AND assessor_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND prior_result IS NULL AND override_reason IS NULL AND length(trim(system_reason)) > 0) OR "
            "(result_state = 'OVERRIDDEN' AND result IN ('PASS', 'INCOMPLETE') AND prior_result IN ('PASS', 'INCOMPLETE') AND assessor_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND length(trim(override_reason)) > 0) OR "
            "(result_state = 'VOID' AND result IS NULL AND assessor_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND length(trim(system_reason)) > 0)",
            name="assessment_decision_state_shape",
        ),
    )
    op.create_table(
        "assessor_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assessment_decision_id", sa.String(length=36), nullable=False),
        sa.Column("assessor_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "action",
            _enum("assessor_review_action", "CONFIRM", "OVERRIDE", "VOID", "RETURN"),
            nullable=False,
        ),
        sa.Column(
            "prior_result",
            _enum("assessor_review_prior_result", "PASS", "INCOMPLETE"),
            nullable=True,
        ),
        sa.Column(
            "new_result", _enum("assessor_review_new_result", "PASS", "INCOMPLETE"), nullable=True
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_decision_id"], ["assessment_decisions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["assessor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("length(trim(reason)) > 0", name="assessor_review_reason"),
        sa.CheckConstraint(
            "(action = 'CONFIRM' AND prior_result IS NULL AND new_result IN ('PASS', 'INCOMPLETE')) OR "
            "(action = 'OVERRIDE' AND prior_result IN ('PASS', 'INCOMPLETE') "
            "AND new_result IN ('PASS', 'INCOMPLETE') AND prior_result != new_result) OR "
            "(action = 'VOID' AND prior_result IN ('PASS', 'INCOMPLETE') AND new_result IS NULL) OR "
            "(action = 'RETURN' AND prior_result IS NULL AND new_result IS NULL)",
            name="assessor_review_action_shape",
        ),
    )
    op.create_table(
        "reassessment_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("prior_assessment_attempt_id", sa.String(length=36), nullable=False),
        sa.Column("replacement_assessment_attempt_id", sa.String(length=36), nullable=False),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["prior_assessment_attempt_id"], ["assessment_attempts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["replacement_assessment_attempt_id"], ["assessment_attempts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "replacement_assessment_attempt_id", name="uq_reassessment_links_replacement"
        ),
        sa.CheckConstraint(
            "prior_assessment_attempt_id != replacement_assessment_attempt_id",
            name="reassessment_link_distinct_attempts",
        ),
        sa.CheckConstraint("length(trim(reason)) > 0", name="reassessment_link_reason"),
    )
    op.create_table(
        "appeals_or_corrections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assessment_attempt_id", sa.String(length=36), nullable=False),
        sa.Column("assessment_decision_id", sa.String(length=36), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("request_kind", sa.String(length=20), nullable=False),
        sa.Column("request_reason", sa.Text(), nullable=False),
        sa.Column(
            "state",
            _enum("appeal_or_correction_state", "PENDING", "RESOLVED", "WITHDRAWN"),
            nullable=False,
        ),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_attempt_id"], ["assessment_attempts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["assessment_decision_id"], ["assessment_decisions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("length(trim(request_reason)) > 0", name="appeal_or_correction_reason"),
        sa.CheckConstraint(
            "(state = 'PENDING' AND resolved_at IS NULL AND resolved_by_user_id IS NULL) OR (state IN ('RESOLVED', 'WITHDRAWN') AND resolved_at IS NOT NULL AND resolved_by_user_id IS NOT NULL)",
            name="appeal_or_correction_state_shape",
        ),
    )
    op.execute(
        "CREATE TRIGGER trg_submission_attempts_immutable_update BEFORE UPDATE ON submission_attempts BEGIN SELECT RAISE(ABORT, 'submission attempts are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_submission_attempts_immutable_delete BEFORE DELETE ON submission_attempts BEGIN SELECT RAISE(ABORT, 'submission attempts are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_assessment_attempts_scope_insert BEFORE INSERT ON assessment_attempts BEGIN "
        "SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM submission_attempts AS response "
        "JOIN assessment_definition_versions AS definition ON definition.id = NEW.assessment_definition_version_id "
        "JOIN task_form_versions AS form ON form.id = NEW.task_form_version_id "
        "JOIN bloom_target_versions AS bloom ON bloom.id = NEW.bloom_target_version_id "
        "JOIN pass_rule_versions AS rule ON rule.id = NEW.pass_rule_version_id "
        "WHERE response.id = NEW.response_version_id AND response.student_id = NEW.student_id "
        "AND response.task_id = NEW.task_id AND response.task_form_version_id = form.id "
        "AND definition.course_id = NEW.course_id AND form.course_id = NEW.course_id "
        "AND bloom.course_id = NEW.course_id AND rule.course_id = NEW.course_id "
        "AND form.learning_task_id = NEW.task_id "
        "AND form.assessment_definition_version_id = definition.id "
        "AND bloom.assessment_definition_version_id = definition.id "
        "AND rule.assessment_definition_version_id = definition.id) "
        "THEN RAISE(ABORT, 'invalid assessment attempt scope') END; END"
    )
    op.execute(
        "CREATE TRIGGER trg_assessment_attempts_scope_update BEFORE UPDATE OF course_id, student_id, task_id, response_version_id, assessment_definition_version_id, task_form_version_id, bloom_target_version_id, pass_rule_version_id ON assessment_attempts BEGIN "
        "SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM submission_attempts AS response "
        "JOIN assessment_definition_versions AS definition ON definition.id = NEW.assessment_definition_version_id "
        "JOIN task_form_versions AS form ON form.id = NEW.task_form_version_id "
        "JOIN bloom_target_versions AS bloom ON bloom.id = NEW.bloom_target_version_id "
        "JOIN pass_rule_versions AS rule ON rule.id = NEW.pass_rule_version_id "
        "WHERE response.id = NEW.response_version_id AND response.student_id = NEW.student_id "
        "AND response.task_id = NEW.task_id AND response.task_form_version_id = form.id "
        "AND definition.course_id = NEW.course_id AND form.course_id = NEW.course_id "
        "AND bloom.course_id = NEW.course_id AND rule.course_id = NEW.course_id "
        "AND form.learning_task_id = NEW.task_id "
        "AND form.assessment_definition_version_id = definition.id "
        "AND bloom.assessment_definition_version_id = definition.id "
        "AND rule.assessment_definition_version_id = definition.id) "
        "THEN RAISE(ABORT, 'invalid assessment attempt scope') END; END"
    )
    op.execute(
        "CREATE TRIGGER trg_assessment_decisions_faulted_attempt BEFORE INSERT ON assessment_decisions WHEN EXISTS (SELECT 1 FROM assessment_attempts WHERE id = NEW.assessment_attempt_id AND state IN ('FAULTED', 'VOID')) BEGIN SELECT RAISE(ABORT, 'faulted assessment attempt cannot receive a decision'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_assessment_attempts_lifecycle BEFORE UPDATE OF state ON assessment_attempts WHEN NOT ((OLD.state = 'PENDING' AND NEW.state IN ('EVALUATED', 'FAULTED', 'VOID')) OR (OLD.state = 'EVALUATED' AND NEW.state = 'VOID') OR (OLD.state = 'FAULTED' AND NEW.state = 'PENDING')) BEGIN SELECT RAISE(ABORT, 'invalid assessment attempt lifecycle'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_assessment_attempts_decided_fault BEFORE UPDATE OF state ON assessment_attempts WHEN NEW.state = 'FAULTED' AND EXISTS (SELECT 1 FROM assessment_decisions WHERE assessment_attempt_id = NEW.id) BEGIN SELECT RAISE(ABORT, 'decided assessment attempts cannot become faulted'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_assessment_attempts_void_decision BEFORE UPDATE OF state ON assessment_attempts WHEN NEW.state = 'VOID' AND EXISTS (SELECT 1 FROM assessment_decisions WHERE assessment_attempt_id = NEW.id AND result_state != 'VOID') BEGIN SELECT RAISE(ABORT, 'void assessment attempts require a void decision'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_criterion_evaluations_scope_insert BEFORE INSERT ON criterion_evaluations BEGIN "
        "SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM assessment_attempts AS attempt JOIN criterion_versions AS criterion ON criterion.id = NEW.criterion_version_id JOIN pass_rule_versions AS rule ON rule.id = attempt.pass_rule_version_id JOIN json_tree(rule.expression) AS leaf ON leaf.key = 'criterion_version_id' AND leaf.type = 'text' AND leaf.value = NEW.criterion_version_id WHERE attempt.id = NEW.assessment_attempt_id AND criterion.course_id = attempt.course_id AND criterion.assessment_definition_version_id = attempt.assessment_definition_version_id) THEN RAISE(ABORT, 'invalid criterion evaluation scope') END; END"
    )
    op.execute(
        "CREATE TRIGGER trg_criterion_evaluations_scope_update BEFORE UPDATE OF assessment_attempt_id, criterion_version_id ON criterion_evaluations BEGIN "
        "SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM assessment_attempts AS attempt JOIN criterion_versions AS criterion ON criterion.id = NEW.criterion_version_id JOIN pass_rule_versions AS rule ON rule.id = attempt.pass_rule_version_id JOIN json_tree(rule.expression) AS leaf ON leaf.key = 'criterion_version_id' AND leaf.type = 'text' AND leaf.value = NEW.criterion_version_id WHERE attempt.id = NEW.assessment_attempt_id AND criterion.course_id = attempt.course_id AND criterion.assessment_definition_version_id = attempt.assessment_definition_version_id) THEN RAISE(ABORT, 'invalid criterion evaluation scope') END; END"
    )
    op.execute(
        "CREATE TRIGGER trg_assessment_decisions_version_bundle_insert BEFORE INSERT ON assessment_decisions BEGIN "
        "SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM assessment_attempts WHERE id = NEW.assessment_attempt_id AND bloom_target_version_id = NEW.bloom_target_version_id AND pass_rule_version_id = NEW.pass_rule_version_id) THEN RAISE(ABORT, 'invalid assessment decision version bundle') END; END"
    )
    op.execute(
        "CREATE TRIGGER trg_assessment_decisions_version_bundle_update BEFORE UPDATE OF assessment_attempt_id, bloom_target_version_id, pass_rule_version_id ON assessment_decisions BEGIN "
        "SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM assessment_attempts WHERE id = NEW.assessment_attempt_id AND bloom_target_version_id = NEW.bloom_target_version_id AND pass_rule_version_id = NEW.pass_rule_version_id) THEN RAISE(ABORT, 'invalid assessment decision version bundle') END; END"
    )
    op.execute(
        "CREATE TRIGGER trg_assessment_decisions_lifecycle BEFORE UPDATE ON assessment_decisions WHEN NOT (((OLD.result_state = 'PROVISIONAL' AND NEW.result_state IN ('CONFIRMED', 'OVERRIDDEN', 'VOID')) OR (OLD.result_state = 'CONFIRMED' AND NEW.result_state IN ('OVERRIDDEN', 'VOID')) OR (OLD.result_state = 'OVERRIDDEN' AND NEW.result_state = 'VOID')) AND ((NEW.result_state = 'CONFIRMED' AND EXISTS (SELECT 1 FROM assessor_reviews WHERE assessment_decision_id = NEW.id AND action = 'CONFIRM' AND assessor_user_id = NEW.assessor_user_id AND reviewed_at = NEW.reviewed_at AND new_result = NEW.result)) OR (NEW.result_state = 'OVERRIDDEN' AND NEW.prior_result = OLD.result AND NEW.result != OLD.result AND EXISTS (SELECT 1 FROM assessor_reviews WHERE assessment_decision_id = NEW.id AND action = 'OVERRIDE' AND assessor_user_id = NEW.assessor_user_id AND reviewed_at = NEW.reviewed_at AND prior_result = OLD.result AND new_result = NEW.result AND reason = NEW.override_reason)) OR (NEW.result_state = 'VOID' AND EXISTS (SELECT 1 FROM assessor_reviews WHERE assessment_decision_id = NEW.id AND action = 'VOID' AND assessor_user_id = NEW.assessor_user_id AND reviewed_at = NEW.reviewed_at AND prior_result = OLD.result AND new_result IS NULL)))) BEGIN SELECT RAISE(ABORT, 'assessment decision transitions require a matching assessor review'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_assessment_attempts_immutable_anchors BEFORE UPDATE OF id, course_id, student_id, task_id, response_version_id, assessment_definition_version_id, task_form_version_id, bloom_target_version_id, pass_rule_version_id, created_at ON assessment_attempts WHEN NEW.id IS NOT OLD.id OR NEW.course_id IS NOT OLD.course_id OR NEW.student_id IS NOT OLD.student_id OR NEW.task_id IS NOT OLD.task_id OR NEW.response_version_id IS NOT OLD.response_version_id OR NEW.assessment_definition_version_id IS NOT OLD.assessment_definition_version_id OR NEW.task_form_version_id IS NOT OLD.task_form_version_id OR NEW.bloom_target_version_id IS NOT OLD.bloom_target_version_id OR NEW.pass_rule_version_id IS NOT OLD.pass_rule_version_id OR NEW.created_at IS NOT OLD.created_at BEGIN SELECT RAISE(ABORT, 'assessment attempt version anchors are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_assessment_decisions_immutable_anchors BEFORE UPDATE OF id, assessment_attempt_id, bloom_target_version_id, pass_rule_version_id, evaluation_idempotency_key, evidence_references, system_reason, created_at ON assessment_decisions WHEN NEW.id IS NOT OLD.id OR NEW.assessment_attempt_id IS NOT OLD.assessment_attempt_id OR NEW.bloom_target_version_id IS NOT OLD.bloom_target_version_id OR NEW.pass_rule_version_id IS NOT OLD.pass_rule_version_id OR NEW.evaluation_idempotency_key IS NOT OLD.evaluation_idempotency_key OR NEW.evidence_references IS NOT OLD.evidence_references OR NEW.system_reason IS NOT OLD.system_reason OR NEW.created_at IS NOT OLD.created_at BEGIN SELECT RAISE(ABORT, 'assessment decision evidence and anchors are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_assessment_decisions_immutable_delete BEFORE DELETE ON assessment_decisions BEGIN SELECT RAISE(ABORT, 'assessment records are append-only'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_assessment_attempts_immutable_delete BEFORE DELETE ON assessment_attempts BEGIN SELECT RAISE(ABORT, 'assessment records are append-only'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_appeals_or_corrections_immutable_delete BEFORE DELETE ON appeals_or_corrections BEGIN SELECT RAISE(ABORT, 'assessment records are append-only'); END"
    )
    for table in ("criterion_evaluations", "assessor_reviews", "reassessment_links"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'assessment records are append-only'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'assessment records are append-only'); END"
        )
    op.execute(
        "CREATE TRIGGER trg_reassessment_links_scope_insert BEFORE INSERT ON reassessment_links BEGIN SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM assessment_attempts AS prior JOIN assessment_attempts AS replacement ON replacement.id = NEW.replacement_assessment_attempt_id WHERE prior.id = NEW.prior_assessment_attempt_id AND prior.course_id = replacement.course_id AND prior.student_id = replacement.student_id AND prior.assessment_definition_version_id = replacement.assessment_definition_version_id AND prior.bloom_target_version_id = replacement.bloom_target_version_id AND prior.pass_rule_version_id = replacement.pass_rule_version_id) THEN RAISE(ABORT, 'invalid reassessment link scope') END; END"
    )
    op.execute(
        "CREATE TRIGGER trg_reassessment_links_scope_update BEFORE UPDATE OF prior_assessment_attempt_id, replacement_assessment_attempt_id ON reassessment_links BEGIN SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM assessment_attempts AS prior JOIN assessment_attempts AS replacement ON replacement.id = NEW.replacement_assessment_attempt_id WHERE prior.id = NEW.prior_assessment_attempt_id AND prior.course_id = replacement.course_id AND prior.student_id = replacement.student_id AND prior.assessment_definition_version_id = replacement.assessment_definition_version_id AND prior.bloom_target_version_id = replacement.bloom_target_version_id AND prior.pass_rule_version_id = replacement.pass_rule_version_id) THEN RAISE(ABORT, 'invalid reassessment link scope') END; END"
    )
    op.execute(
        "CREATE TRIGGER trg_appeals_or_corrections_scope_insert BEFORE INSERT ON appeals_or_corrections BEGIN SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM assessment_decisions WHERE id = NEW.assessment_decision_id AND assessment_attempt_id = NEW.assessment_attempt_id) THEN RAISE(ABORT, 'invalid appeal or correction scope') END; END"
    )
    op.execute(
        "CREATE TRIGGER trg_appeals_or_corrections_scope_update BEFORE UPDATE OF assessment_attempt_id, assessment_decision_id ON appeals_or_corrections BEGIN SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM assessment_decisions WHERE id = NEW.assessment_decision_id AND assessment_attempt_id = NEW.assessment_attempt_id) THEN RAISE(ABORT, 'invalid appeal or correction scope') END; END"
    )
    op.execute(
        "CREATE TRIGGER trg_appeals_or_corrections_lifecycle BEFORE UPDATE ON appeals_or_corrections WHEN NOT (OLD.state = 'PENDING' AND NEW.state IN ('RESOLVED', 'WITHDRAWN') AND NEW.assessment_attempt_id IS OLD.assessment_attempt_id AND NEW.assessment_decision_id IS OLD.assessment_decision_id AND NEW.requested_by_user_id IS OLD.requested_by_user_id AND NEW.request_kind IS OLD.request_kind AND NEW.request_reason IS OLD.request_reason AND NEW.created_at IS OLD.created_at) BEGIN SELECT RAISE(ABORT, 'invalid appeal or correction lifecycle'); END"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_appeals_or_corrections_lifecycle")
    op.execute("DROP TRIGGER IF EXISTS trg_appeals_or_corrections_scope_update")
    op.execute("DROP TRIGGER IF EXISTS trg_appeals_or_corrections_scope_insert")
    op.execute("DROP TRIGGER IF EXISTS trg_reassessment_links_scope_update")
    op.execute("DROP TRIGGER IF EXISTS trg_reassessment_links_scope_insert")
    for table in ("criterion_evaluations", "assessor_reviews", "reassessment_links"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable_delete")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable_update")
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_decisions_immutable_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_attempts_immutable_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_appeals_or_corrections_immutable_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_decisions_immutable_anchors")
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_attempts_immutable_anchors")
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_attempts_void_decision")
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_attempts_lifecycle")
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_decisions_version_bundle_update")
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_decisions_version_bundle_insert")
    op.execute("DROP TRIGGER IF EXISTS trg_criterion_evaluations_scope_update")
    op.execute("DROP TRIGGER IF EXISTS trg_criterion_evaluations_scope_insert")
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_attempts_decided_fault")
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_decisions_lifecycle")
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_decisions_faulted_attempt")
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_attempts_scope_update")
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_attempts_scope_insert")
    op.execute("DROP TRIGGER IF EXISTS trg_submission_attempts_immutable_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_submission_attempts_immutable_update")
    op.drop_table("appeals_or_corrections")
    op.drop_table("reassessment_links")
    op.drop_table("assessor_reviews")
    op.drop_table("assessment_decisions")
    op.drop_table("criterion_evaluations")
    op.drop_table("assessment_attempts")
    with op.batch_alter_table("submission_attempts") as batch:
        batch.drop_constraint("uq_submission_attempts_idempotency", type_="unique")
        batch.drop_constraint("submission_attempt_content_digest", type_="check")
        batch.drop_constraint("submission_attempt_legacy_score", type_="check")
        batch.drop_constraint(
            "fk_submission_attempts_task_form_version_id_task_form_versions", type_="foreignkey"
        )
        batch.drop_column("declared_conditions")
        batch.drop_column("idempotency_key")
        batch.drop_column("content_digest")
        batch.drop_column("response_schema_version")
        batch.drop_column("task_form_version_id")
        batch.alter_column("score", existing_type=sa.Integer(), nullable=False)
        batch.create_check_constraint("submission_attempt_score", "score BETWEEN 0 AND 100")
    with op.batch_alter_table("audit_events") as batch:
        batch.drop_constraint("audit_action", type_="check")
        batch.alter_column(
            "action",
            existing_type=sa.String(length=100),
            type_=_enum(
                "audit_action",
                "feedback_generation_started",
                "feedback_generation_completed",
                "feedback_judged",
                "feedback_regenerated",
                "feedback_fallback_used",
                "feedback_viewed",
                "feedback_reported",
                "research_export_created",
                "workflow_completed",
                "workflow_failed",
            ),
            existing_nullable=False,
        )
