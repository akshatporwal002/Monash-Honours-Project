import json
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.domain.assessment import (
    AssessmentPurpose,
    BloomKnowledge,
    BloomProcess,
    CriterionDecision,
)
from app.models.enums import JudgeDecision, JudgeEvaluationStatus
from app.schemas.assessment import AssessmentVersionReference, EvidenceReference

ExternalId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=50_000),
]
PromptText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000),
]
OutputText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=12_000),
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
Score = Annotated[int, Field(ge=0, le=100)]
NonNegativeInt = Annotated[int, Field(ge=0)]
NonNegativeDecimal = Annotated[Decimal, Field(ge=0)]
SimulationOutcomeKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]

QUALITY_POLICY_VERSION = "quality-policy-v1"
QUALITY_SCORE_THRESHOLD = 80


class FeedbackContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class FeedbackResponseClassification(str, Enum):
    CORRECT = "correct"
    PARTIALLY_CORRECT = "partially_correct"
    INCORRECT = "incorrect"


class ContextProviderStatus(str, Enum):
    NOT_REQUESTED = "not_requested"
    COMPLETED = "completed"
    EMPTY = "empty"
    FAILED = "failed"


class AssessmentContextStatus(str, Enum):
    NOT_ASSESSED = "not_assessed"
    RESOLVED = "resolved"
    MISSING = "missing"
    STALE = "stale"
    ACCESS_DENIED = "access_denied"
    INVALID = "invalid"


class FeedbackAgentOutput(FeedbackContract):
    # Structured model output arrives as ordinary JSON, so wire-format enum
    # strings must be accepted before the rest of the fields are validated.
    model_config = ConfigDict(extra="forbid", frozen=True, strict=False)

    response_classification: FeedbackResponseClassification
    summary: ShortOutputText
    identified_error: OutputText | None
    explanation: OutputText
    improvement_actions: list[ShortOutputText] = Field(max_length=20)
    recommended_next_step: ShortOutputText
    source_references: list[ExternalId] = Field(max_length=100)
    simulation_references: list[ExternalId] = Field(max_length=20)

    @model_validator(mode="after")
    def validate_incorrect_feedback(self) -> "FeedbackAgentOutput":
        if self.response_classification is FeedbackResponseClassification.INCORRECT:
            if self.identified_error is None:
                raise ValueError("incorrect feedback requires identified_error")
            if not self.improvement_actions:
                raise ValueError("incorrect feedback requires at least one improvement action")
        return self


class TaskContext(FeedbackContract):
    task_id: ExternalId
    course_id: ExternalId
    task_type: ExternalId
    prompt: PromptText
    difficulty: ExternalId
    expected_answer: JsonValue | None = None
    marking_criteria: JsonValue | None = None
    learning_outcome_id: ExternalId
    source_references: list[ExternalId] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def require_marking_information(self) -> "TaskContext":
        if self.expected_answer is None and self.marking_criteria is None:
            raise ValueError("task context requires expected_answer or marking_criteria")
        for value in (self.expected_answer, self.marking_criteria):
            if (
                value is not None
                and len(json.dumps(value, ensure_ascii=False, separators=(",", ":"))) > 50_000
            ):
                raise ValueError("task marking context exceeds the allowed size")
        return self


class FeedbackCriterionEvaluationContext(FeedbackContract):
    decision: CriterionDecision
    evidence_references: list[EvidenceReference] = Field(default_factory=list, max_length=100)
    evaluator_reference: ExternalId
    model_version: ExternalId | None = None
    prompt_version: ExternalId | None = None
    retrieval_version: ExternalId | None = None
    reason: NonEmptyText
    evaluated_at: datetime

    @field_validator("evaluated_at")
    @classmethod
    def require_evaluation_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("criterion evaluation time must include a timezone")
        return value


class FeedbackCriterionContext(FeedbackContract):
    criterion_id: ExternalId
    criterion_version_id: ExternalId
    criterion_version: Annotated[int, Field(ge=1)]
    learner_description: NonEmptyText
    evidence_description: NonEmptyText
    mandatory: bool
    evidence_source_types: list[ExternalId] = Field(min_length=1, max_length=50)
    met_rule: NonEmptyText
    not_met_rule: NonEmptyText
    not_evaluable_rule: NonEmptyText
    approved_anchors: JsonValue
    critical_error_rules: JsonValue
    evaluator_type: ExternalId
    evaluation: FeedbackCriterionEvaluationContext | None = None


class AssessmentFeedbackContext(FeedbackContract):
    contract_version: Literal["learnlens.assessed-feedback-context.v1"] = (
        "learnlens.assessed-feedback-context.v1"
    )
    assessment: AssessmentVersionReference
    task: TaskContext
    response_schema_version: ExternalId
    response_content_digest: ExternalId
    task_form_id: ExternalId
    task_source_version: ExternalId
    task_source_digest: ExternalId
    task_family: ExternalId
    task_form_context: JsonValue
    task_form_constraints: JsonValue
    assessment_claim: NonEmptyText
    assessment_purpose: AssessmentPurpose
    bloom_process: BloomProcess
    bloom_knowledge: BloomKnowledge
    criteria: list[FeedbackCriterionContext] = Field(min_length=1, max_length=64)
    pass_rule_expression: JsonValue
    permitted_tools: JsonValue
    instructional_support: JsonValue
    access_conditions: JsonValue
    transfer_rule: JsonValue
    evidence_sufficiency: JsonValue

    @model_validator(mode="after")
    def validate_frozen_scope(self) -> "AssessmentFeedbackContext":
        reference = self.assessment
        if self.task.task_id != reference.task_id or self.task.course_id != reference.course_id:
            raise ValueError("assessed feedback task does not match the frozen assessment")
        criterion_ids = [item.criterion_version_id for item in self.criteria]
        if len(set(criterion_ids)) != len(criterion_ids):
            raise ValueError("assessed feedback criteria must be unique")
        for criterion in self.criteria:
            evaluation = criterion.evaluation
            if evaluation is not None and any(
                evidence.assessment != reference for evidence in evaluation.evidence_references
            ):
                raise ValueError("criterion evidence does not match the frozen assessment")
        return self


class AssessmentFeedbackContextResolution(FeedbackContract):
    status: AssessmentContextStatus
    context: AssessmentFeedbackContext | None = None
    reason_code: ExternalId | None = None

    @model_validator(mode="after")
    def validate_resolution_shape(self) -> "AssessmentFeedbackContextResolution":
        if self.status is AssessmentContextStatus.RESOLVED:
            if self.context is None or self.reason_code is not None:
                raise ValueError("resolved assessment context requires context only")
            return self
        if self.context is not None or self.reason_code is None:
            raise ValueError("unresolved assessment context requires a reason code only")
        return self


class SubmissionContext(FeedbackContract):
    submission_id: ExternalId
    task_id: ExternalId
    course_id: ExternalId | None = None
    student_id: ExternalId
    attempt_number: Annotated[int, Field(ge=1)]
    submitted_answer: PromptText
    score: float | None = None
    submitted_at: datetime


class RetrievalContext(FeedbackContract):
    retrieval_request_id: ExternalId
    task_id: ExternalId | None = None
    course_id: ExternalId | None = None
    source_id: ExternalId
    document_id: ExternalId
    chunk_id: ExternalId
    chunk_text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=50_000),
    ]
    relevance_score: Annotated[float, Field(ge=0, le=1)]
    source_label: NonEmptyText


class RetrievalResult(FeedbackContract):
    status: ContextProviderStatus
    request_ids: list[ExternalId] = Field(default_factory=list, max_length=100)
    items: list[RetrievalContext] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def validate_status_shape(self) -> "RetrievalResult":
        if self.status is ContextProviderStatus.COMPLETED and not self.items:
            raise ValueError("completed retrieval requires at least one item")
        if self.status is not ContextProviderStatus.COMPLETED and self.items:
            raise ValueError("only completed retrieval can contain items")
        item_request_ids = {item.retrieval_request_id for item in self.items}
        if self.status is ContextProviderStatus.COMPLETED:
            if not self.request_ids or not item_request_ids.issubset(set(self.request_ids)):
                raise ValueError("retrieval request IDs must cover all returned items")
        elif self.status is ContextProviderStatus.NOT_REQUESTED and self.request_ids:
            raise ValueError("retrieval that was not requested cannot have request IDs")
        return self


class SimulationContext(FeedbackContract):
    simulation_id: ExternalId
    task_id: ExternalId | None = None
    course_id: ExternalId | None = None
    status: ExternalId
    circuit_summary: PromptText | None = None
    measurement_counts: dict[SimulationOutcomeKey, NonNegativeInt] = Field(
        default_factory=dict,
        max_length=4_096,
    )
    probability_distribution: dict[
        SimulationOutcomeKey,
        Annotated[float, Field(ge=0, le=1)],
    ] = Field(
        default_factory=dict,
        max_length=4_096,
    )
    error_details: Annotated[str, StringConstraints(max_length=2_000)] | None = None


class SimulationResult(FeedbackContract):
    status: ContextProviderStatus
    context: SimulationContext | None = None

    @model_validator(mode="after")
    def validate_status_shape(self) -> "SimulationResult":
        if self.status is ContextProviderStatus.COMPLETED and self.context is None:
            raise ValueError("completed simulation requires context")
        if self.status is not ContextProviderStatus.COMPLETED and self.context is not None:
            raise ValueError("only completed simulation can contain context")
        return self


class FeedbackContext(FeedbackContract):
    correlation_id: UuidString
    task: TaskContext
    submission: SubmissionContext
    retrieval_context: list[RetrievalContext] = Field(
        default_factory=list,
        max_length=50,
    )
    simulation_context: SimulationContext | None = None
    retrieval_status: ContextProviderStatus = ContextProviderStatus.NOT_REQUESTED
    retrieval_request_ids: list[ExternalId] = Field(
        default_factory=list,
        max_length=100,
    )
    simulation_status: ContextProviderStatus = ContextProviderStatus.NOT_REQUESTED
    assessment_context: AssessmentFeedbackContext | None = None

    @model_validator(mode="before")
    @classmethod
    def infer_legacy_provider_statuses(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        retrieval_items = normalized.get("retrieval_context")
        if retrieval_items and "retrieval_status" not in normalized:
            normalized["retrieval_status"] = ContextProviderStatus.COMPLETED
        if retrieval_items and "retrieval_request_ids" not in normalized:
            normalized["retrieval_request_ids"] = [
                (
                    item.retrieval_request_id
                    if isinstance(item, RetrievalContext)
                    else item.get("retrieval_request_id")
                )
                for item in retrieval_items
            ]
        if (
            normalized.get("simulation_context") is not None
            and "simulation_status" not in normalized
        ):
            normalized["simulation_status"] = ContextProviderStatus.COMPLETED
        return normalized

    @model_validator(mode="after")
    def validate_context_scope(self) -> "FeedbackContext":
        if self.task.task_id != self.submission.task_id:
            raise ValueError("task and submission context refer to different tasks")
        if self.task.course_id != self.submission.course_id:
            raise ValueError("task and submission context refer to different courses")
        if self.assessment_context is not None:
            assessment = self.assessment_context.assessment
            if (
                self.assessment_context.task != self.task
                or assessment.response_version_id != self.submission.submission_id
                or assessment.task_id != self.submission.task_id
                or assessment.course_id != self.submission.course_id
            ):
                raise ValueError("assessment context does not match the feedback workflow")
        if self.retrieval_context:
            if self.retrieval_status is not ContextProviderStatus.COMPLETED:
                raise ValueError("retrieval items require completed retrieval status")
            item_request_ids = {item.retrieval_request_id for item in self.retrieval_context}
            if not item_request_ids.issubset(set(self.retrieval_request_ids)):
                raise ValueError("retrieval request IDs must cover all returned items")
            if any(item.task_id != self.task.task_id for item in self.retrieval_context):
                raise ValueError("retrieval context refers to a different task")
            if any(item.course_id != self.task.course_id for item in self.retrieval_context):
                raise ValueError("retrieval context refers to a different course")
        elif self.retrieval_status is ContextProviderStatus.COMPLETED:
            raise ValueError("completed retrieval requires context items")
        if self.simulation_context is not None:
            if self.simulation_status is not ContextProviderStatus.COMPLETED:
                raise ValueError("simulation context requires completed simulation status")
            if self.simulation_context.task_id != self.task.task_id:
                raise ValueError("simulation context refers to a different task")
            if self.simulation_context.course_id != self.task.course_id:
                raise ValueError("simulation context refers to a different course")
        elif self.simulation_status is ContextProviderStatus.COMPLETED:
            raise ValueError("completed simulation requires context")
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


class FeedbackSourceAttribution(FeedbackContract):
    source_id: ExternalId
    label: NonEmptyText


class GeneratedFeedback(FeedbackContract):
    feedback_content: dict[str, JsonValue]
    provider: ExternalId
    model: ExternalId
    prompt_version: ExternalId
    source_references: list[ExternalId] = Field(default_factory=list, max_length=100)
    source_attributions: list[FeedbackSourceAttribution] = Field(
        default_factory=list,
        max_length=100,
    )
    simulation_references: list[ExternalId] = Field(default_factory=list, max_length=20)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    estimated_cost: NonNegativeDecimal = Decimal("0")
    usage_complete: bool = False

    @model_validator(mode="before")
    @classmethod
    def infer_usage_completeness(cls, value: object) -> object:
        if isinstance(value, dict) and "usage_complete" not in value:
            normalized = dict(value)
            normalized["usage_complete"] = (
                "token_usage" in normalized and "estimated_cost" in normalized
            )
            return normalized
        return value

    @field_validator("feedback_content")
    @classmethod
    def require_content(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if not value:
            raise ValueError("feedback_content cannot be empty")
        if len(json.dumps(value, ensure_ascii=False, separators=(",", ":"))) > 65_536:
            raise ValueError("feedback_content exceeds the allowed size")
        return value


class JudgeResult(FeedbackContract):
    decision: JudgeDecision
    correctness_score: Score
    relevance_score: Score
    grounding_score: Score
    actionability_score: Score
    safety_score: Score
    reason: NonEmptyText
    unsupported_claims: list[ShortOutputText] = Field(default_factory=list, max_length=50)
    regeneration_instructions: list[ShortOutputText] = Field(
        default_factory=list,
        max_length=20,
    )


def quality_policy_passes(
    reported_decision: JudgeDecision | None,
    result: JudgeResult,
    quality_policy_version: str,
) -> bool:
    return (
        quality_policy_version == QUALITY_POLICY_VERSION
        and reported_decision is JudgeDecision.PASS
        and result.correctness_score >= QUALITY_SCORE_THRESHOLD
        and result.relevance_score >= QUALITY_SCORE_THRESHOLD
        and result.grounding_score >= QUALITY_SCORE_THRESHOLD
        and result.actionability_score >= QUALITY_SCORE_THRESHOLD
        and result.safety_score == 100
        and not result.unsupported_claims
    )


class JudgeAgentOutput(FeedbackContract):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=False)

    decision: JudgeDecision
    correctness_score: Score
    relevance_score: Score
    grounding_score: Score
    actionability_score: Score
    safety_score: Score
    reason: NonEmptyText
    unsupported_claims: list[ShortOutputText] = Field(max_length=50)
    regeneration_instructions: list[ShortOutputText] = Field(max_length=20)


class JudgeEvaluationOutcome(FeedbackContract):
    evaluation_status: JudgeEvaluationStatus
    reported_decision: JudgeDecision | None = None
    judge_result: JudgeResult | None = None
    reason: NonEmptyText
    error_category: ExternalId | None = None
    provider: ExternalId | None = None
    model: ExternalId | None = None
    prompt_version: ExternalId | None = None
    quality_policy_version: ExternalId = "quality-policy-v1"
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    estimated_cost: NonNegativeDecimal = Decimal("0")
    usage_complete: bool = False

    @model_validator(mode="before")
    @classmethod
    def infer_usage_completeness(cls, value: object) -> object:
        if isinstance(value, dict) and "usage_complete" not in value:
            normalized = dict(value)
            normalized["usage_complete"] = (
                "token_usage" in normalized and "estimated_cost" in normalized
            )
            return normalized
        return value

    @model_validator(mode="after")
    def validate_evaluation_shape(self) -> "JudgeEvaluationOutcome":
        if self.evaluation_status is JudgeEvaluationStatus.VALID:
            if self.reported_decision is None or self.judge_result is None:
                raise ValueError("valid judge outcomes require reported and effective results")
            if self.error_category is not None:
                raise ValueError("valid judge outcomes cannot include an error category")
            if self.provider is None or self.model is None or self.prompt_version is None:
                raise ValueError("valid judge outcomes require provider metadata")
            expected_decision = (
                JudgeDecision.PASS
                if quality_policy_passes(
                    self.reported_decision,
                    self.judge_result,
                    self.quality_policy_version,
                )
                else JudgeDecision.FAIL
            )
            if self.judge_result.decision is not expected_decision:
                raise ValueError("effective judge decision violates the quality policy")
        else:
            if self.reported_decision is not None or self.judge_result is not None:
                raise ValueError("failed judge outcomes cannot include decisions")
            if self.error_category is None:
                raise ValueError("failed judge outcomes require an error category")
        return self


class FeedbackRegenerationContext(FeedbackContract):
    previous_feedback: GeneratedFeedback
    judge_evaluation: JudgeEvaluationOutcome


class SafeFallbackFeedback(FeedbackContract):
    feedback_content: dict[str, JsonValue]
    source_references: list[ExternalId] = Field(default_factory=list, max_length=100)
    simulation_references: list[ExternalId] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_fallback_references(self) -> "SafeFallbackFeedback":
        if self.source_references or self.simulation_references:
            raise ValueError("safe fallback feedback cannot contain references")
        if not self.feedback_content:
            raise ValueError("safe fallback feedback cannot be empty")
        if (
            len(
                json.dumps(
                    self.feedback_content,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
            > 65_536
        ):
            raise ValueError("safe fallback feedback exceeds the allowed size")
        return self


class FeedbackPipelineStatus(str, Enum):
    VALIDATED = "validated"
    FALLBACK = "fallback"


class FeedbackPipelineResult(FeedbackContract):
    workflow_run_id: UuidString
    feedback_id: UuidString
    submission_id: ExternalId
    status: FeedbackPipelineStatus
    validated_feedback: GeneratedFeedback | None
    safe_fallback: SafeFallbackFeedback | None = None
    judge_result: JudgeResult | None = None
    judge_evaluations: list[JudgeEvaluationOutcome] = Field(
        default_factory=list,
        max_length=2,
    )
    regeneration_count: Annotated[int, Field(ge=0, le=1)] = 0
    fallback_used: bool = False
    latency_ms: NonNegativeInt
    token_usage: TokenUsage
    estimated_cost: NonNegativeDecimal
    source_references: list[ExternalId] = Field(default_factory=list, max_length=100)
    idempotent_replay: bool = False

    @model_validator(mode="after")
    def validate_release_state(self) -> "FeedbackPipelineResult":
        if self.status is FeedbackPipelineStatus.VALIDATED:
            if self.validated_feedback is None or self.safe_fallback is not None:
                raise ValueError("validated result requires validated_feedback")
            if self.fallback_used:
                raise ValueError("validated result cannot set fallback_used")
            if self.judge_result is None:
                raise ValueError("validated result requires a passing final judgement")
            if self.judge_result.decision is not JudgeDecision.PASS:
                raise ValueError("validated result cannot contain a failed final judgement")
            if (
                self.judge_result.correctness_score < QUALITY_SCORE_THRESHOLD
                or self.judge_result.relevance_score < QUALITY_SCORE_THRESHOLD
                or self.judge_result.grounding_score < QUALITY_SCORE_THRESHOLD
                or self.judge_result.actionability_score < QUALITY_SCORE_THRESHOLD
                or self.judge_result.safety_score != 100
                or self.judge_result.unsupported_claims
            ):
                raise ValueError("validated result violates the quality policy")
            if len(self.judge_evaluations) != self.regeneration_count + 1:
                raise ValueError("validated result requires one judgement per attempt")
            final_evaluation = self.judge_evaluations[-1]
            if (
                final_evaluation.evaluation_status is not JudgeEvaluationStatus.VALID
                or final_evaluation.judge_result != self.judge_result
                or not quality_policy_passes(
                    final_evaluation.reported_decision,
                    self.judge_result,
                    final_evaluation.quality_policy_version,
                )
            ):
                raise ValueError("released feedback must match the policy-approved judgement")
            if self.source_references != self.validated_feedback.source_references:
                raise ValueError("released source references must match validated feedback")
        elif self.safe_fallback is None or self.validated_feedback is not None:
            raise ValueError("fallback result requires only safe_fallback")
        elif not self.fallback_used:
            raise ValueError("fallback result must set fallback_used")
        elif self.source_references:
            raise ValueError("fallback result cannot contain source references")
        if len(self.judge_evaluations) > self.regeneration_count + 1:
            raise ValueError("judge evaluations do not match the regeneration count")
        return self
