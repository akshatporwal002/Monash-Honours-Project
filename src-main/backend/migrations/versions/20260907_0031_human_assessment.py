"""Preserve human criterion decisions as append-only assessment history.

Revision ID: 20260907_0031
Revises: 20260907_0030
"""

from importlib import import_module

import sqlalchemy as sa
from alembic import op

revision = "20260907_0031"
down_revision = "20260907_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if not sa.inspect(connection).has_table("human_assessment_actions"):
        op.create_table(
            "human_assessment_actions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "assessment_attempt_id",
                sa.String(36),
                sa.ForeignKey("assessment_attempts.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "assessment_decision_id",
                sa.String(36),
                sa.ForeignKey("assessment_decisions.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "assessor_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("idempotency_key", sa.String(128), nullable=False),
            sa.Column("request_digest", sa.String(64), nullable=False),
            sa.Column("expected_token", sa.String(64), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column(
                "result",
                sa.Enum(
                    "PASS",
                    "INCOMPLETE",
                    name="human_action_result",
                    native_enum=False,
                    create_constraint=True,
                ),
                nullable=False,
            ),
            sa.Column("result_state", sa.String(20), nullable=False),
            sa.Column(
                "review_id",
                sa.String(36),
                sa.ForeignKey("assessor_reviews.id", ondelete="RESTRICT"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "assessment_attempt_id", "revision", name="uq_human_action_revision"
            ),
            sa.UniqueConstraint(
                "assessment_attempt_id", "idempotency_key", name="uq_human_action_key"
            ),
            sa.CheckConstraint("revision > 0", name="human_action_revision"),
            sa.CheckConstraint(
                "result_state IN ('CONFIRMED', 'OVERRIDDEN')", name="human_action_state"
            ),
            sa.CheckConstraint(
                "length(expected_token) = 64 AND length(request_digest) = 64 AND length(trim(idempotency_key)) > 0",
                name="human_action_receipt",
            ),
            sa.CheckConstraint("length(trim(reason)) > 0", name="human_action_reason"),
        )
    if not sa.inspect(connection).has_table("human_criterion_decisions"):
        op.create_table(
            "human_criterion_decisions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "action_id",
                sa.String(36),
                sa.ForeignKey("human_assessment_actions.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "criterion_version_id",
                sa.String(36),
                sa.ForeignKey("criterion_versions.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "decision",
                sa.Enum(
                    "MET",
                    "NOT_MET",
                    "NOT_EVALUABLE",
                    name="human_criterion_decision",
                    native_enum=False,
                    create_constraint=True,
                ),
                nullable=False,
            ),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("evidence_references", sa.JSON(), nullable=False),
            sa.Column("evaluator_reference", sa.String(255), nullable=False),
            sa.UniqueConstraint(
                "action_id", "criterion_version_id", name="uq_human_criterion_action"
            ),
            sa.CheckConstraint("length(trim(reason)) > 0", name="human_criterion_reason"),
        )
    if connection.dialect.name == "sqlite":
        for _, _, statement in human_review_guards():
            op.execute(sa.text(statement))


def downgrade() -> None:
    connection = op.get_bind()
    tables = ("human_criterion_decisions", "human_assessment_actions")
    for table in tables:
        if (
            sa.inspect(connection).has_table(table)
            and connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        ):
            raise RuntimeError(
                "Human assessment history is protected; restore a verified backup instead"
            )
    # Run the frozen predecessor's protected-history preflight before changing schema.
    import_module("migrations.versions.20260907_0030_learning_episodes")._preflight_downgrade()
    for table in tables:
        if sa.inspect(connection).has_table(table):
            op.drop_table(table)


# Frozen migration guards. Do not import live application models.
def human_review_guards() -> list[tuple[str, str, str]]:
    guards = []
    for table in ("human_assessment_actions", "human_criterion_decisions"):
        for operation in ("UPDATE", "DELETE"):
            name = f"{table}_no_{operation.lower()}"
            guards.append(
                (
                    table,
                    name,
                    f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'Human assessment history is append-only'); END",
                )
            )
        unique = (
            "assessment_attempt_id = NEW.assessment_attempt_id AND (revision = NEW.revision OR idempotency_key = NEW.idempotency_key)"
            if table == "human_assessment_actions"
            else "action_id = NEW.action_id AND criterion_version_id = NEW.criterion_version_id"
        )
        name = f"{table}_no_replace"
        guards.append(
            (
                table,
                name,
                f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE INSERT ON {table} WHEN EXISTS (SELECT 1 FROM {table} WHERE id = NEW.id OR ({unique})) BEGIN SELECT RAISE(ABORT, 'Human assessment history is append-only'); END",
            )
        )
    scope = """NOT EXISTS (
      SELECT 1 FROM assessment_attempts a JOIN assessment_decisions d ON d.assessment_attempt_id = a.id
      WHERE a.id = NEW.assessment_attempt_id AND d.id = NEW.assessment_decision_id
    ) OR NEW.revision != COALESCE((SELECT MAX(revision) + 1 FROM human_assessment_actions WHERE assessment_attempt_id = NEW.assessment_attempt_id), 1)"""
    guards.append(
        (
            "human_assessment_actions",
            "human_action_scope",
            f"CREATE TRIGGER IF NOT EXISTS human_action_scope BEFORE INSERT ON human_assessment_actions WHEN {scope} BEGIN SELECT RAISE(ABORT, 'Invalid human assessment action scope'); END",
        )
    )
    scope = """NOT EXISTS (
      SELECT 1 FROM human_assessment_actions h JOIN assessment_attempts a ON a.id = h.assessment_attempt_id
      JOIN criterion_versions c ON c.assessment_definition_version_id = a.assessment_definition_version_id AND c.course_id = a.course_id
      JOIN pass_rule_versions r ON r.id = a.pass_rule_version_id
      WHERE h.id = NEW.action_id AND c.id = NEW.criterion_version_id
      AND EXISTS (SELECT 1 FROM json_tree(r.expression) WHERE key = 'criterion_version_id' AND value = NEW.criterion_version_id)
      AND NEW.evaluator_reference = 'human:' || h.assessor_user_id || ':' || h.id
      AND json_array_length(NEW.evidence_references) > 0
    )"""
    guards.append(
        (
            "human_criterion_decisions",
            "human_criterion_scope",
            f"CREATE TRIGGER IF NOT EXISTS human_criterion_scope BEFORE INSERT ON human_criterion_decisions WHEN {scope} BEGIN SELECT RAISE(ABORT, 'Invalid human criterion scope'); END",
        )
    )
    return guards
