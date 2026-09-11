"""Read-only, exact reviewed evidence for assessed feedback."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic_core import to_jsonable_python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.assessment import AssessmentAttemptState, ResultState
from app.models.assessment import (
    AssessmentApprovalState,
    AssessmentAttempt,
    AssessmentDecision,
    TaskApproval,
)
from app.models.episode import EpisodeHelpUse
from app.models.human_assessment import HumanAssessmentAction, HumanCriterionDecision
from app.models.lms import SubmissionAttempt
from app.models.persistence import LearningTask
from app.models.task_review import TaskReviewEvent, TaskRevision
from app.schemas.assessment import EvidenceReference, ResolvedEvidenceReference
from app.schemas.feedback import (
    AssessmentContextStatus,
    AssessmentFeedbackContext,
    AssessmentFeedbackContextResolution,
    FeedbackCriterionContext,
    FeedbackCriterionEvaluationContext,
    SubmissionContext,
    TaskContext,
)
from app.services.assessment.evaluation import AssessmentEvaluationConflictError
from app.services.assessment.frozen_review import FrozenReviewEvidenceReader
from app.services.assessment.transfer_boundary import active_course_transfer
from app.services.episode_contract import FrozenResponseError, FrozenResponseReader
from app.services.episode_responses import SqlAlchemyFrozenResponseReader


class SqlAlchemyAssessmentFeedbackContextProvider:
    """Read preserved standards and current human decisions without recovery writes."""

    def __init__(self, session: Session, *, reader: FrozenResponseReader | None = None) -> None:
        self._session = session
        self._reader = reader or SqlAlchemyFrozenResponseReader(session)

    async def resolve(self, submission: SubmissionContext) -> AssessmentFeedbackContextResolution:
        with self._session.no_autoflush:
            return self._resolve(submission)

    def _resolve(self, submission):
        response = self._session.get(SubmissionAttempt, submission.submission_id)
        if response is None:
            return _unresolved(AssessmentContextStatus.MISSING, "RESPONSE_VERSION_MISSING")
        if (
            str(response.student_id) != submission.student_id
            or response.task_id != submission.task_id
        ):
            return _unresolved(AssessmentContextStatus.ACCESS_DENIED, "ASSESSMENT_SCOPE_DENIED")
        attempt = self._session.scalar(
            select(AssessmentAttempt).where(
                AssessmentAttempt.response_version_id == submission.submission_id
            )
        )
        if attempt is None:
            if (
                response.assessment_work_start_id
                or response.task_form_version_id
                or (response.response_schema_version or "").startswith("assessment.")
            ):
                return _unresolved(AssessmentContextStatus.MISSING, "ASSESSMENT_ATTEMPT_MISSING")
            if response.response_schema_version == "practice.response.v1":
                return self._practice_resolution(response)
            return _unresolved(AssessmentContextStatus.NOT_ASSESSED, "NOT_ASSESSED")
        if (
            attempt.course_id != submission.course_id
            or str(attempt.student_id) != submission.student_id
        ):
            return _unresolved(AssessmentContextStatus.ACCESS_DENIED, "ASSESSMENT_SCOPE_DENIED")
        frozen = FrozenReviewEvidenceReader(self._session, self._reader)
        try:
            reference = frozen.reference(attempt)
            preserved = self._reader.read(assessment=reference)
        except (FrozenResponseError, ValueError, TypeError, KeyError):
            return _unresolved(AssessmentContextStatus.INVALID, "FROZEN_RESPONSE_INVALID")
        try:
            bundle = frozen.bundle(attempt)
            reviewed = frozen.context(bundle)
            revision = self._session.get(TaskRevision, reviewed.task_revision_id)
            snapshot = revision.snapshot
            form, definition = bundle.form, bundle.definition
            plan = (
                form.constraints.get("episode_plan") if isinstance(form.constraints, dict) else None
            )
            simulations = list(frozen.resolver.simulations(reference, preserved))
            action, decisions = self._human_decisions(attempt)
            allowed, active = feedback_release_state(
                self._session, attempt, preserved, definition, action
            )
            for row in decisions.values():
                for raw in row.evidence_references:
                    evidence = EvidenceReference.model_validate(raw)
                    resolved = frozen.resolver.resolve(
                        assessment=reference, evidence_id=evidence.evidence_id
                    )
                    if (
                        not isinstance(resolved, ResolvedEvidenceReference)
                        or resolved.reference != evidence
                    ):
                        raise ValueError("Human evidence no longer matches its frozen record")
            criteria = [
                _criterion_context(
                    criterion, decisions.get(criterion.id) if allowed else None, reference, action
                )
                for criterion in bundle.criteria
            ]
            approval = self._session.scalar(
                select(TaskApproval).where(
                    TaskApproval.task_form_version_id == form.id,
                    TaskApproval.assessment_definition_version_id == definition.id,
                    TaskApproval.course_id == attempt.course_id,
                    TaskApproval.approval_state == AssessmentApprovalState.APPROVED,
                )
            )
            review = self._session.get(TaskReviewEvent, approval.task_review_event_id)
            task = TaskContext(
                task_id=attempt.task_id,
                course_id=attempt.course_id,
                task_type=snapshot["task_type"],
                prompt="\n\n".join(
                    part
                    for part in (reviewed.supported_prompt, reviewed.supported_instructions)
                    if part
                ),
                difficulty=snapshot["difficulty"],
                marking_criteria=[
                    {
                        "criterion_version_id": c.criterion_version_id,
                        "learner_description": c.learner_description,
                        "mandatory": c.mandatory,
                    }
                    for c in criteria
                ],
                learning_outcome_id=reference.outcome_id,
                source_references=list(snapshot.get("source_references") or []),
                assessed=True,
                source_approvals=dict(review.source_approvals),
            )
            help_ids = (
                list(
                    self._session.scalars(
                        select(EpisodeHelpUse.id)
                        .where(
                            EpisodeHelpUse.student_id == attempt.student_id,
                            EpisodeHelpUse.task_id == attempt.task_id,
                            EpisodeHelpUse.assessment_work_start_id
                            == preserved.assessment_work_start_id,
                            EpisodeHelpUse.task_form_version_id == form.id,
                            EpisodeHelpUse.created_at <= response.submitted_at,
                        )
                        .order_by(EpisodeHelpUse.created_at, EpisodeHelpUse.id)
                    )
                )
                if preserved.assessment_work_start_id
                else []
            )
            context = AssessmentFeedbackContext(
                assessment=reference,
                task=task,
                response_schema_version=preserved.reference.schema_version,
                response_content_digest=preserved.reference.content_digest,
                task_form_id=form.task_form_id,
                task_source_version=form.source_version,
                task_source_digest=form.source_digest,
                task_family=form.task_family,
                task_form_context=form.context,
                task_form_constraints=form.constraints,
                assessment_claim=definition.claim,
                assessment_purpose=definition.purpose,
                bloom_process=bundle.bloom.bloom_process,
                bloom_knowledge=bundle.bloom.knowledge_dimension,
                criteria=criteria,
                pass_rule_expression=bundle.rule.expression,
                permitted_tools=definition.permitted_tools,
                instructional_support=definition.instructional_support,
                access_conditions=definition.access_conditions,
                transfer_rule=definition.transfer_rule,
                evidence_sufficiency=definition.evidence_sufficiency,
                frozen_response=preserved,
                task_revision_id=reviewed.task_revision_id,
                current_human_action_id=action.id if action and allowed else None,
                feedback_release_allowed=allowed,
                active_transfer=active,
                approved_hints=list(plan.get("supported_hints", [])) if plan and not active else [],
                required_reflection=True,
                help_use_ids=help_ids,
                simulation_evidence=to_jsonable_python(simulations),
                context_warnings=(
                    [] if allowed else ["Feedback release is not permitted at this stage."]
                )
                + (
                    ["Simulation evidence is pending or has a technical fault."]
                    if any(run["status"] != "completed" for run in simulations)
                    else []
                ),
            )
        except (
            AssessmentEvaluationConflictError,
            FrozenResponseError,
            ValueError,
            TypeError,
            KeyError,
        ):
            return _unresolved(
                AssessmentContextStatus.MISSING, "FROZEN_REVIEWED_CONTEXT_UNAVAILABLE"
            )
        return AssessmentFeedbackContextResolution(
            status=AssessmentContextStatus.RESOLVED, context=context
        )

    def _practice_resolution(self, response):
        from app.schemas.episode import EpisodePayloadV1, ResponseContent
        from app.services.episodes import EpisodeService
        from app.services.feedback.practice_evidence import practice_response_input
        from app.services.misconception_state import active_fresh_check
        from app.services.task_review import TaskReviewError, TaskReviewService

        try:
            practice_response_input(response)
            task = self._session.get(LearningTask, response.task_id)
            TaskReviewService(self._session).require_available(task)
            EpisodeService(self._session).validate_response(
                None,
                EpisodePayloadV1.model_validate(response.episode),
                ResponseContent(
                    answer=response.answer, code=response.code, circuit=response.circuit
                ),
                student_id=response.student_id,
                task_id=response.task_id,
            )
            # Generic practice has no frozen support/release policy. Do not route a reviewed
            # formal episode plan (including its private transfer solution) through it.
            if isinstance(task.marking_criteria, dict) and task.marking_criteria.get(
                "episode_plan"
            ):
                return _unresolved(AssessmentContextStatus.INVALID, "PRACTICE_FEEDBACK_RESTRICTED")
            active = active_course_transfer(self._session, response.student_id, task.course_id)
            if active or active_fresh_check(self._session, response.student_id, response.task_id):
                return _unresolved(AssessmentContextStatus.INVALID, "PRACTICE_FEEDBACK_RESTRICTED")
        except (ValueError, TypeError, TaskReviewError):
            return _unresolved(AssessmentContextStatus.INVALID, "PRACTICE_RESPONSE_INVALID")
        return _unresolved(AssessmentContextStatus.NOT_ASSESSED, "NOT_ASSESSED")

    def _human_decisions(self, attempt):
        decision = self._session.scalar(
            select(AssessmentDecision).where(AssessmentDecision.assessment_attempt_id == attempt.id)
        )
        if decision is None or decision.result_state not in {
            ResultState.CONFIRMED,
            ResultState.OVERRIDDEN,
        }:
            return None, {}
        action = self._session.scalar(
            select(HumanAssessmentAction)
            .where(HumanAssessmentAction.assessment_attempt_id == attempt.id)
            .order_by(HumanAssessmentAction.revision.desc())
            .limit(1)
        )
        if action is None or (
            action.assessment_decision_id,
            action.result_state,
            action.result,
        ) != (decision.id, decision.result_state, decision.result):
            return None, {}
        rows = self._session.scalars(
            select(HumanCriterionDecision).where(HumanCriterionDecision.action_id == action.id)
        )
        return action, {row.criterion_version_id: row for row in rows}


def feedback_release_state(session, attempt, response, definition, human_action=None):
    """Recheck timing on every release, including reads of previously generated feedback."""
    active = active_course_transfer(session, attempt.student_id, attempt.course_id)
    if active or attempt.state in {AssessmentAttemptState.VOID, AssessmentAttemptState.FAULTED}:
        return False, active
    transfer_required = (
        isinstance(definition.transfer_rule, dict)
        and definition.transfer_rule.get("required") is True
    )
    if (response.episode is not None or transfer_required) and (
        response.episode is None or response.episode.transfer is None
    ):
        return False, active
    for policy in (definition.instructional_support, definition.transfer_rule):
        if not isinstance(policy, dict):
            continue
        for key in ("feedback_release", "feedback_release_timing", "feedback_timing"):
            timing = policy.get(key)
            if timing is None:
                continue
            if timing in ("after_assessment", "after_confirmation"):
                if human_action is None:
                    return False, active
            elif timing not in ("after_submission", "after_transfer", "after_episode"):
                return False, active
    return True, active


def _criterion_context(criterion, evaluation, assessment, action):
    evaluation_context = None
    if evaluation is not None:
        references = [
            EvidenceReference.model_validate(item) for item in evaluation.evidence_references
        ]
        if not references or any(ref.assessment != assessment for ref in references):
            raise ValueError("Human criterion evidence is foreign or missing")
        evaluation_context = FeedbackCriterionEvaluationContext(
            decision=evaluation.decision,
            evidence_references=references,
            evaluator_reference=f"human-action:{action.id}",
            reason=evaluation.reason,
            evaluated_at=_as_utc(action.created_at),
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


def _unresolved(status, reason_code):
    return AssessmentFeedbackContextResolution(status=status, reason_code=reason_code)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
