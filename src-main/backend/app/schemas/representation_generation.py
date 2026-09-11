"""Source-grounded representation drafts; review and delivery remain separate."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.practice_representations import PracticeRepresentation
from app.schemas.support_representations import RepresentationMode


class RepresentationSourceQuote(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_reference: str = Field(min_length=1, max_length=100)
    quote: str = Field(min_length=1, max_length=4000)


class GeneratedCircuitOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    gate: Literal["h", "x", "cx"]
    targets: list[int] = Field(min_length=1, max_length=2)


class GeneratedCircuit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    qubits: int = Field(ge=1, le=5, strict=True)
    operations: list[GeneratedCircuitOperation] = Field(max_length=30)
    shots: int = Field(default=1024, ge=1, le=4096, strict=True)
    seed: int = Field(default=42, ge=0, strict=True)

    @model_validator(mode="after")
    def supported_geometry(self):
        for operation in self.operations:
            if (
                len(operation.targets) != (2 if operation.gate == "cx" else 1)
                or len(set(operation.targets)) != len(operation.targets)
                or any(
                    type(target) is not int or not 0 <= target < self.qubits
                    for target in operation.targets
                )
            ):
                raise ValueError("Generated circuit gates must target valid distinct task wires")
        return self


class GeneratedRepresentation(PracticeRepresentation):
    circuit: GeneratedCircuit | None = None
    source_quotes: list[RepresentationSourceQuote] = Field(min_length=1, max_length=20)

    def reviewed_content(self):
        value = self.model_dump(mode="json", exclude={"source_quotes"})
        if self.circuit is not None:
            value["circuit"] = self.circuit.model_dump(mode="json", exclude_defaults=True)
        return value


class UnavailableRepresentation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    mode: RepresentationMode
    reason: str = Field(min_length=1, max_length=1000)


class GeneratedRepresentations(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["learnlens.generated-representations.v1"] = (
        "learnlens.generated-representations.v1"
    )
    status: Literal["DRAFT"] = "DRAFT"
    variants: list[GeneratedRepresentation] = Field(min_length=1, max_length=20)
    unavailable_modes: list[UnavailableRepresentation] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def distinct_and_grounded(self):
        if len({item.representation_id for item in self.variants}) != len(self.variants):
            raise ValueError("Generated representation IDs must be distinct")
        for item in self.variants:
            if set(item.source_references) != {
                quote.source_reference for quote in item.source_quotes
            }:
                raise ValueError("Every representation source needs an exact source quote")
        available = {item.mode for item in self.variants}
        missing = [item.mode for item in self.unavailable_modes]
        if len(set(missing)) != len(missing) or available & set(missing):
            raise ValueError("Unavailable modes must be distinct and not also offered")
        if available | set(missing) != {"text", "visual", "worked_example", "circuit", "stepwise"}:
            raise ValueError("Offer each format or explain why it is unavailable for this draft")
        return self


class RepresentationGenerationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_revision_id: str = Field(min_length=1, max_length=100)
    target: Literal["practice", "supported", "transfer"]


class RepresentationGenerationRead(BaseModel):
    revision_id: str
    target: Literal["practice", "supported", "transfer"]
    candidate: GeneratedRepresentations
    provider: str
    model: str


def representation_response_schema():
    """Explicit object fields for the existing strict structured-output transport."""
    schema = GeneratedRepresentations.model_json_schema()

    def visit(value):
        if isinstance(value, dict):
            value.pop("default", None)
            if value.get("type") == "object":
                value["additionalProperties"] = False
                value["required"] = list(value.get("properties", {}))
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(schema)
    return schema
