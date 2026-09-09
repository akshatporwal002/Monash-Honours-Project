"""Learner result projection and scoped requests for assessor review."""

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.domain.assessment import AppealOrCorrectionState, AssessorReviewAction, ResultState
from app.models.appeal_resolution import AppealResolution
from app.models.assessment import (
    AppealOrCorrection,
    AssessmentAttempt,
    AssessmentDecision,
    AssessmentDefinitionVersion,
    AssessorReview,
    BloomTargetVersion,
    CriterionEvaluation,
    CriterionVersion,
    OutcomeVersion,
    PassRuleVersion,
)
from app.models.human_assessment import HumanAssessmentAction, HumanCriterionDecision
from app.models.lms import PlatformAuditEvent, SubmissionAttempt
from app.models.user import User, UserRole
from app.schemas.learner_results import (
    AppealResolutionWrite,
    LearnerAppealRead,
    LearnerAppealWrite,
    LearnerCriterionRead,
    LearnerDecisionEventRead,
    LearnerResultRead,
)
from app.services.assessment.access import RoleAssignmentService
from app.services.assessment.pass_rules import referenced_criterion_version_ids
from app.services.lms import LmsService, LmsServiceError


class LearnerResultService:
    def __init__(self, session: Session, *, assignments: RoleAssignmentService | None = None):
        self.session = session
        self.assignments = assignments or RoleAssignmentService(session)

    def _owned_attempt(self, learner: User, response_id: str) -> AssessmentAttempt:
        response = self.session.get(SubmissionAttempt, response_id)
        if (
            not learner.is_active
            or learner.role is not UserRole.STUDENT
            or response is None
            or response.student_id != learner.id
        ):
            raise LmsServiceError(404, "Assessment response not found")
        LmsService(self.session).get_draft(learner, response.task_id)
        attempt = self.session.scalar(
            select(AssessmentAttempt).where(
                AssessmentAttempt.response_version_id == response.id,
                AssessmentAttempt.student_id == learner.id,
            )
        )
        if attempt is None:
            raise LmsServiceError(404, "Assessment response not found")
        return attempt

    def read(self, learner: User, response_id: str) -> LearnerResultRead:
        attempt = self._owned_attempt(learner, response_id)
        decision = self.session.scalar(
            select(AssessmentDecision).where(AssessmentDecision.assessment_attempt_id == attempt.id)
        )
        definition = self.session.get(
            AssessmentDefinitionVersion, attempt.assessment_definition_version_id
        )
        outcome = self.session.get(OutcomeVersion, definition.outcome_version_id)
        bloom = self.session.get(BloomTargetVersion, attempt.bloom_target_version_id)
        rule = self.session.get(PassRuleVersion, attempt.pass_rule_version_id)
        reviews = self._reviews(decision.id) if decision else []
        latest = reviews[-1] if reviews else None
        released = bool(
            decision and decision.result_state in {ResultState.CONFIRMED, ResultState.OVERRIDDEN}
        )
        status = "Awaiting assessor review"
        if decision and decision.result_state is ResultState.VOID:
            status = "Attempt voided"
        elif released:
            status = (
                "Confirmed by assessor"
                if decision.result_state is ResultState.CONFIRMED
                else "Updated by assessor"
            )
        elif latest and latest.action is AssessorReviewAction.WITHHOLD:
            status = "Result withheld pending review"
        elif latest and latest.action is AssessorReviewAction.RETURN:
            status = "Returned for further work"

        evaluations = {}
        if released:
            evaluations = {
                row.criterion_version_id: row.decision
                for row in self.session.scalars(
                    select(CriterionEvaluation).where(
                        CriterionEvaluation.assessment_attempt_id == attempt.id
                    )
                )
            }
            human = self.session.scalar(
                select(HumanAssessmentAction)
                .where(HumanAssessmentAction.assessment_attempt_id == attempt.id)
                .order_by(HumanAssessmentAction.revision.desc())
                .limit(1)
            )
            if human:
                evaluations.update(
                    {
                        row.criterion_version_id: row.decision
                        for row in self.session.scalars(
                            select(HumanCriterionDecision).where(
                                HumanCriterionDecision.action_id == human.id
                            )
                        )
                    }
                )
        criteria = list(
            self.session.scalars(
                select(CriterionVersion)
                .where(CriterionVersion.id.in_(referenced_criterion_version_ids(rule.expression)))
                .order_by(CriterionVersion.id)
            )
        )
        requests = list(
            self.session.scalars(
                select(AppealOrCorrection)
                .where(AppealOrCorrection.assessment_attempt_id == attempt.id)
                .order_by(AppealOrCorrection.created_at, AppealOrCorrection.id)
            )
        )
        reason = "Your response is saved. An authorised assessor must review the evidence before a result is available."
        next_action = "Review your saved response and the criteria. Request assessor review if you need an explanation or correction."
        if released:
            verb = (
                "confirmed"
                if decision.result_state is ResultState.CONFIRMED
                else "recorded an override to"
            )
            reason = f"The assessor {verb} {decision.result.value}."
            for verdict, label in (
                ("MET", "Evidence shown"),
                ("NOT_MET", "Evidence still needed"),
                ("NOT_EVALUABLE", "Evidence needing review"),
            ):
                descriptions = [
                    row.learner_description
                    for row in criteria
                    if evaluations.get(row.id) and evaluations[row.id].value == verdict
                ]
                if descriptions:
                    reason += f" {label}: {'; '.join(descriptions)}"
            if decision.result.value == "INCOMPLETE":
                permitted = definition.next_action_contract.get("when_incomplete")
                if isinstance(permitted, str) and permitted.strip():
                    next_action = f"{permitted.strip()} Ask your assessor if you need clarification or a correction."
        if status == "Attempt voided":
            reason = "This attempt cannot supply a current result. Ask your assessor about the next permitted action."
        return LearnerResultRead(
            response_version_id=response_id,
            assessment_attempt_id=attempt.id,
            decision_id=decision.id if decision else None,
            result=decision.result if released else None,
            status=status,
            bloom_process=bloom.bloom_process,
            outcome=outcome.statement,
            criteria=[
                LearnerCriterionRead(
                    id=row.id,
                    description=row.learner_description,
                    evidence_description=row.evidence_description,
                    mandatory=row.mandatory,
                    decision=evaluations.get(row.id),
                )
                for row in criteria
            ],
            evidence_response_id=response_id,
            reason=reason,
            next_action=next_action,
            review_revision=latest.review_revision if latest else 0,
            can_request_review=decision is not None,
            history=[
                LearnerDecisionEventRead(action=row.action.value, at=row.reviewed_at)
                for row in reviews
            ],
            requests=[self._request_read(row) for row in requests],
        )

    def request_review(
        self, learner: User, response_id: str, payload: LearnerAppealWrite
    ) -> LearnerAppealRead:
        self._lock(learner.id)
        attempt = self._owned_attempt(learner, response_id)
        decision = self.session.scalar(
            select(AssessmentDecision).where(AssessmentDecision.assessment_attempt_id == attempt.id)
        )
        if decision is None:
            raise LmsServiceError(
                409, "Assessment processing has not yet created a reviewable record"
            )
        identity = str(
            uuid5(
                NAMESPACE_URL,
                f"learnlens.appeal:{learner.id}:{response_id}:{payload.idempotency_key}",
            )
        )
        prior = self.session.get(AppealOrCorrection, identity)
        if prior:
            if (prior.request_reason, prior.request_kind) != (payload.reason, payload.request_kind):
                raise LmsServiceError(409, "This request key was used with different details")
            self.session.rollback()
            return self._request_read(prior)
        pending = self.session.scalar(
            select(AppealOrCorrection).where(
                AppealOrCorrection.assessment_attempt_id == attempt.id,
                AppealOrCorrection.state == AppealOrCorrectionState.PENDING,
            )
        )
        if pending:
            raise LmsServiceError(409, "A review request is already pending for this response")
        appeal = AppealOrCorrection(
            id=identity,
            assessment_attempt_id=attempt.id,
            assessment_decision_id=decision.id,
            requested_by_user_id=learner.id,
            request_kind=payload.request_kind,
            request_reason=payload.reason,
            state=AppealOrCorrectionState.PENDING,
        )
        self.session.add(appeal)
        self._audit(learner.id, identity, "assessment_review.requested")
        self._commit()
        return self._request_read(appeal)

    def queue(self, assessor: User, course_id: str, *, offset: int = 0) -> list[LearnerAppealRead]:
        self.assignments.require_assessor_access(assessor, course_id)
        rows = self.session.scalars(
            select(AppealOrCorrection)
            .join(AssessmentAttempt)
            .where(
                AssessmentAttempt.course_id == course_id,
                AppealOrCorrection.state == AppealOrCorrectionState.PENDING,
            )
            .order_by(AppealOrCorrection.created_at, AppealOrCorrection.id)
            .limit(50)
            .offset(offset)
        )
        return [self._request_read(row) for row in rows]

    def resolve(
        self, assessor: User, appeal_id: str, payload: AppealResolutionWrite
    ) -> LearnerAppealRead:
        self._lock(assessor.id)
        appeal = self.session.get(AppealOrCorrection, appeal_id)
        if appeal is None:
            raise LmsServiceError(404, "Review request not found")
        attempt = self.session.get(AssessmentAttempt, appeal.assessment_attempt_id)
        self.assignments.require_assessor_access(assessor, attempt.course_id)
        prior = self.session.scalar(
            select(AppealResolution).where(AppealResolution.appeal_id == appeal.id)
        )
        if prior:
            if (
                prior.assessor_user_id,
                prior.reason,
                prior.learner_notice,
                prior.decision_revision,
            ) != (
                assessor.id,
                payload.reason,
                payload.learner_notice,
                payload.expected_decision_revision,
            ):
                raise LmsServiceError(409, "This request has already been resolved")
            self.session.rollback()
            return self._request_read(appeal)
        reviews = self._reviews(appeal.assessment_decision_id)
        revision = reviews[-1].review_revision if reviews else 0
        if payload.expected_decision_revision != revision:
            raise LmsServiceError(
                409, "The decision changed. Reload and review it before resolving this request"
            )
        if appeal.state is not AppealOrCorrectionState.PENDING:
            raise LmsServiceError(409, "This request is no longer pending")
        at = datetime.now(UTC)
        self.session.add(
            AppealResolution(
                appeal_id=appeal.id,
                assessor_user_id=assessor.id,
                decision_revision=revision,
                reason=payload.reason,
                learner_notice=payload.learner_notice,
                created_at=at,
            )
        )
        appeal.state = AppealOrCorrectionState.RESOLVED
        appeal.resolved_by_user_id = assessor.id
        appeal.resolved_at = at
        self._audit(assessor.id, appeal.id, "assessment_review.resolved")
        self._commit()
        return self._request_read(appeal)

    def _request_read(self, appeal: AppealOrCorrection) -> LearnerAppealRead:
        attempt = self.session.get(AssessmentAttempt, appeal.assessment_attempt_id)
        resolution = self.session.scalar(
            select(AppealResolution).where(AppealResolution.appeal_id == appeal.id)
        )
        decision = self.session.get(AssessmentDecision, appeal.assessment_decision_id)
        notice = None
        if resolution:
            notice = (
                resolution.learner_notice
                if decision.result_state in {ResultState.CONFIRMED, ResultState.OVERRIDDEN}
                else "Your assessor has reviewed this request. A detailed notice will be available when a result is released."
            )
        reviews = self._reviews(appeal.assessment_decision_id)
        return LearnerAppealRead(
            id=appeal.id,
            response_version_id=attempt.response_version_id,
            decision_id=appeal.assessment_decision_id,
            request_kind=appeal.request_kind,
            reason=appeal.request_reason,
            state=appeal.state.value,
            requested_at=appeal.created_at,
            resolved_at=appeal.resolved_at,
            learner_notice=notice,
            decision_revision=reviews[-1].review_revision if reviews else 0,
        )

    def _reviews(self, decision_id: str) -> list[AssessorReview]:
        return list(
            self.session.scalars(
                select(AssessorReview)
                .where(AssessorReview.assessment_decision_id == decision_id)
                .order_by(AssessorReview.review_revision)
            )
        )

    def _lock(self, actor_id: int) -> None:
        try:
            self.session.execute(
                update(User).where(User.id == actor_id).values(is_active=User.is_active)
            )
        except OperationalError as error:
            self.session.rollback()
            raise LmsServiceError(
                409, "Review records are busy. Retry with the same details"
            ) from error

    def _audit(self, actor_id: int, appeal_id: str, action: str) -> None:
        self.session.add(
            PlatformAuditEvent(
                actor_id=actor_id,
                action=action,
                resource_type="appeal_or_correction",
                resource_id=appeal_id,
                correlation_id=appeal_id,
                details={"policy_version": "learner-visibility-v1-selection"},
            )
        )

    def _commit(self) -> None:
        try:
            self.session.commit()
        except (IntegrityError, OperationalError) as error:
            self.session.rollback()
            raise LmsServiceError(409, "Review records changed. Reload and retry") from error
