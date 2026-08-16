"""Safety-contract tests for non-diagnostic learner-model inference."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.platform_enums import (
    EvidenceLinkRelation,
    InferenceStatus,
    LearnerModelDimension,
    ModelSource,
)
from app.services.learner_model.contracts import (
    LearnerModelEvidenceSignal,
    LearnerModelSnapshotPayload,
    LearnerOutcomeEstimatePayload,
)
from app.services.learner_model.safety import (
    LearnerModelReviewRequiredError,
    LearnerModelSafetyError,
    reject_banned_fields,
    require_human_review_for_model_source,
    require_safe_claim_text,
)


def _estimate(**overrides: object) -> LearnerOutcomeEstimatePayload:
    values: dict[str, object] = {
        "estimate_id": "estimate-1",
        "dimension": LearnerModelDimension.REASONING_STRENGTH,
        "inference_status": InferenceStatus.UNCERTAIN,
        "uncertainty": 0.8,
        "reason_code": "rule.reasoning_strength.v1",
        "evidence_observed_at": "2026-08-16T12:00:00+00:00",
        "evidence_signals": (
            LearnerModelEvidenceSignal(
                evidence_id="evidence-1",
                relation=EvidenceLinkRelation.SUPPORTS,
            ),
        ),
    }
    values.update(overrides)
    return LearnerOutcomeEstimatePayload.model_validate(values)


@pytest.mark.parametrize(
    "unsafe",
    (
        "diagnosis.adhd.v1",
        "disability.dyslexia.v1",
        "neurodivergent.autism.v1",
        "medical.condition.v1",
        "demographic.group.v1",
        "psychological.trait.v1",
        "motivation.low.v1",
        "fixed-ability.low.v1",
        "learning-style.visual.v1",
    ),
)
def test_banned_claim_categories_are_rejected(unsafe: str) -> None:
    with pytest.raises(LearnerModelSafetyError):
        require_safe_claim_text(unsafe)
    with pytest.raises(ValidationError):
        _estimate(reason_code=unsafe)


def test_strict_contract_rejects_grade_result_and_unsafe_extra_fields() -> None:
    values: dict[str, object] = {
        "snapshot_id": "snapshot-1",
        "course_id": "course-1",
        "learner_id": "learner-1",
        "outcome_id": "outcome-1",
        "model_source": ModelSource.RULE_BASED,
        "model_version": "learner-model-rules.v1",
        "rule_version": "learner-rules.v1",
        "record_version": 1,
        "actor_reference": "learner-1",
        "correlation_id": "correlation-1",
        "idempotency_key": "idempotency-1",
        "occurred_at": "2026-08-16T12:00:00+00:00",
        "estimates": (_estimate(),),
    }
    for forbidden in (
        {"score": 100},
        {"assessment_result": "PASS"},
        {"diagnosis": "private"},
        {"learning_style": "visual"},
    ):
        with pytest.raises(ValidationError):
            LearnerModelSnapshotPayload.model_validate({**values, **forbidden})
    with pytest.raises(LearnerModelSafetyError):
        reject_banned_fields({"demographic_label": "private"})


def test_non_rule_sources_require_an_explicit_human_review_threshold() -> None:
    require_human_review_for_model_source(ModelSource.RULE_BASED, None)
    require_human_review_for_model_source(ModelSource.ADVISORY_MODEL, "educator-1")
    with pytest.raises(LearnerModelReviewRequiredError):
        require_human_review_for_model_source(ModelSource.ADVISORY_MODEL, None)
