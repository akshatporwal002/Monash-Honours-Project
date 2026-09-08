"""Strict contracts for protected learner annotations and educator reviews."""

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

from app.domain.platform_enums import (
    CorrectionAction,
    CorrectionTargetKind,
    InferenceStatus,
    LearnerModelDimension,
    ModelSource,
)
from app.schemas.evidence import OpaqueId, VersionNumber

ProtectedCorrectionText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000),
]
ReviewVersion = Annotated[int, Field(ge=0, le=2_147_483_647)]


class FrozenCorrectionContract(BaseModel):
    """Immutable boundary model that rejects undeclared sensitive fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class CorrectionTarget(FrozenCorrectionContract):
    """Explicitly identify one immutable evidence record or estimate."""

    target_kind: CorrectionTargetKind
    evidence_id: OpaqueId | None = None
    estimate_id: OpaqueId | None = None

    @model_validator(mode="after")
    def require_one_matching_target(self) -> "CorrectionTarget":
        valid = (
            self.evidence_id is not None and self.estimate_id is None
            if self.target_kind is CorrectionTargetKind.EVIDENCE
            else self.estimate_id is not None and self.evidence_id is None
        )
        if not valid:
            raise ValueError("target_kind must identify exactly one matching target")
        return self


class LearnerAnnotationRequest(FrozenCorrectionContract):
    """Public actor-free request; route code derives learner and actor identity."""

    course_id: OpaqueId
    outcome_id: OpaqueId
    target: CorrectionTarget
    note: ProtectedCorrectionText
    idempotency_key: OpaqueId
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class EducatorCorrectionReviewRequest(FrozenCorrectionContract):
    """Public actor-free review request; the route supplies educator identity."""

    annotation_id: OpaqueId
    expected_latest_review_version: ReviewVersion
    action: Literal[
        CorrectionAction.ACCEPTED,
        CorrectionAction.REJECTED,
        CorrectionAction.NEEDS_REVIEW,
    ]
    reason: ProtectedCorrectionText
    idempotency_key: OpaqueId
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


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


class LearnerAnnotationCommand(_ScopedCorrectionFields):
    contract_version: Literal["learnlens.learner-annotation-command.v1"] = (
        "learnlens.learner-annotation-command.v1"
    )
    annotation_id: OpaqueId
    record_version: VersionNumber
    action: Literal[CorrectionAction.ANNOTATED] = CorrectionAction.ANNOTATED
    note: ProtectedCorrectionText


class LearnerAnnotationPayload(LearnerAnnotationCommand):
    contract_version: Literal["learnlens.learner-annotation.v1"] = "learnlens.learner-annotation.v1"


class _EducatorCorrectionReviewFields(_ScopedCorrectionFields):
    review_id: OpaqueId
    annotation_id: OpaqueId
    prior_review_id: OpaqueId | None = None
    review_version: VersionNumber
    expected_latest_review_version: ReviewVersion
    action: Literal[
        CorrectionAction.ACCEPTED,
        CorrectionAction.REJECTED,
        CorrectionAction.NEEDS_REVIEW,
    ]
    reason: ProtectedCorrectionText

    @model_validator(mode="after")
    def require_next_review_version(self) -> "_EducatorCorrectionReviewFields":
        if self.review_version != self.expected_latest_review_version + 1:
            raise ValueError("review_version must follow expected_latest_review_version")
        if (self.review_version == 1) != (self.prior_review_id is None):
            raise ValueError("prior_review_id must match review ancestry")
        return self


class EducatorCorrectionReviewCommand(_EducatorCorrectionReviewFields):
    contract_version: Literal["learnlens.educator-correction-review-command.v1"] = (
        "learnlens.educator-correction-review-command.v1"
    )


class EducatorCorrectionReviewPayload(EducatorCorrectionReviewCommand):
    contract_version: Literal["learnlens.educator-correction-review.v1"] = (
        "learnlens.educator-correction-review.v1"
    )


class LearnerModelTimelineEvidence(FrozenCorrectionContract):
    id: OpaqueId
    type: str
    provenance: str
    occurred_at: datetime


class LearnerModelTimelineEstimate(FrozenCorrectionContract):
    estimate_id: OpaqueId
    dimension: LearnerModelDimension
    inference_status: InferenceStatus
    uncertainty: float = Field(ge=0, le=1)
    reason_code: str
    evidence_observed_at: datetime
    evidence_links: list[list[str]]


class LearnerModelTimelineSnapshot(FrozenCorrectionContract):
    snapshot_id: OpaqueId
    prior_snapshot_id: OpaqueId | None = None
    record_version: VersionNumber
    model_source: ModelSource
    model_version: str
    rule_version: str
    occurred_at: datetime
    validation_classification: str
    estimates: list[LearnerModelTimelineEstimate]


class LearnerModelTimelineCorrection(FrozenCorrectionContract):
    annotation: LearnerAnnotationPayload
    reviews: list[EducatorCorrectionReviewPayload]


class LearnerModelTimelineEntry(FrozenCorrectionContract):
    """A cursor-addressable transition; details remain in the typed projections."""

    entry_type: Literal["OBSERVATION", "INFERENCE", "ANNOTATION", "REVIEW"]
    reference_id: OpaqueId
    occurred_at: datetime


class LearnerModelTimelineResponse(FrozenCorrectionContract):
    """Role-safe metadata projection; it deliberately excludes evidence artefacts."""

    evidence: list[LearnerModelTimelineEvidence]
    snapshots: list[LearnerModelTimelineSnapshot]
    corrections: list[LearnerModelTimelineCorrection]
    entries: list[LearnerModelTimelineEntry]
    next_cursor: str | None = None


__all__ = [
    "CorrectionTarget",
    "EducatorCorrectionReviewCommand",
    "EducatorCorrectionReviewPayload",
    "EducatorCorrectionReviewRequest",
    "FrozenCorrectionContract",
    "LearnerAnnotationCommand",
    "LearnerAnnotationPayload",
    "LearnerAnnotationRequest",
    "LearnerModelTimelineCorrection",
    "LearnerModelTimelineEntry",
    "LearnerModelTimelineEstimate",
    "LearnerModelTimelineEvidence",
    "LearnerModelTimelineResponse",
    "LearnerModelTimelineSnapshot",
    "ProtectedCorrectionText",
    "ReviewVersion",
]
