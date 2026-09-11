"""Typed operational moderation and validation contracts; no learner exposure."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.domain.assessment import AssessmentResult, CriterionDecision, ResultState

ModerationStage = Literal["ORIGINAL", "SECOND", "RESOLUTION", "DRIFT", "DRIFT_RESOLUTION"]
ModerationAction = Literal[
    "ORIGINAL", "SECOND", "RESOLUTION", "DRIFT", "DRIFT_RESOLUTION", "CORRECTION"
]
ModerationState = Literal[
    "ORIGINAL_REQUIRED",
    "SECOND_REQUIRED",
    "DISAGREEMENT",
    "DRIFT_REQUIRED",
    "DRIFT_DISAGREEMENT",
    "READY",
    "NOT_SAMPLED",
]


class ModerationCriterionRead(BaseModel):
    criterion_version_id: str
    decision: CriterionDecision
    reason: str
    evidence_ids: list[str]


class ModerationHistoryRead(BaseModel):
    stage: ModerationStage
    cycle: int
    actor_id: int
    result: AssessmentResult
    reason: str
    criteria: list[ModerationCriterionRead]
    created_at: datetime


class ModerationRecordRead(BaseModel):
    attempt_id: str
    cycle: int
    task_family: str
    sequence: int
    policy_id: str
    drift_check: bool
    state: ModerationState
    formal_state: ResultState | None
    result: AssessmentResult | None
    next_stage: ModerationAction | None
    history_withheld: bool
    history: list[ModerationHistoryRead]


class ModerationQueueRead(BaseModel):
    policy_status: Literal["CONFIGURED", "POLICY_REQUIRED"]
    records: list[ModerationRecordRead]


class ModerationPolicyReceipt(BaseModel):
    policy_id: str
    version: int


class ModerationReviewReceipt(BaseModel):
    review_id: str
    stage: ModerationStage
    result: AssessmentResult


class EvaluatorValidationStatusRead(BaseModel):
    state: Literal["PENDING", "VALIDATED", "INVALIDATED"]
    validation_id: str | None
    fingerprint: str
    reason: str
    ai_activation: Literal["PENDING", "RELEASED"]


class EvaluatorValidationReceipt(BaseModel):
    validation_id: str
    state: Literal["VALIDATED"]
    ai_activation: Literal["PENDING"]
