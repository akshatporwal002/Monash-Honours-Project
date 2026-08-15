"""Frozen Person A assessment contracts for Person B and API clients."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.domain.assessment import (
    AssessmentPurpose,
    AssessmentResult,
    BloomKnowledge,
    BloomProcess,
    CriterionDecision,
    MisconceptionState,
    QualityReviewDecision,
    ResultState,
    SubmissionState,
)

OpaqueId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=255,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
VersionNumber = Annotated[int, Field(ge=1, le=2_147_483_647)]
ContractVersion = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    ),
]
EvidenceType = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z][a-z0-9._-]*$",
    ),
]
ContentDigest = Annotated[
    str,
    StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$"),
]
ReasonCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    ),
]
ReferenceField = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z][a-z0-9_]*$",
    ),
]


class FrozenAssessmentContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class AssessmentVersionReference(FrozenAssessmentContract):
    course_id: OpaqueId
    assessment_definition_id: OpaqueId
    assessment_definition_version: VersionNumber
    outcome_id: OpaqueId
    outcome_version: VersionNumber
    bloom_target_id: OpaqueId
    bloom_target_version: VersionNumber
    criterion_set_id: OpaqueId
    criterion_set_version: VersionNumber
    pass_rule_id: OpaqueId
    pass_rule_version: VersionNumber
    task_id: OpaqueId
    task_form_version: VersionNumber
    assessment_attempt_id: OpaqueId
    response_version_id: OpaqueId


class EvidenceReference(FrozenAssessmentContract):
    contract_version: Literal["learnlens.assessment-evidence.v1"] = (
        "learnlens.assessment-evidence.v1"
    )
    assessment: AssessmentVersionReference
    evidence_id: OpaqueId
    evidence_type: EvidenceType
    schema_version: ContractVersion
    record_version: VersionNumber
    content_digest: ContentDigest
    source_record_id: OpaqueId
    source_record_version: VersionNumber
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class ResolvedEvidenceReference(FrozenAssessmentContract):
    status: Literal["RESOLVED"] = "RESOLVED"
    reference: EvidenceReference


class MissingEvidenceReference(FrozenAssessmentContract):
    status: Literal["MISSING"] = "MISSING"
    assessment: AssessmentVersionReference
    evidence_id: OpaqueId
    reason_code: ReasonCode


class StaleEvidenceReference(FrozenAssessmentContract):
    status: Literal["STALE"] = "STALE"
    reference: EvidenceReference
    mismatched_fields: Annotated[tuple[ReferenceField, ...], Field(min_length=1, max_length=32)]
    reason_code: ReasonCode


class ConflictingEvidenceReference(FrozenAssessmentContract):
    status: Literal["CONFLICT"] = "CONFLICT"
    assessment: AssessmentVersionReference
    evidence_ids: Annotated[tuple[OpaqueId, ...], Field(min_length=2, max_length=32)]
    reason_code: ReasonCode


class AccessDeniedEvidenceReference(FrozenAssessmentContract):
    status: Literal["ACCESS_DENIED"] = "ACCESS_DENIED"
    assessment: AssessmentVersionReference
    reference_id: OpaqueId
    reason_code: ReasonCode


class InvalidEvidenceReference(FrozenAssessmentContract):
    status: Literal["INVALID"] = "INVALID"
    reference_id: OpaqueId | None = None
    reason_code: ReasonCode


EvidenceReferenceResolution: TypeAlias = Annotated[
    ResolvedEvidenceReference
    | MissingEvidenceReference
    | StaleEvidenceReference
    | ConflictingEvidenceReference
    | AccessDeniedEvidenceReference
    | InvalidEvidenceReference,
    Field(discriminator="status"),
]


class EvidenceReferenceResolutionEnvelope(FrozenAssessmentContract):
    resolution: EvidenceReferenceResolution


class FormalResultSummary(FrozenAssessmentContract):
    contract_version: Literal["learnlens.formal-result-summary.v1"] = (
        "learnlens.formal-result-summary.v1"
    )
    course_id: OpaqueId
    assessment_definition_id: OpaqueId
    assessment_attempt_id: OpaqueId
    response_version_id: OpaqueId
    decision_id: OpaqueId | None = None
    result: AssessmentResult | None = None
    result_state: ResultState
    reason_code: ReasonCode | None = None
    decided_at: datetime | None = None
    assessor_reviewed_at: datetime | None = None

    @field_validator("decided_at", "assessor_reviewed_at")
    @classmethod
    def require_optional_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("result timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_result_lifecycle(self) -> FormalResultSummary:
        if self.result_state is ResultState.NOT_ASSESSED:
            if any(
                value is not None
                for value in (self.decision_id, self.result, self.reason_code, self.decided_at)
            ):
                raise ValueError("NOT_ASSESSED cannot contain a decision or result")
            if self.assessor_reviewed_at is not None:
                raise ValueError("NOT_ASSESSED cannot contain an assessor review time")
            return self

        if self.decision_id is None or self.result is None or self.decided_at is None:
            raise ValueError("assessed states require a decision, result, and decision time")

        reviewed_states = {ResultState.CONFIRMED, ResultState.OVERRIDDEN, ResultState.VOID}
        if self.result_state in reviewed_states and self.assessor_reviewed_at is None:
            raise ValueError("reviewed result states require an assessor review time")
        return self


def legacy_judge_decision_to_quality_review(
    value: str | Enum,
) -> QualityReviewDecision:
    """Map stored legacy judge values without accepting them as learner results."""

    raw_value = value.value if isinstance(value, Enum) else value
    mapping = {
        "pass": QualityReviewDecision.APPROVED,
        "fail": QualityReviewDecision.REJECTED,
    }
    try:
        return mapping[raw_value]
    except KeyError:
        raise ValueError("unsupported legacy Quality Judge decision") from None


ASSESSMENT_CONTRACT_TYPES: tuple[type[object], ...] = (
    AssessmentResult,
    ResultState,
    SubmissionState,
    AssessmentPurpose,
    BloomProcess,
    BloomKnowledge,
    CriterionDecision,
    MisconceptionState,
    QualityReviewDecision,
    AssessmentVersionReference,
    EvidenceReference,
    ResolvedEvidenceReference,
    MissingEvidenceReference,
    StaleEvidenceReference,
    ConflictingEvidenceReference,
    AccessDeniedEvidenceReference,
    InvalidEvidenceReference,
    EvidenceReferenceResolutionEnvelope,
    FormalResultSummary,
)


__all__ = [
    "ASSESSMENT_CONTRACT_TYPES",
    "AccessDeniedEvidenceReference",
    "AssessmentPurpose",
    "AssessmentResult",
    "AssessmentVersionReference",
    "BloomKnowledge",
    "BloomProcess",
    "ConflictingEvidenceReference",
    "CriterionDecision",
    "EvidenceReference",
    "EvidenceReferenceResolution",
    "EvidenceReferenceResolutionEnvelope",
    "FormalResultSummary",
    "InvalidEvidenceReference",
    "MisconceptionState",
    "MissingEvidenceReference",
    "QualityReviewDecision",
    "ResolvedEvidenceReference",
    "ResultState",
    "StaleEvidenceReference",
    "SubmissionState",
    "legacy_judge_decision_to_quality_review",
]
