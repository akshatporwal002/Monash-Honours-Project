"""Versioned assessment-definition drafting and approval."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.assessment import AssessmentPurpose, BloomKnowledge, BloomProcess
from app.models.assessment import (
    AssessmentApprovalState,
    AssessmentDefinition,
    AssessmentDefinitionVersion,
    BloomTarget,
    BloomTargetVersion,
    Criterion,
    CriterionEvaluatorType,
    CriterionVersion,
    OutcomeVersion,
    PassRule,
    PassRuleVersion,
    TaskApproval,
    TaskForm,
    TaskFormVersion,
)
from app.models.lms import PlatformAuditEvent
from app.models.persistence import LearningTask
from app.services.assessment.alignment import (
    AssessmentAlignmentError,
    validate_definition_alignment,
)
from app.services.assessment.repository import (
    AssessmentDefinitionNotFoundError,
    AssessmentDefinitionRepository,
)


class AssessmentDefinitionError(Exception):
    """Base error for definition drafting and approval."""


class AssessmentDefinitionValidationError(AssessmentDefinitionError):
    """The proposed definition is incomplete or misaligned."""


class AssessmentDefinitionConflictError(AssessmentDefinitionError):
    """A stale draft or approval race occurred.  Map this to HTTP 409."""

    status_code = 409


@dataclass(frozen=True)
class CriterionDraft:
    stable_key: str
    learner_description: str
    evidence_description: str
    mandatory: bool
    evidence_source_types: list[str]
    met_rule: str
    not_met_rule: str
    not_evaluable_rule: str
    approved_anchors: dict[str, Any] | list[Any]
    critical_error_rules: dict[str, Any] | list[Any]
    evaluator_type: CriterionEvaluatorType = CriterionEvaluatorType.RULES


@dataclass(frozen=True)
class TaskFormDraft:
    learning_task_id: str
    source_version: str
    source_digest: str
    task_family: str
    context: dict[str, Any] | list[Any]
    constraints: dict[str, Any] | list[Any]


@dataclass(frozen=True)
class AssessmentDefinitionDraft:
    outcome_version_id: str
    claim: str
    supporting_evidence: dict[str, Any] | list[Any]
    contradicting_evidence: dict[str, Any] | list[Any]
    insufficient_evidence: dict[str, Any] | list[Any]
    task_conditions: dict[str, Any] | list[Any]
    next_action_contract: dict[str, Any] | list[Any]
    purpose: AssessmentPurpose
    permitted_tools: dict[str, Any] | list[Any]
    instructional_support: dict[str, Any] | list[Any]
    access_conditions: dict[str, Any] | list[Any]
    transfer_rule: dict[str, Any] | list[Any]
    evidence_sufficiency: dict[str, Any] | list[Any]
    bloom_process: BloomProcess
    knowledge_dimension: BloomKnowledge
    criteria: list[CriterionDraft]
    pass_rule_expression: dict[str, Any]
    task_forms: list[TaskFormDraft]


class AssessmentDefinitionService:
    """Persist complete versions and approve one immutable definition at a time."""

    def __init__(
        self,
        session: Session,
        *,
        correlation_id: str | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.session = session
        self.repository = AssessmentDefinitionRepository(session)
        self.correlation_id = correlation_id or str(uuid4())
        self._now = now or (lambda: datetime.now(UTC))

    def create_draft(
        self,
        *,
        course_id: str,
        learning_outcome_id: str,
        actor_user_id: int,
        draft: AssessmentDefinitionDraft,
    ) -> AssessmentDefinitionVersion:
        try:
            identity = self.repository.create_identity(
                course_id=course_id,
                learning_outcome_id=learning_outcome_id,
                created_by_user_id=actor_user_id,
            )
        except AssessmentDefinitionNotFoundError as error:
            self.session.rollback()
            raise AssessmentDefinitionValidationError(str(error)) from error
        except IntegrityError as error:
            self.session.rollback()
            raise AssessmentDefinitionConflictError(
                "an assessment definition already exists for this outcome"
            ) from error
        return self._write_version(
            course_id=course_id,
            assessment_definition_id=identity.id,
            version=1,
            actor_user_id=actor_user_id,
            draft=draft,
            action="assessment_definition.drafted",
        )

    def update_draft(
        self,
        *,
        course_id: str,
        assessment_definition_id: str,
        expected_version: int,
        actor_user_id: int,
        draft: AssessmentDefinitionDraft,
    ) -> AssessmentDefinitionVersion:
        current = self._get_expected_draft(
            course_id=course_id,
            assessment_definition_id=assessment_definition_id,
            expected_version=expected_version,
            allow_approved=True,
        )
        return self._write_version(
            course_id=course_id,
            assessment_definition_id=assessment_definition_id,
            version=current.version + 1,
            actor_user_id=actor_user_id,
            draft=draft,
            action="assessment_definition.revised",
        )

    def approve(
        self,
        *,
        course_id: str,
        assessment_definition_id: str,
        expected_version: int,
        actor_user_id: int,
        approval_reason: str,
    ) -> AssessmentDefinitionVersion:
        version = self._get_expected_draft(
            course_id=course_id,
            assessment_definition_id=assessment_definition_id,
            expected_version=expected_version,
            for_update=True,
        )
        clean_reason = approval_reason.strip()
        if not clean_reason:
            raise AssessmentDefinitionValidationError("approval_reason is required")
        try:
            self._validate_approval_ready(version)
            approved_at = self._utc(self._now())
            components = self._components(version)
            for component in components:
                component.approval_state = AssessmentApprovalState.APPROVED
                component.approved_at = approved_at
                component.approved_by_user_id = actor_user_id
            version.approval_state = AssessmentApprovalState.APPROVED
            version.approved_at = approved_at
            version.approved_by_user_id = actor_user_id
            for form in version.task_form_versions:
                self.session.add(
                    TaskApproval(
                        course_id=course_id,
                        assessment_definition_version_id=version.id,
                        task_form_version_id=form.id,
                        actor_user_id=actor_user_id,
                        approval_reason=clean_reason,
                        approval_state=AssessmentApprovalState.APPROVED,
                        approved_at=approved_at,
                        approved_by_user_id=actor_user_id,
                    )
                )
            self._audit(actor_user_id, "assessment_definition.approved", version)
            self.session.commit()
        except AssessmentDefinitionError:
            self.session.rollback()
            raise
        except (AssessmentAlignmentError, ValueError) as error:
            self.session.rollback()
            raise AssessmentDefinitionValidationError(str(error)) from error
        except (IntegrityError, SQLAlchemyError) as error:
            self.session.rollback()
            raise AssessmentDefinitionConflictError(
                "assessment definition changed before approval completed"
            ) from error
        return version

    def _write_version(
        self,
        *,
        course_id: str,
        assessment_definition_id: str,
        version: int,
        actor_user_id: int,
        draft: AssessmentDefinitionDraft,
        action: str,
    ) -> AssessmentDefinitionVersion:
        try:
            outcome = self.session.scalar(
                select(OutcomeVersion).where(
                    OutcomeVersion.id == draft.outcome_version_id,
                    OutcomeVersion.course_id == course_id,
                )
            )
            if outcome is None:
                raise AssessmentDefinitionValidationError(
                    "outcome version not found in this course"
                )
            row = AssessmentDefinitionVersion(
                course_id=course_id,
                assessment_definition_id=assessment_definition_id,
                outcome_version_id=outcome.id,
                version=version,
                owner_user_id=actor_user_id,
                created_by_user_id=actor_user_id,
                claim=draft.claim,
                supporting_evidence=draft.supporting_evidence,
                contradicting_evidence=draft.contradicting_evidence,
                insufficient_evidence=draft.insufficient_evidence,
                task_conditions=draft.task_conditions,
                next_action_contract=draft.next_action_contract,
                purpose=draft.purpose,
                permitted_tools=draft.permitted_tools,
                instructional_support=draft.instructional_support,
                access_conditions=draft.access_conditions,
                transfer_rule=draft.transfer_rule,
                evidence_sufficiency=draft.evidence_sufficiency,
            )
            self.session.add(row)
            self.session.flush()
            bloom = self.session.scalar(
                select(BloomTarget).where(
                    BloomTarget.assessment_definition_id == assessment_definition_id
                )
            )
            if bloom is None:
                bloom = BloomTarget(assessment_definition_id=assessment_definition_id)
                self.session.add(bloom)
            rule = self.session.scalar(
                select(PassRule).where(
                    PassRule.assessment_definition_id == assessment_definition_id
                )
            )
            if rule is None:
                rule = PassRule(assessment_definition_id=assessment_definition_id)
                self.session.add(rule)
            self.session.flush()
            bloom_version = BloomTargetVersion(
                course_id=course_id,
                bloom_target_id=bloom.id,
                assessment_definition_version_id=row.id,
                version=version,
                owner_user_id=actor_user_id,
                created_by_user_id=actor_user_id,
                bloom_process=draft.bloom_process,
                knowledge_dimension=draft.knowledge_dimension,
            )
            self.session.add(bloom_version)
            criterion_versions = self._add_criteria(
                course_id, assessment_definition_id, row, version, actor_user_id, draft.criteria
            )
            self.session.flush()
            self.session.add(
                PassRuleVersion(
                    course_id=course_id,
                    pass_rule_id=rule.id,
                    assessment_definition_version_id=row.id,
                    version=version,
                    owner_user_id=actor_user_id,
                    created_by_user_id=actor_user_id,
                    expression=self._bind_pass_rule(draft.pass_rule_expression, criterion_versions),
                )
            )
            self._add_task_forms(
                course_id, assessment_definition_id, row, version, actor_user_id, draft.task_forms
            )
            self._audit(actor_user_id, action, row)
            self.session.commit()
        except AssessmentDefinitionError:
            self.session.rollback()
            raise
        except IntegrityError as error:
            self.session.rollback()
            raise AssessmentDefinitionConflictError(
                "assessment definition changed before the new version was saved"
            ) from error
        except (SQLAlchemyError, ValueError) as error:
            self.session.rollback()
            raise AssessmentDefinitionValidationError(str(error)) from error
        return row

    def _add_criteria(
        self,
        course_id: str,
        assessment_definition_id: str,
        version_row: AssessmentDefinitionVersion,
        version: int,
        actor_user_id: int,
        drafts: list[CriterionDraft],
    ) -> dict[str, CriterionVersion]:
        versions: dict[str, CriterionVersion] = {}
        for draft in drafts:
            if not draft.stable_key.strip() or draft.stable_key in versions:
                raise AssessmentDefinitionValidationError(
                    "criterion stable keys must be unique and non-empty"
                )
            criterion = self.session.scalar(
                select(Criterion).where(
                    Criterion.assessment_definition_id == assessment_definition_id,
                    Criterion.stable_key == draft.stable_key,
                )
            )
            if criterion is None:
                criterion = Criterion(
                    assessment_definition_id=assessment_definition_id,
                    stable_key=draft.stable_key,
                )
            row = CriterionVersion(
                course_id=course_id,
                criterion=criterion,
                assessment_definition_version_id=version_row.id,
                version=version,
                owner_user_id=actor_user_id,
                created_by_user_id=actor_user_id,
                learner_description=draft.learner_description,
                evidence_description=draft.evidence_description,
                mandatory=draft.mandatory,
                evidence_source_types=draft.evidence_source_types,
                met_rule=draft.met_rule,
                not_met_rule=draft.not_met_rule,
                not_evaluable_rule=draft.not_evaluable_rule,
                approved_anchors=draft.approved_anchors,
                critical_error_rules=draft.critical_error_rules,
                evaluator_type=draft.evaluator_type,
            )
            self.session.add(row)
            versions[draft.stable_key] = row
        return versions

    def _add_task_forms(
        self,
        course_id: str,
        assessment_definition_id: str,
        version_row: AssessmentDefinitionVersion,
        version: int,
        actor_user_id: int,
        drafts: list[TaskFormDraft],
    ) -> None:
        definition = self.session.get(AssessmentDefinition, assessment_definition_id)
        if definition is None:
            raise AssessmentDefinitionValidationError("assessment definition not found")
        for draft in drafts:
            task = self.session.scalar(
                select(LearningTask).where(
                    LearningTask.id == draft.learning_task_id,
                    LearningTask.course_id == course_id,
                    LearningTask.learning_outcome_id == definition.learning_outcome_id,
                )
            )
            if task is None:
                raise AssessmentDefinitionValidationError(
                    "task form must reference a task in the definition course and outcome"
                )
            form = TaskForm(assessment_definition_id=assessment_definition_id)
            self.session.add(
                TaskFormVersion(
                    course_id=course_id,
                    task_form=form,
                    assessment_definition_version_id=version_row.id,
                    learning_task_id=draft.learning_task_id,
                    version=version,
                    owner_user_id=actor_user_id,
                    created_by_user_id=actor_user_id,
                    source_version=draft.source_version,
                    source_digest=draft.source_digest,
                    task_family=draft.task_family,
                    context=draft.context,
                    constraints=draft.constraints,
                )
            )

    @staticmethod
    def _bind_pass_rule(
        expression: dict[str, Any], criteria: dict[str, CriterionVersion]
    ) -> dict[str, Any]:
        def bind(node: Any) -> Any:
            if not isinstance(node, dict):
                raise AssessmentDefinitionValidationError("pass-rule clauses must be objects")
            if set(node) == {"criterion"}:
                key = node["criterion"]
                if not isinstance(key, str) or key not in criteria:
                    raise AssessmentDefinitionValidationError(
                        "pass rule references an unknown criterion"
                    )
                return {"criterion_version_id": criteria[key].id}
            if set(node) == {"operator", "clauses"}:
                clauses = node["clauses"]
                if not isinstance(clauses, list):
                    raise AssessmentDefinitionValidationError("pass-rule clauses must be a list")
                return {"operator": node["operator"], "clauses": [bind(item) for item in clauses]}
            raise AssessmentDefinitionValidationError("pass-rule expression has an unknown field")

        bound = bind(expression)
        if not isinstance(bound, dict):
            raise AssessmentDefinitionValidationError("pass-rule expression must be an object")
        return bound

    def _get_expected_draft(
        self,
        *,
        course_id: str,
        assessment_definition_id: str,
        expected_version: int,
        for_update: bool = False,
        allow_approved: bool = False,
    ) -> AssessmentDefinitionVersion:
        try:
            row = self.repository.get_version(
                course_id=course_id,
                assessment_definition_id=assessment_definition_id,
                version=expected_version,
                for_update=for_update,
            )
        except AssessmentDefinitionNotFoundError as error:
            raise AssessmentDefinitionConflictError(
                "assessment definition draft is stale or unavailable"
            ) from error
        current_version = max(
            item.version
            for item in self.repository.list_versions(
                course_id=course_id,
                assessment_definition_id=assessment_definition_id,
            )
        )
        if current_version != expected_version:
            raise AssessmentDefinitionConflictError("assessment definition draft is stale")
        if row.approval_state is AssessmentApprovalState.DRAFT:
            return row
        if allow_approved and row.approval_state is AssessmentApprovalState.APPROVED:
            return row
        else:
            raise AssessmentDefinitionConflictError("assessment definition draft is stale")

    def _validate_approval_ready(self, version: AssessmentDefinitionVersion) -> None:
        outcome = self.session.get(OutcomeVersion, version.outcome_version_id)
        if outcome is None or outcome.course_id != version.course_id:
            raise AssessmentDefinitionValidationError("definition source outcome is unavailable")
        if outcome.approval_state is not AssessmentApprovalState.APPROVED:
            raise AssessmentDefinitionValidationError("definition source outcome is not approved")
        components = self._components(version)
        if any(
            component.approval_state is not AssessmentApprovalState.DRAFT
            for component in components
        ):
            raise AssessmentDefinitionConflictError("definition component changed before approval")
        if not version.pass_rule_versions:
            raise AssessmentDefinitionValidationError("an approved definition requires a pass rule")
        validate_definition_alignment(
            claim=version.claim,
            supporting_evidence=version.supporting_evidence,
            contradicting_evidence=version.contradicting_evidence,
            insufficient_evidence=version.insufficient_evidence,
            task_conditions=version.task_conditions,
            next_action_contract=version.next_action_contract,
            permitted_tools=version.permitted_tools,
            instructional_support=version.instructional_support,
            access_conditions=version.access_conditions,
            transfer_rule=version.transfer_rule,
            evidence_sufficiency=version.evidence_sufficiency,
            bloom_process=version.bloom_target_versions[0].bloom_process
            if len(version.bloom_target_versions) == 1
            else self._invalid_bloom_target(),
            criteria=version.criterion_versions,
            task_forms=version.task_form_versions,
        )

    @staticmethod
    def _components(version: AssessmentDefinitionVersion) -> list[Any]:
        return [
            *version.bloom_target_versions,
            *version.criterion_versions,
            *version.pass_rule_versions,
            *version.task_form_versions,
        ]

    @staticmethod
    def _invalid_bloom_target() -> BloomProcess:
        raise AssessmentDefinitionValidationError(
            "an approved definition requires exactly one Bloom target"
        )

    def _audit(
        self,
        actor_user_id: int,
        action: str,
        version: AssessmentDefinitionVersion,
    ) -> None:
        self.session.add(
            PlatformAuditEvent(
                actor_id=actor_user_id,
                action=action,
                resource_type="assessment_definition_version",
                resource_id=version.id,
                correlation_id=self.correlation_id,
                details={
                    "assessment_definition_id": version.assessment_definition_id,
                    "course_id": version.course_id,
                    "version": version.version,
                },
            )
        )

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
