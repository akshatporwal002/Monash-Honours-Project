"""Progress keeps observed activity, uncertain estimates and released results separate."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.assessment import AssessmentResult
from app.schemas.activity_continuation import ActivityHistory


class ProgressContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProgressObservation(ProgressContract):
    evidence_id: str
    task_id: str
    response_id: str | None
    kind: str
    support_level: int
    occurred_at: datetime
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
    occurred_at: datetime
    evidence: list[ProgressEvidenceLink]


class ProgressResult(ProgressContract):
    response_id: str
    task_id: str
    result: AssessmentResult | None
    status: str
    occurred_at: datetime


class ProgressAdaptation(ProgressContract):
    workflow_id: str
    state: str
    reason: str
    uncertainty: float
    snapshot_id: str | None
    evidence_ids: list[str]
    occurred_at: datetime
    choices: list[ActivityHistory]


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


class LearningProgressPage(ProgressContract):
    course_id: str
    course_title: str
    generated_at: datetime
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
    occurred_at: datetime
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
