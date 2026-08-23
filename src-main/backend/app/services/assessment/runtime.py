"""Configured assessment evaluation adapters for production and workers."""

from __future__ import annotations

from datetime import UTC

from sqlalchemy.orm import Session

from app.domain.assessment import AssessmentReasonCode, BloomProcess, QualityReviewDecision
from app.models.assessment import CriterionEvaluatorType, CriterionVersion
from app.models.lms import SubmissionAttempt
from app.schemas.assessment import AssessmentVersionReference, EvidenceReference
from app.services.assessment.evaluation import (
    AssessmentEvaluationService,
    CriterionEvaluationUnavailableError,
)
from app.services.assessment.evaluators import (
    CriterionEvaluationRequest,
    EvaluatorOutcome,
    RuleCriterionEvaluator,
)


class SqlAlchemyRuleCriterionEvaluationPort:
    """Evaluate approved rule criteria against one immutable response record."""

    def __init__(self, session: Session) -> None:
        self._session = session

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
