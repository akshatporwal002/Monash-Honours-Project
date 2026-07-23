from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models.enums import (
    ExperimentalCondition,
    FeedbackStatus,
    JudgeDecision,
    JudgeEvaluationStatus,
    LearningEventType,
    ResearchStatus,
    WorkflowOutcome,
    WorkflowStage,
)


ExternalId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
ShortLabel = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
UuidString = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$",
    ),
]
Score = Annotated[int, Field(ge=0, le=100)]
NonNegativeInt = Annotated[int, Field(ge=0)]
NonNegativeDecimal = Annotated[Decimal, Field(ge=0)]

ALLOWED_LEARNING_EVENT_METADATA_KEYS = frozenset(
    {
        "attempt_number",
        "completion_status",
        "duration_ms",
        "feedback_status",
        "score",
        "source",
    }
)
SENSITIVE_METADATA_KEYS = frozenset(
    {
        "access_token",
        "answer",
        "api_key",
        "email",
        "name",
        "prompt",
        "raw_answer",
        "submitted_answer",
        "token",
    }
)


def _normalise_sqlite_datetime(value: Any) -> Any:
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class PersistenceSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        populate_by_name=True,
        strict=True,
    )


class WorkflowRunCreate(PersistenceSchema):
    submission_id: ExternalId
    current_stage: WorkflowStage = WorkflowStage.PENDING
    regeneration_count: Annotated[int, Field(ge=0, le=1)] = 0
    final_outcome: WorkflowOutcome | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    @field_validator("started_at", "completed_at", mode="before")
    @classmethod
    def normalise_timestamps(cls, value: Any) -> Any:
        return _normalise_sqlite_datetime(value)

    @model_validator(mode="after")
    def validate_terminal_state(self) -> "WorkflowRunCreate":
        terminal = self.current_stage in {WorkflowStage.COMPLETED, WorkflowStage.FAILED}
        if terminal != (self.final_outcome is not None and self.completed_at is not None):
            raise ValueError("terminal workflows require both final_outcome and completed_at")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be earlier than started_at")
        return self


class WorkflowRunRead(WorkflowRunCreate):
    id: UuidString


class FeedbackRecordCreate(PersistenceSchema):
    submission_id: ExternalId
    workflow_run_id: UuidString
    feedback_content: dict[str, JsonValue]
    status: FeedbackStatus = FeedbackStatus.PENDING_JUDGEMENT
    generation_attempt: Annotated[int, Field(ge=1, le=2)] | None = None
    provider: ShortLabel | None = None
    model: ExternalId | None = None
    prompt_version: ShortLabel | None = None
    source_references: list[ExternalId] = Field(default_factory=list)
    simulation_references: list[ExternalId] = Field(default_factory=list)
    input_tokens: NonNegativeInt = 0
    output_tokens: NonNegativeInt = 0
    total_tokens: NonNegativeInt = 0
    estimated_cost: NonNegativeDecimal = Decimal("0")

    @field_validator("feedback_content")
    @classmethod
    def require_feedback_content(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if not value:
            raise ValueError("feedback_content cannot be empty")
        return value

    @model_validator(mode="after")
    def validate_generation_details(self) -> "FeedbackRecordCreate":
        fallback = self.status is FeedbackStatus.SAFE_FALLBACK
        generation_details = (
            self.generation_attempt,
            self.provider,
            self.model,
            self.prompt_version,
        )
        if fallback and any(value is not None for value in generation_details):
            raise ValueError("safe fallback feedback cannot have generation or model details")
        if not fallback and any(value is None for value in generation_details):
            raise ValueError("generated feedback requires generation and provider details")
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total_tokens must equal input_tokens plus output_tokens")
        return self


class FeedbackRecordRead(FeedbackRecordCreate):
    id: UuidString
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def normalise_created_at(cls, value: Any) -> Any:
        return _normalise_sqlite_datetime(value)


class JudgeEvaluationCreate(PersistenceSchema):
    feedback_id: UuidString
    evaluation_status: JudgeEvaluationStatus
    decision: JudgeDecision | None = None
    correctness_score: Score | None = None
    relevance_score: Score | None = None
    grounding_score: Score | None = None
    actionability_score: Score | None = None
    safety_score: Score | None = None
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    unsupported_claims: list[str] = Field(default_factory=list)
    regeneration_instructions: list[str] = Field(default_factory=list)
    error_category: ShortLabel | None = None

    @model_validator(mode="after")
    def validate_result_shape(self) -> "JudgeEvaluationCreate":
        scores = (
            self.correctness_score,
            self.relevance_score,
            self.grounding_score,
            self.actionability_score,
            self.safety_score,
        )
        if self.evaluation_status is JudgeEvaluationStatus.VALID:
            if self.decision is None or any(score is None for score in scores):
                raise ValueError("valid judge evaluations require a decision and all scores")
            if self.error_category is not None:
                raise ValueError("valid judge evaluations cannot include an error category")
        elif self.decision is not None or any(score is not None for score in scores):
            raise ValueError("failed judge evaluations cannot include a decision or scores")
        elif self.error_category is None:
            raise ValueError("failed judge evaluations require an error category")
        return self


class JudgeEvaluationRead(JudgeEvaluationCreate):
    id: UuidString
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def normalise_created_at(cls, value: Any) -> Any:
        return _normalise_sqlite_datetime(value)


class LearningEventCreate(PersistenceSchema):
    pseudonymous_user_id: ExternalId
    course_id: ExternalId
    task_id: ExternalId
    event_type: LearningEventType
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: UuidString
    metadata: dict[str, JsonValue] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("metadata_payload", "metadata"),
        serialization_alias="metadata",
    )
    deduplication_key: ExternalId | None = None

    @field_validator("occurred_at", mode="before")
    @classmethod
    def normalise_occurred_at(cls, value: Any) -> Any:
        return _normalise_sqlite_datetime(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        unknown = set(value) - ALLOWED_LEARNING_EVENT_METADATA_KEYS
        if unknown:
            raise ValueError(f"learning-event metadata keys are not allowed: {sorted(unknown)}")
        if set(value) & SENSITIVE_METADATA_KEYS:
            raise ValueError("learning-event metadata contains sensitive keys")
        return value


class LearningEventRead(LearningEventCreate):
    id: UuidString


class ResearchEvaluationCreate(PersistenceSchema):
    case_id: UuidString
    workflow_run_id: UuidString | None = None
    pseudonymous_user_id: ExternalId
    course_id: ExternalId
    task_id: ExternalId
    submission_reference: ExternalId
    experimental_condition: ExperimentalCondition
    prompt_version: ShortLabel
    provider: ShortLabel
    model: ExternalId
    input_references: list[JsonValue] = Field(default_factory=list)
    retrieved_sources: list[JsonValue] = Field(default_factory=list)
    simulation_reference: ExternalId | None = None
    generated_output: dict[str, JsonValue] = Field(default_factory=dict)
    judge_result: dict[str, JsonValue] | None = None
    latency_ms: NonNegativeInt = 0
    input_tokens: NonNegativeInt = 0
    output_tokens: NonNegativeInt = 0
    total_tokens: NonNegativeInt = 0
    estimated_cost: NonNegativeDecimal = Decimal("0")
    regeneration_count: Annotated[int, Field(ge=0, le=1)] = 0
    status: ResearchStatus = ResearchStatus.PENDING
    completed_at: datetime | None = None

    @field_validator("completed_at", mode="before")
    @classmethod
    def normalise_completed_at(cls, value: Any) -> Any:
        return _normalise_sqlite_datetime(value)

    @model_validator(mode="after")
    def validate_measurements_and_status(self) -> "ResearchEvaluationCreate":
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total_tokens must equal input_tokens plus output_tokens")
        pending = self.status is ResearchStatus.PENDING
        if pending != (self.completed_at is None):
            raise ValueError("completed and failed research records require completed_at")
        return self


class ResearchEvaluationRead(ResearchEvaluationCreate):
    id: UuidString
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def normalise_created_at(cls, value: Any) -> Any:
        return _normalise_sqlite_datetime(value)
