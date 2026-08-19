"""Strict, versioned Person B evidence contracts without formal-result fields."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.domain.platform_enums import (
    AccessSupportState,
    EvidenceLinkRelation,
    EvidenceProvenance,
    EvidenceType,
    InstructionalSupportLevel,
    ObservationType,
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
ContentDigest = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
ContractVersion = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    ),
]
ProtectedEvidenceContent = Annotated[str, StringConstraints(min_length=1, max_length=65_536)]


class FrozenEvidenceContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class EvidenceArtifact(FrozenEvidenceContract):
    contract_version: Literal["learnlens.evidence-artifact.v1"] = "learnlens.evidence-artifact.v1"
    artifact_id: OpaqueId
    course_id: OpaqueId
    learner_id: OpaqueId
    content: ProtectedEvidenceContent
    content_digest: ContentDigest
    content_format: ContractVersion
    record_version: VersionNumber
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class EvidenceRecord(FrozenEvidenceContract):
    contract_version: Literal["learnlens.evidence-record.v1"] = "learnlens.evidence-record.v1"
    evidence_id: OpaqueId
    course_id: OpaqueId
    learner_id: OpaqueId
    outcome_id: OpaqueId | None = None
    activity_id: OpaqueId
    task_id: OpaqueId
    response_version_id: OpaqueId | None = None
    source_interaction_id: OpaqueId | None = None
    source_version: ContractVersion | None
    task_conditions_version: VersionNumber | None = None
    evidence_type: EvidenceType
    provenance: EvidenceProvenance
    observation_type: ObservationType
    instructional_support_level: InstructionalSupportLevel
    access_support_state: AccessSupportState
    artifact_id: OpaqueId | None = None
    content_digest: ContentDigest
    actor_reference: OpaqueId
    agent_reference: OpaqueId | None = None
    correlation_id: OpaqueId
    schema_version: ContractVersion
    record_version: VersionNumber
    idempotency_key: OpaqueId
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class EvidenceLink(FrozenEvidenceContract):
    contract_version: Literal["learnlens.evidence-link.v1"] = "learnlens.evidence-link.v1"
    evidence_id: OpaqueId
    linked_evidence_id: OpaqueId
    relation: EvidenceLinkRelation
    actor_reference: OpaqueId
    correlation_id: OpaqueId
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class EvidenceRecordReference(FrozenEvidenceContract):
    contract_version: Literal["learnlens.evidence.v1"] = "learnlens.evidence.v1"
    evidence_id: OpaqueId
    course_id: OpaqueId
    evidence_type: EvidenceType
    schema_version: ContractVersion
    record_version: VersionNumber
    content_digest: ContentDigest
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


__all__ = [
    "EvidenceArtifact",
    "EvidenceLink",
    "EvidenceRecord",
    "EvidenceRecordReference",
    "FrozenEvidenceContract",
]
