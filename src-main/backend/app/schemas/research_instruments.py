"""Synthetic draft instrument contracts, independent of teaching and formal assessment."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StringConstraints, model_validator

from app.schemas.research_governance import Code, GovernanceContract

Token = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,47}$")]
Stage = Literal[
    "T0_BASELINE",
    "T1_STUDY_ACTIVITY",
    "T1_FORMAL_SUPPORTED",
    "T1_FORMAL_UNAIDED",
    "T2_CONCEPTUAL",
    "T2_TRANSFER",
    "T3_CONCEPTUAL",
    "T3_TRANSFER",
]
MissingReason = Literal[
    "not_collected",
    "not_applicable",
    "participant_skipped",
    "technical_failure",
    "not_evaluable",
    "outside_window",
    "withdrawn",
    "not_approved",
]
ExportField = Literal[
    "instrument.record_id",
    "instrument.participant_id",
    "instrument.course_ref",
    "instrument.sequence_id",
    "instrument.form_id",
    "instrument.form_version",
    "instrument.item_id",
    "instrument.stage",
    "instrument.outcome_ref",
    "instrument.task_ref",
    "instrument.response_ref",
    "instrument.choice_code",
    "instrument.integer_value",
    "instrument.missing_reason",
    "instrument.event_kind",
    "instrument.reason_code",
    "instrument.revision",
    "instrument.supersedes_id",
    "instrument.correction_reason_code",
]


class InstrumentItem(GovernanceContract):
    item_id: Token
    prompt: str = Field(min_length=1, max_length=2000)
    response_type: Literal["choice", "integer", "text"]
    choices: list[Token] = Field(default_factory=list, max_length=30)
    minimum: int | None = None
    maximum: int | None = None
    max_characters: int | None = Field(default=None, ge=1, le=10_000)

    @model_validator(mode="after")
    def shape(self):
        if self.response_type == "choice":
            if (
                not self.choices
                or len(set(self.choices)) != len(self.choices)
                or any(v is not None for v in (self.minimum, self.maximum, self.max_characters))
            ):
                raise ValueError("choice items require only unique controlled choices")
        elif self.response_type == "integer":
            if (
                self.choices
                or self.max_characters is not None
                or self.minimum is None
                or self.maximum is None
                or self.minimum > self.maximum
            ):
                raise ValueError("integer items require explicit bounds only")
        elif (
            self.choices
            or self.minimum is not None
            or self.maximum is not None
            or self.max_characters is None
        ):
            raise ValueError("text items require an explicit character bound only")
        return self


class InstrumentDefinition(GovernanceContract):
    schema_version: Literal["learnlens.instrument-definition.v1"] = (
        "learnlens.instrument-definition.v1"
    )
    synthetic_only: bool = True
    review_status: Literal["DRAFT_FOR_REVIEW"] = "DRAFT_FOR_REVIEW"
    title: str = Field(min_length=1, max_length=200)
    instrument_kind: Literal[
        "conceptual", "transfer", "retention", "learner_experience", "educator_review", "process"
    ]
    stages: list[Stage] = Field(min_length=1, max_length=8)
    items: list[InstrumentItem] = Field(min_length=1, max_length=30)
    event_reason_codes: list[Token] = Field(min_length=1, max_length=30)
    support_manifest_reference: Code

    @model_validator(mode="after")
    def unique(self):
        if (
            len({i.item_id for i in self.items}) != len(self.items)
            or len(set(self.stages)) != len(self.stages)
            or len(set(self.event_reason_codes)) != len(self.event_reason_codes)
        ):
            raise ValueError("instrument identifiers and codes must be unique")
        return self


class FormWrite(GovernanceContract):
    request_key: Code
    expected_version: int = Field(ge=0)
    definition: InstrumentDefinition


class FormFreeze(GovernanceContract):
    request_key: Code
    content_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    synthetic_review_reference: Code


class FormRead(GovernanceContract):
    id: str
    instrument_key: str
    version: int
    content_digest: str
    definition: InstrumentDefinition
    frozen_for_synthetic_validation: bool
    frozen: bool = False
    production_active: bool = False


class InstrumentAnswer(GovernanceContract):
    item_id: Token
    choice_code: Token | None = None
    integer_value: int | None = Field(default=None, strict=True)
    response_text: str | None = Field(default=None, max_length=10_000)
    missing_reason: MissingReason | None = None

    @model_validator(mode="after")
    def one_value(self):
        if (
            sum(
                v is not None
                for v in (
                    self.choice_code,
                    self.integer_value,
                    self.response_text,
                    self.missing_reason,
                )
            )
            != 1
        ):
            raise ValueError("exactly one answer value or missingness reason is required")
        return self


class LearningStageLinks(GovernanceContract):
    outcome_id: Code | None = None
    task_id: Code | None = None
    response_id: Code | None = None


class InstrumentRecordWrite(GovernanceContract):
    request_key: Code
    subject_user_id: int = Field(gt=0)
    form_version_id: Code
    sequence_key: Code
    stage: Stage
    kind: Literal["response", "missingness", "attrition", "deviation"]
    links: LearningStageLinks = Field(default_factory=LearningStageLinks)
    answers: list[InstrumentAnswer] = Field(default_factory=list, max_length=30)
    reason_code: Token | None = None
    missing_reason: MissingReason | None = None
    supersedes_id: Code | None = None
    correction_reason_code: Token | None = None

    @model_validator(mode="after")
    def shape(self):
        if self.kind == "response":
            if not self.answers or self.reason_code is not None or self.missing_reason is not None:
                raise ValueError("response records require answers only")
        elif (
            self.answers
            or self.reason_code is None
            or (self.kind == "missingness") != (self.missing_reason is not None)
        ):
            raise ValueError(
                "status records require a controlled reason and explicit missingness where applicable"
            )
        if (self.supersedes_id is None) != (self.correction_reason_code is None):
            raise ValueError("corrections require an original reference and controlled reason")
        if len({a.item_id for a in self.answers}) != len(self.answers):
            raise ValueError("duplicate answer item")
        return self


class InstrumentReceipt(GovernanceContract):
    id: str
    revision: int
    recorded_at: AwareDatetime
    production_active: bool = False


class InstrumentReadRequest(GovernanceContract):
    fields: list[ExportField] = Field(min_length=1, max_length=24)


class InstrumentExportRequest(InstrumentReadRequest):
    format: Literal["csv", "json"]
    stages: list[Stage] = Field(min_length=1, max_length=8)
