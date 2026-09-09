"""Public result and review-request contracts exclude private evaluator content."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain.assessment import AssessmentResult, BloomProcess, CriterionDecision

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ResultContract(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class LearnerCriterionRead(ResultContract):
    id: str
    description: str
    evidence_description: str
    mandatory: bool
    decision: CriterionDecision | None = None


class LearnerDecisionEventRead(ResultContract):
    action: str
    at: datetime


class LearnerAppealWrite(ResultContract):
    reason: Reason
    request_kind: Literal["REVIEW", "CORRECTION", "APPEAL"] = "REVIEW"
    idempotency_key: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class AppealResolutionWrite(ResultContract):
    expected_decision_revision: int = Field(ge=0)
    reason: Reason
    learner_notice: Reason


class LearnerAppealRead(ResultContract):
    id: str
    response_version_id: str
    decision_id: str
    request_kind: str
    reason: str
    state: str
    requested_at: datetime
    resolved_at: datetime | None = None
    learner_notice: str | None = None
    decision_revision: int


class LearnerResultRead(ResultContract):
    response_version_id: str
    assessment_attempt_id: str
    decision_id: str | None
    result: AssessmentResult | None
    status: str
    bloom_process: BloomProcess
    outcome: str
    criteria: list[LearnerCriterionRead]
    evidence_response_id: str
    reason: str
    next_action: str
    review_revision: int
    can_request_review: bool
    history: list[LearnerDecisionEventRead]
    requests: list[LearnerAppealRead]
