"""Configured assessment evaluation adapters for production and workers."""

from __future__ import annotations

from datetime import UTC

from sqlalchemy.orm import Session

from app.domain.assessment import (
    AssessmentReasonCode,
    BloomProcess,
    CriterionDecision,
    QualityReviewDecision,
)
from app.models.assessment import CriterionEvaluatorType, CriterionVersion
from app.models.lms import SubmissionAttempt
from app.schemas.assessment import AssessmentVersionReference, EvidenceReference
from app.services.assessment.circuit_rules import CircuitRuleSettings, evaluate_circuit_structure
from app.services.assessment.evaluation import (
    AssessmentEvaluationService,
    CriterionEvaluationUnavailableError,
)
from app.services.assessment.evaluators import (
    CriterionEvaluationRequest,
    EvaluatorOutcome,
    RuleCriterionEvaluator,
)
from app.services.assessment.evidence import FrozenEvidenceValidator
from app.services.assessment.response_evidence import ResponseEvidenceResolver
from app.services.assessment.rule_settings import validate_rule_settings
from app.services.episode_contract import FrozenResponseError, FrozenResponseReader
from app.services.evidence.assessment_port import AssessmentEvidencePort


class SqlAlchemyRuleCriterionEvaluationPort:
    """Evaluate approved rule criteria against one immutable response record."""

    def __init__(self, session: Session, *, reader: FrozenResponseReader | None = None) -> None:
        self._session = session
        self._reader = reader

    def evaluate(
        self,
        *,
        assessment: AssessmentVersionReference,
        response_text: str,
        bloom_process: BloomProcess,
        criterion: CriterionVersion,
    ) -> EvaluatorOutcome:
        if criterion.evaluator_type is not CriterionEvaluatorType.RULES:
            raise CriterionEvaluationUnavailableError(
                "this criterion requires an approved human or validated evaluator"
            )
        if criterion.critical_error_rules:
            raise CriterionEvaluationUnavailableError(
                "critical errors require explicit phrase exclusions or human assessment"
            )
        try:
            settings = validate_rule_settings(criterion.approved_anchors, bloom_process)
        except ValueError as error:
            raise CriterionEvaluationUnavailableError(
                "invalid rule settings require human assessment"
            ) from error
        if isinstance(settings, CircuitRuleSettings):
            return self._circuit(assessment, criterion, settings)
        response = self._session.get(SubmissionAttempt, assessment.response_version_id)
        if (
            response is None
            or response.id != assessment.response_version_id
            or response.task_id != assessment.task_id
            or response.answer != response_text
            or not response.response_schema_version
            or not response.content_digest
        ):
            raise ValueError("the frozen learner response is unavailable or stale")
        occurred_at = response.submitted_at
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)
        evidence = EvidenceReference(
            assessment=assessment,
            evidence_id=response.id,
            evidence_type="learner_response",
            schema_version=response.response_schema_version,
            record_version=1,
            content_digest=response.content_digest,
            source_record_id=response.id,
            source_record_version=1,
            occurred_at=occurred_at,
        )
        return RuleCriterionEvaluator().evaluate(
            CriterionEvaluationRequest(
                response_text=response_text,
                bloom_process=bloom_process,
                approved_anchors=criterion.approved_anchors,
                evidence=(evidence,),
            )
        )

    def _circuit(self, assessment, criterion, settings):
        if self._reader is None:
            from app.services.episode_responses import SqlAlchemyFrozenResponseReader

            self._reader = SqlAlchemyFrozenResponseReader(self._session)
        try:
            response = self._reader.read(assessment=assessment)
            evidence = FrozenEvidenceValidator().resolve_and_validate(
                AssessmentEvidencePort(ResponseEvidenceResolver(self._reader, self._session)),
                assessment=assessment,
                evidence_ids=(response.reference.evidence_id,),
                allowed_types=criterion.evidence_source_types,
            )
            if settings.stage == "supported":
                circuit = response.content.circuit
            else:
                circuit = (
                    response.episode.transfer.content.circuit
                    if response.episode and response.episode.transfer
                    else None
                )
            decision, reason = evaluate_circuit_structure(settings, circuit)
        except (FrozenResponseError, ValueError) as error:
            raise CriterionEvaluationUnavailableError(
                "Frozen circuit evidence requires human review"
            ) from error
        if decision is CriterionDecision.NOT_EVALUABLE:
            raise CriterionEvaluationUnavailableError(reason)
        return EvaluatorOutcome(
            decision=decision,
            reason=reason,
            evidence=evidence,
            evaluator_type=CriterionEvaluatorType.RULES,
            evaluator_reference="rules.circuit-structure.v1",
        )


class AdvisoryAssessmentQualityReviewPort:
    """Keep automated assessment quality review unavailable until D-07 is approved."""

    def review(
        self,
        *,
        assessment: AssessmentVersionReference,
        reason_code: AssessmentReasonCode,
        evidence: tuple[EvidenceReference, ...],
    ) -> QualityReviewDecision | None:
        del assessment, reason_code, evidence
        return None


def build_assessment_evaluation_service(
    session: Session,
    correlation_id: str,
) -> AssessmentEvaluationService:
    return AssessmentEvaluationService(
        session,
        criterion_port=SqlAlchemyRuleCriterionEvaluationPort(session),
        quality_port=AdvisoryAssessmentQualityReviewPort(),
        correlation_id=correlation_id,
        retain_pending_on_fault=True,
    )


__all__ = [
    "AdvisoryAssessmentQualityReviewPort",
    "SqlAlchemyRuleCriterionEvaluationPort",
    "build_assessment_evaluation_service",
]
