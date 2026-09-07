"""Append-only assessor criterion decisions and immutable action receipts."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DDL,
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.assessment import AssessmentResult, CriterionDecision
from app.models.assessment import enum_column
from app.models.persistence import new_uuid, utc_now


class HumanAssessmentAction(Base):
    __tablename__ = "human_assessment_actions"
    __table_args__ = (
        UniqueConstraint("assessment_attempt_id", "revision", name="uq_human_action_revision"),
        UniqueConstraint("assessment_attempt_id", "idempotency_key", name="uq_human_action_key"),
        CheckConstraint("revision > 0", name="human_action_revision"),
        CheckConstraint("result_state IN ('CONFIRMED', 'OVERRIDDEN')", name="human_action_state"),
        CheckConstraint(
            "length(expected_token) = 64 AND length(request_digest) = 64 AND length(trim(idempotency_key)) > 0",
            name="human_action_receipt",
        ),
        CheckConstraint("length(trim(reason)) > 0", name="human_action_reason"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    assessment_attempt_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_attempts.id", ondelete="RESTRICT")
    )
    assessment_decision_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_decisions.id", ondelete="RESTRICT")
    )
    assessor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    revision: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_digest: Mapped[str] = mapped_column(String(64))
    expected_token: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)
    result: Mapped[AssessmentResult] = mapped_column(
        enum_column(AssessmentResult, "human_action_result")
    )
    result_state: Mapped[str] = mapped_column(String(20))
    review_id: Mapped[str | None] = mapped_column(
        ForeignKey("assessor_reviews.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class HumanCriterionDecision(Base):
    __tablename__ = "human_criterion_decisions"
    __table_args__ = (
        UniqueConstraint("action_id", "criterion_version_id", name="uq_human_criterion_action"),
        CheckConstraint("length(trim(reason)) > 0", name="human_criterion_reason"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    action_id: Mapped[str] = mapped_column(
        ForeignKey("human_assessment_actions.id", ondelete="RESTRICT")
    )
    criterion_version_id: Mapped[str] = mapped_column(
        ForeignKey("criterion_versions.id", ondelete="RESTRICT")
    )
    decision: Mapped[CriterionDecision] = mapped_column(
        enum_column(CriterionDecision, "human_criterion_decision")
    )
    reason: Mapped[str] = mapped_column(Text)
    evidence_references: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    evaluator_reference: Mapped[str] = mapped_column(String(255))


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


def _immutable(*_: Any) -> None:
    raise ValueError("Human assessment history is append-only")


for _model in (HumanAssessmentAction, HumanCriterionDecision):
    event.listen(_model, "before_update", _immutable)
    event.listen(_model, "before_delete", _immutable)
    for _table, _name, _statement in human_review_guards():
        if _table == _model.__tablename__:
            event.listen(
                _model.__table__, "after_create", DDL(_statement).execute_if(dialect="sqlite")
            )
