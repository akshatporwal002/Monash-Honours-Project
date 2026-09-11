"""Progress keeps observed activity, uncertain estimates and released results separate."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from app.domain.assessment import AssessmentResult
from app.domain.platform_enums import InferenceStatus, LearnerModelDimension
from app.schemas.activity_continuation import ActivityHistory
from app.services.learner_model.contracts import LearnerModelEvidenceSignal
from app.services.learner_model.safety import require_safe_claim_text


def _utc_instant(value: datetime) -> datetime:
    # These progress sources store UTC. SQLite reloads their DateTime columns
    # without tzinfo; restore that meaning without changing the recorded instant.
    # Aware values must be converted, not relabelled (including non-UTC offsets).
    if value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


ProgressTimestamp = Annotated[
    datetime,
    AfterValidator(_utc_instant),
    Field(description="Recorded instant serialized with an explicit UTC offset."),
]


class ProgressContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProgressObservation(ProgressContract):
    evidence_id: str
    task_id: str
    response_id: str | None
    kind: str
    support_level: int
    occurred_at: ProgressTimestamp
    confidence: float | str | None = None


class ProgressEvidenceLink(ProgressContract):
    evidence_id: str
    relation: str


class ProgressEstimate(ProgressContract):
    snapshot_id: str
    prior_snapshot_id: str | None
    estimate_id: str
    dimension: str
    status: str
    uncertainty: float
    reason: str
    occurred_at: ProgressTimestamp
    evidence: list[ProgressEvidenceLink]


class ProgressResult(ProgressContract):
    response_id: str
    task_id: str
    result: AssessmentResult | None
    status: str
    occurred_at: ProgressTimestamp


class ProgressChoice(ActivityHistory):
    created_at: ProgressTimestamp


class ProgressAdaptation(ProgressContract):
    workflow_id: str
    state: str
    reason: str
    uncertainty: float
    snapshot_id: str | None
    evidence_ids: list[str]
    occurred_at: ProgressTimestamp
    choices: list[ProgressChoice]


class ProgressOutcome(ProgressContract):
    definition_version_id: str
    result: AssessmentResult | None
    status: str
    selection_rule: str | None
    evidence_response_ids: list[str]
    explanation: str


class ProgressScopeRead(ProgressContract):
    learner_id: int
    learner_name: str
    outcome_id: str
    outcome_title: str
    observations: dict[str, int]
    weekly_observations: dict[str, dict[str, int]]
    independent_responses: int
    supported_responses: int
    recent_evidence: list[ProgressObservation]
    estimates: list[ProgressEstimate]
    results: list[ProgressResult]
    outcome_results: list[ProgressOutcome]
    adaptations: list[ProgressAdaptation]
    misconception_ids: list[str]
    snapshot_version: int = 0
    indicators: list["ProgressIndicator"] = Field(default_factory=list)
    indicator_evidence_truncated: bool = False


class ProgressIndicator(ProgressContract):
    id: str
    kind: Literal["feedback_revision", "feedback_transfer", "question_clarification"]
    status: Literal["REVIEW_REQUIRED"] = "REVIEW_REQUIRED"
    explanation: str
    evidence_ids: list[str]
    occurred_at: ProgressTimestamp
    uncertainty: float = 1
    rule_version: str = "progress-indicators.v1"


class ProfileReviewRequest(ProgressContract):
    expected_version: int = Field(ge=0)
    dimension: LearnerModelDimension
    status: InferenceStatus
    uncertainty: float = Field(ge=0, le=1, allow_inf_nan=False)
    reason: str = Field(min_length=10, max_length=500)
    evidence: list[LearnerModelEvidenceSignal] = Field(min_length=1, max_length=30)
    idempotency_key: str = Field(min_length=1, max_length=100)

    @field_validator("reason")
    @classmethod
    def safe_reason(cls, value):
        return require_safe_claim_text(value.strip())

    @field_validator("evidence")
    @classmethod
    def unique_evidence(cls, value):
        if len({item.evidence_id for item in value}) != len(value):
            raise ValueError("Evidence references must be distinct")
        return value


class ProfileReviewReceipt(ProgressContract):
    snapshot_id: str
    version: int
    created: bool


class LearningProgressPage(ProgressContract):
    course_id: str
    course_title: str
    generated_at: ProgressTimestamp
    cohort_observations: dict[str, int]
    cohort_weekly_observations: dict[str, dict[str, int]]
    cohort_weekly_trends: dict[str, dict[str, int]]
    items: list[ProgressScopeRead]
    next_offset: int | None
    history_limit: int = Field(default=20)


class ProgressEvidenceField(ProgressContract):
    label: str
    text: str


class ProgressEvidenceDetail(ProgressObservation):
    course_id: str
    learner_id: int
    outcome_id: str
    status: str
    fields: list[ProgressEvidenceField]
    related_evidence_ids: list[str]


class ProgressTrendRecord(ProgressContract):
    id: str
    learner_id: int
    learner_name: str
    outcome_id: str
    occurred_at: ProgressTimestamp
    kind: str
    evidence_id: str | None
    task_id: str | None
    response_id: str | None
    workflow_id: str | None
    estimate_id: str | None
    uncertainty: float | None
    reason: str | None
    evidence_ids: list[str]


class ProgressTrendPage(ProgressContract):
    items: list[ProgressTrendRecord]
    next_offset: int | None
