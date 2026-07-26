import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, ClassVar

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
from app.schemas.feedback import QUALITY_POLICY_VERSION, QUALITY_SCORE_THRESHOLD
from app.schemas.learning_events import validate_learning_event_metadata

ExternalId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
ShortLabel = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
SanitizedCategory = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9_.-]*$",
    ),
]
BoundedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=50_000),
]
ShortOutputText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4_000),
]
UuidString = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$",
    ),
]
PseudonymousReference = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^v1_[0-9a-f]{64}$",
    ),
]
Score = Annotated[int, Field(ge=0, le=100)]
NonNegativeInt = Annotated[int, Field(ge=0)]
StoredCost = Annotated[
    Decimal,
    Field(ge=0, max_digits=12, decimal_places=6),
]

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
_PSEUDONYM = re.compile(r"^v1_[0-9a-f]{64}$")


def _normalise_sqlite_datetime(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return value


class PersistenceSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        populate_by_name=True,
        strict=True,
    )


class ResearchSourceMeasurement(PersistenceSchema):
    source_id: ExternalId
    label: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000),
    ]
    relevance_score: Annotated[float, Field(ge=0, le=1)]


class WorkflowRunCreate(PersistenceSchema):
    submission_id: ExternalId
    course_id: ExternalId | None = None
    task_id: ExternalId | None = None
    current_stage: WorkflowStage = WorkflowStage.PENDING
    regeneration_count: Annotated[int, Field(ge=0, le=1)] = 0
    final_outcome: WorkflowOutcome | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    lease_expires_at: datetime | None = None
    execution_token: UuidString | None = None
    execution_attempt_count: Annotated[int, Field(ge=0, le=3)] = 0
    next_retry_at: datetime | None = None
    latency_ms: NonNegativeInt | None = None
    failure_category: SanitizedCategory | None = None

    @field_validator(
        "started_at",
        "completed_at",
        "lease_expires_at",
        "next_retry_at",
        mode="before",
    )
    @classmethod
    def normalise_timestamps(cls, value: Any) -> Any:
        return _normalise_sqlite_datetime(value)

    @model_validator(mode="after")
    def validate_terminal_state(self) -> "WorkflowRunCreate":
        if self.current_stage is WorkflowStage.COMPLETED:
            if (
                self.final_outcome
                not in {
                    WorkflowOutcome.FIRST_PASS,
                    WorkflowOutcome.SECOND_PASS,
                    WorkflowOutcome.SAFE_FALLBACK,
                }
                or self.completed_at is None
            ):
                raise ValueError("completed workflows require a released outcome")
        elif self.current_stage is WorkflowStage.FAILED:
            if (
                self.final_outcome is not WorkflowOutcome.WORKFLOW_FAILED
                or self.completed_at is None
            ):
                raise ValueError("failed workflows require the workflow-failed outcome")
        elif self.final_outcome is not None or self.completed_at is not None:
            raise ValueError("nonterminal workflows cannot have terminal fields")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be earlier than started_at")
        if (self.current_stage is WorkflowStage.FAILED) != (self.failure_category is not None):
            raise ValueError("failed workflows require a failure category")
        if self.next_retry_at is not None and self.current_stage is not WorkflowStage.FAILED:
            raise ValueError("only failed workflows can be scheduled for retry")
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
    source_attributions: list[dict[str, ExternalId]] = Field(default_factory=list)
    simulation_references: list[ExternalId] = Field(default_factory=list)
    input_tokens: NonNegativeInt = 0
    output_tokens: NonNegativeInt = 0
    total_tokens: NonNegativeInt = 0
    estimated_cost: StoredCost = Decimal("0")
    usage_complete: bool = False

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
    reported_decision: JudgeDecision | None = None
    decision: JudgeDecision | None = None
    correctness_score: Score | None = None
    relevance_score: Score | None = None
    grounding_score: Score | None = None
    actionability_score: Score | None = None
    safety_score: Score | None = None
    reason: BoundedText
    unsupported_claims: list[ShortOutputText] = Field(default_factory=list, max_length=50)
    regeneration_instructions: list[ShortOutputText] = Field(
        default_factory=list,
        max_length=20,
    )
    error_category: SanitizedCategory | None = None
    provider: ShortLabel | None = None
    model: ExternalId | None = None
    prompt_version: ShortLabel | None = None
    quality_policy_version: ShortLabel = "quality-policy-v1"
    input_tokens: NonNegativeInt = 0
    output_tokens: NonNegativeInt = 0
    total_tokens: NonNegativeInt = 0
    estimated_cost: StoredCost = Decimal("0")
    usage_complete: bool = False

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
            if (
                self.reported_decision is None
                or self.decision is None
                or any(score is None for score in scores)
            ):
                raise ValueError("valid judge evaluations require a decision and all scores")
            if self.error_category is not None:
                raise ValueError("valid judge evaluations cannot include an error category")
            if self.provider is None or self.model is None or self.prompt_version is None:
                raise ValueError("valid judge evaluations require provider metadata")
            policy_passes = (
                self.quality_policy_version == QUALITY_POLICY_VERSION
                and self.reported_decision is JudgeDecision.PASS
                and self.correctness_score is not None
                and self.correctness_score >= QUALITY_SCORE_THRESHOLD
                and self.relevance_score is not None
                and self.relevance_score >= QUALITY_SCORE_THRESHOLD
                and self.grounding_score is not None
                and self.grounding_score >= QUALITY_SCORE_THRESHOLD
                and self.actionability_score is not None
                and self.actionability_score >= QUALITY_SCORE_THRESHOLD
                and self.safety_score == 100
                and not self.unsupported_claims
            )
            expected = JudgeDecision.PASS if policy_passes else JudgeDecision.FAIL
            if self.decision is not expected:
                raise ValueError("effective judge decision violates the quality policy")
        elif (
            self.reported_decision is not None
            or self.decision is not None
            or any(score is not None for score in scores)
        ):
            raise ValueError("failed judge evaluations cannot include a decision or scores")
        elif self.error_category is None:
            raise ValueError("failed judge evaluations require an error category")
        elif self.unsupported_claims or self.regeneration_instructions:
            raise ValueError("failed judge evaluations cannot include model-authored result text")
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total_tokens must equal input_tokens plus output_tokens")
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
    workflow_reference: UuidString | None = None
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

    @model_validator(mode="after")
    def validate_metadata(self) -> "LearningEventCreate":
        self.metadata = validate_learning_event_metadata(self.event_type, self.metadata)
        return self


class LearningEventRead(LearningEventCreate):
    id: UuidString


class ResearchEvaluationCreate(PersistenceSchema):
    _allow_legacy_read: ClassVar[bool] = False

    case_id: UuidString
    workflow_run_id: UuidString
    correlation_id: UuidString
    pseudonymous_user_id: PseudonymousReference
    course_id: ExternalId
    task_id: ExternalId
    task_type: ExternalId
    submission_reference: PseudonymousReference
    experimental_condition: ExperimentalCondition
    prompt_version: ShortLabel
    provider: ShortLabel
    model: ExternalId
    input_references: list[ExternalId] = Field(default_factory=list, max_length=100)
    retrieved_sources: list[ResearchSourceMeasurement] = Field(
        default_factory=list,
        max_length=100,
    )
    simulation_reference: ExternalId | None = None
    simulation_status: ShortLabel = "not_requested"
    generated_output: dict[str, JsonValue] = Field(default_factory=dict)
    judge_result: dict[str, JsonValue] | None = None
    measurement_schema_version: ShortLabel = "research-v1"
    latency_ms: NonNegativeInt | None = None
    input_tokens: NonNegativeInt = 0
    output_tokens: NonNegativeInt = 0
    total_tokens: NonNegativeInt = 0
    estimated_cost: StoredCost = Decimal("0")
    regeneration_count: Annotated[int, Field(ge=0, le=1)] = 0
    fallback_used: bool = False
    comparable: bool = False
    usage_complete: bool = False
    retrieval_request_count: NonNegativeInt = 0
    retrieval_hit_count: NonNegativeInt = 0
    first_judge_status: JudgeEvaluationStatus | None = None
    first_judge_decision: JudgeDecision | None = None
    final_judge_status: JudgeEvaluationStatus | None = None
    final_judge_decision: JudgeDecision | None = None
    correctness_score: Score | None = None
    relevance_score: Score | None = None
    grounding_score: Score | None = None
    actionability_score: Score | None = None
    safety_score: Score | None = None
    unsupported_claim_count: NonNegativeInt | None = None
    quality_policy_version: ShortLabel | None = None
    evaluation_latency_ms: NonNegativeInt | None = None
    evaluation_input_tokens: NonNegativeInt = 0
    evaluation_output_tokens: NonNegativeInt = 0
    evaluation_total_tokens: NonNegativeInt = 0
    evaluation_estimated_cost: StoredCost = Decimal("0")
    evaluation_usage_complete: bool = False
    status: ResearchStatus = ResearchStatus.PENDING
    execution_token: UuidString | None = None
    lease_expires_at: datetime | None = None
    processing_attempts: Annotated[int, Field(ge=0, le=3)] = 0
    failure_category: SanitizedCategory | None = None
    completed_at: datetime | None = None

    @field_validator("lease_expires_at", "completed_at", mode="before")
    @classmethod
    def normalise_research_timestamps(cls, value: Any) -> Any:
        return _normalise_sqlite_datetime(value)

    @field_validator("generated_output", "judge_result")
    @classmethod
    def bound_structured_measurements(
        cls,
        value: dict[str, JsonValue] | None,
    ) -> dict[str, JsonValue] | None:
        if value is None:
            return None
        try:
            encoded = json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError):
            raise ValueError("research measurements must be valid JSON") from None
        if len(encoded) > 65_536:
            raise ValueError("research measurements exceed the allowed size")
        return value

    @model_validator(mode="after")
    def validate_measurements_and_status(self) -> "ResearchEvaluationCreate":
        legacy_read = self._allow_legacy_read and self.measurement_schema_version == "legacy-v1"
        if self.measurement_schema_version == "legacy-v1" and not legacy_read:
            raise ValueError("legacy measurement versions are read-only")
        if not legacy_read and self.workflow_run_id != self.case_id:
            raise ValueError("research case ID must equal workflow ID")
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total_tokens must equal input_tokens plus output_tokens")
        if (
            self.evaluation_total_tokens
            != self.evaluation_input_tokens + self.evaluation_output_tokens
        ):
            raise ValueError(
                "evaluation_total_tokens must equal evaluation input plus output tokens"
            )
        if self.retrieval_hit_count > self.retrieval_request_count:
            raise ValueError("retrieval hits cannot exceed retrieval requests")

        if self.status is ResearchStatus.PENDING:
            if (
                self.completed_at is not None
                or self.execution_token is not None
                or self.lease_expires_at is not None
                or self.failure_category is not None
            ):
                raise ValueError("pending research records cannot contain claim or terminal fields")
        elif self.status is ResearchStatus.RUNNING:
            if (
                self.completed_at is not None
                or self.execution_token is None
                or self.lease_expires_at is None
                or self.failure_category is not None
                or self.processing_attempts < 1
            ):
                raise ValueError("running research records require one fenced active claim")
        elif self.status is ResearchStatus.COMPLETED:
            if (
                self.completed_at is None
                or self.execution_token is not None
                or self.lease_expires_at is not None
                or self.failure_category is not None
            ):
                raise ValueError("completed research records require clean terminal fields")
        elif (
            self.completed_at is None
            or self.execution_token is not None
            or self.lease_expires_at is not None
            or self.failure_category is None
        ):
            raise ValueError("failed research records require one sanitized failure category")

        self._validate_judge_measurement(
            self.first_judge_status,
            self.first_judge_decision,
            final=False,
        )
        self._validate_judge_measurement(
            self.final_judge_status,
            self.final_judge_decision,
            final=True,
        )
        if (
            not legacy_read
            and self.experimental_condition is ExperimentalCondition.SINGLE_STEP_BASELINE
            and (
                self.input_references
                or self.retrieved_sources
                or self.simulation_reference is not None
                or self.simulation_status != "not_requested"
                or self.retrieval_request_count
                or self.retrieval_hit_count
                or self.regeneration_count
                or self.fallback_used
            )
        ):
            raise ValueError("baseline research records cannot contain agentic context")
        return self

    def _validate_judge_measurement(
        self,
        status: JudgeEvaluationStatus | None,
        decision: JudgeDecision | None,
        *,
        final: bool,
    ) -> None:
        if status is None:
            if decision is not None:
                raise ValueError("judge decisions require a judge status")
            if final and any(value is not None for value in self._final_measurements()):
                raise ValueError("final judge measurements require a final judge status")
            return
        if status is JudgeEvaluationStatus.VALID:
            if decision is None:
                raise ValueError("valid judge measurements require an effective decision")
            if final and any(value is None for value in self._final_measurements()):
                raise ValueError(
                    "valid final judge measurements require scores and policy metadata"
                )
            if final and decision is JudgeDecision.PASS and not self._final_policy_passes():
                raise ValueError("final judge pass violates the quality policy")
        elif decision is not None:
            raise ValueError("technical judge measurements cannot include a decision")
        elif final and any(
            value is not None
            for value in (
                self.correctness_score,
                self.relevance_score,
                self.grounding_score,
                self.actionability_score,
                self.safety_score,
                self.unsupported_claim_count,
            )
        ):
            raise ValueError("technical final judge measurements cannot include scores")

    def _final_measurements(self) -> tuple[object, ...]:
        return (
            self.correctness_score,
            self.relevance_score,
            self.grounding_score,
            self.actionability_score,
            self.safety_score,
            self.unsupported_claim_count,
            self.quality_policy_version,
        )

    def _final_policy_passes(self) -> bool:
        return (
            self.quality_policy_version == QUALITY_POLICY_VERSION
            and self.correctness_score is not None
            and self.correctness_score >= QUALITY_SCORE_THRESHOLD
            and self.relevance_score is not None
            and self.relevance_score >= QUALITY_SCORE_THRESHOLD
            and self.grounding_score is not None
            and self.grounding_score >= QUALITY_SCORE_THRESHOLD
            and self.actionability_score is not None
            and self.actionability_score >= QUALITY_SCORE_THRESHOLD
            and self.safety_score == 100
            and self.unsupported_claim_count == 0
        )


class ResearchEvaluationRead(ResearchEvaluationCreate):
    _allow_legacy_read: ClassVar[bool] = True

    workflow_run_id: UuidString | None = None
    correlation_id: UuidString | None = None
    pseudonymous_user_id: ExternalId
    submission_reference: ExternalId
    retrieved_sources: list[dict[str, JsonValue]] = Field(
        default_factory=list,
        max_length=100,
    )
    id: UuidString
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def normalise_created_at(cls, value: Any) -> Any:
        return _normalise_sqlite_datetime(value)

    @model_validator(mode="after")
    def validate_current_or_legacy_read(self) -> "ResearchEvaluationRead":
        if self.measurement_schema_version == "legacy-v1":
            if self.comparable or self.usage_complete or self.evaluation_usage_complete:
                raise ValueError("legacy research measurements must remain incomplete")
            return self
        if (
            self.workflow_run_id is None
            or self.correlation_id is None
            or self.workflow_run_id != self.case_id
            or _PSEUDONYM.fullmatch(self.pseudonymous_user_id) is None
            or _PSEUDONYM.fullmatch(self.submission_reference) is None
        ):
            raise ValueError("current research measurements require pseudonymous shared scope")
        for source in self.retrieved_sources:
            ResearchSourceMeasurement.model_validate(source)
        return self
