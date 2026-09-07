"""Bounded operational observations, separate from model estimates and results."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.platform_enums import AccessSupportState, EvidenceType, ObservationType


class LiveEvidenceRead(BaseModel):
    evidence_id: str
    task_id: str
    outcome_id: str
    response_version_id: str | None
    source_interaction_id: str | None
    evidence_type: EvidenceType
    observation_type: ObservationType
    access_support_state: AccessSupportState
    instructional_support_level: int
    occurred_at: datetime
    content_digest: str
    related_evidence_ids: list[str]


class LiveEvidencePage(BaseModel):
    items: list[LiveEvidenceRead]
    next_offset: int | None


class FeedbackAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feedback_id: str = Field(min_length=36, max_length=36, pattern=r"^[0-9a-f-]+$")


class FeedbackAcknowledgementRead(BaseModel):
    evidence_id: str
    acknowledged: bool = True
