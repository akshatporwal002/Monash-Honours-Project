"""Create one provisional, version-bound assessment decision after safe evaluation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.assessment import (
    AssessmentAttemptState,
    AssessmentResult,
    BloomProcess,
    QualityReviewDecision,
    ResultState,
)
from app.models.assessment import (
    AssessmentApprovalState,
    AssessmentAttempt,
    AssessmentDecision,
    AssessmentDefinitionVersion,
    BloomTargetVersion,
    CriterionEvaluation,
    CriterionVersion,
    OutcomeVersion,
    PassRuleVersion,
    TaskApproval,
    TaskFormVersion,
)
from app.models.lms import PlatformAuditEvent, SubmissionAttempt
from app.schemas.assessment import AssessmentVersionReference, EvidenceReference
from app.services.assessment.evaluators import EvaluatorOutcome
from app.services.assessment.pass_rules import (
    CriterionRuleOutcome,
    PassRuleEngine,
    PassRuleEvaluationRequest,
    referenced_criterion_version_ids,
)
from app.services.assessment.submissions import AssessmentSubmissionService


class AssessmentEvaluationError(Exception):
    """Base failure for assessment evaluation orchestration."""


class AssessmentEvaluationNotFoundError(AssessmentEvaluationError):
    """The requested assessment attempt is not visible to the caller."""


class AssessmentEvaluationConflictError(AssessmentEvaluationError):
    """A frozen attempt no longer has a safe evaluation path."""


class AssessmentEvaluationFaultError(AssessmentEvaluationError):
    """A provider or system fault retained work but created no learner result."""


class CriterionEvaluationPort(Protocol):
    """Resolve evidence and evaluate one frozen criterion outside this orchestrator."""

    def evaluate(
        self,
        *,
        assessment: AssessmentVersionReference,
        response_text: str,
        bloom_process: BloomProcess,
        criterion: CriterionVersion,
    ) -> EvaluatorOutcome:
        """Return an evidence-validated typed outcome or raise on evaluator failure."""


class QualityReviewPort(Protocol):
    """Review an operational reason and evidence without receiving a learner result."""

    def review(
        self,
        *,
        assessment: AssessmentVersionReference,
        reason_code: str,
        evidence: tuple[EvidenceReference, ...],
    ) -> QualityReviewDecision | None:
        """Return the separate quality namespace, or None when review is unavailable."""


class UnavailableCriterionEvaluationPort:
    """Fail closed until the evidence-backed evaluator provider is configured."""

    def evaluate(self, **_: object) -> EvaluatorOutcome:
        raise RuntimeError("assessment criterion evaluation is not configured")


class UnavailableQualityReviewPort:
    """Keep quality review under human review until its provider is configured."""

    def review(self, **_: object) -> QualityReviewDecision | None:
        return None


@dataclass(frozen=True)
class AssessmentEvaluationResult:
    decision_id: str
    result: AssessmentResult
    result_state: ResultState
    reason_code: str
    replayed: bool


class AssessmentEvaluationService:
    """Orchestrate frozen evaluation without accepting scores or research inputs."""

    def __init__(
        self,
        session: Session,
        *,
        criterion_port: CriterionEvaluationPort,
        quality_port: QualityReviewPort,
        correlation_id: str | None = None,
    ) -> None:
        self.session = session
        self.criterion_port = criterion_port
        self.quality_port = quality_port
        self.correlation_id = correlation_id or str(uuid4())

    def evaluate(
        self,
        *,
        assessment_attempt_id: str,
        evaluation_idempotency_key: str,
        actor_user_id: int | None = None,
    ) -> AssessmentEvaluationResult:
        if not evaluation_idempotency_key.strip() or len(evaluation_idempotency_key) > 255:
            raise AssessmentEvaluationConflictError("evaluation idempotency key is invalid")
        attempt = self.session.get(AssessmentAttempt, assessment_attempt_id)
        if attempt is None or (actor_user_id is not None and attempt.student_id != actor_user_id):
            raise AssessmentEvaluationNotFoundError("assessment attempt was not found")

        existing = self.session.scalar(
            select(AssessmentDecision).where(
                AssessmentDecision.evaluation_idempotency_key == evaluation_idempotency_key
            )
        )
        if existing is not None:
            if existing.assessment_attempt_id != attempt.id:
                self._audit(
                    "assessment_evaluation.conflict",
                    attempt,
                    {"reason_code": "IDEMPOTENCY_CONFLICT"},
                )
                self.session.commit()
                raise AssessmentEvaluationConflictError(
                    "evaluation key belongs to another assessment attempt"
                )
            self._audit("assessment_evaluation.replayed", attempt, {"decision_id": existing.id})
            self.session.commit()
            return self._result(existing, replayed=True)

        try:
            bundle = self._load_bundle(attempt)
        except AssessmentEvaluationConflictError as error:
            self._audit(
                "assessment_evaluation.conflict", attempt, {"reason_code": "VERSION_CONFLICT"}
            )
            self.session.commit()
            raise error

        self._audit(
            "assessment_evaluation.requested", attempt, {"pass_rule_version_id": bundle.rule.id}
        )
        try:
            outcomes = tuple(
                self.criterion_port.evaluate(
                    assessment=bundle.reference,
                    response_text=bundle.response.answer,
                    bloom_process=bundle.bloom.bloom_process,
                    criterion=criterion,
                )
                for criterion in bundle.criteria
            )
            self._validate_outcomes(outcomes, bundle)
            rule = PassRuleEngine().evaluate(
                PassRuleEvaluationRequest(
                    expression=bundle.rule.expression,
                    approved_criterion_version_ids=frozenset(
                        criterion.id for criterion in bundle.criteria
                    ),
                    mandatory_criterion_version_ids=frozenset(
                        criterion.id for criterion in bundle.criteria if criterion.mandatory
                    ),
                    criterion_outcomes=tuple(
                        CriterionRuleOutcome(criterion.id, outcome.decision)
                        for criterion, outcome in zip(bundle.criteria, outcomes, strict=True)
                    ),
                )
            )
        except Exception as error:
            self.session.rollback()
            self._record_fault(attempt.id, "EVALUATION_PROVIDER_OR_RULE_FAULT")
            raise AssessmentEvaluationFaultError(
                "assessment evaluation could not complete"
            ) from error

        quality_status = self._quality_status(bundle.reference, rule.reason_code, outcomes)
        if quality_status == "FAULTED":
            self.session.rollback()
            self._record_fault(attempt.id, "QUALITY_REVIEW_FAULT")
            raise AssessmentEvaluationFaultError("quality review could not complete")

        for criterion, outcome in zip(bundle.criteria, outcomes, strict=True):
            self.session.add(
                CriterionEvaluation(
                    assessment_attempt_id=attempt.id,
                    criterion_version_id=criterion.id,
                    decision=outcome.decision,
                    evidence_references=[
                        reference.model_dump(mode="json") for reference in outcome.evidence
                    ],
                    evaluator_reference=outcome.evaluator_reference,
                    model_version=outcome.model_version,
                    prompt_version=outcome.prompt_version,
                    retrieval_version=outcome.retrieval_version,
                    reason=outcome.reason,
                )
            )
        decision = AssessmentDecision(
            assessment_attempt_id=attempt.id,
            bloom_target_version_id=attempt.bloom_target_version_id,
            pass_rule_version_id=attempt.pass_rule_version_id,
            evaluation_idempotency_key=evaluation_idempotency_key,
            result=rule.result,
            result_state=ResultState.PROVISIONAL,
            evidence_references={
                "criterion_evaluations": [
                    {
                        "criterion_version_id": criterion.id,
                        "evidence": [
                            reference.model_dump(mode="json") for reference in outcome.evidence
                        ],
                    }
                    for criterion, outcome in zip(bundle.criteria, outcomes, strict=True)
                ]
            },
            system_reason=rule.reason_code,
        )
        self.session.add(decision)
        attempt.state = AssessmentAttemptState.EVALUATED
        self._audit(
            "assessment_evaluation.provisional",
            attempt,
            {
                "result": rule.result.value,
                "reason_code": rule.reason_code,
                "quality_review_status": quality_status,
                "criterion_count": len(outcomes),
            },
        )
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            replay = self.session.scalar(
                select(AssessmentDecision).where(
                    AssessmentDecision.evaluation_idempotency_key == evaluation_idempotency_key
                )
            )
            if replay is not None and replay.assessment_attempt_id == attempt.id:
                return self._result(replay, replayed=True)
            raise AssessmentEvaluationConflictError(
                "assessment evaluation changed before completion"
            ) from error
        return self._result(decision, replayed=False)

    def _load_bundle(self, attempt: AssessmentAttempt) -> "_EvaluationBundle":
        if attempt.state is not AssessmentAttemptState.PENDING:
            raise AssessmentEvaluationConflictError("assessment attempt is not pending evaluation")
        response = self.session.get(SubmissionAttempt, attempt.response_version_id)
        definition = self.session.get(
            AssessmentDefinitionVersion, attempt.assessment_definition_version_id
        )
        form = self.session.get(TaskFormVersion, attempt.task_form_version_id)
        bloom = self.session.get(BloomTargetVersion, attempt.bloom_target_version_id)
        rule = self.session.get(PassRuleVersion, attempt.pass_rule_version_id)
        outcome = (
            self.session.get(OutcomeVersion, definition.outcome_version_id) if definition else None
        )
        if any(value is None for value in (response, definition, form, bloom, rule, outcome)):
            raise AssessmentEvaluationConflictError("frozen assessment versions are unavailable")
        assert (
            response is not None
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
            or response.student_id != attempt.student_id
            or response.task_id != attempt.task_id
            or response.task_form_version_id != form.id
            or not response.response_schema_version
            or not response.content_digest
            or not form.source_version
            or not form.source_digest
        ):
            raise AssessmentEvaluationConflictError(
                "assessment attempt version or source evidence is stale"
            )
        approved_form = self.session.scalar(
            select(TaskApproval.id).where(
                TaskApproval.task_form_version_id == form.id,
                TaskApproval.assessment_definition_version_id == definition.id,
                TaskApproval.approval_state == AssessmentApprovalState.APPROVED,
            )
        )
        if approved_form is None:
            raise AssessmentEvaluationConflictError("assessment task form is no longer approved")
        AssessmentSubmissionService(self.session).assert_current_form_matches(attempt)
        newer_rule = self.session.scalar(
            select(PassRuleVersion.id).where(
                PassRuleVersion.pass_rule_id == rule.pass_rule_id,
                PassRuleVersion.version > rule.version,
                PassRuleVersion.approval_state == AssessmentApprovalState.APPROVED,
            )
        )
        if newer_rule is not None:
            raise AssessmentEvaluationConflictError(
                "pass rule changed after the response was recorded"
            )
        criterion_ids = referenced_criterion_version_ids(rule.expression)
        criteria = tuple(
            self.session.scalars(
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
            raise AssessmentEvaluationConflictError("pass rule criterion versions are unavailable")
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
        return _EvaluationBundle(response, definition, form, bloom, rule, criteria, reference)

    @staticmethod
    def _validate_outcomes(
        outcomes: Iterable[EvaluatorOutcome], bundle: "_EvaluationBundle"
    ) -> None:
        for criterion, outcome in zip(bundle.criteria, outcomes, strict=True):
            if not outcome.reason.strip() or not outcome.evidence:
                raise ValueError("criterion evaluator returned incomplete evidence")
            if any(
                reference.assessment != bundle.reference
                or reference.evidence_type not in criterion.evidence_source_types
                for reference in outcome.evidence
            ):
                raise ValueError("criterion evaluator returned invalid frozen evidence")

    def _quality_status(
        self,
        reference: AssessmentVersionReference,
        reason_code: str,
        outcomes: Iterable[EvaluatorOutcome],
    ) -> str:
        evidence = tuple(reference for outcome in outcomes for reference in outcome.evidence)
        try:
            decision = self.quality_port.review(
                assessment=reference,
                reason_code=reason_code,
                evidence=evidence,
            )
        except Exception:
            return "FAULTED"
        return decision.value if decision is not None else "UNAVAILABLE"

    def _record_fault(self, attempt_id: str, reason_code: str) -> None:
        attempt = self.session.get(AssessmentAttempt, attempt_id)
        if attempt is None:
            raise AssessmentEvaluationNotFoundError("assessment attempt was not found")
        attempt.state = AssessmentAttemptState.FAULTED
        attempt.fault_reason = (
            "Assessment evaluation could not complete. The response is retained for review."
        )
        self._audit(
            "assessment_evaluation.faulted",
            attempt,
            {"reason_code": reason_code},
            outcome="failure",
        )
        self.session.commit()

    def _audit(
        self,
        action: str,
        attempt: AssessmentAttempt,
        details: dict[str, object],
        *,
        outcome: str = "success",
    ) -> None:
        self.session.add(
            PlatformAuditEvent(
                actor_id=None,
                action=action,
                resource_type="assessment_attempt",
                resource_id=attempt.id,
                correlation_id=self.correlation_id,
                outcome=outcome,
                details={"course_id": attempt.course_id, **details},
            )
        )

    @staticmethod
    def _result(decision: AssessmentDecision, *, replayed: bool) -> AssessmentEvaluationResult:
        assert decision.result is not None
        return AssessmentEvaluationResult(
            decision_id=decision.id,
            result=decision.result,
            result_state=decision.result_state,
            reason_code=decision.system_reason,
            replayed=replayed,
        )


@dataclass(frozen=True)
class _EvaluationBundle:
    response: SubmissionAttempt
    definition: AssessmentDefinitionVersion
    form: TaskFormVersion
    bloom: BloomTargetVersion
    rule: PassRuleVersion
    criteria: tuple[CriterionVersion, ...]
    reference: AssessmentVersionReference
