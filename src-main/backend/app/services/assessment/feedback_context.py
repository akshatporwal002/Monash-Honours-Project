"""Read-only frozen assessment context for the feedback pipeline."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment import (
    AssessmentApprovalState,
    AssessmentAttempt,
    AssessmentDefinitionVersion,
    BloomTargetVersion,
    CriterionEvaluation,
    CriterionVersion,
    OutcomeVersion,
    PassRuleVersion,
    TaskApproval,
    TaskFormVersion,
)
from app.models.lms import SubmissionAttempt
from app.models.persistence import LearningTask
from app.schemas.assessment import AssessmentVersionReference, EvidenceReference
from app.schemas.feedback import (
    AssessmentContextStatus,
    AssessmentFeedbackContext,
    AssessmentFeedbackContextResolution,
    FeedbackCriterionContext,
    FeedbackCriterionEvaluationContext,
    SubmissionContext,
    TaskContext,
)
from app.services.assessment.pass_rules import referenced_criterion_version_ids
from app.services.assessment.submissions import AssessmentSubmissionService


class SqlAlchemyAssessmentFeedbackContextProvider:
    """Resolve one immutable assessment bundle without exposing result mutation."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def resolve(
        self,
        submission: SubmissionContext,
    ) -> AssessmentFeedbackContextResolution:
        response = self._session.get(SubmissionAttempt, submission.submission_id)
        if response is None:
            return _unresolved(AssessmentContextStatus.MISSING, "RESPONSE_VERSION_MISSING")

        attempt = self._session.scalar(
            select(AssessmentAttempt).where(
                AssessmentAttempt.response_version_id == submission.submission_id
            )
        )
        if attempt is None:
            if response.task_form_version_id is not None or (
                response.response_schema_version or ""
            ).startswith("assessment."):
                return _unresolved(
                    AssessmentContextStatus.MISSING,
                    "ASSESSMENT_ATTEMPT_MISSING",
                )
            return _unresolved(AssessmentContextStatus.NOT_ASSESSED, "NOT_ASSESSED")

        if (
            attempt.course_id != submission.course_id
            or str(attempt.student_id) != submission.student_id
        ):
            return _unresolved(AssessmentContextStatus.ACCESS_DENIED, "ASSESSMENT_SCOPE_DENIED")
        if (
            attempt.response_version_id != submission.submission_id
            or attempt.task_id != submission.task_id
            or response.student_id != attempt.student_id
            or response.task_id != attempt.task_id
        ):
            return _unresolved(AssessmentContextStatus.STALE, "ASSESSMENT_REFERENCE_MISMATCH")

        loaded = self._load(attempt)
        if isinstance(loaded, AssessmentFeedbackContextResolution):
            return loaded
        response, task, definition, form, bloom, rule, outcome, criteria = loaded

        reference = AssessmentVersionReference(
            course_id=attempt.course_id,
            assessment_definition_id=definition.assessment_definition_id,
            assessment_definition_version=definition.version,
            outcome_id=outcome.learning_outcome_id,
            outcome_version=outcome.version,
            bloom_target_id=bloom.bloom_target_id,
            bloom_target_version=bloom.version,
            criterion_set_id=definition.assessment_definition_id,
            criterion_set_version=definition.version,
            pass_rule_id=rule.pass_rule_id,
            pass_rule_version=rule.version,
            task_id=attempt.task_id,
            task_form_version=form.version,
            assessment_attempt_id=attempt.id,
            response_version_id=response.id,
        )
        evaluations = {
            evaluation.criterion_version_id: evaluation
            for evaluation in self._session.scalars(
                select(CriterionEvaluation).where(
                    CriterionEvaluation.assessment_attempt_id == attempt.id
                )
            ).all()
        }
        try:
            criterion_contexts = [
                _criterion_context(criterion, evaluations.get(criterion.id), reference)
                for criterion in criteria
            ]
            task_context = TaskContext(
                task_id=task.id,
                course_id=attempt.course_id,
                task_type=task.task_type.value,
                prompt=task.instructions,
                difficulty=task.difficulty,
                marking_criteria=[
                    {
                        "criterion_version_id": criterion.id,
                        "learner_description": criterion.learner_description,
                        "mandatory": criterion.mandatory,
                    }
                    for criterion in criteria
                ],
                learning_outcome_id=outcome.learning_outcome_id,
                source_references=list(task.source_references or []),
            )
            context = AssessmentFeedbackContext(
                assessment=reference,
                task=task_context,
                response_schema_version=response.response_schema_version or "",
                response_content_digest=response.content_digest or "",
                task_form_id=form.task_form_id,
                task_source_version=form.source_version,
                task_source_digest=form.source_digest,
                task_family=form.task_family,
                task_form_context=form.context,
                task_form_constraints=form.constraints,
                assessment_claim=definition.claim,
                assessment_purpose=definition.purpose,
                bloom_process=bloom.bloom_process,
                bloom_knowledge=bloom.knowledge_dimension,
                criteria=criterion_contexts,
                pass_rule_expression=rule.expression,
                permitted_tools=definition.permitted_tools,
                instructional_support=definition.instructional_support,
                access_conditions=definition.access_conditions,
                transfer_rule=definition.transfer_rule,
                evidence_sufficiency=definition.evidence_sufficiency,
            )
        except (TypeError, ValueError, ValidationError):
            return _unresolved(AssessmentContextStatus.INVALID, "ASSESSMENT_CONTEXT_INVALID")
        return AssessmentFeedbackContextResolution(
            status=AssessmentContextStatus.RESOLVED,
            context=context,
        )

    def _load(
        self,
        attempt: AssessmentAttempt,
    ) -> (
        tuple[
            SubmissionAttempt,
            LearningTask,
            AssessmentDefinitionVersion,
            TaskFormVersion,
            BloomTargetVersion,
            PassRuleVersion,
            OutcomeVersion,
            tuple[CriterionVersion, ...],
        ]
        | AssessmentFeedbackContextResolution
    ):
        response = self._session.get(SubmissionAttempt, attempt.response_version_id)
        task = self._session.get(LearningTask, attempt.task_id)
        definition = self._session.get(
            AssessmentDefinitionVersion,
            attempt.assessment_definition_version_id,
        )
        form = self._session.get(TaskFormVersion, attempt.task_form_version_id)
        bloom = self._session.get(BloomTargetVersion, attempt.bloom_target_version_id)
        rule = self._session.get(PassRuleVersion, attempt.pass_rule_version_id)
        outcome = (
            self._session.get(OutcomeVersion, definition.outcome_version_id)
            if definition is not None
            else None
        )
        if any(value is None for value in (response, task, definition, form, bloom, rule, outcome)):
            return _unresolved(AssessmentContextStatus.MISSING, "FROZEN_VERSION_MISSING")
        assert (
            response is not None
            and task is not None
            and definition is not None
            and form is not None
            and bloom is not None
            and rule is not None
            and outcome is not None
        )
        if (
            definition.approval_state is not AssessmentApprovalState.APPROVED
            or definition.formal_result_eligible is not True
            or form.assessment_definition_version_id != definition.id
            or form.learning_task_id != attempt.task_id
            or bloom.assessment_definition_version_id != definition.id
            or rule.assessment_definition_version_id != definition.id
            or outcome.course_id != attempt.course_id
            or task.course_id != attempt.course_id
            or task.learning_outcome_id != outcome.learning_outcome_id
            or response.student_id != attempt.student_id
            or response.task_id != attempt.task_id
            or response.task_form_version_id != form.id
            or not response.response_schema_version
            or not response.content_digest
            or not form.source_version
            or not form.source_digest
        ):
            return _unresolved(AssessmentContextStatus.STALE, "FROZEN_VERSION_MISMATCH")
        approved_form = self._session.scalar(
            select(TaskApproval.id).where(
                TaskApproval.task_form_version_id == form.id,
                TaskApproval.assessment_definition_version_id == definition.id,
                TaskApproval.approval_state == AssessmentApprovalState.APPROVED,
            )
        )
        if approved_form is None:
            return _unresolved(AssessmentContextStatus.STALE, "TASK_FORM_NOT_APPROVED")
        try:
            AssessmentSubmissionService(self._session).assert_current_form_matches(attempt)
            criterion_ids = referenced_criterion_version_ids(rule.expression)
        except (RuntimeError, ValueError):
            return _unresolved(AssessmentContextStatus.STALE, "CURRENT_VERSION_CONFLICT")
        criteria = tuple(
            self._session.scalars(
                select(CriterionVersion)
                .where(
                    CriterionVersion.id.in_(criterion_ids),
                    CriterionVersion.course_id == attempt.course_id,
                    CriterionVersion.assessment_definition_version_id == definition.id,
                )
                .order_by(CriterionVersion.id)
            ).all()
        )
        if {criterion.id for criterion in criteria} != criterion_ids:
            return _unresolved(AssessmentContextStatus.MISSING, "CRITERION_VERSION_MISSING")
        newer_rule = self._session.scalar(
            select(PassRuleVersion.id).where(
                PassRuleVersion.pass_rule_id == rule.pass_rule_id,
                PassRuleVersion.version > rule.version,
                PassRuleVersion.approval_state == AssessmentApprovalState.APPROVED,
            )
        )
        if newer_rule is not None:
            return _unresolved(AssessmentContextStatus.STALE, "PASS_RULE_VERSION_CHANGED")
        return response, task, definition, form, bloom, rule, outcome, criteria


def _criterion_context(
    criterion: CriterionVersion,
    evaluation: CriterionEvaluation | None,
    assessment: AssessmentVersionReference,
) -> FeedbackCriterionContext:
    evaluation_context = None
    if evaluation is not None:
        raw_references = evaluation.evidence_references
        if not isinstance(raw_references, list):
            raise ValueError("criterion evidence references must be a list")
        references = [EvidenceReference.model_validate(item) for item in raw_references]
        if any(reference.assessment != assessment for reference in references):
            raise ValueError("criterion evidence references are stale")
        evaluation_context = FeedbackCriterionEvaluationContext(
            decision=evaluation.decision,
            evidence_references=references,
            evaluator_reference=evaluation.evaluator_reference,
            model_version=evaluation.model_version,
            prompt_version=evaluation.prompt_version,
            retrieval_version=evaluation.retrieval_version,
            reason=evaluation.reason,
            evaluated_at=_as_utc(evaluation.evaluated_at),
        )
    return FeedbackCriterionContext(
        criterion_id=criterion.criterion_id,
        criterion_version_id=criterion.id,
        criterion_version=criterion.version,
        learner_description=criterion.learner_description,
        evidence_description=criterion.evidence_description,
        mandatory=criterion.mandatory,
        evidence_source_types=list(criterion.evidence_source_types),
        met_rule=criterion.met_rule,
        not_met_rule=criterion.not_met_rule,
        not_evaluable_rule=criterion.not_evaluable_rule,
        approved_anchors=criterion.approved_anchors,
        critical_error_rules=criterion.critical_error_rules,
        evaluator_type=criterion.evaluator_type.value,
        evaluation=evaluation_context,
    )


def _unresolved(
    status: AssessmentContextStatus,
    reason_code: str,
) -> AssessmentFeedbackContextResolution:
    return AssessmentFeedbackContextResolution(status=status, reason_code=reason_code)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = ["SqlAlchemyAssessmentFeedbackContextProvider"]
