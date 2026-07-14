from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models.enums import JudgeDecision


ExternalId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
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


class FeedbackContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class TaskContext(FeedbackContract):
    task_id: ExternalId
    course_id: ExternalId
    task_type: ExternalId
    prompt: NonEmptyText
    difficulty: ExternalId
    expected_answer: JsonValue | None = None
    marking_criteria: JsonValue | None = None
    learning_outcome_id: ExternalId
    source_references: list[ExternalId] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_marking_information(self) -> "TaskContext":
        if self.expected_answer is None and self.marking_criteria is None:
            raise ValueError("task context requires expected_answer or marking_criteria")
        return self


class SubmissionContext(FeedbackContract):
    submission_id: ExternalId
    task_id: ExternalId
    student_id: ExternalId
    attempt_number: Annotated[int, Field(ge=1)]
    submitted_answer: NonEmptyText
    score: float | None = None
    submitted_at: datetime


class RetrievalContext(FeedbackContract):
    retrieval_request_id: ExternalId
    source_id: ExternalId
    document_id: ExternalId
    chunk_id: ExternalId
    chunk_text: NonEmptyText
    relevance_score: Annotated[float, Field(ge=0, le=1)]
    source_label: NonEmptyText


class SimulationContext(FeedbackContract):
    simulation_id: ExternalId
    status: ExternalId
    circuit_summary: str | None = None
    measurement_counts: dict[str, NonNegativeInt] = Field(default_factory=dict)
    probability_distribution: dict[str, Annotated[float, Field(ge=0, le=1)]] = Field(
        default_factory=dict
    )
    error_details: str | None = None


class FeedbackContext(FeedbackContract):
    correlation_id: UuidString
    task: TaskContext
    submission: SubmissionContext
    retrieval_context: list[RetrievalContext] = Field(default_factory=list)
    simulation_context: SimulationContext | None = None

    @model_validator(mode="after")
    def validate_task_reference(self) -> "FeedbackContext":
        if self.task.task_id != self.submission.task_id:
            raise ValueError("task and submission context refer to different tasks")
        return self


class TokenUsage(FeedbackContract):
    input_tokens: NonNegativeInt = 0
    output_tokens: NonNegativeInt = 0
    total_tokens: NonNegativeInt = 0

    @model_validator(mode="after")
    def validate_total(self) -> "TokenUsage":
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total_tokens must equal input_tokens plus output_tokens")
        return self


class GeneratedFeedback(FeedbackContract):
    feedback_content: dict[str, JsonValue]
    model: ExternalId
    source_references: list[ExternalId] = Field(default_factory=list)
    simulation_references: list[ExternalId] = Field(default_factory=list)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    estimated_cost: NonNegativeDecimal = Decimal("0")

    @field_validator("feedback_content")
    @classmethod
    def require_content(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if not value:
            raise ValueError("feedback_content cannot be empty")
        return value


class JudgeResult(FeedbackContract):
    decision: JudgeDecision
    correctness_score: Score
    relevance_score: Score
    grounding_score: Score
    actionability_score: Score
    safety_score: Score
    reason: NonEmptyText
    unsupported_claims: list[str] = Field(default_factory=list)
    regeneration_instructions: list[str] = Field(default_factory=list)


class FeedbackPipelineStatus(str, Enum):
    VALIDATED = "validated"
    REJECTED = "rejected"


class FeedbackPipelineResult(FeedbackContract):
    workflow_run_id: UuidString
    feedback_id: UuidString
    submission_id: ExternalId
    status: FeedbackPipelineStatus
    validated_feedback: GeneratedFeedback | None
    judge_result: JudgeResult
    regeneration_count: Annotated[int, Field(ge=0, le=1)] = 0
    fallback_used: bool = False
    latency_ms: NonNegativeInt
    token_usage: TokenUsage
    estimated_cost: NonNegativeDecimal
    source_references: list[ExternalId] = Field(default_factory=list)
    idempotent_replay: bool = False

    @model_validator(mode="after")
    def validate_release_state(self) -> "FeedbackPipelineResult":
        if self.status is FeedbackPipelineStatus.VALIDATED:
            if self.validated_feedback is None:
                raise ValueError("validated result requires validated_feedback")
        elif self.validated_feedback is not None:
            raise ValueError("rejected result cannot expose feedback")
        return self
