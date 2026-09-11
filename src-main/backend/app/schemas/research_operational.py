"""Explicit operational field selection and externally reviewed redaction spans."""

from typing import Literal

from pydantic import Field, JsonValue, model_validator

from app.schemas.research_governance import Code, GovernanceContract, OperationalField


class RedactionSpan(GovernanceContract):
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("redaction span must be nonempty")
        return self


class OperationalRedaction(GovernanceContract):
    field: Literal[
        "operational.response_text",
        "operational.code",
        "operational.ai_output",
        "operational.episode",
        "operational.adaptation_reasons",
        "operational.override_reasons",
    ]
    source_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    rule_reference: Code
    review_evidence_reference: Code
    spans: list[RedactionSpan] = Field(max_length=300)


class OperationalSelection(GovernanceContract):
    allocation_id: Code
    instrument_record_id: Code
    fields: list[OperationalField] = Field(min_length=1, max_length=32)
    redactions: list[OperationalRedaction] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.fields)) != len(self.fields) or len(
            {r.field for r in self.redactions}
        ) != len(self.redactions):
            raise ValueError("duplicate operational field")
        if any(r.field not in self.fields for r in self.redactions):
            raise ValueError("redaction for unselected field")
        return self


class OperationalCapture(OperationalSelection):
    request_key: Code
    expected_revision: int = Field(ge=0)


class OperationalFieldRead(GovernanceContract):
    value: JsonValue = None
    missing_reason: (
        Literal[
            "not_recorded",
            "not_applicable",
            "usage_incomplete",
            "adapter_unavailable",
            "redaction_required",
        ]
        | None
    ) = None
    source_digest: str
    source_references: list[str]
    adapter_version: str


class OperationalPreview(GovernanceContract):
    fields: dict[str, OperationalFieldRead]
    production_active: Literal[False] = False
