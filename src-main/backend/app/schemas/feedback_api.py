from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models.enums import FeedbackReportCategory, WorkflowStage
from app.schemas.feedback import FeedbackResponseClassification

NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=12_000),
]
ShortOutputText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4_000),
]
SourceLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
ExternalId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class FeedbackApiContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class AuthenticatedActor(FeedbackApiContract):
    actor_reference: ExternalId
    role: ExternalId


class FeedbackWorkflowStatus(str, Enum):
    PROCESSING = "processing"
    VALIDATED = "validated"
    FALLBACK = "fallback"
    FAILED = "failed"


class FeedbackSourceView(FeedbackApiContract):
    source_id: ExternalId
    label: SourceLabel


class ValidatedFeedbackView(FeedbackApiContract):
    kind: Literal["validated"] = "validated"
    feedback_id: ExternalId
    response_classification: FeedbackResponseClassification | None = None
    summary: ShortOutputText
    identified_error: NonEmptyText | None = None
    explanation: NonEmptyText | None = None
    improvement_actions: list[ShortOutputText] = Field(default_factory=list, max_length=20)
    recommended_next_step: ShortOutputText | None = None
    sources: list[FeedbackSourceView] = Field(default_factory=list, max_length=100)
    simulation_references: list[ExternalId] = Field(default_factory=list, max_length=20)
    ai_generated_notice: ShortOutputText


class SafeFallbackView(FeedbackApiContract):
    kind: Literal["safe_fallback"] = "safe_fallback"
    feedback_id: ExternalId
    summary: ShortOutputText
    explanation: NonEmptyText
    recommended_next_step: ShortOutputText
    sources: list[FeedbackSourceView] = Field(default_factory=list, max_length=100)
    simulation_references: list[ExternalId] = Field(default_factory=list, max_length=20)


class FeedbackFailureView(FeedbackApiContract):
    code: Literal["feedback_processing_failed"] = "feedback_processing_failed"
    message: Literal["Feedback processing could not be completed."] = (
        "Feedback processing could not be completed."
    )
    retryable: bool


class FeedbackWorkflowResponse(FeedbackApiContract):
    workflow_run_id: ExternalId
    submission_id: ExternalId
    status: FeedbackWorkflowStatus
    processing_stage: WorkflowStage | None = None
    feedback: ValidatedFeedbackView | SafeFallbackView | None = None
    error: FeedbackFailureView | None = None

    @model_validator(mode="after")
    def validate_state(self) -> "FeedbackWorkflowResponse":
        if self.status is FeedbackWorkflowStatus.PROCESSING:
            if self.processing_stage is None or self.feedback is not None or self.error is not None:
                raise ValueError("processing responses require only a processing stage")
        elif self.status is FeedbackWorkflowStatus.FAILED:
            if self.error is None or self.feedback is not None or self.processing_stage is not None:
                raise ValueError("failed responses require only a sanitized error")
        elif self.feedback is None or self.error is not None or self.processing_stage is not None:
            raise ValueError("terminal responses require only released feedback")
        return self


class FeedbackReportRequest(FeedbackApiContract):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=False)

    category: FeedbackReportCategory
    note: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
        | None
    ) = None

    @field_validator("note", mode="before")
    @classmethod
    def blank_note_is_absent(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class FeedbackReportResponse(FeedbackApiContract):
    report_id: ExternalId
    status: Literal["received"] = "received"


class FeedbackApiErrorDetail(FeedbackApiContract):
    code: ExternalId
    message: NonEmptyText


class FeedbackApiErrorResponse(FeedbackApiContract):
    error: FeedbackApiErrorDetail
