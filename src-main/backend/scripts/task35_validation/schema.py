"""Strict, exportable review-import contract. Null is not a negative rating."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(min_length=1, pattern=r"\S")]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Decision = Literal["MET", "NOT_MET", "NOT_EVALUABLE"]
Channel = Literal["task", "feedback", "evaluation", "judge", "assessment"]
DIMENSIONS = ("accuracy", "clarity", "relevance", "useful_action", "outcome_fit", "support")
COMPONENTS = {"model", "prompt", "source", "rule", "retrieval", "task", "curriculum", "bloom"}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Manifest(Strict):
    version: Literal["task35-manifest-v1"]
    components: dict[str, Text]
    files: dict[str, Digest]
    source_references: list[dict[str, str]]
    provenance: Literal["DRAFT", "SYNTHETIC", "RECORDED"]

    @model_validator(mode="after")
    def complete(self):
        if set(self.components) != COMPONENTS or not self.files or not self.source_references:
            raise ValueError("manifest requires all version dimensions, files and sources")
        return self


class Case(Strict):
    case_id: Text
    status: Literal["DRAFT"]
    family: Text
    task_type: Text
    variant: Text
    access_form: Text
    style: Text
    stage: Literal["supported", "unaided_transfer"]
    source_ids: list[Text] = Field(min_length=1)
    criteria: dict[str, Text] = Field(min_length=1)
    prompt: Text
    response: Text
    draft_expected: dict[str, Decision]
    draft_rationale: Text
    draft_feedback_candidate: Text
    draft_judge_flawed: bool
    draft_judge_rationale: Text
    reviewer_decision: None = None
    reviewer_provenance: None = None

    @model_validator(mode="after")
    def criterion_scope(self):
        if set(self.criteria) != set(self.draft_expected):
            raise ValueError("draft decisions must match criterion versions")
        return self


class Reviewer(Strict):
    reviewer_id: Text
    name: Text
    expertise_reference: Text
    training_reference: Text
    appointment_reference: Text


class Values(Strict):
    factual_correct: bool | None = None
    hallucination: bool | None = None
    feedback_ratings: dict[str, Annotated[int, Field(ge=1, le=5)]] | None = None
    incomplete_response: bool | None = None
    next_action_and_revision: bool | None = None
    flawed: bool | None = None
    criteria: dict[str, Decision] | None = None
    result: Literal["PASS", "INCOMPLETE"] | None = None


def validate_values(channel: str, values: Values) -> None:
    present = {k for k, v in values.model_dump().items() if v is not None}
    required = {
        "task": {"factual_correct", "hallucination"},
        "evaluation": {"factual_correct", "hallucination"},
        "feedback": {
            "factual_correct",
            "hallucination",
            "feedback_ratings",
            "incomplete_response",
            "next_action_and_revision",
        },
        "judge": {"flawed"},
        "assessment": {"criteria", "result"},
    }[channel]
    if present != required:
        raise ValueError(f"{channel} requires exactly {sorted(required)}")
    if channel == "feedback" and set(values.feedback_ratings) != set(DIMENSIONS):
        raise ValueError("all six feedback dimensions are required")
    if values.hallucination and values.factual_correct:
        raise ValueError("an incorrect/unsupported claim cannot be factually correct")


class Output(Strict):
    case_id: Text
    channel: Channel
    manifest_digest: Digest
    case_digest: Digest
    state: Literal["RECORDED", "MISSING", "INVALID", "ABSTAINED"]
    text: str = ""
    reason: str = ""
    judge_decision: Literal["APPROVED", "REJECTED"] | None = None
    criteria: dict[str, Decision] | None = None
    result: Literal["PASS", "INCOMPLETE"] | None = None

    @model_validator(mode="after")
    def payload(self):
        if self.state != "RECORDED":
            if not self.reason.strip() or self.judge_decision or self.criteria or self.result:
                raise ValueError("non-recorded output needs reason and no decisions")
        else:
            if not self.text.strip():
                raise ValueError("recorded output needs preserved text")
            if self.channel == "judge" and self.judge_decision is None:
                raise ValueError("judge decision required")
            if self.channel == "assessment" and (not self.criteria or self.result is None):
                raise ValueError("assessment criterion decisions and result required")
        if self.channel != "judge" and self.judge_decision is not None:
            raise ValueError("judge decision only belongs to judge channel")
        if self.channel != "assessment" and (self.criteria is not None or self.result is not None):
            raise ValueError("assessment decisions only belong to assessment channel")
        return self


class Rating(Strict):
    rating_id: Text
    case_id: Text
    channel: Channel
    reviewer_id: Text
    rated_at: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$")]
    manifest_digest: Digest
    case_digest: Digest
    output_digest: Digest | None = None
    state: Literal["RATED", "ABSTAINED", "INVALID"]
    rationale: Text
    independent: Literal[True]
    values: Values | None = None

    @model_validator(mode="after")
    def payload(self):
        from datetime import datetime

        datetime.fromisoformat(self.rated_at.replace("Z", "+00:00"))
        if self.channel == "assessment" and self.output_digest is not None:
            raise ValueError("human assessment baseline must be blinded to system output")
        if self.channel != "assessment" and self.output_digest is None:
            raise ValueError("output quality rating must bind the exact output")
        if self.state == "RATED":
            if self.values is None:
                raise ValueError("rated review needs values")
            validate_values(self.channel, self.values)
        elif self.values is not None:
            raise ValueError("abstained/invalid ratings cannot carry decisions")
        return self


class Adjudication(Strict):
    case_id: Text
    channel: Channel
    reviewer_id: Text
    rating_ids: list[Text] = Field(min_length=2, max_length=2)
    rationale: Text
    decided_at: Text
    values: Values

    @model_validator(mode="after")
    def payload(self):
        from datetime import datetime

        if datetime.fromisoformat(self.decided_at.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError("adjudication requires an offset timestamp")
        validate_values(self.channel, self.values)
        return self


class CaseApproval(Strict):
    case_id: Text
    case_digest: Digest
    manifest_digest: Digest
    reviewer_id: Text
    approval_reference: Text


class Bundle(Strict):
    schema_version: Literal["task35-review-v1"]
    provenance: Literal["SYNTHETIC", "EXPERT_RECORDED"]
    manifest: Manifest
    cases: list[Case] = Field(min_length=1, max_length=10000)
    reviewers: list[Reviewer] = Field(default_factory=list)
    approvals: list[CaseApproval] = Field(default_factory=list)
    outputs: list[Output] = Field(default_factory=list)
    ratings: list[Rating] = Field(default_factory=list)
    adjudications: list[Adjudication] = Field(default_factory=list)
