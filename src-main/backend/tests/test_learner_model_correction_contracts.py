"""Validation proof for learner-model correction boundary contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.platform_enums import CorrectionAction, CorrectionTargetKind
from app.services.learner_model.correction_contracts import (
    CorrectionTarget,
    EducatorCorrectionReviewCommand,
    EducatorCorrectionReviewPayload,
    LearnerAnnotationCommand,
    LearnerAnnotationPayload,
)


def _annotation_values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "annotation_id": "annotation-1",
        "course_id": "course-1",
        "learner_id": "learner-1",
        "outcome_id": "outcome-1",
        "target": {
            "target_kind": CorrectionTargetKind.EVIDENCE,
            "evidence_id": "evidence-1",
        },
        "record_version": 1,
        "actor_reference": "learner-1",
        "correlation_id": "correlation-1",
        "idempotency_key": "annotation-key-1",
        "occurred_at": "2026-08-24T10:00:00+10:00",
        "note": "This evidence does not reflect what I intended.",
    }
    values.update(overrides)
    return values


def _review_values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "review_id": "review-1",
        "annotation_id": "annotation-1",
        "course_id": "course-1",
        "learner_id": "learner-1",
        "outcome_id": "outcome-1",
        "target": {
            "target_kind": CorrectionTargetKind.ESTIMATE,
            "estimate_id": "estimate-1",
        },
        "review_version": 1,
        "expected_latest_review_version": 0,
        "action": CorrectionAction.NEEDS_REVIEW,
        "actor_reference": "educator-1",
        "correlation_id": "correlation-1",
        "idempotency_key": "review-key-1",
        "occurred_at": "2026-08-24T10:05:00+10:00",
        "reason": "More evidence is required before resolving this annotation.",
    }
    values.update(overrides)
    return values


def test_annotation_command_and_payload_are_strict_frozen_read_models() -> None:
    command = LearnerAnnotationCommand.model_validate(_annotation_values())
    payload = LearnerAnnotationPayload.model_validate(_annotation_values())

    assert command.action is CorrectionAction.ANNOTATED
    assert payload.contract_version == "learnlens.learner-annotation.v1"
    assert payload.target.evidence_id == "evidence-1"
    with pytest.raises(ValidationError):
        command.note = "mutated"
    with pytest.raises(ValidationError):
        LearnerAnnotationCommand.model_validate(_annotation_values(unknown_field="unsafe"))


def test_review_command_and_payload_limit_actions_to_educator_decisions() -> None:
    command = EducatorCorrectionReviewCommand.model_validate(_review_values())
    payload = EducatorCorrectionReviewPayload.model_validate(
        _review_values(action=CorrectionAction.ACCEPTED)
    )

    assert command.action is CorrectionAction.NEEDS_REVIEW
    assert payload.action is CorrectionAction.ACCEPTED
    with pytest.raises(ValidationError):
        EducatorCorrectionReviewCommand.model_validate(
            _review_values(action=CorrectionAction.ANNOTATED)
        )
    with pytest.raises(ValidationError):
        LearnerAnnotationCommand.model_validate(
            _annotation_values(action=CorrectionAction.ACCEPTED)
        )


@pytest.mark.parametrize(
    "target",
    (
        {"target_kind": CorrectionTargetKind.EVIDENCE},
        {
            "target_kind": CorrectionTargetKind.EVIDENCE,
            "evidence_id": "evidence-1",
            "estimate_id": "estimate-1",
        },
        {"target_kind": CorrectionTargetKind.EVIDENCE, "estimate_id": "estimate-1"},
        {"target_kind": CorrectionTargetKind.ESTIMATE, "evidence_id": "evidence-1"},
    ),
)
def test_target_requires_exactly_one_identifier_matching_its_kind(
    target: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        CorrectionTarget.model_validate(target)


@pytest.mark.parametrize(
    "field",
    (
        "formal_result",
        "assessment_result",
        "numeric_score",
        "score",
        "research_condition",
        "diagnosis",
        "demographic",
    ),
)
def test_sensitive_or_out_of_scope_fields_are_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        LearnerAnnotationCommand.model_validate(_annotation_values(**{field: "private"}))
    with pytest.raises(ValidationError):
        EducatorCorrectionReviewCommand.model_validate(_review_values(**{field: "private"}))


@pytest.mark.parametrize(
    ("factory", "field"),
    (
        (_annotation_values, "note"),
        (_review_values, "reason"),
    ),
)
@pytest.mark.parametrize("text", ("", "   ", "x" * 2_001))
def test_protected_correction_text_is_non_empty_and_bounded(factory, field: str, text: str) -> None:
    with pytest.raises(ValidationError):
        values = factory(**{field: text})
        if field == "note":
            LearnerAnnotationCommand.model_validate(values)
        else:
            EducatorCorrectionReviewCommand.model_validate(values)


def test_timestamps_are_timezone_aware_and_versions_are_bounded() -> None:
    with pytest.raises(ValidationError):
        LearnerAnnotationCommand.model_validate(
            _annotation_values(occurred_at="2026-08-24T10:00:00")
        )
    with pytest.raises(ValidationError):
        LearnerAnnotationCommand.model_validate(_annotation_values(record_version=0))
    with pytest.raises(ValidationError):
        EducatorCorrectionReviewCommand.model_validate(
            _review_values(expected_latest_review_version=-1)
        )
    with pytest.raises(ValidationError):
        EducatorCorrectionReviewCommand.model_validate(
            _review_values(review_version=3, expected_latest_review_version=1)
        )


@pytest.mark.parametrize(
    "required_field",
    (
        "course_id",
        "learner_id",
        "outcome_id",
        "actor_reference",
        "correlation_id",
        "idempotency_key",
    ),
)
def test_scope_and_trace_identifiers_are_required(required_field: str) -> None:
    values = _annotation_values()
    del values[required_field]

    with pytest.raises(ValidationError):
        LearnerAnnotationCommand.model_validate(values)


def test_learner_note_remains_protected_untrusted_content() -> None:
    note = "I think this wrongly implies a diagnosis and a PASS result."

    command = LearnerAnnotationCommand.model_validate(_annotation_values(note=note))

    assert command.note == note
    assert "note" not in command.target.model_dump()
