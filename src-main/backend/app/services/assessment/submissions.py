"""Freeze approved assessment versions when an assessed response is accepted."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.assessment import AssessmentAttemptState, AssessmentPurpose
from app.models.assessment import (
    AssessmentApprovalState,
    AssessmentAttempt,
    AssessmentDefinitionVersion,
    BloomTargetVersion,
    CriterionVersion,
    PassRuleVersion,
    TaskApproval,
    TaskFormVersion,
)
from app.models.lms import SubmissionAttempt
from app.models.persistence import LearningTask


@dataclass(frozen=True)
class FrozenAssessmentVersions:
    definition_version_id: str
    task_form_version_id: str
    bloom_target_version_id: str
    pass_rule_version_id: str


@dataclass(frozen=True)
class AssessmentTaskDeclaration:
    versions: FrozenAssessmentVersions
    purpose: str
    bloom_process: str
    knowledge_dimension: str
    claim: str
    criteria: tuple[tuple[str, bool], ...]
    task_conditions: dict[str, Any] | list[Any]
    permitted_tools: dict[str, Any] | list[Any]
    instructional_support: dict[str, Any] | list[Any]
    access_conditions: dict[str, Any] | list[Any]
    transfer_rule: dict[str, Any] | list[Any]


class AssessmentSubmissionService:
    """Find the declared assessment bundle and append its formal attempt."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def frozen_versions_for_task(self, task: LearningTask) -> FrozenAssessmentVersions | None:
        declaration = self.declaration_for_task(task)
        return declaration.versions if declaration is not None else None

    def declaration_for_task(self, task: LearningTask) -> AssessmentTaskDeclaration | None:
        form = self.session.scalar(
            select(TaskFormVersion)
            .join(TaskApproval, TaskApproval.task_form_version_id == TaskFormVersion.id)
            .join(
                AssessmentDefinitionVersion,
                AssessmentDefinitionVersion.id == TaskFormVersion.assessment_definition_version_id,
            )
            .where(
                TaskFormVersion.course_id == task.course_id,
                TaskFormVersion.learning_task_id == task.id,
                TaskApproval.approval_state == AssessmentApprovalState.APPROVED,
                AssessmentDefinitionVersion.approval_state == AssessmentApprovalState.APPROVED,
                AssessmentDefinitionVersion.formal_result_eligible.is_(True),
                AssessmentDefinitionVersion.purpose.notin_(
                    [AssessmentPurpose.DIAGNOSTIC, AssessmentPurpose.FORMATIVE]
                ),
            )
            .order_by(TaskFormVersion.created_at.desc(), TaskFormVersion.id.desc())
        )
        if form is None:
            return None
        bloom = self.session.scalar(
            select(BloomTargetVersion).where(
                BloomTargetVersion.assessment_definition_version_id
                == form.assessment_definition_version_id
            )
        )
        rule = self.session.scalar(
            select(PassRuleVersion).where(
                PassRuleVersion.assessment_definition_version_id
                == form.assessment_definition_version_id
            )
        )
        if bloom is None or rule is None:
            raise RuntimeError("approved assessment definition is missing frozen rule versions")
        definition = form.assessment_definition_version
        criteria = tuple(
            (criterion.learner_description, criterion.mandatory)
            for criterion in self.session.scalars(
                select(CriterionVersion)
                .where(CriterionVersion.assessment_definition_version_id == definition.id)
                .order_by(CriterionVersion.created_at, CriterionVersion.id)
            )
        )
        return AssessmentTaskDeclaration(
            versions=FrozenAssessmentVersions(
                form.assessment_definition_version_id, form.id, bloom.id, rule.id
            ),
            purpose=definition.purpose.value,
            bloom_process=bloom.bloom_process.value,
            knowledge_dimension=bloom.knowledge_dimension.value,
            claim=definition.claim,
            criteria=criteria,
            task_conditions=definition.task_conditions,
            permitted_tools=definition.permitted_tools,
            instructional_support=definition.instructional_support,
            access_conditions=definition.access_conditions,
            transfer_rule=definition.transfer_rule,
        )

    def create_attempt(
        self,
        *,
        task: LearningTask,
        student_id: int,
        response: SubmissionAttempt,
        versions: FrozenAssessmentVersions,
    ) -> AssessmentAttempt:
        attempt = AssessmentAttempt(
            course_id=task.course_id,
            student_id=student_id,
            task_id=task.id,
            response_version_id=response.id,
            assessment_definition_version_id=versions.definition_version_id,
            task_form_version_id=versions.task_form_version_id,
            bloom_target_version_id=versions.bloom_target_version_id,
            pass_rule_version_id=versions.pass_rule_version_id,
            state=AssessmentAttemptState.PENDING,
        )
        self.session.add(attempt)
        return attempt

    def mark_fault_for_response(self, response_version_id: str, reason: str) -> bool:
        """Keep a formal response for review when its follow-up workflow fails."""

        attempt = self.session.scalar(
            select(AssessmentAttempt).where(
                AssessmentAttempt.response_version_id == response_version_id
            )
        )
        if attempt is None or attempt.state is not AssessmentAttemptState.PENDING:
            return False
        attempt.state = AssessmentAttemptState.FAULTED
        attempt.fault_reason = reason
        self.session.flush()
        return True

    def assert_current_form_matches(self, attempt: AssessmentAttempt) -> None:
        """Reject finalisation if the response's declared form has since changed."""

        task = self.session.get(LearningTask, attempt.task_id)
        declaration = self.declaration_for_task(task) if task is not None else None
        if (
            declaration is None
            or declaration.versions.task_form_version_id != attempt.task_form_version_id
        ):
            raise ValueError("The approved task form changed after this response was recorded")
