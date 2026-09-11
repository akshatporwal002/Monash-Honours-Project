"""Study workflow contracts. Recorded references do not activate production research."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.schemas.research_governance import Code, GovernanceContract, OperationalField
from app.schemas.research_instruments import (
    ExportField,
    FormRead,
    InstrumentRecordWrite,
    MissingReason,
    Stage,
    Token,
)

StudyExportField = Literal[
    "study.record_id",
    "study.participant_id",
    "study.sequence_id",
    "study.stage",
    "study.condition",
    "study.plan_id",
    "study.record_kind",
    "study.instrument_record_id",
    "study.packet_id",
    "study.rubric_code",
    "study.value_code",
    "study.missing_reason",
]


class StudyStage(GovernanceContract):
    stage: Stage
    form_id: Code


class StudyRubric(GovernanceContract):
    code: Token
    wording: str = Field(min_length=1, max_length=2000)
    values: list[Token] = Field(min_length=1, max_length=30)


class StudyPlan(GovernanceContract):
    kind: Literal["plan"] = "plan"
    expected_revision: int = Field(ge=0)
    authority_reference: Code
    evidence_reference: Code
    allocation_rule_reference: Code
    redaction_rule_reference: Code
    conditions: list[Token] = Field(min_length=1, max_length=20)
    stages: list[StudyStage] = Field(min_length=1, max_length=8)
    rubrics: list[StudyRubric] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def unique(self):
        for values in (
            self.conditions,
            [s.stage for s in self.stages],
            [r.code for r in self.rubrics],
            *[r.values for r in self.rubrics],
        ):
            if len(set(values)) != len(values):
                raise ValueError("study codes must be unique")
        return self


class StudyAllocation(GovernanceContract):
    kind: Literal["allocation"] = "allocation"
    subject_user_id: int = Field(gt=0)
    plan_id: Code
    sequence_key: Code
    condition: Token
    allocation_evidence_reference: Code


class StudyPacket(GovernanceContract):
    kind: Literal["packet"] = "packet"
    allocation_id: Code
    instrument_record_id: Code
    reviewer_user_id: int = Field(gt=0)
    rubric_code: Token
    redacted_evidence: str = Field(min_length=1, max_length=10000)
    redaction_evidence_reference: Code


class StudyRating(GovernanceContract):
    kind: Literal["rating"] = "rating"
    packet_id: Code
    value_code: Token | None = None
    missing_reason: MissingReason | None = None

    @model_validator(mode="after")
    def value(self):
        if (self.value_code is None) == (self.missing_reason is None):
            raise ValueError("provide one coded value or missingness reason")
        return self


class StudyOutcome(StudyRating):
    kind: Literal["outcome"] = "outcome"
    rating_id: Code
    interpretation_reference: Code


class StudyCommand(GovernanceContract):
    request_key: Code
    decision: Annotated[
        StudyPlan | StudyAllocation | StudyPacket | StudyRating | StudyOutcome,
        Field(discriminator="kind"),
    ]


class StudySelfResponse(GovernanceContract):
    allocation_id: Code
    record: InstrumentRecordWrite


class StudyExportRequest(GovernanceContract):
    format: Literal["csv", "json"]
    fields: list[StudyExportField | ExportField | OperationalField] = Field(
        min_length=1, max_length=64
    )
    stages: list[Stage] = Field(min_length=1, max_length=8)


class StudyReceipt(GovernanceContract):
    id: str
    kind: str
    revision: int
    production_active: Literal[False] = False


class StudyPacketRead(GovernanceContract):
    id: str
    stage: Stage
    rubric: StudyRubric
    redacted_evidence: str
    production_active: Literal[False] = False


class StudyPlanRead(GovernanceContract):
    id: str
    revision: int
    plan: StudyPlan
    production_active: Literal[False] = False


class StudyAssignedForm(GovernanceContract):
    stage: Stage
    form: FormRead


class StudyAssignmentRead(GovernanceContract):
    allocation_id: str
    stages: list[StudyAssignedForm]
