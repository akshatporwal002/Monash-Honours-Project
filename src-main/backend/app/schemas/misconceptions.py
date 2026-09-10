"""Human-reviewed learning checks, separate from formal assessment."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.domain.assessment import MisconceptionState
from app.domain.platform_enums import InstructionalSupportLevel

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Reference = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
State = MisconceptionState
Stage = Literal["PROBE", "REVISION", "TRANSFER"]


class MisconceptionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_key: Reference


class MisconceptionOpen(MisconceptionWrite):
    feedback_id: Reference
    hypothesis: Text
    confidence: float = Field(ge=0, lt=1, allow_inf_nan=False)
    evidence_ids: list[Reference] = Field(min_length=1, max_length=20)
    probe: Text
    explanation: Text
    explanation_support_level: InstructionalSupportLevel = Field(ge=1, le=5)
    fresh_question: Text
    selection_reason: Text
    content_approval_reason: Text
    persistence_stages: list[Stage] = Field(min_length=2, max_length=3)

    @model_validator(mode="after")
    def distinct_stages(self):
        if len(set(self.persistence_stages)) != len(self.persistence_stages):
            raise ValueError("Choose distinct stages for the evidence rule")
        return self


class MisconceptionAnswer(MisconceptionWrite):
    expected_version: int = Field(ge=0)
    stage: Stage
    answer: Text
    reasoning: Text
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    help_used: bool
    start_fresh_check: bool = False

    @model_validator(mode="after")
    def explicit_fresh_start(self):
        if self.start_fresh_check != (self.stage == "REVISION"):
            raise ValueError("Saving the revision requires an explicit fresh-check start")
        return self


class MisconceptionExit(MisconceptionWrite):
    expected_version: int = Field(ge=0)
    reason: Text
    disposition: Literal["DEFERRED", "INVALIDATED"]


class MisconceptionReview(MisconceptionWrite):
    expected_version: int = Field(ge=0)
    state: State
    confidence: float = Field(ge=0, lt=1, allow_inf_nan=False)
    supports: list[Reference] = Field(default_factory=list, max_length=20)
    contradicts: list[Reference] = Field(default_factory=list, max_length=20)
    reason: Text
    next_action: Text

    @model_validator(mode="after")
    def require_distinct_evidence(self):
        all_ids = self.supports + self.contradicts
        if len(set(all_ids)) != len(all_ids) or not all_ids:
            raise ValueError("Choose distinct evidence and give each item one relation")
        return self


class MisconceptionResponseRead(BaseModel):
    id: str
    evidence_id: str
    version: int
    stage: Stage
    answer: str
    reasoning: str
    confidence: float
    help_used: bool
    created_at: datetime


class MisconceptionReviewRead(BaseModel):
    id: str
    version: int
    actor_id: int
    state: State
    confidence: float
    supports: list[str]
    contradicts: list[str]
    reason: str
    next_action: str
    evidence_id: str
    snapshot_id: str
    escalation_id: str | None
    created_at: datetime


class MisconceptionClosureRead(BaseModel):
    disposition: Literal["DEFERRED", "INVALIDATED"]
    reason: str
    actor_id: int
    created_at: datetime


class MisconceptionRead(BaseModel):
    id: str
    task_id: str
    course_id: str
    outcome_id: str
    student_id: int
    hypothesis: str
    evidence_ids: list[str]
    selection_reason: str
    content_approval_reason: str
    approved_by: int
    approved_at: datetime
    version: int
    state: State
    confidence: float
    next_stage: Stage | None
    probe: str | None
    explanation: str | None
    fresh_question: str | None
    responses: list[MisconceptionResponseRead]
    reviews: list[MisconceptionReviewRead]
    persistence_stages: list[Stage]
    closure: MisconceptionClosureRead | None
    teaching_available: bool
    initial_evidence: list["MisconceptionEvidenceRead"]


class MisconceptionEvidenceRead(BaseModel):
    id: str
    kind: str
    content: str


class MisconceptionCandidateRead(BaseModel):
    feedback_id: str
    task_id: str
    student_id: int
    student_name: str
    course_title: str
    task_title: str
    response: str
    evidence: list[MisconceptionEvidenceRead]
