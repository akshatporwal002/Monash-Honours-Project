"""Immutable, course-scoped assessment-definition records."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    inspect,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship, validates

from app.db.base import Base
from app.domain.assessment import (
    AppealOrCorrectionState,
    AssessmentAttemptState,
    AssessmentPurpose,
    AssessmentResult,
    AssessorReviewAction,
    BloomKnowledge,
    BloomProcess,
    CriterionDecision,
    ResultState,
)

if TYPE_CHECKING:
    from app.models.lms import LearningOutcome


def new_uuid() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


def enum_column(enum_type: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


class AssessmentApprovalState(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    RETIRED = "RETIRED"


class CriterionEvaluatorType(StrEnum):
    RULES = "rules"
    HUMAN = "human"
    VALIDATED_AI = "validated_ai"
    MIXED = "mixed"


class ImmutableAssessmentVersionError(RuntimeError):
    """Raised when application code changes a finalised assessment version."""


_APPROVAL_COLUMNS = {
    "approval_state",
    "approved_at",
    "approved_by_user_id",
    "retired_at",
    "retired_by_user_id",
    "retirement_reason",
}
_RETIREMENT_COLUMNS = {
    "approval_state",
    "retired_at",
    "retired_by_user_id",
    "retirement_reason",
}
_NUMERIC_RULE_FIELDS = {
    "grade",
    "grade_band",
    "mark",
    "marks",
    "percentage",
    "point",
    "points",
    "score",
    "weight",
    "weights",
}
_BOOLEAN_OPERATORS = {"ALL_OF", "ANY_OF", "NOT"}


def _approval_shape_constraint(name: str) -> CheckConstraint:
    return CheckConstraint(
        "(approval_state = 'DRAFT' AND approved_at IS NULL AND approved_by_user_id IS NULL "
        "AND retired_at IS NULL AND retired_by_user_id IS NULL AND retirement_reason IS NULL) OR "
        "(approval_state = 'APPROVED' AND approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL "
        "AND retired_at IS NULL AND retired_by_user_id IS NULL AND retirement_reason IS NULL) OR "
        "(approval_state = 'RETIRED' AND approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL "
        "AND retired_at IS NOT NULL AND retired_by_user_id IS NOT NULL "
        "AND length(trim(retirement_reason)) > 0)",
        name=name,
    )


class AssessmentVersionRecord:
    """Columns shared by every immutable assessment-definition version."""

    __abstract__ = True

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    approval_state: Mapped[AssessmentApprovalState] = mapped_column(
        enum_column(AssessmentApprovalState, "assessment_approval_state"),
        nullable=False,
        default=AssessmentApprovalState.DRAFT,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    retirement_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class AssessmentDefinition(Base):
    """Stable identity for all immutable versions of one assessed outcome."""

    __tablename__ = "assessment_definitions"
    __table_args__ = (
        UniqueConstraint(
            "course_id", "learning_outcome_id", name="uq_assessment_definitions_course_outcome"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    learning_outcome_id: Mapped[str] = mapped_column(
        ForeignKey("learning_outcomes.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    learning_outcome: Mapped["LearningOutcome"] = relationship(
        back_populates="assessment_definitions"
    )
    versions: Mapped[list[AssessmentDefinitionVersion]] = relationship(
        back_populates="assessment_definition",
        cascade="all, delete-orphan",
        order_by="AssessmentDefinitionVersion.version",
    )
    criteria: Mapped[list[Criterion]] = relationship(
        back_populates="assessment_definition", cascade="all, delete-orphan"
    )
    bloom_targets: Mapped[list[BloomTarget]] = relationship(
        back_populates="assessment_definition", cascade="all, delete-orphan"
    )
    pass_rules: Mapped[list[PassRule]] = relationship(
        back_populates="assessment_definition", cascade="all, delete-orphan"
    )
    task_forms: Mapped[list[TaskForm]] = relationship(
        back_populates="assessment_definition", cascade="all, delete-orphan"
    )


class OutcomeVersion(AssessmentVersionRecord, Base):
    __tablename__ = "outcome_versions"
    __table_args__ = (
        UniqueConstraint(
            "learning_outcome_id", "version", name="uq_outcome_versions_outcome_version"
        ),
        CheckConstraint("version > 0", name="outcome_version_positive"),
        _approval_shape_constraint("outcome_version_approval_shape"),
    )

    learning_outcome_id: Mapped[str] = mapped_column(
        ForeignKey("learning_outcomes.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    source_version: Mapped[str] = mapped_column(String(100), nullable=False)


class AssessmentDefinitionVersion(AssessmentVersionRecord, Base):
    __tablename__ = "assessment_definition_versions"
    __table_args__ = (
        UniqueConstraint(
            "assessment_definition_id",
            "version",
            name="uq_assessment_definition_versions_identity_version",
        ),
        CheckConstraint("version > 0", name="assessment_definition_version_positive"),
        CheckConstraint(
            "(formal_result_eligible IS NULL AND result_eligibility_declared_at IS NULL) OR "
            "(formal_result_eligible IS NOT NULL AND result_eligibility_declared_at IS NOT NULL)",
            name="assessment_definition_result_eligibility_shape",
        ),
        _approval_shape_constraint("assessment_definition_version_approval_shape"),
    )

    assessment_definition_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    outcome_version_id: Mapped[str] = mapped_column(
        ForeignKey("outcome_versions.id", ondelete="RESTRICT"), nullable=False
    )
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_evidence: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    contradicting_evidence: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    insufficient_evidence: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    task_conditions: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    next_action_contract: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    purpose: Mapped[AssessmentPurpose] = mapped_column(
        enum_column(AssessmentPurpose, "assessment_purpose"), nullable=False
    )
    permitted_tools: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    instructional_support: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    access_conditions: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    transfer_rule: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    evidence_sufficiency: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    formal_result_eligible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    result_eligibility_declared_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    assessment_definition: Mapped[AssessmentDefinition] = relationship(back_populates="versions")
    bloom_target_versions: Mapped[list[BloomTargetVersion]] = relationship(
        back_populates="assessment_definition_version", cascade="all, delete-orphan"
    )
    criterion_versions: Mapped[list[CriterionVersion]] = relationship(
        back_populates="assessment_definition_version", cascade="all, delete-orphan"
    )
    pass_rule_versions: Mapped[list[PassRuleVersion]] = relationship(
        back_populates="assessment_definition_version", cascade="all, delete-orphan"
    )
    task_form_versions: Mapped[list[TaskFormVersion]] = relationship(
        back_populates="assessment_definition_version", cascade="all, delete-orphan"
    )


class BloomTarget(Base):
    __tablename__ = "bloom_targets"
    __table_args__ = (
        UniqueConstraint("assessment_definition_id", name="uq_bloom_targets_definition"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    assessment_definition_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    assessment_definition: Mapped[AssessmentDefinition] = relationship(
        back_populates="bloom_targets"
    )


class BloomTargetVersion(AssessmentVersionRecord, Base):
    __tablename__ = "bloom_target_versions"
    __table_args__ = (
        UniqueConstraint(
            "bloom_target_id", "version", name="uq_bloom_target_versions_identity_version"
        ),
        CheckConstraint("version > 0", name="bloom_target_version_positive"),
        _approval_shape_constraint("bloom_target_version_approval_shape"),
    )

    bloom_target_id: Mapped[str] = mapped_column(
        ForeignKey("bloom_targets.id", ondelete="RESTRICT"), nullable=False
    )
    assessment_definition_version_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_definition_versions.id", ondelete="RESTRICT"), nullable=False
    )
    bloom_process: Mapped[BloomProcess] = mapped_column(
        enum_column(BloomProcess, "bloom_process"), nullable=False
    )
    knowledge_dimension: Mapped[BloomKnowledge] = mapped_column(
        enum_column(BloomKnowledge, "bloom_knowledge"), nullable=False
    )

    assessment_definition_version: Mapped[AssessmentDefinitionVersion] = relationship(
        back_populates="bloom_target_versions"
    )


class Criterion(Base):
    __tablename__ = "criteria"
    __table_args__ = (
        UniqueConstraint(
            "assessment_definition_id", "stable_key", name="uq_criteria_definition_key"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    assessment_definition_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    stable_key: Mapped[str] = mapped_column(String(100), nullable=False)
    assessment_definition: Mapped[AssessmentDefinition] = relationship(back_populates="criteria")
    versions: Mapped[list[CriterionVersion]] = relationship(
        back_populates="criterion",
        cascade="all, delete-orphan",
        order_by="CriterionVersion.version",
    )


class CriterionVersion(AssessmentVersionRecord, Base):
    __tablename__ = "criterion_versions"
    __table_args__ = (
        UniqueConstraint("criterion_id", "version", name="uq_criterion_versions_identity_version"),
        CheckConstraint("version > 0", name="criterion_version_positive"),
        _approval_shape_constraint("criterion_version_approval_shape"),
    )

    criterion_id: Mapped[str] = mapped_column(
        ForeignKey("criteria.id", ondelete="RESTRICT"), nullable=False
    )
    assessment_definition_version_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_definition_versions.id", ondelete="RESTRICT"), nullable=False
    )
    learner_description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_description: Mapped[str] = mapped_column(Text, nullable=False)
    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evidence_source_types: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    met_rule: Mapped[str] = mapped_column(Text, nullable=False)
    not_met_rule: Mapped[str] = mapped_column(Text, nullable=False)
    not_evaluable_rule: Mapped[str] = mapped_column(Text, nullable=False)
    approved_anchors: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    critical_error_rules: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    evaluator_type: Mapped[CriterionEvaluatorType] = mapped_column(
        enum_column(CriterionEvaluatorType, "criterion_evaluator_type"), nullable=False
    )

    criterion: Mapped[Criterion] = relationship(back_populates="versions")
    assessment_definition_version: Mapped[AssessmentDefinitionVersion] = relationship(
        back_populates="criterion_versions"
    )


class PassRule(Base):
    __tablename__ = "pass_rules"
    __table_args__ = (
        UniqueConstraint("assessment_definition_id", name="uq_pass_rules_definition"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    assessment_definition_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    assessment_definition: Mapped[AssessmentDefinition] = relationship(back_populates="pass_rules")
    versions: Mapped[list[PassRuleVersion]] = relationship(
        back_populates="pass_rule", cascade="all, delete-orphan", order_by="PassRuleVersion.version"
    )


def _validate_rule_value(value: Any) -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, int | float):
        raise ValueError("pass-rule expressions cannot contain numeric scoring values")
    if isinstance(value, list):
        for item in value:
            _validate_rule_value(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if key.casefold() in _NUMERIC_RULE_FIELDS:
                raise ValueError("pass-rule expressions cannot contain scores or weights")
            _validate_rule_value(item)
        return
    raise ValueError("pass-rule expressions must contain JSON values")


def validate_pass_rule_expression(value: Any) -> dict[str, Any]:
    """Validate the Boolean criterion expression persisted independently of prompts."""

    _validate_rule_value(value)
    if not isinstance(value, dict):
        raise ValueError("pass-rule expression must be an object")

    def validate_node(node: Any) -> None:
        if not isinstance(node, dict):
            raise ValueError("pass-rule clauses must be objects")
        if "criterion_version_id" in node:
            criterion_version_id = node["criterion_version_id"]
            if set(node) != {"criterion_version_id"}:
                raise ValueError("criterion clauses cannot contain unknown fields")
            if not isinstance(criterion_version_id, str) or not criterion_version_id.strip():
                raise ValueError("criterion clauses require a criterion_version_id")
            return
        operator = node.get("operator")
        if not isinstance(operator, str) or operator not in _BOOLEAN_OPERATORS:
            raise ValueError("pass-rule expression has an unknown Boolean operator")
        if set(node) != {"operator", "clauses"}:
            raise ValueError("pass-rule Boolean operators cannot contain unknown fields")
        clauses = node.get("clauses")
        if not isinstance(clauses, list) or not clauses:
            raise ValueError("Boolean operators require one or more clauses")
        if operator == "NOT" and len(clauses) != 1:
            raise ValueError("NOT requires exactly one clause")
        for clause in clauses:
            validate_node(clause)

    validate_node(value)
    return value


class PassRuleVersion(AssessmentVersionRecord, Base):
    __tablename__ = "pass_rule_versions"
    __table_args__ = (
        UniqueConstraint("pass_rule_id", "version", name="uq_pass_rule_versions_identity_version"),
        CheckConstraint("version > 0", name="pass_rule_version_positive"),
        _approval_shape_constraint("pass_rule_version_approval_shape"),
    )

    pass_rule_id: Mapped[str] = mapped_column(
        ForeignKey("pass_rules.id", ondelete="RESTRICT"), nullable=False
    )
    assessment_definition_version_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_definition_versions.id", ondelete="RESTRICT"), nullable=False
    )
    expression: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    pass_rule: Mapped[PassRule] = relationship(back_populates="versions")
    assessment_definition_version: Mapped[AssessmentDefinitionVersion] = relationship(
        back_populates="pass_rule_versions"
    )

    @validates("expression")
    def validate_expression(self, _key: str, value: Any) -> dict[str, Any]:
        return validate_pass_rule_expression(value)


class TaskForm(Base):
    __tablename__ = "task_forms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    assessment_definition_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    assessment_definition: Mapped[AssessmentDefinition] = relationship(back_populates="task_forms")
    versions: Mapped[list[TaskFormVersion]] = relationship(
        back_populates="task_form", cascade="all, delete-orphan", order_by="TaskFormVersion.version"
    )


class TaskFormVersion(AssessmentVersionRecord, Base):
    __tablename__ = "task_form_versions"
    __table_args__ = (
        UniqueConstraint("task_form_id", "version", name="uq_task_form_versions_identity_version"),
        CheckConstraint("version > 0", name="task_form_version_positive"),
        _approval_shape_constraint("task_form_version_approval_shape"),
    )

    task_form_id: Mapped[str] = mapped_column(
        ForeignKey("task_forms.id", ondelete="RESTRICT"), nullable=False
    )
    assessment_definition_version_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_definition_versions.id", ondelete="RESTRICT"), nullable=False
    )
    learning_task_id: Mapped[str] = mapped_column(
        ForeignKey("learning_tasks.id", ondelete="RESTRICT"), nullable=False
    )
    source_version: Mapped[str] = mapped_column(String(100), nullable=False)
    source_digest: Mapped[str] = mapped_column(String(100), nullable=False)
    task_family: Mapped[str] = mapped_column(String(100), nullable=False)
    context: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    constraints: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)

    task_form: Mapped[TaskForm] = relationship(back_populates="versions")
    assessment_definition_version: Mapped[AssessmentDefinitionVersion] = relationship(
        back_populates="task_form_versions"
    )
    approvals: Mapped[list[TaskApproval]] = relationship(
        back_populates="task_form_version", cascade="all, delete-orphan"
    )


class TaskApproval(Base):
    __tablename__ = "task_approvals"
    __table_args__ = (
        UniqueConstraint(
            "task_form_version_id", "approval_state", name="uq_task_approvals_form_state"
        ),
        CheckConstraint("length(trim(approval_reason)) > 0", name="task_approval_reason"),
        _approval_shape_constraint("task_approval_shape"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    assessment_definition_version_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_definition_versions.id", ondelete="RESTRICT"), nullable=False
    )
    task_form_version_id: Mapped[str] = mapped_column(
        ForeignKey("task_form_versions.id", ondelete="RESTRICT"), nullable=False
    )
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    approval_reason: Mapped[str] = mapped_column(Text, nullable=False)
    approval_state: Mapped[AssessmentApprovalState] = mapped_column(
        enum_column(AssessmentApprovalState, "assessment_approval_state"), nullable=False
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    retirement_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    task_form_version: Mapped[TaskFormVersion] = relationship(back_populates="approvals")


class AssessmentAttempt(Base):
    """One formal evaluation of an immutable learner response version."""

    __tablename__ = "assessment_attempts"
    __table_args__ = (
        UniqueConstraint("response_version_id", name="uq_assessment_attempts_response_version"),
        CheckConstraint(
            "(state IN ('PENDING', 'EVALUATED') AND fault_reason IS NULL) OR "
            "(state IN ('FAULTED', 'VOID') AND length(trim(fault_reason)) > 0)",
            name="assessment_attempt_state_shape",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    task_id: Mapped[str] = mapped_column(
        ForeignKey("learning_tasks.id", ondelete="RESTRICT"), nullable=False
    )
    response_version_id: Mapped[str] = mapped_column(
        ForeignKey("submission_attempts.id", ondelete="RESTRICT"), nullable=False
    )
    assessment_definition_version_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_definition_versions.id", ondelete="RESTRICT"), nullable=False
    )
    task_form_version_id: Mapped[str] = mapped_column(
        ForeignKey("task_form_versions.id", ondelete="RESTRICT"), nullable=False
    )
    bloom_target_version_id: Mapped[str] = mapped_column(
        ForeignKey("bloom_target_versions.id", ondelete="RESTRICT"), nullable=False
    )
    pass_rule_version_id: Mapped[str] = mapped_column(
        ForeignKey("pass_rule_versions.id", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[AssessmentAttemptState] = mapped_column(
        enum_column(AssessmentAttemptState, "assessment_attempt_state"),
        nullable=False,
        default=AssessmentAttemptState.PENDING,
    )
    fault_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    response_version: Mapped[Any] = relationship(
        "SubmissionAttempt", back_populates="assessment_attempt"
    )
    decisions: Mapped[list[AssessmentDecision]] = relationship(
        back_populates="assessment_attempt", cascade="all, delete-orphan"
    )


class AssessmentLegacyHistory(Base):
    """Read-only archive of pre-versioned assessment values.

    This record is not a formal assessment decision.  It retains source data
    while the compatibility path is available, and can only map an explicit
    public legacy FAIL value to INCOMPLETE.
    """

    __tablename__ = "assessment_legacy_history"
    __table_args__ = (
        UniqueConstraint(
            "source_table",
            "source_record_id",
            name="uq_assessment_legacy_history_source_record",
        ),
        CheckConstraint(
            "mapped_result IS NULL OR ("
            "source_table = 'legacy_learner_results' "
            "AND upper(trim(source_result)) = 'FAIL' "
            "AND mapped_result = 'INCOMPLETE' "
            "AND migration_reason = 'LEGACY_PUBLIC_FAIL_TO_INCOMPLETE'"
            ")",
            name="assessment_legacy_history_mapped_result",
        ),
        Index("ix_assessment_legacy_history_response", "response_version_id"),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    source_table: Mapped[str] = mapped_column(String(100), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    response_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("submission_attempts.id", ondelete="RESTRICT"), nullable=True
    )
    source_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_result: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mapped_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    migration_revision: Mapped[str] = mapped_column(String(32), nullable=False)
    migration_actor: Mapped[str] = mapped_column(String(255), nullable=False)
    migration_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CriterionEvaluation(Base):
    __tablename__ = "criterion_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "assessment_attempt_id",
            "criterion_version_id",
            name="uq_criterion_evaluations_attempt_criterion",
        ),
        CheckConstraint("length(trim(reason)) > 0", name="criterion_evaluation_reason"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    assessment_attempt_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_attempts.id", ondelete="RESTRICT"), nullable=False
    )
    criterion_version_id: Mapped[str] = mapped_column(
        ForeignKey("criterion_versions.id", ondelete="RESTRICT"), nullable=False
    )
    decision: Mapped[CriterionDecision] = mapped_column(
        enum_column(CriterionDecision, "criterion_decision"), nullable=False
    )
    evidence_references: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    evaluator_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retrieval_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class AssessmentDecision(Base):
    __tablename__ = "assessment_decisions"
    __table_args__ = (
        UniqueConstraint("assessment_attempt_id", name="uq_assessment_decisions_attempt"),
        UniqueConstraint("evaluation_idempotency_key", name="uq_assessment_decisions_idempotency"),
        CheckConstraint(
            "(result_state = 'PROVISIONAL' AND result IN ('PASS', 'INCOMPLETE') "
            "AND assessor_user_id IS NULL AND reviewed_at IS NULL AND prior_result IS NULL "
            "AND override_reason IS NULL AND length(trim(system_reason)) > 0) OR "
            "(result_state = 'CONFIRMED' AND result IN ('PASS', 'INCOMPLETE') "
            "AND assessor_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND prior_result IS NULL "
            "AND override_reason IS NULL AND length(trim(system_reason)) > 0) OR "
            "(result_state = 'OVERRIDDEN' AND result IN ('PASS', 'INCOMPLETE') "
            "AND prior_result IN ('PASS', 'INCOMPLETE') AND assessor_user_id IS NOT NULL "
            "AND reviewed_at IS NOT NULL AND length(trim(override_reason)) > 0) OR "
            "(result_state = 'VOID' AND result IS NULL AND assessor_user_id IS NOT NULL "
            "AND reviewed_at IS NOT NULL AND length(trim(system_reason)) > 0)",
            name="assessment_decision_state_shape",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    assessment_attempt_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_attempts.id", ondelete="RESTRICT"), nullable=False
    )
    bloom_target_version_id: Mapped[str] = mapped_column(
        ForeignKey("bloom_target_versions.id", ondelete="RESTRICT"), nullable=False
    )
    pass_rule_version_id: Mapped[str] = mapped_column(
        ForeignKey("pass_rule_versions.id", ondelete="RESTRICT"), nullable=False
    )
    evaluation_idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    result: Mapped[AssessmentResult | None] = mapped_column(
        enum_column(AssessmentResult, "assessment_result"), nullable=True
    )
    result_state: Mapped[ResultState] = mapped_column(
        enum_column(ResultState, "assessment_result_state"), nullable=False
    )
    evidence_references: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON, nullable=False)
    system_reason: Mapped[str] = mapped_column(Text, nullable=False)
    assessor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    prior_result: Mapped[AssessmentResult | None] = mapped_column(
        enum_column(AssessmentResult, "assessment_prior_result"), nullable=True
    )
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    assessment_attempt: Mapped[AssessmentAttempt] = relationship(back_populates="decisions")
    reviews: Mapped[list[AssessorReview]] = relationship(
        back_populates="assessment_decision", cascade="all, delete-orphan"
    )


class AssessorReview(Base):
    __tablename__ = "assessor_reviews"
    __table_args__ = (
        CheckConstraint("length(trim(reason)) > 0", name="assessor_review_reason"),
        CheckConstraint(
            "(action = 'CONFIRM' AND prior_result IS NULL AND new_result IN ('PASS', 'INCOMPLETE')) OR "
            "(action = 'OVERRIDE' AND prior_result IN ('PASS', 'INCOMPLETE') "
            "AND new_result IN ('PASS', 'INCOMPLETE') AND prior_result != new_result) OR "
            "(action = 'VOID' AND prior_result IN ('PASS', 'INCOMPLETE') AND new_result IS NULL) OR "
            "(action = 'RETURN' AND prior_result IS NULL AND new_result IS NULL)",
            name="assessor_review_action_shape",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    assessment_decision_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_decisions.id", ondelete="RESTRICT"), nullable=False
    )
    assessor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[AssessorReviewAction] = mapped_column(
        enum_column(AssessorReviewAction, "assessor_review_action"), nullable=False
    )
    prior_result: Mapped[AssessmentResult | None] = mapped_column(
        enum_column(AssessmentResult, "assessor_review_prior_result"), nullable=True
    )
    new_result: Mapped[AssessmentResult | None] = mapped_column(
        enum_column(AssessmentResult, "assessor_review_new_result"), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    assessment_decision: Mapped[AssessmentDecision] = relationship(back_populates="reviews")


class ReassessmentLink(Base):
    __tablename__ = "reassessment_links"
    __table_args__ = (
        UniqueConstraint(
            "replacement_assessment_attempt_id", name="uq_reassessment_links_replacement"
        ),
        CheckConstraint(
            "prior_assessment_attempt_id != replacement_assessment_attempt_id",
            name="reassessment_link_distinct_attempts",
        ),
        CheckConstraint("length(trim(reason)) > 0", name="reassessment_link_reason"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    prior_assessment_attempt_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_attempts.id", ondelete="RESTRICT"), nullable=False
    )
    replacement_assessment_attempt_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_attempts.id", ondelete="RESTRICT"), nullable=False
    )
    approved_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class AppealOrCorrection(Base):
    __tablename__ = "appeals_or_corrections"
    __table_args__ = (
        CheckConstraint("length(trim(request_reason)) > 0", name="appeal_or_correction_reason"),
        CheckConstraint(
            "(state = 'PENDING' AND resolved_at IS NULL AND resolved_by_user_id IS NULL) OR "
            "(state IN ('RESOLVED', 'WITHDRAWN') AND resolved_at IS NOT NULL AND resolved_by_user_id IS NOT NULL)",
            name="appeal_or_correction_state_shape",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    assessment_attempt_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_attempts.id", ondelete="RESTRICT"), nullable=False
    )
    assessment_decision_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_decisions.id", ondelete="RESTRICT"), nullable=False
    )
    requested_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    request_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    request_reason: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[AppealOrCorrectionState] = mapped_column(
        enum_column(AppealOrCorrectionState, "appeal_or_correction_state"),
        nullable=False,
        default=AppealOrCorrectionState.PENDING,
    )
    resolved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


def _prevent_finalised_version_mutation(
    _mapper: object,
    connection: Any,
    target: Any,
) -> None:
    state = inspect(target)
    if state.attrs.id.history.has_changes():
        raise ImmutableAssessmentVersionError("assessment version row identifiers are immutable")
    if state.attrs.version.history.has_changes():
        raise ImmutableAssessmentVersionError("assessment version numbers are immutable")
    identity_column = _VERSION_IDENTITY_COLUMNS[type(target)]
    if state.attrs[identity_column].history.has_changes():
        raise ImmutableAssessmentVersionError("assessment version identities are immutable")
    prior_state = AssessmentApprovalState(
        connection.execute(
            select(target.__table__.c.approval_state).where(target.__table__.c.id == target.id)
        ).scalar_one()
    )
    changed_columns = {
        attribute.key for attribute in state.attrs if attribute.history.has_changes()
    }
    if prior_state is AssessmentApprovalState.RETIRED:
        raise ImmutableAssessmentVersionError(
            "approved and retired assessment versions are immutable"
        )
    if prior_state is AssessmentApprovalState.APPROVED:
        if (
            target.approval_state is not AssessmentApprovalState.RETIRED
            or not changed_columns <= _RETIREMENT_COLUMNS
        ):
            raise ImmutableAssessmentVersionError(
                "approved assessment versions are immutable except for retirement"
            )
        return
    if target.approval_state is AssessmentApprovalState.APPROVED:
        if not changed_columns <= _APPROVAL_COLUMNS:
            raise ImmutableAssessmentVersionError(
                "approval cannot change assessment version content"
            )
    elif target.approval_state is AssessmentApprovalState.RETIRED:
        raise ImmutableAssessmentVersionError(
            "assessment versions must be approved before retirement"
        )


def _prevent_approval_mutation(_mapper: object, _connection: object, _target: Any) -> None:
    raise ImmutableAssessmentVersionError("task approval records are immutable")


def _validate_assessment_decision_transition(
    _mapper: object,
    connection: Any,
    target: AssessmentDecision,
) -> None:
    prior_state = ResultState(
        connection.execute(
            select(AssessmentDecision.result_state).where(AssessmentDecision.id == target.id)
        ).scalar_one()
    )
    allowed = {
        ResultState.PROVISIONAL: {ResultState.CONFIRMED, ResultState.OVERRIDDEN, ResultState.VOID},
        ResultState.CONFIRMED: {ResultState.OVERRIDDEN, ResultState.VOID},
        ResultState.OVERRIDDEN: {ResultState.VOID},
    }
    if target.result_state not in allowed.get(prior_state, set()):
        raise ImmutableAssessmentVersionError("assessment decision lifecycle transition is invalid")


def _prevent_faulted_attempt_decision(
    _mapper: object,
    connection: Any,
    target: AssessmentDecision,
) -> None:
    state = AssessmentAttemptState(
        connection.execute(
            select(AssessmentAttempt.state).where(
                AssessmentAttempt.id == target.assessment_attempt_id
            )
        ).scalar_one()
    )
    if state in {AssessmentAttemptState.FAULTED, AssessmentAttemptState.VOID}:
        raise ImmutableAssessmentVersionError(
            "faulted assessment attempts cannot receive decisions"
        )


def _validate_assessment_attempt_transition(
    _mapper: object,
    connection: Any,
    target: AssessmentAttempt,
) -> None:
    prior_state = AssessmentAttemptState(
        connection.execute(
            select(AssessmentAttempt.state).where(AssessmentAttempt.id == target.id)
        ).scalar_one()
    )
    if target.state is prior_state:
        return
    allowed = {
        AssessmentAttemptState.PENDING: {
            AssessmentAttemptState.EVALUATED,
            AssessmentAttemptState.FAULTED,
            AssessmentAttemptState.VOID,
        },
        AssessmentAttemptState.EVALUATED: {AssessmentAttemptState.VOID},
        AssessmentAttemptState.FAULTED: {AssessmentAttemptState.PENDING},
    }
    if target.state not in allowed.get(prior_state, set()):
        raise ImmutableAssessmentVersionError("assessment attempt lifecycle transition is invalid")
    decision_state = connection.execute(
        select(AssessmentDecision.result_state).where(
            AssessmentDecision.assessment_attempt_id == target.id
        )
    ).scalar_one_or_none()
    if target.state is AssessmentAttemptState.FAULTED and decision_state is not None:
        raise ImmutableAssessmentVersionError("decided assessment attempts cannot become faulted")
    if target.state is AssessmentAttemptState.VOID and decision_state not in {
        None,
        ResultState.VOID,
        ResultState.VOID.value,
    }:
        raise ImmutableAssessmentVersionError("void assessment attempts require a void decision")


_ASSESSMENT_ATTEMPT_VERSION_COLUMNS = frozenset(
    {
        "id",
        "course_id",
        "student_id",
        "task_id",
        "response_version_id",
        "assessment_definition_version_id",
        "task_form_version_id",
        "bloom_target_version_id",
        "pass_rule_version_id",
        "created_at",
    }
)


def _prevent_assessment_attempt_version_mutation(
    _mapper: object,
    _connection: object,
    target: AssessmentAttempt,
) -> None:
    changed_columns = {
        column
        for column in _ASSESSMENT_ATTEMPT_VERSION_COLUMNS
        if inspect(target).attrs[column].history.has_changes()
    }
    if changed_columns:
        raise ImmutableAssessmentVersionError("assessment attempt version anchors are immutable")


_ASSESSMENT_DECISION_IMMUTABLE_COLUMNS = frozenset(
    {
        "id",
        "assessment_attempt_id",
        "bloom_target_version_id",
        "pass_rule_version_id",
        "evaluation_idempotency_key",
        "evidence_references",
        "system_reason",
        "created_at",
    }
)


def _prevent_assessment_decision_anchor_mutation(
    _mapper: object,
    _connection: object,
    target: AssessmentDecision,
) -> None:
    changed_columns = {
        column
        for column in _ASSESSMENT_DECISION_IMMUTABLE_COLUMNS
        if inspect(target).attrs[column].history.has_changes()
    }
    if changed_columns:
        raise ImmutableAssessmentVersionError(
            "assessment decision evidence and anchors are immutable"
        )


def _validate_appeal_transition(
    _mapper: object,
    connection: Any,
    target: AppealOrCorrection,
) -> None:
    prior_state = AppealOrCorrectionState(
        connection.execute(
            select(AppealOrCorrection.state).where(AppealOrCorrection.id == target.id)
        ).scalar_one()
    )
    if (
        target.state
        not in {
            AppealOrCorrectionState.RESOLVED,
            AppealOrCorrectionState.WITHDRAWN,
        }
        or prior_state is not AppealOrCorrectionState.PENDING
    ):
        raise ImmutableAssessmentVersionError(
            "appeal or correction lifecycle transition is invalid"
        )
    immutable_columns = {
        "assessment_attempt_id",
        "assessment_decision_id",
        "requested_by_user_id",
        "request_kind",
        "request_reason",
        "created_at",
    }
    if any(inspect(target).attrs[column].history.has_changes() for column in immutable_columns):
        raise ImmutableAssessmentVersionError("appeal or correction request details are immutable")


def _prevent_assessment_record_mutation(_mapper: object, _connection: object, _target: Any) -> None:
    raise ImmutableAssessmentVersionError("assessment records are append-only")


def _prevent_legacy_history_insert(_mapper: object, _connection: object, _target: Any) -> None:
    raise ImmutableAssessmentVersionError("assessment legacy history is migration-only")


for _version_model in (
    OutcomeVersion,
    AssessmentDefinitionVersion,
    BloomTargetVersion,
    CriterionVersion,
    PassRuleVersion,
    TaskFormVersion,
):
    event.listen(_version_model, "before_update", _prevent_finalised_version_mutation)
    event.listen(_version_model, "before_delete", _prevent_finalised_version_mutation)


_VERSION_IDENTITY_COLUMNS = {
    OutcomeVersion: "learning_outcome_id",
    AssessmentDefinitionVersion: "assessment_definition_id",
    BloomTargetVersion: "bloom_target_id",
    CriterionVersion: "criterion_id",
    PassRuleVersion: "pass_rule_id",
    TaskFormVersion: "task_form_id",
}


def _criterion_version_ids(expression: dict[str, Any]) -> set[str]:
    if "criterion_version_id" in expression:
        return {expression["criterion_version_id"]}
    return {
        criterion_id
        for clause in expression["clauses"]
        for criterion_id in _criterion_version_ids(clause)
    }


def _criterion_version_is_referenced(connection: Any, criterion_version_id: str) -> bool:
    return any(
        criterion_version_id in _criterion_version_ids(expression)
        for expression in connection.execute(select(PassRuleVersion.expression)).scalars()
    )


def _prevent_referenced_criterion_version_mutation(
    _mapper: object,
    connection: Any,
    target: CriterionVersion,
) -> None:
    state = inspect(target)
    if not (
        state.attrs.course_id.history.has_changes()
        or state.attrs.assessment_definition_version_id.history.has_changes()
    ):
        return
    if _criterion_version_is_referenced(connection, target.id):
        raise ImmutableAssessmentVersionError(
            "referenced criterion versions cannot change course or definition version"
        )


def _prevent_referenced_criterion_version_delete(
    _mapper: object,
    connection: Any,
    target: CriterionVersion,
) -> None:
    if _criterion_version_is_referenced(connection, target.id):
        raise ImmutableAssessmentVersionError("referenced criterion versions cannot be deleted")


@event.listens_for(Session, "before_flush")
def _validate_pass_rule_criterion_scope(session: Session, *_: object) -> None:
    for rule_version in session.new.union(session.dirty):
        if not isinstance(rule_version, PassRuleVersion):
            continue
        criterion_ids = _criterion_version_ids(rule_version.expression)
        criteria = {
            criterion.id: criterion
            for criterion in session.scalars(
                select(CriterionVersion).where(CriterionVersion.id.in_(criterion_ids))
            )
        }
        criteria.update(
            {
                criterion.id: criterion
                for criterion in session.new
                if isinstance(criterion, CriterionVersion)
                and criterion.id is not None
                and criterion.id in criterion_ids
            }
        )
        if criteria.keys() != criterion_ids or any(
            criterion.course_id != rule_version.course_id
            or criterion.assessment_definition_version_id
            != rule_version.assessment_definition_version_id
            for criterion in criteria.values()
        ):
            raise ValueError(
                "pass-rule criterion versions must belong to the same course and definition version"
            )

    from app.models.lms import SubmissionAttempt

    pending = {item.id: item for item in session.new if getattr(item, "id", None) is not None}
    for attempt in session.new.union(session.dirty):
        if not isinstance(attempt, AssessmentAttempt):
            continue
        response = pending.get(attempt.response_version_id) or session.get(
            SubmissionAttempt, attempt.response_version_id
        )
        definition = pending.get(attempt.assessment_definition_version_id) or session.get(
            AssessmentDefinitionVersion, attempt.assessment_definition_version_id
        )
        form = pending.get(attempt.task_form_version_id) or session.get(
            TaskFormVersion, attempt.task_form_version_id
        )
        bloom = pending.get(attempt.bloom_target_version_id) or session.get(
            BloomTargetVersion, attempt.bloom_target_version_id
        )
        rule = pending.get(attempt.pass_rule_version_id) or session.get(
            PassRuleVersion, attempt.pass_rule_version_id
        )
        if (
            not isinstance(response, SubmissionAttempt)
            or not isinstance(definition, AssessmentDefinitionVersion)
            or not isinstance(form, TaskFormVersion)
            or not isinstance(bloom, BloomTargetVersion)
            or not isinstance(rule, PassRuleVersion)
            or response.student_id != attempt.student_id
            or response.task_id != attempt.task_id
            or response.task_form_version_id != attempt.task_form_version_id
            or any(
                version.course_id != attempt.course_id
                or version.assessment_definition_version_id != definition.id
                for version in (form, bloom, rule)
            )
        ):
            raise ValueError(
                "assessment attempts must reference one exact course-scoped version bundle"
            )

    for evaluation in session.new.union(session.dirty):
        if not isinstance(evaluation, CriterionEvaluation):
            continue
        attempt = pending.get(evaluation.assessment_attempt_id) or session.get(
            AssessmentAttempt, evaluation.assessment_attempt_id
        )
        criterion = pending.get(evaluation.criterion_version_id) or session.get(
            CriterionVersion, evaluation.criterion_version_id
        )
        rule = (
            pending.get(attempt.pass_rule_version_id)
            if isinstance(attempt, AssessmentAttempt)
            else None
        )
        rule = rule or (
            session.get(PassRuleVersion, attempt.pass_rule_version_id)
            if isinstance(attempt, AssessmentAttempt)
            else None
        )
        if (
            not isinstance(attempt, AssessmentAttempt)
            or not isinstance(criterion, CriterionVersion)
            or not isinstance(rule, PassRuleVersion)
            or criterion.course_id != attempt.course_id
            or criterion.assessment_definition_version_id
            != attempt.assessment_definition_version_id
            or evaluation.criterion_version_id not in _criterion_version_ids(rule.expression)
        ):
            raise ValueError(
                "criterion evaluations must use the assessment attempt frozen pass rule"
            )

    for decision in session.new.union(session.dirty):
        if not isinstance(decision, AssessmentDecision):
            continue
        attempt = pending.get(decision.assessment_attempt_id) or session.get(
            AssessmentAttempt, decision.assessment_attempt_id
        )
        if (
            not isinstance(attempt, AssessmentAttempt)
            or decision.bloom_target_version_id != attempt.bloom_target_version_id
            or decision.pass_rule_version_id != attempt.pass_rule_version_id
        ):
            raise ValueError("assessment decisions must use the assessment attempt version bundle")

    for decision in session.dirty:
        if not isinstance(decision, AssessmentDecision):
            continue
        state_history = inspect(decision).attrs.result_state.history
        if not state_history.has_changes():
            continue
        prior_state = (
            state_history.deleted[0]
            if state_history.deleted
            else session.execute(
                select(AssessmentDecision.result_state).where(AssessmentDecision.id == decision.id)
            ).scalar_one()
        )
        prior_state = ResultState(prior_state)
        result_history = inspect(decision).attrs.result.history
        prior_result = (
            result_history.deleted[0]
            if result_history.deleted
            else session.execute(
                select(AssessmentDecision.result).where(AssessmentDecision.id == decision.id)
            ).scalar_one()
        )
        prior_result = AssessmentResult(prior_result) if prior_result is not None else None
        expected_action = {
            ResultState.CONFIRMED: AssessorReviewAction.CONFIRM,
            ResultState.OVERRIDDEN: AssessorReviewAction.OVERRIDE,
            ResultState.VOID: AssessorReviewAction.VOID,
        }.get(decision.result_state)
        matching_review = next(
            (
                review
                for review in session.new
                if isinstance(review, AssessorReview)
                and review.assessment_decision_id == decision.id
                and review.action is expected_action
                and review.assessor_user_id == decision.assessor_user_id
                and review.reviewed_at == decision.reviewed_at
                and review.new_result == decision.result
                and (
                    expected_action is not AssessorReviewAction.OVERRIDE
                    or (
                        review.prior_result == prior_result
                        and decision.prior_result == prior_result
                        and decision.result != prior_result
                        and review.reason == decision.override_reason
                    )
                )
                and (
                    expected_action is not AssessorReviewAction.VOID
                    or review.prior_result == prior_result
                )
            ),
            None,
        )
        if prior_state is ResultState.PROVISIONAL and expected_action is None:
            continue
        if matching_review is None:
            raise ValueError("assessment decision transitions require a matching assessor review")

    for reassessment in session.new.union(session.dirty):
        if not isinstance(reassessment, ReassessmentLink):
            continue
        prior_attempt = pending.get(reassessment.prior_assessment_attempt_id) or session.get(
            AssessmentAttempt, reassessment.prior_assessment_attempt_id
        )
        replacement_attempt = pending.get(
            reassessment.replacement_assessment_attempt_id
        ) or session.get(AssessmentAttempt, reassessment.replacement_assessment_attempt_id)
        if (
            not isinstance(prior_attempt, AssessmentAttempt)
            or not isinstance(replacement_attempt, AssessmentAttempt)
            or (
                prior_attempt.course_id,
                prior_attempt.student_id,
                prior_attempt.assessment_definition_version_id,
                prior_attempt.bloom_target_version_id,
                prior_attempt.pass_rule_version_id,
            )
            != (
                replacement_attempt.course_id,
                replacement_attempt.student_id,
                replacement_attempt.assessment_definition_version_id,
                replacement_attempt.bloom_target_version_id,
                replacement_attempt.pass_rule_version_id,
            )
        ):
            raise ValueError("reassessment links must connect one learner under one standard")

    for appeal in session.new.union(session.dirty):
        if not isinstance(appeal, AppealOrCorrection):
            continue
        decision = pending.get(appeal.assessment_decision_id) or session.get(
            AssessmentDecision, appeal.assessment_decision_id
        )
        if (
            not isinstance(decision, AssessmentDecision)
            or decision.assessment_attempt_id != appeal.assessment_attempt_id
        ):
            raise ValueError(
                "appeals and corrections must reference the decision's assessment attempt"
            )


event.listen(TaskApproval, "before_update", _prevent_approval_mutation)
event.listen(TaskApproval, "before_delete", _prevent_approval_mutation)
event.listen(CriterionVersion, "before_update", _prevent_referenced_criterion_version_mutation)
event.listen(CriterionVersion, "before_delete", _prevent_referenced_criterion_version_delete)
event.listen(AssessmentDecision, "before_update", _validate_assessment_decision_transition)
event.listen(AssessmentDecision, "before_update", _prevent_assessment_decision_anchor_mutation)
event.listen(AssessmentDecision, "before_insert", _prevent_faulted_attempt_decision)
event.listen(AssessmentDecision, "before_delete", _prevent_assessment_record_mutation)
event.listen(AssessmentAttempt, "before_update", _validate_assessment_attempt_transition)
event.listen(AssessmentAttempt, "before_update", _prevent_assessment_attempt_version_mutation)
event.listen(AssessmentAttempt, "before_delete", _prevent_assessment_record_mutation)
event.listen(AppealOrCorrection, "before_update", _validate_appeal_transition)
event.listen(AppealOrCorrection, "before_delete", _prevent_assessment_record_mutation)
event.listen(AssessmentLegacyHistory, "before_insert", _prevent_legacy_history_insert)
for _append_only_model in (
    AssessmentLegacyHistory,
    CriterionEvaluation,
    AssessorReview,
    ReassessmentLink,
):
    event.listen(_append_only_model, "before_update", _prevent_assessment_record_mutation)
    event.listen(_append_only_model, "before_delete", _prevent_assessment_record_mutation)


__all__ = [
    "AssessmentApprovalState",
    "AssessmentAttempt",
    "AssessmentDefinition",
    "AssessmentDefinitionVersion",
    "AssessmentLegacyHistory",
    "BloomTarget",
    "BloomTargetVersion",
    "CriterionEvaluation",
    "Criterion",
    "CriterionEvaluatorType",
    "CriterionVersion",
    "ImmutableAssessmentVersionError",
    "OutcomeVersion",
    "PassRule",
    "PassRuleVersion",
    "AppealOrCorrection",
    "AssessmentDecision",
    "AssessorReview",
    "ReassessmentLink",
    "TaskApproval",
    "TaskForm",
    "TaskFormVersion",
    "validate_pass_rule_expression",
]
