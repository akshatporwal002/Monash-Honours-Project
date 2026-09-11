"""Course-scoped human decisions for attempts that have no automated decision."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Callable
from uuid import uuid4

from sqlalchemy import exists, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.domain.assessment import (
    AssessmentAttemptState,
    CriterionDecision,
    ResultState,
)
from app.models.assessment import (
    AssessmentAttempt,
    AssessmentDecision,
    AssessmentEvaluationJob,
    AssessmentEvaluationJobState,
    AssessorReview,
    CriterionEvaluation,
)
from app.models.human_assessment import HumanAssessmentAction, HumanCriterionDecision
from app.models.lms import Course, PlatformAuditEvent
from app.models.user import User
from app.services.assessment.access import RoleAssignmentService
from app.services.assessment.evaluation import (
    AssessmentEvaluationConflictError,
)
from app.services.assessment.evidence import EvidenceValidationError, FrozenEvidenceValidator
from app.services.assessment.frozen_review import FrozenReviewEvidenceReader
from app.services.assessment.pass_rules import (
    CriterionRuleOutcome,
    PassRuleEngine,
    PassRuleEvaluationRequest,
)
from app.services.assessment.response_evidence import ResponseEvidenceResolver
from app.services.assessment.review import (
    AssessmentReviewConflictError,
    AssessmentReviewNotFoundError,
    AssessmentReviewService,
    AssessmentReviewValidationError,
)
from app.services.episode_contract import FrozenResponseError, FrozenResponseReader
from app.services.evidence.assessment_port import AssessmentEvidencePort


@dataclass(frozen=True)
class HumanCriterionInput:
    criterion_version_id: str
    decision: CriterionDecision
    reason: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class HumanAssessmentRequest:
    idempotency_key: str
    expected_token: str
    reason: str
    criteria: tuple[HumanCriterionInput, ...]


class HumanAssessmentService:
    def __init__(
        self,
        session: Session,
        *,
        assignments: RoleAssignmentService,
        reader: FrozenResponseReader,
        now: Callable[[], datetime] | None = None,
        correlation_id: str | None = None,
    ) -> None:
        self.session = session
        self.assignments = assignments
        self.reader = reader
        self.now = now or (lambda: datetime.now(UTC))
        self.correlation_id = correlation_id or str(uuid4())
        self.resolver = ResponseEvidenceResolver(reader, session)

    def queue(self, actor: User, *, course_id: str, limit: int = 50, offset: int = 0):
        self.assignments.require_assessor_access(actor, course_id)
        attempts = self.session.scalars(
            select(AssessmentAttempt)
            .where(
                AssessmentAttempt.course_id == course_id,
                ~exists(
                    select(AssessmentDecision.id).where(
                        AssessmentDecision.assessment_attempt_id == AssessmentAttempt.id
                    )
                ),
            )
            .order_by(AssessmentAttempt.created_at, AssessmentAttempt.id)
            .limit(limit)
            .offset(offset)
        ).all()
        return tuple(self._detail(attempt) for attempt in attempts)

    def detail(self, actor: User, *, assessment_attempt_id: str):
        return self._detail(self._visible(actor, assessment_attempt_id))

    def _visible(self, actor: User, attempt_id: str) -> AssessmentAttempt:
        attempt = self.session.get(AssessmentAttempt, attempt_id, populate_existing=True)
        if attempt is None:
            raise AssessmentReviewNotFoundError("Assessment attempt not found")
        self.assignments.require_assessor_access(actor, attempt.course_id)
        return attempt

    def _bundle(self, attempt):
        return FrozenReviewEvidenceReader(self.session, self.reader).bundle(attempt)

    def _actions(self, attempt_id):
        return self.session.scalars(
            select(HumanAssessmentAction)
            .where(HumanAssessmentAction.assessment_attempt_id == attempt_id)
            .order_by(HumanAssessmentAction.revision)
        ).all()

    def _token(self, attempt):
        job = self.session.get(AssessmentEvaluationJob, attempt.id, populate_existing=True)
        decision = self.session.scalar(
            select(AssessmentDecision)
            .where(AssessmentDecision.assessment_attempt_id == attempt.id)
            .execution_options(populate_existing=True)
        )
        reviews = (
            self.session.scalars(
                select(AssessorReview)
                .where(AssessorReview.assessment_decision_id == decision.id)
                .order_by(AssessorReview.review_revision)
            ).all()
            if decision
            else []
        )
        values = [
            attempt.id,
            attempt.state,
            attempt.fault_reason,
            [
                getattr(job, name)
                for name in (
                    "state",
                    "processing_attempts",
                    "execution_token",
                    "lease_expires_at",
                    "next_retry_at",
                    "failure_category",
                    "updated_at",
                )
            ]
            if job
            else None,
            [decision.id, decision.result_state, decision.result] if decision else None,
            reviews[-1].review_revision if reviews else 0,
            [action.id for action in self._actions(attempt.id)],
        ]
        return hashlib.sha256(json.dumps(values, default=str, sort_keys=True).encode()).hexdigest()

    def _detail(self, attempt):
        job = self.session.get(AssessmentEvaluationJob, attempt.id, populate_existing=True)
        evidence = FrozenReviewEvidenceReader(self.session, self.reader).read(attempt)
        simulations = evidence["simulations"]
        criteria = []
        versions = {}
        issues = list(evidence["issues"])
        try:
            bundle = self._bundle(attempt)
            versions = bundle.reference.model_dump()
            evaluations = {
                row.criterion_version_id: row
                for row in self.session.scalars(
                    select(CriterionEvaluation).where(
                        CriterionEvaluation.assessment_attempt_id == attempt.id
                    )
                )
            }
            for criterion in bundle.criteria:
                evaluation = evaluations.get(criterion.id)
                criteria.append(
                    {
                        "criterion_version_id": criterion.id,
                        "criterion_version": criterion.version,
                        "learner_description": criterion.learner_description,
                        "evidence_description": criterion.evidence_description,
                        "mandatory": criterion.mandatory,
                        "evidence_source_types": criterion.evidence_source_types,
                        "met_rule": criterion.met_rule,
                        "not_met_rule": criterion.not_met_rule,
                        "not_evaluable_rule": criterion.not_evaluable_rule,
                        "approved_anchors": criterion.approved_anchors,
                        "critical_error_rules": criterion.critical_error_rules,
                        "evaluator_type": criterion.evaluator_type,
                        "decision": evaluation.decision if evaluation else None,
                        "reason": evaluation.reason if evaluation else None,
                    }
                )
        except (AssessmentEvaluationConflictError, FrozenResponseError, ValueError):
            issues.append(
                "Frozen evidence or approved versions are unavailable or stale. Technical review is required."
            )
        if attempt.state in {AssessmentAttemptState.FAULTED, AssessmentAttemptState.VOID}:
            issues.append(
                "This attempt is technically invalid. Keep it under review and arrange a fair new attempt."
            )
        if (
            job
            and job.state is AssessmentEvaluationJobState.RUNNING
            and _utc(job.lease_expires_at) > _utc(self.now())
        ):
            issues.append(
                "An assessment worker is still processing this response. Reload after it finishes."
            )
        actions = self._actions(attempt.id)
        history = []
        for action in actions:
            entries = self.session.scalars(
                select(HumanCriterionDecision).where(HumanCriterionDecision.action_id == action.id)
            ).all()
            history.append(
                {
                    "action_id": action.id,
                    "revision": action.revision,
                    "assessor_user_id": action.assessor_user_id,
                    "reason": action.reason,
                    "result": action.result,
                    "result_state": action.result_state,
                    "created_at": action.created_at,
                    "criteria": [
                        {
                            "criterion_version_id": row.criterion_version_id,
                            "decision": row.decision,
                            "reason": row.reason,
                            "evidence_references": row.evidence_references,
                            "evaluator_reference": row.evaluator_reference,
                        }
                        for row in entries
                    ],
                }
            )
        return {
            "assessment_attempt_id": attempt.id,
            "course_id": attempt.course_id,
            "state": attempt.state,
            "job_state": job.state if job else None,
            "failure_category": job.failure_category if job else None,
            "expected_token": self._token(attempt),
            "response": evidence["response"],
            "response_history": evidence["response_history"],
            "historical_evidence": evidence["historical_evidence"],
            "frozen_context": evidence["frozen_context"],
            "criteria": criteria,
            "versions": versions,
            "simulations": simulations,
            "history": history,
            "issues": issues,
            "can_finalise": not issues,
            "created_at": attempt.created_at,
        }

    def finalise(self, actor: User, *, assessment_attempt_id: str, request: HumanAssessmentRequest):
        self._validate_request(request)
        attempt = self._visible(actor, assessment_attempt_id)
        digest = hashlib.sha256(
            json.dumps(asdict(request), default=str, sort_keys=True).encode()
        ).hexdigest()
        try:
            # Publication and course-grant changes use this same row lock.
            self.session.execute(
                update(Course)
                .where(Course.id == attempt.course_id)
                .values(id=Course.id, updated_at=Course.updated_at)
            )
            self.assignments.require_assessor_access(actor, attempt.course_id)
            self.session.refresh(attempt)
            actions = self._actions(attempt.id)
            replay = next(
                (action for action in actions if action.idempotency_key == request.idempotency_key),
                None,
            )
            if replay:
                if replay.request_digest != digest or replay.assessor_user_id != actor.id:
                    raise AssessmentReviewConflictError(
                        "This action key was used with different content or an assessor"
                    )
                self.session.rollback()
                return self._receipt(replay, True)
            if request.expected_token != self._token(attempt):
                raise AssessmentReviewConflictError(
                    "Assessment work changed. Reload the frozen evidence before acting."
                )
            detail = self._detail(attempt)
            if not detail["can_finalise"]:
                raise AssessmentReviewConflictError(" ".join(detail["issues"]))
            outcome, references = self.evaluate_request(actor, attempt, request)
            from app.services.assessment.moderation import ModerationService

            ModerationService(self.session).require_ready(actor, attempt, outcome.result)
            self._claim_job(attempt)
            decision = self.session.scalar(
                select(AssessmentDecision).where(
                    AssessmentDecision.assessment_attempt_id == attempt.id
                )
            )
            action_id = str(uuid4())
            if decision is None:
                decision = AssessmentDecision(
                    assessment_attempt_id=attempt.id,
                    bloom_target_version_id=attempt.bloom_target_version_id,
                    pass_rule_version_id=attempt.pass_rule_version_id,
                    evaluation_idempotency_key=f"human:{action_id}",
                    result=outcome.result,
                    result_state=ResultState.PROVISIONAL,
                    evidence_references={
                        "human_action_id": action_id,
                        "criteria": [
                            {
                                "criterion_version_id": entry.criterion_version_id,
                                "decision": entry.decision,
                                "reason": entry.reason,
                                "evidence": [
                                    ref.model_dump(mode="json")
                                    for ref in references[entry.criterion_version_id]
                                ],
                            }
                            for entry in request.criteria
                        ],
                    },
                    system_reason=outcome.reason_code,
                )
                self.session.add(decision)
                self.session.flush()
                attempt.state = AssessmentAttemptState.EVALUATED
                self.session.flush()
            review = self._confirm(actor, decision, outcome.result, request.reason)
            action = HumanAssessmentAction(
                id=action_id,
                assessment_attempt_id=attempt.id,
                assessment_decision_id=decision.id,
                assessor_user_id=actor.id,
                revision=len(actions) + 1,
                idempotency_key=request.idempotency_key,
                request_digest=digest,
                expected_token=request.expected_token,
                reason=request.reason.strip(),
                result=outcome.result,
                result_state=decision.result_state.value,
                review_id=review.id if review else None,
                created_at=self.now(),
            )
            self.session.add(action)
            self.session.flush()
            for entry in request.criteria:
                self.session.add(
                    HumanCriterionDecision(
                        action_id=action.id,
                        criterion_version_id=entry.criterion_version_id,
                        decision=entry.decision,
                        reason=entry.reason.strip(),
                        evidence_references=[
                            ref.model_dump(mode="json")
                            for ref in references[entry.criterion_version_id]
                        ],
                        evaluator_reference=f"human:{actor.id}:{action.id}",
                    )
                )
            self.session.add(
                PlatformAuditEvent(
                    actor_id=actor.id,
                    action="assessment_human.confirmed",
                    resource_type="assessment_attempt",
                    resource_id=attempt.id,
                    correlation_id=self.correlation_id,
                    details={
                        "course_id": attempt.course_id,
                        "human_action_id": action.id,
                        "criterion_count": len(request.criteria),
                        "pass_rule_version_id": attempt.pass_rule_version_id,
                        "result": outcome.result.value,
                    },
                )
            )
            self.session.commit()
            return self._receipt(action, False)
        except (IntegrityError, OperationalError) as error:
            self.session.rollback()
            raise AssessmentReviewConflictError(
                "Assessment work changed while this action was recorded. Reload and retry."
            ) from error
        except EvidenceValidationError as error:
            self.session.rollback()
            raise AssessmentReviewConflictError(
                "Frozen criterion evidence is unavailable, stale, or not approved"
            ) from error
        except Exception:
            self.session.rollback()
            raise

    def evaluate_request(self, actor, attempt, request):
        self._validate_request(request)
        self.assignments.require_assessor_access(actor, attempt.course_id)
        if request.expected_token != self._token(attempt):
            raise AssessmentReviewConflictError(
                "Assessment evidence changed. Reload before review."
            )
        detail = self._detail(attempt)
        if not detail["can_finalise"]:
            raise AssessmentReviewConflictError(" ".join(detail["issues"]))
        bundle = self._bundle(attempt)
        by_id = {entry.criterion_version_id: entry for entry in request.criteria}
        if len(by_id) != len(request.criteria) or set(by_id) != {
            criterion.id for criterion in bundle.criteria
        }:
            raise AssessmentReviewValidationError(
                "Provide exactly one decision for every frozen pass-rule criterion"
            )
        references = {}
        for criterion in bundle.criteria:
            entry = by_id[criterion.id]
            references[criterion.id] = FrozenEvidenceValidator().resolve_and_validate(
                AssessmentEvidencePort(self.resolver),
                assessment=bundle.reference,
                evidence_ids=entry.evidence_ids,
                allowed_types=criterion.evidence_source_types,
            )
        outcome = PassRuleEngine().evaluate(
            PassRuleEvaluationRequest(
                expression=bundle.rule.expression,
                approved_criterion_version_ids=frozenset(by_id),
                mandatory_criterion_version_ids=frozenset(
                    criterion.id for criterion in bundle.criteria if criterion.mandatory
                ),
                criterion_outcomes=tuple(
                    CriterionRuleOutcome(entry.criterion_version_id, entry.decision)
                    for entry in request.criteria
                ),
            )
        )
        return outcome, references

    def _claim_job(self, attempt):
        job = self.session.get(AssessmentEvaluationJob, attempt.id, populate_existing=True)
        if job is None:
            return
        statement = update(AssessmentEvaluationJob).where(
            AssessmentEvaluationJob.assessment_attempt_id == attempt.id
        )
        for name in (
            "state",
            "processing_attempts",
            "execution_token",
            "lease_expires_at",
            "next_retry_at",
            "failure_category",
            "updated_at",
        ):
            column, value = getattr(AssessmentEvaluationJob, name), getattr(job, name)
            statement = statement.where(column.is_(None) if value is None else column == value)
        result = self.session.execute(
            statement.values(
                state=AssessmentEvaluationJobState.COMPLETED,
                processing_attempts=max(1, job.processing_attempts),
                execution_token=None,
                lease_expires_at=None,
                next_retry_at=None,
                failure_category=None,
                completed_at=self.now(),
                updated_at=self.now(),
            )
        )
        if result.rowcount != 1:
            raise AssessmentReviewConflictError("Assessment worker changed before the human claim")

    def _confirm(self, actor, decision, result, reason):
        return AssessmentReviewService(
            self.session, assignments=self.assignments, now=self.now
        ).confirm_calculated_result(actor, decision, result, reason)

    @staticmethod
    def _validate_request(request):
        if (
            not request.idempotency_key.strip()
            or len(request.idempotency_key) > 128
            or len(request.expected_token) != 64
        ):
            raise AssessmentReviewValidationError("Human action key or expected token is invalid")
        if (
            not request.reason.strip()
            or len(request.reason) > 2000
            or not request.criteria
            or len(request.criteria) > 100
        ):
            raise AssessmentReviewValidationError("Record an action reason and criterion decisions")
        for entry in request.criteria:
            if (
                not isinstance(entry.decision, CriterionDecision)
                or not entry.reason.strip()
                or len(entry.reason) > 2000
                or not entry.evidence_ids
                or len(entry.evidence_ids) > 100
            ):
                raise AssessmentReviewValidationError(
                    "Every criterion needs a decision, reason, and frozen evidence"
                )

    @staticmethod
    def _receipt(action, replayed):
        return {
            "action_id": action.id,
            "assessment_attempt_id": action.assessment_attempt_id,
            "decision_id": action.assessment_decision_id,
            "result": action.result,
            "result_state": action.result_state,
            "revision": action.revision,
            "replayed": replayed,
        }


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
