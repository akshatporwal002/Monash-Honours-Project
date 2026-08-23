"""Strict contracts for learner annotations and educator correction reviews."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.domain.platform_enums import CorrectionAction, CorrectionTargetKind
from app.schemas.evidence import OpaqueId, VersionNumber

ProtectedCorrectionText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000),
]
ReviewVersion = Annotated[int, Field(ge=0, le=2_147_483_647)]


class FrozenCorrectionContract(BaseModel):
    """Immutable boundary model that rejects undeclared and sensitive fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class CorrectionTarget(FrozenCorrectionContract):
    """An explicit reference to exactly one evidence record or model estimate."""

    target_kind: CorrectionTargetKind
    evidence_id: OpaqueId | None = None
    estimate_id: OpaqueId | None = None

    @model_validator(mode="after")
    def require_one_matching_target(self) -> CorrectionTarget:
        if self.target_kind is CorrectionTargetKind.EVIDENCE:
            valid = self.evidence_id is not None and self.estimate_id is None
        else:
            valid = self.estimate_id is not None and self.evidence_id is None
        if not valid:
            raise ValueError("target_kind must identify exactly one matching target")
        return self


class _ScopedCorrectionFields(FrozenCorrectionContract):
    course_id: OpaqueId
    learner_id: OpaqueId
    outcome_id: OpaqueId
    target: CorrectionTarget
    actor_reference: OpaqueId
    correlation_id: OpaqueId
    idempotency_key: OpaqueId
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class _LearnerAnnotationFields(_ScopedCorrectionFields):
    annotation_id: OpaqueId
    record_version: VersionNumber
    action: Literal[CorrectionAction.ANNOTATED] = CorrectionAction.ANNOTATED
    note: ProtectedCorrectionText


class LearnerAnnotationCommand(_LearnerAnnotationFields):
    contract_version: Literal["learnlens.learner-annotation-command.v1"] = (
        "learnlens.learner-annotation-command.v1"
    )


class LearnerAnnotationPayload(_LearnerAnnotationFields):
    contract_version: Literal["learnlens.learner-annotation.v1"] = "learnlens.learner-annotation.v1"


class _EducatorCorrectionReviewFields(_ScopedCorrectionFields):
    review_id: OpaqueId
    annotation_id: OpaqueId
    review_version: VersionNumber
    expected_latest_review_version: ReviewVersion
    action: Literal[
        CorrectionAction.ACCEPTED,
        CorrectionAction.REJECTED,
        CorrectionAction.NEEDS_REVIEW,
    ]
    reason: ProtectedCorrectionText

    @model_validator(mode="after")
    def require_next_review_version(self) -> _EducatorCorrectionReviewFields:
        if self.review_version != self.expected_latest_review_version + 1:
            raise ValueError("review_version must follow expected_latest_review_version")
        return self


class EducatorCorrectionReviewCommand(_EducatorCorrectionReviewFields):
    contract_version: Literal["learnlens.educator-correction-review-command.v1"] = (
        "learnlens.educator-correction-review-command.v1"
    )


class EducatorCorrectionReviewPayload(_EducatorCorrectionReviewFields):
    contract_version: Literal["learnlens.educator-correction-review.v1"] = (
        "learnlens.educator-correction-review.v1"
    )


__all__ = [
    "CorrectionTarget",
    "EducatorCorrectionReviewCommand",
    "EducatorCorrectionReviewPayload",
    "FrozenCorrectionContract",
    "LearnerAnnotationCommand",
    "LearnerAnnotationPayload",
    "ProtectedCorrectionText",
    "ReviewVersion",
]
