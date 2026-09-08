"""Boundary tests for learner annotation and educator review contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.platform_enums import CorrectionAction, CorrectionTargetKind
from app.services.learner_model.correction_contracts import (
    CorrectionTarget,
    EducatorCorrectionReviewCommand,
    EducatorCorrectionReviewRequest,
    LearnerAnnotationCommand,
    LearnerAnnotationRequest,
)


def _target() -> CorrectionTarget:
    return CorrectionTarget(target_kind=CorrectionTargetKind.EVIDENCE, evidence_id="evidence-1")


def _annotation(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "annotation_id": "annotation-1",
        "course_id": "course-1",
        "learner_id": "learner-1",
        "outcome_id": "outcome-1",
        "target": _target(),
        "actor_reference": "learner-1",
        "correlation_id": "correlation-1",
        "idempotency_key": "annotation-key-1",
        "occurred_at": "2026-09-08T12:00:00+00:00",
        "record_version": 1,
        "note": "The recorded context is incomplete.",
    }
    values.update(overrides)
    return values


def test_target_requires_exactly_one_matching_evidence_or_estimate() -> None:
    with pytest.raises(ValidationError):
        CorrectionTarget(target_kind=CorrectionTargetKind.EVIDENCE)
    with pytest.raises(ValidationError):
        CorrectionTarget(
            target_kind=CorrectionTargetKind.EVIDENCE,
            evidence_id="evidence-1",
            estimate_id="estimate-1",
        )
    assert (
        CorrectionTarget(
            target_kind=CorrectionTargetKind.ESTIMATE, estimate_id="estimate-1"
        ).estimate_id
        == "estimate-1"
    )


def test_annotation_contract_is_strict_bounded_and_timezone_aware() -> None:
    assert (
        LearnerAnnotationCommand.model_validate(_annotation()).action is CorrectionAction.ANNOTATED
    )
    for invalid in (
        {"score": 100},
        {"diagnosis": "private"},
        {"demographic_label": "private"},
        {"note": " "},
        {"note": "x" * 2_001},
        {"occurred_at": "2026-09-08T12:00:00"},
    ):
        with pytest.raises(ValidationError):
            LearnerAnnotationCommand.model_validate({**_annotation(), **invalid})


def test_public_annotation_request_cannot_supply_identity_fields() -> None:
    payload = {
        "course_id": "course-1",
        "outcome_id": "outcome-1",
        "target": _target(),
        "note": "I need to add context.",
        "idempotency_key": "annotation-key-1",
        "occurred_at": "2026-09-08T12:00:00+00:00",
    }
    assert LearnerAnnotationRequest.model_validate(payload).course_id == "course-1"
    with pytest.raises(ValidationError):
        LearnerAnnotationRequest.model_validate({**payload, "actor_reference": "learner-1"})


def test_review_contract_accepts_only_educator_outcomes_and_valid_ancestry() -> None:
    values = {
        "review_id": "review-1",
        "annotation_id": "annotation-1",
        "course_id": "course-1",
        "learner_id": "learner-1",
        "outcome_id": "outcome-1",
        "target": _target(),
        "actor_reference": "educator-1",
        "correlation_id": "correlation-1",
        "idempotency_key": "review-key-1",
        "occurred_at": "2026-09-08T12:00:00+00:00",
        "review_version": 1,
        "expected_latest_review_version": 0,
        "action": CorrectionAction.ACCEPTED,
        "reason": "The evidence requires a controlled follow-up.",
    }
    assert (
        EducatorCorrectionReviewCommand.model_validate(values).action is CorrectionAction.ACCEPTED
    )
    for invalid in (
        {"action": CorrectionAction.ANNOTATED},
        {"review_version": 2},
        {"prior_review_id": "review-0"},
        {"reason": " "},
        {"assessment_result": "PASS"},
    ):
        with pytest.raises(ValidationError):
            EducatorCorrectionReviewCommand.model_validate({**values, **invalid})


def test_public_review_request_cannot_supply_actor_or_scope() -> None:
    payload = {
        "annotation_id": "annotation-1",
        "expected_latest_review_version": 0,
        "action": CorrectionAction.NEEDS_REVIEW,
        "reason": "More context is needed.",
        "idempotency_key": "review-key-1",
        "occurred_at": "2026-09-08T12:00:00+00:00",
    }
    assert EducatorCorrectionReviewRequest.model_validate(payload).annotation_id == "annotation-1"
    with pytest.raises(ValidationError):
        EducatorCorrectionReviewRequest.model_validate({**payload, "course_id": "course-1"})
