"""Course-scoped assessor review of provisional assessment decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.assessment import (
    AssessmentAttemptState,
    AssessmentReasonCode,
    AssessmentResult,
    AssessorReviewAction,
    CriterionDecision,
    ResultState,
    public_assessment_reason_code,
)
from app.models.assessment import (
    AssessmentAttempt,
    AssessmentDecision,
    AssessmentDefinitionVersion,
    AssessorReview,
    BloomTargetVersion,
    CriterionEvaluation,
    CriterionVersion,
    OutcomeVersion,
    PassRuleVersion,
    TaskFormVersion,
)
from app.models.lms import PlatformAuditEvent, SubmissionAttempt
from app.models.user import User
from app.services.assessment.access import RoleAssignmentService


class AssessmentReviewError(Exception):
    """Base error for assessor review operations."""


class AssessmentReviewNotFoundError(AssessmentReviewError):
    """The decision is absent or must not be disclosed to this caller."""


class AssessmentReviewConflictError(AssessmentReviewError):
    """The assessor acted on an out-of-date review revision."""


class AssessmentReviewValidationError(AssessmentReviewError):
    """The requested action cannot safely change the decision."""


@dataclass(frozen=True)
class AssessmentReviewFilters:
    course_id: str
    outcome_id: str | None = None
    result: AssessmentResult | None = None
    result_state: ResultState | None = None
    review_flag: str | None = None
    minimum_age_hours: int | None = None


@dataclass(frozen=True)
class CriterionReviewDetail:
    criterion_version_id: str
    criterion_version: int
    decision: CriterionDecision
    reason: str
    evidence_references: dict[str, Any] | list[Any]
    evaluator_reference: str
    model_version: str | None
    prompt_version: str | None
    retrieval_version: str | None


@dataclass(frozen=True)
class AssessorReviewHistory:
    id: str
    review_revision: int
    assessor_user_id: int
    action: AssessorReviewAction
    prior_result: AssessmentResult | None
    new_result: AssessmentResult | None
    reason: str
    reviewed_at: datetime


@dataclass(frozen=True)
class AssessmentReviewDetail:
    decision_id: str
    course_id: str
    outcome_id: str
    response_text: str
    response_conditions: dict[str, Any] | list[Any]
    result: AssessmentResult | None
    result_state: ResultState
    system_reason: AssessmentReasonCode
    review_revision: int
    quality_review_status: str
    versions: dict[str, str | int]
    criteria: tuple[CriterionReviewDetail, ...]
    missing_criterion_version_ids: tuple[str, ...]
    history: tuple[AssessorReviewHistory, ...]
    created_at: datetime


@dataclass(frozen=True)
class AssessmentReviewActionRequest:
    action: AssessorReviewAction
    reason: str
    expected_result_state: ResultState
    expected_review_revision: int
    new_result: AssessmentResult | None = None


@dataclass(frozen=True)
class AssessmentReviewActionResult:
    decision_id: str
    review_id: str
    result: AssessmentResult | None
    result_state: ResultState
    review_revision: int
    replayed: bool


class AssessmentReviewService:
    """Expose immutable evidence and record one authorised assessor action."""

    def __init__(
        self,
        session: Session,
        *,
        assignments: RoleAssignmentService,
        correlation_id: str | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.session = session
        self.assignments = assignments
        self.correlation_id = correlation_id or str(uuid4())
        self._now = now or (lambda: datetime.now(UTC))

    def list_queue(
        self,
        actor: User,
        *,
        filters: AssessmentReviewFilters,
    ) -> tuple[AssessmentReviewDetail, ...]:
        self.assignments.require_assessor_access(actor, filters.course_id)
        if filters.minimum_age_hours is not None and filters.minimum_age_hours < 0:
            raise AssessmentReviewValidationError("minimum review age must be non-negative")
        allowed_flags = {None, "QUALITY_REJECTED", "QUALITY_UNAVAILABLE"}
        if filters.review_flag not in allowed_flags:
            raise AssessmentReviewValidationError("review flag is invalid")

        minimum_created_at = (
            self._utc(self._now()) - timedelta(hours=filters.minimum_age_hours)
            if filters.minimum_age_hours is not None
            else None
        )
        query = (
            select(AssessmentDecision)
            .join(AssessmentAttempt)
            .where(AssessmentAttempt.course_id == filters.course_id)
        )
        if filters.outcome_id is not None:
            query = (
                query.join(
                    AssessmentDefinitionVersion,
                    AssessmentDefinitionVersion.id
                    == AssessmentAttempt.assessment_definition_version_id,
                )
                .join(
                    OutcomeVersion,
                    OutcomeVersion.id == AssessmentDefinitionVersion.outcome_version_id,
                )
                .where(OutcomeVersion.learning_outcome_id == filters.outcome_id)
            )
        if filters.result is not None:
            query = query.where(AssessmentDecision.result == filters.result)
        if filters.result_state is not None:
            query = query.where(AssessmentDecision.result_state == filters.result_state)
        if minimum_created_at is not None:
            query = query.where(AssessmentDecision.created_at <= minimum_created_at)
        if filters.review_flag is not None:
            quality_status = (
                "REJECTED" if filters.review_flag == "QUALITY_REJECTED" else "UNAVAILABLE"
            )
            quality_event = PlatformAuditEvent.__table__.alias("quality_event_filter")
            query = query.where(
                exists(
                    select(1).where(
                        quality_event.c.action == "assessment_evaluation.provisional",
                        quality_event.c.resource_type == "assessment_attempt",
                        quality_event.c.resource_id == AssessmentAttempt.id,
                        quality_event.c.details["quality_review_status"].as_string()
                        == quality_status,
                    )
                )
            )
        decisions = self.session.scalars(
            query.order_by(AssessmentDecision.created_at, AssessmentDecision.id)
        ).all()
        return self._details(decisions)

    def get_detail(self, actor: User, *, decision_id: str) -> AssessmentReviewDetail:
        decision = self._visible_decision(actor, decision_id)
        return self._detail(decision)

    def act(
        self,
        actor: User,
        *,
        decision_id: str,
        request: AssessmentReviewActionRequest,
    ) -> AssessmentReviewActionResult:
        if not request.reason.strip() or len(request.reason) > 2_000:
            raise AssessmentReviewValidationError("review reason is invalid")
        if request.expected_review_revision < 0:
            raise AssessmentReviewValidationError("review revision is invalid")
        decision = self._visible_decision(actor, decision_id)
        reviews = self._reviews(decision.id)
        current_revision = reviews[-1].review_revision if reviews else 0
        if request.expected_review_revision != current_revision:
            replay = self._replay(reviews, actor, request)
            if replay is not None:
                self._audit("assessment_review.replayed", decision, actor, replay, replayed=True)
                self.session.commit()
                return self._result(decision, replay, replayed=True)
            raise AssessmentReviewConflictError("assessment review changed before this action")
        if decision.result_state is not request.expected_result_state:
            raise AssessmentReviewConflictError(
                "assessment result state changed before this action"
            )

        self._validate_action(decision, request)
        reviewed_at = self._utc(self._now())
        review = AssessorReview(
            assessment_decision_id=decision.id,
            review_revision=current_revision + 1,
            assessor_user_id=actor.id,
            action=request.action,
            prior_result=self._prior_result(decision, request.action),
            new_result=self._new_result(decision, request),
            reason=request.reason.strip(),
            reviewed_at=reviewed_at,
        )
        self.session.add(review)
        try:
            # The migrated database requires the append-only review row to exist
            # before its trigger accepts the matching decision transition.
            self.session.flush()
            self._apply_action(decision, request, actor.id, reviewed_at)
            self._audit("assessment_review.recorded", decision, actor, review, replayed=False)
            if request.action is AssessorReviewAction.VOID:
                self.session.flush()
                attempt = self.session.get(AssessmentAttempt, decision.assessment_attempt_id)
                assert attempt is not None
                attempt.state = AssessmentAttemptState.VOID
                attempt.fault_reason = (
                    "An authorised assessor voided this formal assessment attempt."
                )
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise AssessmentReviewConflictError(
                "assessment review changed before this action"
            ) from error
        return self._result(decision, review, replayed=False)

    def _visible_decision(self, actor: User, decision_id: str) -> AssessmentDecision:
        decision = self.session.get(AssessmentDecision, decision_id)
        if decision is None:
            raise AssessmentReviewNotFoundError("assessment decision was not found")
        attempt = self.session.get(AssessmentAttempt, decision.assessment_attempt_id)
        if attempt is None:
            raise AssessmentReviewNotFoundError("assessment decision was not found")
        self.assignments.require_assessor_access(actor, attempt.course_id)
        return decision

    def _detail(self, decision: AssessmentDecision) -> AssessmentReviewDetail:
        return self._details((decision,))[0]

    def _details(
        self, decisions: list[AssessmentDecision] | tuple[AssessmentDecision, ...]
    ) -> tuple[AssessmentReviewDetail, ...]:
        if not decisions:
            return ()

        attempt_ids = {decision.assessment_attempt_id for decision in decisions}
        attempts = {
            attempt.id: attempt
            for attempt in self.session.scalars(
                select(AssessmentAttempt).where(AssessmentAttempt.id.in_(attempt_ids))
            )
        }
        responses = {
            response.id: response
            for response in self.session.scalars(
                select(SubmissionAttempt).where(
                    SubmissionAttempt.id.in_(
                        attempt.response_version_id for attempt in attempts.values()
                    )
                )
            )
        }
        definitions = {
            definition.id: definition
            for definition in self.session.scalars(
                select(AssessmentDefinitionVersion).where(
                    AssessmentDefinitionVersion.id.in_(
                        attempt.assessment_definition_version_id for attempt in attempts.values()
                    )
                )
            )
        }
        blooms = {
            bloom.id: bloom
            for bloom in self.session.scalars(
                select(BloomTargetVersion).where(
                    BloomTargetVersion.id.in_(
                        attempt.bloom_target_version_id for attempt in attempts.values()
                    )
                )
            )
        }
        rules = {
            rule.id: rule
            for rule in self.session.scalars(
                select(PassRuleVersion).where(
                    PassRuleVersion.id.in_(
                        attempt.pass_rule_version_id for attempt in attempts.values()
                    )
                )
            )
        }
        forms = {
            form.id: form
            for form in self.session.scalars(
                select(TaskFormVersion).where(
                    TaskFormVersion.id.in_(
                        attempt.task_form_version_id for attempt in attempts.values()
                    )
                )
            )
        }
        outcomes = {
            outcome.id: outcome
            for outcome in self.session.scalars(
                select(OutcomeVersion).where(
                    OutcomeVersion.id.in_(
                        definition.outcome_version_id for definition in definitions.values()
                    )
                )
            )
        }

        evaluations_by_attempt: dict[str, list[CriterionEvaluation]] = {}
        evaluations = self.session.scalars(
            select(CriterionEvaluation)
            .where(CriterionEvaluation.assessment_attempt_id.in_(attempt_ids))
            .order_by(
                CriterionEvaluation.assessment_attempt_id,
                CriterionEvaluation.criterion_version_id,
            )
        ).all()
        for evaluation in evaluations:
            evaluations_by_attempt.setdefault(evaluation.assessment_attempt_id, []).append(
                evaluation
            )
        criteria = {
            criterion.id: criterion
            for criterion in self.session.scalars(
                select(CriterionVersion).where(
                    CriterionVersion.id.in_(
                        evaluation.criterion_version_id for evaluation in evaluations
                    )
                )
            )
        }

        decision_ids = {decision.id for decision in decisions}
        reviews_by_decision: dict[str, list[AssessorReview]] = {}
        for review in self.session.scalars(
            select(AssessorReview)
            .where(AssessorReview.assessment_decision_id.in_(decision_ids))
            .order_by(AssessorReview.assessment_decision_id, AssessorReview.review_revision)
        ):
            reviews_by_decision.setdefault(review.assessment_decision_id, []).append(review)
        quality_by_attempt: dict[str, str] = {}
        for event in self.session.scalars(
            select(PlatformAuditEvent)
            .where(
                PlatformAuditEvent.action == "assessment_evaluation.provisional",
                PlatformAuditEvent.resource_type == "assessment_attempt",
                PlatformAuditEvent.resource_id.in_(attempt_ids),
            )
            .order_by(PlatformAuditEvent.occurred_at.desc(), PlatformAuditEvent.id.desc())
        ):
            quality_by_attempt.setdefault(
                event.resource_id,
                str(event.details.get("quality_review_status", "NOT_RECORDED")),
            )

        details: list[AssessmentReviewDetail] = []
        for decision in decisions:
            attempt = attempts[decision.assessment_attempt_id]
            response = responses[attempt.response_version_id]
            definition = definitions[attempt.assessment_definition_version_id]
            bloom = blooms[attempt.bloom_target_version_id]
            rule = rules[attempt.pass_rule_version_id]
            form = forms[attempt.task_form_version_id]
            outcome = outcomes[definition.outcome_version_id]
            review_rows = reviews_by_decision.get(decision.id, [])
            evaluation_rows = evaluations_by_attempt.get(attempt.id, [])
            criterion_rows = [
                criteria[evaluation.criterion_version_id] for evaluation in evaluation_rows
            ]
            details.append(
                AssessmentReviewDetail(
                    decision_id=decision.id,
                    course_id=attempt.course_id,
                    outcome_id=outcome.learning_outcome_id,
                    response_text=response.answer,
                    response_conditions=response.declared_conditions,
                    result=decision.result,
                    result_state=decision.result_state,
                    system_reason=public_assessment_reason_code(decision.system_reason),
                    review_revision=(review_rows[-1].review_revision if review_rows else 0),
                    quality_review_status=quality_by_attempt.get(attempt.id, "NOT_RECORDED"),
                    versions={
                        "assessment_definition_id": definition.assessment_definition_id,
                        "assessment_definition_version": definition.version,
                        "outcome_id": outcome.learning_outcome_id,
                        "outcome_version": outcome.version,
                        "bloom_target_id": bloom.bloom_target_id,
                        "bloom_target_version": bloom.version,
                        "pass_rule_id": rule.pass_rule_id,
                        "pass_rule_version": rule.version,
                        "task_form_id": form.id,
                        "task_form_version": form.version,
                        "response_version_id": response.id,
                    },
                    criteria=tuple(
                        CriterionReviewDetail(
                            criterion_version_id=criterion.id,
                            criterion_version=criterion.version,
                            decision=evaluation.decision,
                            reason=evaluation.reason,
                            evidence_references=evaluation.evidence_references,
                            evaluator_reference=evaluation.evaluator_reference,
                            model_version=evaluation.model_version,
                            prompt_version=evaluation.prompt_version,
                            retrieval_version=evaluation.retrieval_version,
                        )
                        for evaluation, criterion in zip(
                            evaluation_rows, criterion_rows, strict=True
                        )
                    ),
                    missing_criterion_version_ids=tuple(
                        criterion.id
                        for evaluation, criterion in zip(
                            evaluation_rows, criterion_rows, strict=True
                        )
                        if evaluation.decision is CriterionDecision.NOT_EVALUABLE
                    ),
                    history=tuple(
                        AssessorReviewHistory(
                            id=review.id,
                            review_revision=review.review_revision,
                            assessor_user_id=review.assessor_user_id,
                            action=review.action,
                            prior_result=review.prior_result,
                            new_result=review.new_result,
                            reason=review.reason,
                            reviewed_at=review.reviewed_at,
                        )
                        for review in review_rows
                    ),
                    created_at=decision.created_at,
                )
            )
        return tuple(details)

    def _reviews(self, decision_id: str) -> list[AssessorReview]:
        return list(
            self.session.scalars(
                select(AssessorReview)
                .where(AssessorReview.assessment_decision_id == decision_id)
                .order_by(AssessorReview.review_revision)
            )
        )

    @staticmethod
    def _validate_action(
        decision: AssessmentDecision,
        request: AssessmentReviewActionRequest,
    ) -> None:
        if request.action is AssessorReviewAction.CONFIRM:
            if (
                decision.result_state is not ResultState.PROVISIONAL
                or request.new_result is not None
            ):
                raise AssessmentReviewValidationError("only a provisional result can be confirmed")
        elif request.action is AssessorReviewAction.OVERRIDE:
            if (
                decision.result_state not in {ResultState.PROVISIONAL, ResultState.CONFIRMED}
                or request.new_result is None
                or request.new_result is decision.result
            ):
                raise AssessmentReviewValidationError(
                    "override must change a provisional or confirmed result"
                )
        elif request.action is AssessorReviewAction.VOID:
            if (
                decision.result_state
                not in {
                    ResultState.PROVISIONAL,
                    ResultState.CONFIRMED,
                    ResultState.OVERRIDDEN,
                }
                or request.new_result is not None
            ):
                raise AssessmentReviewValidationError("only an active result can be voided")
        elif request.action in {AssessorReviewAction.WITHHOLD, AssessorReviewAction.RETURN}:
            if (
                decision.result_state is not ResultState.PROVISIONAL
                or request.new_result is not None
            ):
                raise AssessmentReviewValidationError(
                    "withhold and return actions keep a provisional result under review"
                )
        else:
            raise AssessmentReviewValidationError("review action is invalid")

    @staticmethod
    def _prior_result(
        decision: AssessmentDecision,
        action: AssessorReviewAction,
    ) -> AssessmentResult | None:
        if action in {AssessorReviewAction.OVERRIDE, AssessorReviewAction.VOID}:
            return decision.result
        return None

    @staticmethod
    def _new_result(
        decision: AssessmentDecision,
        request: AssessmentReviewActionRequest,
    ) -> AssessmentResult | None:
        if request.action is AssessorReviewAction.CONFIRM:
            return decision.result
        return request.new_result

    def _apply_action(
        self,
        decision: AssessmentDecision,
        request: AssessmentReviewActionRequest,
        actor_user_id: int,
        reviewed_at: datetime,
    ) -> None:
        if request.action is AssessorReviewAction.CONFIRM:
            decision.result_state = ResultState.CONFIRMED
            decision.assessor_user_id = actor_user_id
            decision.reviewed_at = reviewed_at
        elif request.action is AssessorReviewAction.OVERRIDE:
            decision.prior_result = decision.result
            decision.result = request.new_result
            decision.result_state = ResultState.OVERRIDDEN
            decision.override_reason = request.reason.strip()
            decision.assessor_user_id = actor_user_id
            decision.reviewed_at = reviewed_at
        elif request.action is AssessorReviewAction.VOID:
            decision.result = None
            decision.result_state = ResultState.VOID
            decision.assessor_user_id = actor_user_id
            decision.reviewed_at = reviewed_at

    def _replay(
        self,
        reviews: list[AssessorReview],
        actor: User,
        request: AssessmentReviewActionRequest,
    ) -> AssessorReview | None:
        if not reviews:
            return None
        latest = reviews[-1]
        expected_new_result = request.new_result
        if request.action is AssessorReviewAction.CONFIRM:
            expected_new_result = latest.new_result
        if (
            latest.review_revision == request.expected_review_revision + 1
            and latest.assessor_user_id == actor.id
            and latest.action is request.action
            and latest.reason == request.reason.strip()
            and latest.new_result is expected_new_result
        ):
            return latest
        return None

    def _audit(
        self,
        action: str,
        decision: AssessmentDecision,
        actor: User,
        review: AssessorReview,
        *,
        replayed: bool,
    ) -> None:
        attempt = self.session.get(AssessmentAttempt, decision.assessment_attempt_id)
        assert attempt is not None
        self.session.add(
            PlatformAuditEvent(
                actor_id=actor.id,
                action=action,
                resource_type="assessment_decision",
                resource_id=decision.id,
                correlation_id=self.correlation_id,
                details={
                    "course_id": attempt.course_id,
                    "assessment_attempt_id": attempt.id,
                    "review_id": review.id,
                    "review_revision": review.review_revision,
                    "review_action": review.action.value,
                    "result": decision.result.value if decision.result is not None else None,
                    "result_state": decision.result_state.value,
                    "pass_rule_version_id": decision.pass_rule_version_id,
                    "bloom_target_version_id": decision.bloom_target_version_id,
                    "replayed": replayed,
                },
            )
        )

    @staticmethod
    def _result(
        decision: AssessmentDecision,
        review: AssessorReview,
        *,
        replayed: bool,
    ) -> AssessmentReviewActionResult:
        return AssessmentReviewActionResult(
            decision_id=decision.id,
            review_id=review.id,
            result=decision.result,
            result_state=decision.result_state,
            review_revision=review.review_revision,
            replayed=replayed,
        )

    @staticmethod
    def _utc(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
