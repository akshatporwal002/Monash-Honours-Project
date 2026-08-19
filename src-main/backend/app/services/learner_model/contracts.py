"""Strict, versioned contracts for append-only learner-model snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.domain.platform_enums import (
    EvidenceLinkRelation,
    InferenceStatus,
    LearnerModelDimension,
    ModelSource,
)
from app.schemas.evidence import ContractVersion, OpaqueId, VersionNumber
from app.services.learner_model.safety import require_safe_claim_text

Uncertainty = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
RuleCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    ),
]


class FrozenLearnerModelContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class LearnerModelEvidenceSignal(FrozenLearnerModelContract):
    evidence_id: OpaqueId
    relation: Literal[EvidenceLinkRelation.SUPPORTS, EvidenceLinkRelation.CONTRADICTS]


class LearnerOutcomeEstimatePayload(FrozenLearnerModelContract):
    estimate_id: OpaqueId
    dimension: LearnerModelDimension
    inference_status: InferenceStatus
    uncertainty: Uncertainty
    reason_code: RuleCode
    evidence_observed_at: datetime
    evidence_signals: tuple[LearnerModelEvidenceSignal, ...] = Field(min_length=1)

    @field_validator("reason_code")
    @classmethod
    def reject_banned_reason_codes(cls, value: str) -> str:
        return require_safe_claim_text(value)

    @field_validator("evidence_observed_at")
    @classmethod
    def require_evidence_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("evidence_observed_at must include a timezone")
        return value


class LearnerModelSnapshotPayload(FrozenLearnerModelContract):
    contract_version: Literal["learnlens.learner-model-snapshot.v1"] = (
        "learnlens.learner-model-snapshot.v1"
    )
    snapshot_id: OpaqueId
    course_id: OpaqueId
    learner_id: OpaqueId
    outcome_id: OpaqueId
    prior_snapshot_id: OpaqueId | None = None
    model_source: ModelSource
    model_version: ContractVersion
    rule_version: ContractVersion
    record_version: VersionNumber
    actor_reference: OpaqueId
    agent_reference: OpaqueId | None = None
    correlation_id: OpaqueId
    idempotency_key: OpaqueId
    occurred_at: datetime
    estimates: tuple[LearnerOutcomeEstimatePayload, ...] = Field(min_length=1)

    @field_validator("occurred_at")
    @classmethod
    def require_snapshot_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class LearnerModelBuildCommand(FrozenLearnerModelContract):
    snapshot_id: OpaqueId
    course_id: OpaqueId
    learner_id: OpaqueId
    outcome_id: OpaqueId
    prior_snapshot_id: OpaqueId | None = None
    model_source: ModelSource = ModelSource.RULE_BASED
    model_version: ContractVersion
    rule_version: ContractVersion
    record_version: VersionNumber
    actor_reference: OpaqueId
    agent_reference: OpaqueId | None = None
    reviewed_by_reference: OpaqueId | None = None
    correlation_id: OpaqueId
    idempotency_key: OpaqueId
    occurred_at: datetime
    evidence_signals: tuple[LearnerModelEvidenceSignal, ...] = Field(min_length=1)

    @field_validator("occurred_at")
    @classmethod
    def require_command_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


__all__ = [
    "FrozenLearnerModelContract",
    "LearnerModelBuildCommand",
    "LearnerModelEvidenceSignal",
    "LearnerModelSnapshotPayload",
    "LearnerOutcomeEstimatePayload",
    "RuleCode",
    "Uncertainty",
]
