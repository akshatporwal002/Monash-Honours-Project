"""Create immutable assessment-definition storage.

Revision ID: 20260815_0016
Revises: 20260815_0015
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0016"
down_revision: str | None = "20260815_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPROVAL = sa.Enum(
    "DRAFT",
    "APPROVED",
    "RETIRED",
    name="assessment_approval_state",
    native_enum=False,
    create_constraint=True,
)
PURPOSE = sa.Enum(
    "DIAGNOSTIC",
    "FORMATIVE",
    "AS_LEARNING",
    "SUMMATIVE",
    "RESEARCH",
    name="assessment_purpose",
    native_enum=False,
    create_constraint=True,
)
BLOOM_PROCESS = sa.Enum(
    "REMEMBER",
    "UNDERSTAND",
    "APPLY",
    "ANALYSE",
    "EVALUATE",
    "CREATE",
    name="bloom_process",
    native_enum=False,
    create_constraint=True,
)
BLOOM_KNOWLEDGE = sa.Enum(
    "FACTUAL",
    "CONCEPTUAL",
    "PROCEDURAL",
    "METACOGNITIVE",
    name="bloom_knowledge",
    native_enum=False,
    create_constraint=True,
)
EVALUATOR_TYPE = sa.Enum(
    "rules",
    "human",
    "validated_ai",
    "mixed",
    name="criterion_evaluator_type",
    native_enum=False,
    create_constraint=True,
)


def _approval_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approval_state", APPROVAL, nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_by_user_id", sa.Integer(), nullable=True),
        sa.Column("retirement_reason", sa.Text(), nullable=True),
    ]


def _approval_foreign_keys() -> list[sa.ForeignKeyConstraint]:
    return [
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["retired_by_user_id"], ["users.id"], ondelete="RESTRICT"),
    ]


def _approval_shape(name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "(approval_state = 'DRAFT' AND approved_at IS NULL AND approved_by_user_id IS NULL "
        "AND retired_at IS NULL AND retired_by_user_id IS NULL AND retirement_reason IS NULL) OR "
        "(approval_state = 'APPROVED' AND approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL "
        "AND retired_at IS NULL AND retired_by_user_id IS NULL AND retirement_reason IS NULL) OR "
        "(approval_state = 'RETIRED' AND approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL "
        "AND retired_at IS NOT NULL AND retired_by_user_id IS NOT NULL "
        "AND length(trim(retirement_reason)) > 0)",
        name=name,
    )


def _version_table(
    name: str,
    identity_column: str,
    identity_table: str,
    extra_columns: list[sa.Column[object]],
    constraints: list[object],
) -> None:
    unique_name = (
        "uq_outcome_versions_outcome_version"
        if name == "outcome_versions"
        else f"uq_{name}_identity_version"
    )
    op.create_table(
        name,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column(identity_column, sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_approval_columns(),
        *extra_columns,
        sa.ForeignKeyConstraint([identity_column], [f"{identity_table}.id"], ondelete="RESTRICT"),
        *_approval_foreign_keys(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(identity_column, "version", name=unique_name),
        sa.CheckConstraint("version > 0", name=f"{name[:-1]}_positive"),
        _approval_shape(f"{name[:-1]}_approval_shape"),
        *constraints,
    )


def _trigger(name: str, event: str, table: str, check: str) -> None:
    op.execute(f"CREATE TRIGGER {name} BEFORE {event} ON {table} BEGIN {check} END")


def _scope_check(query: str, message: str) -> str:
    return f"SELECT CASE WHEN NOT EXISTS ({query}) THEN RAISE(ABORT, '{message}') END;"


def _version_check(identity_column: str, table: str) -> str:
    return (
        "SELECT CASE WHEN NEW.version != COALESCE("
        f"(SELECT MAX(version) + 1 FROM {table} WHERE {identity_column} = NEW.{identity_column}), 1) "
        f"THEN RAISE(ABORT, 'invalid {table} version order') END;"
    )


def _immutable_update_check(identity_column: str, columns: tuple[str, ...]) -> str:
    unchanged = " AND ".join(f"NEW.{column} IS OLD.{column}" for column in columns)
    approved_unchanged = (
        f"{unchanged} AND NEW.approved_at IS OLD.approved_at "
        "AND NEW.approved_by_user_id IS OLD.approved_by_user_id"
    )
    return (
        f"SELECT CASE WHEN NEW.id IS NOT OLD.id OR NEW.version IS NOT OLD.version OR NEW.{identity_column} IS NOT OLD.{identity_column} "
        "OR OLD.approval_state = 'RETIRED' "
        "OR (OLD.approval_state = 'DRAFT' AND NEW.approval_state IN ('APPROVED', 'RETIRED') "
        f"AND NOT ({unchanged})) "
        "OR (OLD.approval_state = 'DRAFT' AND NEW.approval_state = 'RETIRED') "
        "OR (OLD.approval_state = 'APPROVED' AND "
        "(NEW.approval_state != 'RETIRED' OR NOT ("
        f"{approved_unchanged}))) "
        "THEN RAISE(ABORT, 'approved assessment version is immutable') END;"
    )


def _pass_rule_expression_check() -> str:
    return """
    SELECT CASE WHEN
        json_valid(NEW.expression) = 0
        OR json_type(NEW.expression) != 'object'
        OR EXISTS (
            SELECT 1 FROM json_tree(NEW.expression)
            WHERE typeof(key) = 'text'
              AND key NOT IN ('operator', 'clauses', 'criterion_version_id')
        )
        OR EXISTS (
            SELECT 1 FROM json_tree(NEW.expression)
            WHERE key = 'operator'
              AND (type != 'text' OR value NOT IN ('ALL_OF', 'ANY_OF', 'NOT'))
        )
        OR EXISTS (
            SELECT 1 FROM json_tree(NEW.expression) AS operator
            WHERE operator.key = 'operator'
              AND NOT EXISTS (
                  SELECT 1 FROM json_tree(NEW.expression) AS clauses
                  WHERE clauses.parent = operator.parent
                    AND clauses.key = 'clauses'
                    AND clauses.type = 'array'
              )
        )
        OR EXISTS (
            SELECT 1 FROM json_tree(NEW.expression) AS operator
            WHERE operator.key = 'operator'
              AND (
                  (SELECT COUNT(*) FROM json_tree(NEW.expression) AS sibling
                   WHERE sibling.parent = operator.parent AND sibling.key = 'operator') != 1
                  OR (SELECT COUNT(*) FROM json_tree(NEW.expression) AS sibling
                      WHERE sibling.parent = operator.parent AND sibling.key = 'clauses') != 1
                  OR (SELECT COUNT(*) FROM json_tree(NEW.expression) AS sibling
                      WHERE sibling.parent = operator.parent) != 2
              )
        )
        OR EXISTS (
            SELECT 1 FROM json_tree(NEW.expression) AS clauses
            WHERE clauses.key = 'clauses'
              AND NOT EXISTS (
                  SELECT 1 FROM json_tree(NEW.expression) AS operator
                  WHERE operator.parent = clauses.parent AND operator.key = 'operator'
              )
        )
        OR EXISTS (
            SELECT 1 FROM json_tree(NEW.expression) AS clauses
            WHERE clauses.key = 'clauses'
              AND json_array_length(NEW.expression, clauses.fullkey) = 0
        )
        OR EXISTS (
            SELECT 1 FROM json_tree(NEW.expression) AS clauses
            WHERE clauses.key = 'clauses'
              AND EXISTS (
                  SELECT 1 FROM json_each(NEW.expression, clauses.fullkey) AS clause
                  WHERE clause.type != 'object'
              )
        )
        OR EXISTS (
            SELECT 1 FROM json_tree(NEW.expression) AS node
            WHERE node.type = 'object'
              AND NOT EXISTS (
                  SELECT 1 FROM json_tree(NEW.expression) AS child
                  WHERE child.parent = node.id
                    AND child.key IN ('operator', 'criterion_version_id')
              )
        )
        OR EXISTS (
            SELECT 1 FROM json_tree(NEW.expression) AS operator
            WHERE operator.key = 'operator' AND operator.value = 'NOT'
              AND json_array_length(
                  NEW.expression,
                  replace(operator.fullkey, '.operator', '.clauses')
              ) != 1
        )
        OR NOT EXISTS (
            SELECT 1 FROM json_tree(NEW.expression)
            WHERE key = 'criterion_version_id' AND type = 'text'
        )
        OR EXISTS (
            SELECT 1 FROM json_tree(NEW.expression) AS leaf
            WHERE leaf.key = 'criterion_version_id'
              AND (
                  leaf.type != 'text'
                  OR EXISTS (
                      SELECT 1 FROM json_tree(NEW.expression) AS sibling
                      WHERE sibling.parent = leaf.parent AND sibling.id != leaf.id
                  )
                  OR NOT EXISTS (
                      SELECT 1 FROM criterion_versions AS criterion
                      WHERE criterion.id = leaf.value
                        AND criterion.course_id = NEW.course_id
                        AND criterion.assessment_definition_version_id = NEW.assessment_definition_version_id
                  )
              )
        )
    THEN RAISE(ABORT, 'invalid pass rule expression') END;
    """


def _referenced_criterion_version_check() -> str:
    return """
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM pass_rule_versions AS rule
        JOIN json_tree(rule.expression) AS leaf
          ON leaf.key = 'criterion_version_id'
        WHERE leaf.type = 'text' AND leaf.value = OLD.id
    ) THEN RAISE(ABORT, 'referenced criterion version cannot change or be deleted') END;
    """


def upgrade() -> None:
    op.create_table(
        "assessment_definitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("learning_outcome_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["learning_outcome_id"], ["learning_outcomes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_id", "learning_outcome_id", name="uq_assessment_definitions_course_outcome"
        ),
    )
    _version_table(
        "outcome_versions",
        "learning_outcome_id",
        "learning_outcomes",
        [
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("statement", sa.Text(), nullable=False),
            sa.Column("source_version", sa.String(length=100), nullable=False),
        ],
        [],
    )
    _version_table(
        "assessment_definition_versions",
        "assessment_definition_id",
        "assessment_definitions",
        [
            sa.Column("outcome_version_id", sa.String(length=36), nullable=False),
            sa.Column("claim", sa.Text(), nullable=False),
            sa.Column("supporting_evidence", sa.JSON(), nullable=False),
            sa.Column("contradicting_evidence", sa.JSON(), nullable=False),
            sa.Column("insufficient_evidence", sa.JSON(), nullable=False),
            sa.Column("task_conditions", sa.JSON(), nullable=False),
            sa.Column("next_action_contract", sa.JSON(), nullable=False),
            sa.Column("purpose", PURPOSE, nullable=False),
            sa.Column("permitted_tools", sa.JSON(), nullable=False),
            sa.Column("instructional_support", sa.JSON(), nullable=False),
            sa.Column("access_conditions", sa.JSON(), nullable=False),
            sa.Column("transfer_rule", sa.JSON(), nullable=False),
            sa.Column("evidence_sufficiency", sa.JSON(), nullable=False),
            sa.Column("formal_result_eligible", sa.Boolean(), nullable=True),
            sa.Column("result_eligibility_declared_at", sa.DateTime(timezone=True), nullable=True),
        ],
        [
            sa.ForeignKeyConstraint(
                ["outcome_version_id"], ["outcome_versions.id"], ondelete="RESTRICT"
            ),
            sa.CheckConstraint(
                "(formal_result_eligible IS NULL AND result_eligibility_declared_at IS NULL) OR (formal_result_eligible IS NOT NULL AND result_eligibility_declared_at IS NOT NULL)",
                name="assessment_definition_result_eligibility_shape",
            ),
        ],
    )
    op.create_table(
        "bloom_targets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assessment_definition_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_definition_id"], ["assessment_definitions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_definition_id", name="uq_bloom_targets_definition"),
    )
    _version_table(
        "bloom_target_versions",
        "bloom_target_id",
        "bloom_targets",
        [
            sa.Column("assessment_definition_version_id", sa.String(length=36), nullable=False),
            sa.Column("bloom_process", BLOOM_PROCESS, nullable=False),
            sa.Column("knowledge_dimension", BLOOM_KNOWLEDGE, nullable=False),
        ],
        [
            sa.ForeignKeyConstraint(
                ["assessment_definition_version_id"],
                ["assessment_definition_versions.id"],
                ondelete="RESTRICT",
            )
        ],
    )
    op.create_table(
        "criteria",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assessment_definition_id", sa.String(length=36), nullable=False),
        sa.Column("stable_key", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_definition_id"], ["assessment_definitions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assessment_definition_id", "stable_key", name="uq_criteria_definition_key"
        ),
    )
    _version_table(
        "criterion_versions",
        "criterion_id",
        "criteria",
        [
            sa.Column("assessment_definition_version_id", sa.String(length=36), nullable=False),
            sa.Column("learner_description", sa.Text(), nullable=False),
            sa.Column("evidence_description", sa.Text(), nullable=False),
            sa.Column("mandatory", sa.Boolean(), nullable=False),
            sa.Column("evidence_source_types", sa.JSON(), nullable=False),
            sa.Column("met_rule", sa.Text(), nullable=False),
            sa.Column("not_met_rule", sa.Text(), nullable=False),
            sa.Column("not_evaluable_rule", sa.Text(), nullable=False),
            sa.Column("approved_anchors", sa.JSON(), nullable=False),
            sa.Column("critical_error_rules", sa.JSON(), nullable=False),
            sa.Column("evaluator_type", EVALUATOR_TYPE, nullable=False),
        ],
        [
            sa.ForeignKeyConstraint(
                ["assessment_definition_version_id"],
                ["assessment_definition_versions.id"],
                ondelete="RESTRICT",
            )
        ],
    )
    op.create_table(
        "pass_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assessment_definition_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_definition_id"], ["assessment_definitions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_definition_id", name="uq_pass_rules_definition"),
    )
    _version_table(
        "pass_rule_versions",
        "pass_rule_id",
        "pass_rules",
        [
            sa.Column("assessment_definition_version_id", sa.String(length=36), nullable=False),
            sa.Column("expression", sa.JSON(), nullable=False),
        ],
        [
            sa.ForeignKeyConstraint(
                ["assessment_definition_version_id"],
                ["assessment_definition_versions.id"],
                ondelete="RESTRICT",
            )
        ],
    )
    op.create_table(
        "task_forms",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("assessment_definition_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_definition_id"], ["assessment_definitions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    _version_table(
        "task_form_versions",
        "task_form_id",
        "task_forms",
        [
            sa.Column("assessment_definition_version_id", sa.String(length=36), nullable=False),
            sa.Column("learning_task_id", sa.String(length=36), nullable=False),
            sa.Column("source_version", sa.String(length=100), nullable=False),
            sa.Column("source_digest", sa.String(length=100), nullable=False),
            sa.Column("task_family", sa.String(length=100), nullable=False),
            sa.Column("context", sa.JSON(), nullable=False),
            sa.Column("constraints", sa.JSON(), nullable=False),
        ],
        [
            sa.ForeignKeyConstraint(
                ["assessment_definition_version_id"],
                ["assessment_definition_versions.id"],
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["learning_task_id"], ["learning_tasks.id"], ondelete="RESTRICT"
            ),
        ],
    )
    op.create_table(
        "task_approvals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("assessment_definition_version_id", sa.String(length=36), nullable=False),
        sa.Column("task_form_version_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("approval_reason", sa.Text(), nullable=False),
        sa.Column("approval_state", APPROVAL, nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_by_user_id", sa.Integer(), nullable=True),
        sa.Column("retirement_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["assessment_definition_version_id"],
            ["assessment_definition_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_form_version_id"], ["task_form_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["retired_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_form_version_id", "approval_state", name="uq_task_approvals_form_state"
        ),
        sa.CheckConstraint("length(trim(approval_reason)) > 0", name="task_approval_reason"),
        _approval_shape("task_approval_shape"),
    )

    checks = {
        "assessment_definitions": _scope_check(
            "SELECT 1 FROM learning_outcomes AS outcome JOIN course_modules AS module ON module.id = outcome.module_id WHERE outcome.id = NEW.learning_outcome_id AND module.course_id = NEW.course_id",
            "invalid assessment definition scope",
        ),
        "outcome_versions": _scope_check(
            "SELECT 1 FROM learning_outcomes AS outcome JOIN course_modules AS module ON module.id = outcome.module_id WHERE outcome.id = NEW.learning_outcome_id AND module.course_id = NEW.course_id",
            "invalid outcome version scope",
        ),
        "assessment_definition_versions": _scope_check(
            "SELECT 1 FROM assessment_definitions AS definition JOIN outcome_versions AS outcome ON outcome.id = NEW.outcome_version_id WHERE definition.id = NEW.assessment_definition_id AND definition.course_id = NEW.course_id AND outcome.course_id = NEW.course_id AND definition.learning_outcome_id = outcome.learning_outcome_id",
            "invalid assessment definition version scope",
        ),
        "bloom_target_versions": _scope_check(
            "SELECT 1 FROM bloom_targets AS target JOIN assessment_definitions AS definition ON definition.id = target.assessment_definition_id JOIN assessment_definition_versions AS version ON version.id = NEW.assessment_definition_version_id WHERE target.id = NEW.bloom_target_id AND definition.id = version.assessment_definition_id AND definition.course_id = NEW.course_id AND version.course_id = NEW.course_id",
            "invalid bloom target version scope",
        ),
        "criterion_versions": _scope_check(
            "SELECT 1 FROM criteria AS criterion JOIN assessment_definitions AS definition ON definition.id = criterion.assessment_definition_id JOIN assessment_definition_versions AS version ON version.id = NEW.assessment_definition_version_id WHERE criterion.id = NEW.criterion_id AND definition.id = version.assessment_definition_id AND definition.course_id = NEW.course_id AND version.course_id = NEW.course_id",
            "invalid criterion version scope",
        ),
        "pass_rule_versions": _scope_check(
            "SELECT 1 FROM pass_rules AS rule JOIN assessment_definitions AS definition ON definition.id = rule.assessment_definition_id JOIN assessment_definition_versions AS version ON version.id = NEW.assessment_definition_version_id WHERE rule.id = NEW.pass_rule_id AND definition.id = version.assessment_definition_id AND definition.course_id = NEW.course_id AND version.course_id = NEW.course_id",
            "invalid pass rule version scope",
        ),
        "task_form_versions": _scope_check(
            "SELECT 1 FROM task_forms AS form JOIN assessment_definitions AS definition ON definition.id = form.assessment_definition_id JOIN assessment_definition_versions AS version ON version.id = NEW.assessment_definition_version_id JOIN learning_tasks AS task ON task.id = NEW.learning_task_id WHERE form.id = NEW.task_form_id AND definition.id = version.assessment_definition_id AND definition.course_id = NEW.course_id AND version.course_id = NEW.course_id AND task.course_id = NEW.course_id",
            "invalid task form version scope",
        ),
        "task_approvals": _scope_check(
            "SELECT 1 FROM task_form_versions AS form JOIN assessment_definition_versions AS version ON version.id = NEW.assessment_definition_version_id WHERE form.id = NEW.task_form_version_id AND form.assessment_definition_version_id = version.id AND form.course_id = NEW.course_id AND version.course_id = NEW.course_id",
            "invalid task approval scope",
        ),
    }
    for table, check in checks.items():
        _trigger(f"trg_{table}_scope_insert", "INSERT", table, check)
        _trigger(f"trg_{table}_scope_update", "UPDATE", table, check)
    _trigger(
        "trg_pass_rule_versions_expression_insert",
        "INSERT",
        "pass_rule_versions",
        _pass_rule_expression_check(),
    )
    _trigger(
        "trg_pass_rule_versions_expression_update",
        "UPDATE OF expression, course_id, assessment_definition_version_id",
        "pass_rule_versions",
        _pass_rule_expression_check(),
    )
    _trigger(
        "trg_criterion_versions_referenced_update",
        "UPDATE OF course_id, assessment_definition_version_id",
        "criterion_versions",
        _referenced_criterion_version_check(),
    )
    _trigger(
        "trg_criterion_versions_referenced_delete",
        "DELETE",
        "criterion_versions",
        _referenced_criterion_version_check(),
    )
    for table, (identity, columns) in {
        "outcome_versions": (
            "learning_outcome_id",
            (
                "id",
                "course_id",
                "learning_outcome_id",
                "version",
                "owner_user_id",
                "created_by_user_id",
                "created_at",
                "title",
                "statement",
                "source_version",
            ),
        ),
        "assessment_definition_versions": (
            "assessment_definition_id",
            (
                "id",
                "course_id",
                "assessment_definition_id",
                "outcome_version_id",
                "version",
                "owner_user_id",
                "created_by_user_id",
                "created_at",
                "claim",
                "supporting_evidence",
                "contradicting_evidence",
                "insufficient_evidence",
                "task_conditions",
                "next_action_contract",
                "purpose",
                "permitted_tools",
                "instructional_support",
                "access_conditions",
                "transfer_rule",
                "evidence_sufficiency",
                "formal_result_eligible",
                "result_eligibility_declared_at",
            ),
        ),
        "bloom_target_versions": (
            "bloom_target_id",
            (
                "id",
                "course_id",
                "bloom_target_id",
                "assessment_definition_version_id",
                "version",
                "owner_user_id",
                "created_by_user_id",
                "created_at",
                "bloom_process",
                "knowledge_dimension",
            ),
        ),
        "criterion_versions": (
            "criterion_id",
            (
                "id",
                "course_id",
                "criterion_id",
                "assessment_definition_version_id",
                "version",
                "owner_user_id",
                "created_by_user_id",
                "created_at",
                "learner_description",
                "evidence_description",
                "mandatory",
                "evidence_source_types",
                "met_rule",
                "not_met_rule",
                "not_evaluable_rule",
                "approved_anchors",
                "critical_error_rules",
                "evaluator_type",
            ),
        ),
        "pass_rule_versions": (
            "pass_rule_id",
            (
                "id",
                "course_id",
                "pass_rule_id",
                "assessment_definition_version_id",
                "version",
                "owner_user_id",
                "created_by_user_id",
                "created_at",
                "expression",
            ),
        ),
        "task_form_versions": (
            "task_form_id",
            (
                "id",
                "course_id",
                "task_form_id",
                "assessment_definition_version_id",
                "learning_task_id",
                "version",
                "owner_user_id",
                "created_by_user_id",
                "created_at",
                "source_version",
                "source_digest",
                "task_family",
                "context",
                "constraints",
            ),
        ),
    }.items():
        _trigger(f"trg_{table}_version_insert", "INSERT", table, _version_check(identity, table))
        _trigger(
            f"trg_{table}_version_update",
            "UPDATE OF version",
            table,
            _version_check(identity, table),
        )
        _trigger(
            f"trg_{table}_immutable_update",
            "UPDATE",
            table,
            _immutable_update_check(identity, columns),
        )
        _trigger(
            f"trg_{table}_immutable_delete",
            "DELETE",
            table,
            "SELECT CASE WHEN OLD.approval_state IN ('APPROVED', 'RETIRED') "
            "THEN RAISE(ABORT, 'approved assessment version is immutable') END;",
        )
    _trigger(
        "trg_task_approvals_immutable_update",
        "UPDATE",
        "task_approvals",
        "SELECT RAISE(ABORT, 'task approval is immutable');",
    )
    _trigger(
        "trg_task_approvals_immutable_delete",
        "DELETE",
        "task_approvals",
        "SELECT RAISE(ABORT, 'task approval is immutable');",
    )


def downgrade() -> None:
    for table in (
        "task_approvals",
        "task_form_versions",
        "pass_rule_versions",
        "criterion_versions",
        "bloom_target_versions",
        "assessment_definition_versions",
        "outcome_versions",
    ):
        for suffix in (
            "scope_update",
            "scope_insert",
            "version_insert",
            "version_update",
            "immutable_update",
            "immutable_delete",
        ):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_{suffix}")
    op.execute("DROP TRIGGER IF EXISTS trg_pass_rule_versions_expression_insert")
    op.execute("DROP TRIGGER IF EXISTS trg_pass_rule_versions_expression_update")
    op.execute("DROP TRIGGER IF EXISTS trg_criterion_versions_referenced_update")
    op.execute("DROP TRIGGER IF EXISTS trg_criterion_versions_referenced_delete")
    for trigger in (
        "trg_assessment_definitions_scope_update",
        "trg_assessment_definitions_scope_insert",
        "trg_task_approvals_immutable_update",
        "trg_task_approvals_immutable_delete",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    for table in (
        "task_approvals",
        "task_form_versions",
        "task_forms",
        "pass_rule_versions",
        "pass_rules",
        "criterion_versions",
        "criteria",
        "bloom_target_versions",
        "bloom_targets",
        "assessment_definition_versions",
        "outcome_versions",
        "assessment_definitions",
    ):
        op.drop_table(table)
