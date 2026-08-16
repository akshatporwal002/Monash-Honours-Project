"""Add ordered assessor review actions.

Revision ID: 20260816_0021
Revises: 20260816_0020
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_0021"
down_revision: str | None = "20260816_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROTECTED_DOWNGRADE_TABLES = (
    "assessor_reviews",
    "learner_model_snapshots",
    "learner_outcome_estimates",
    "learner_model_evidence_links",
    "evidence_artifacts",
    "learning_evidence",
    "evidence_links",
    "assessment_legacy_history",
)


def _action_enum(*, withhold: bool) -> sa.Enum:
    actions = ["CONFIRM", "OVERRIDE", "VOID", "RETURN"]
    if withhold:
        actions.insert(2, "WITHHOLD")
    return sa.Enum(
        *actions,
        name="assessor_review_action",
        native_enum=False,
        create_constraint=True,
    )


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def _create_immutable_triggers() -> None:
    op.execute(
        "CREATE TRIGGER trg_assessor_reviews_immutable_update BEFORE UPDATE ON assessor_reviews "
        "BEGIN SELECT RAISE(ABORT, 'assessment records are append-only'); END"
    )
    op.execute(
        "CREATE TRIGGER trg_assessor_reviews_immutable_delete BEFORE DELETE ON assessor_reviews "
        "BEGIN SELECT RAISE(ABORT, 'assessment records are append-only'); END"
    )


def _drop_immutable_triggers() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_assessor_reviews_immutable_delete")
    op.execute("DROP TRIGGER IF EXISTS trg_assessor_reviews_immutable_update")


def _create_decision_anchor_trigger() -> None:
    op.execute(
        "CREATE TRIGGER trg_assessment_decisions_immutable_anchors BEFORE UPDATE OF id, "
        "assessment_attempt_id, bloom_target_version_id, pass_rule_version_id, "
        "evaluation_idempotency_key, evidence_references, system_reason, created_at ON "
        "assessment_decisions WHEN NEW.id IS NOT OLD.id OR NEW.assessment_attempt_id IS NOT "
        "OLD.assessment_attempt_id OR NEW.bloom_target_version_id IS NOT OLD.bloom_target_version_id "
        "OR NEW.pass_rule_version_id IS NOT OLD.pass_rule_version_id OR "
        "NEW.evaluation_idempotency_key IS NOT OLD.evaluation_idempotency_key OR "
        "NEW.evidence_references IS NOT OLD.evidence_references OR NEW.system_reason IS NOT "
        "OLD.system_reason OR NEW.created_at IS NOT OLD.created_at BEGIN SELECT RAISE(ABORT, "
        "'assessment decision evidence and anchors are immutable'); END"
    )


def _drop_decision_anchor_trigger() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_decisions_immutable_anchors")


def _create_decision_lifecycle_trigger() -> None:
    op.execute(
        "CREATE TRIGGER trg_assessment_decisions_lifecycle BEFORE UPDATE ON assessment_decisions "
        "WHEN NOT (((OLD.result_state = 'PROVISIONAL' AND NEW.result_state IN "
        "('CONFIRMED', 'OVERRIDDEN', 'VOID')) OR (OLD.result_state = 'CONFIRMED' "
        "AND NEW.result_state IN ('OVERRIDDEN', 'VOID')) OR (OLD.result_state = 'OVERRIDDEN' "
        "AND NEW.result_state = 'VOID')) AND ((NEW.result_state = 'CONFIRMED' AND EXISTS "
        "(SELECT 1 FROM assessor_reviews WHERE assessment_decision_id = NEW.id AND action = "
        "'CONFIRM' AND assessor_user_id = NEW.assessor_user_id AND reviewed_at = NEW.reviewed_at "
        "AND new_result = NEW.result)) OR (NEW.result_state = 'OVERRIDDEN' AND NEW.prior_result "
        "= OLD.result AND NEW.result != OLD.result AND EXISTS (SELECT 1 FROM assessor_reviews "
        "WHERE assessment_decision_id = NEW.id AND action = 'OVERRIDE' AND assessor_user_id = "
        "NEW.assessor_user_id AND reviewed_at = NEW.reviewed_at AND prior_result = OLD.result "
        "AND new_result = NEW.result AND reason = NEW.override_reason)) OR (NEW.result_state = "
        "'VOID' AND EXISTS (SELECT 1 FROM assessor_reviews WHERE assessment_decision_id = NEW.id "
        "AND action = 'VOID' AND assessor_user_id = NEW.assessor_user_id AND reviewed_at = "
        "NEW.reviewed_at AND prior_result = OLD.result AND new_result IS NULL)))) "
        "BEGIN SELECT RAISE(ABORT, 'assessment decision transitions require a matching assessor review'); END"
    )


def _drop_decision_lifecycle_trigger() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_assessment_decisions_lifecycle")


def upgrade() -> None:
    _drop_immutable_triggers()
    _drop_decision_lifecycle_trigger()
    _drop_decision_anchor_trigger()
    with op.batch_alter_table("assessor_reviews") as batch:
        batch.drop_constraint("assessor_review_action_shape", type_="check")
        batch.drop_constraint("assessor_review_action", type_="check")
        batch.add_column(sa.Column("review_revision", sa.Integer(), nullable=True))
        batch.alter_column(
            "action",
            existing_type=_action_enum(withhold=False),
            type_=_action_enum(withhold=True),
            existing_nullable=False,
        )
        batch.create_check_constraint(
            "assessor_review_action_shape",
            "(action = 'CONFIRM' AND prior_result IS NULL AND new_result IN ('PASS', 'INCOMPLETE')) OR "
            "(action = 'OVERRIDE' AND prior_result IN ('PASS', 'INCOMPLETE') "
            "AND new_result IN ('PASS', 'INCOMPLETE') AND prior_result != new_result) OR "
            "(action = 'WITHHOLD' AND prior_result IS NULL AND new_result IS NULL) OR "
            "(action = 'VOID' AND prior_result IN ('PASS', 'INCOMPLETE') AND new_result IS NULL) OR "
            "(action = 'RETURN' AND prior_result IS NULL AND new_result IS NULL)",
        )
        batch.create_check_constraint("assessor_review_revision", "review_revision > 0")

    op.execute(
        "UPDATE assessor_reviews AS current SET review_revision = ("
        "SELECT COUNT(*) FROM assessor_reviews AS earlier "
        "WHERE earlier.assessment_decision_id = current.assessment_decision_id "
        "AND (earlier.reviewed_at < current.reviewed_at "
        "OR (earlier.reviewed_at = current.reviewed_at AND earlier.id <= current.id))"
        ")"
    )
    with op.batch_alter_table("assessor_reviews") as batch:
        batch.alter_column("review_revision", existing_type=sa.Integer(), nullable=False)
        batch.create_unique_constraint(
            "uq_assessor_reviews_decision_revision",
            ["assessment_decision_id", "review_revision"],
        )
    _create_decision_lifecycle_trigger()
    _create_decision_anchor_trigger()
    _create_immutable_triggers()


def downgrade() -> None:
    connection = op.get_bind()
    for table in _PROTECTED_DOWNGRADE_TABLES:
        if (
            _has_table(table)
            and connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        ):
            raise RuntimeError(
                "cannot downgrade populated assessor review history or protected learner-model, "
                "evidence, or assessment history; restore the verified backup instead"
            )
    _drop_immutable_triggers()
    _drop_decision_lifecycle_trigger()
    _drop_decision_anchor_trigger()
    with op.batch_alter_table("assessor_reviews") as batch:
        batch.drop_constraint("uq_assessor_reviews_decision_revision", type_="unique")
        batch.drop_constraint("assessor_review_revision", type_="check")
        batch.drop_constraint("assessor_review_action_shape", type_="check")
        batch.drop_constraint("assessor_review_action", type_="check")
        batch.drop_column("review_revision")
        batch.alter_column(
            "action",
            existing_type=_action_enum(withhold=True),
            type_=_action_enum(withhold=False),
            existing_nullable=False,
        )
        batch.create_check_constraint(
            "assessor_review_action_shape",
            "(action = 'CONFIRM' AND prior_result IS NULL AND new_result IN ('PASS', 'INCOMPLETE')) OR "
            "(action = 'OVERRIDE' AND prior_result IN ('PASS', 'INCOMPLETE') "
            "AND new_result IN ('PASS', 'INCOMPLETE') AND prior_result != new_result) OR "
            "(action = 'VOID' AND prior_result IN ('PASS', 'INCOMPLETE') AND new_result IS NULL) OR "
            "(action = 'RETURN' AND prior_result IS NULL AND new_result IS NULL)",
        )
    _create_decision_lifecycle_trigger()
    _create_decision_anchor_trigger()
    _create_immutable_triggers()
