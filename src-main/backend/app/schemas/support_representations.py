"""Reviewed instructional representations released only in the supported stage."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RepresentationMode = Literal["text", "visual", "worked_example", "circuit", "stepwise"]


class SupportRepresentationChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    item_index: int = Field(ge=0, lt=100)
    title: str = Field(min_length=1, max_length=200)
    mode: RepresentationMode
    explanation_detail: Literal["brief", "detailed"] = "detailed"


class SupportRepresentation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    explanation_detail: Literal["brief", "detailed"] = "detailed"
    instructional_support_level: int = Field(ge=1, le=4, strict=True)
    mode: RepresentationMode
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=4000)
    steps: list[str] = Field(default_factory=list, max_length=12)
    circuit: dict | None = None
    source_references: list[str] = Field(min_length=1, max_length=20)
    equivalence_basis: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def valid_content(self):
        if not all(
            value.strip()
            for value in [
                self.title,
                self.text,
                self.equivalence_basis,
                *self.steps,
                *self.source_references,
            ]
        ):
            raise ValueError("Representation text, sources and equivalence basis cannot be blank")
        if self.mode == "worked_example" and self.instructional_support_level < 4:
            raise ValueError("Worked examples must be declared as partial worked support")
        if self.mode in {"visual", "stepwise"} and len(self.steps) < 2:
            raise ValueError("Visual and stepwise representations need at least two labelled steps")
        if any(len(step) > 1000 for step in self.steps):
            raise ValueError("Representation steps must be concise")
        if self.mode == "circuit" and self.circuit is None:
            raise ValueError("A circuit representation needs a circuit")
        if self.mode != "circuit" and self.circuit is not None:
            raise ValueError("Only circuit representations may carry circuit content")
        return self


class AccessRepresentation(SupportRepresentation):
    """A reviewed equivalent input with no instructional help or worked solution."""

    instructional_support_level: int = Field(default=0, ge=0, le=0, strict=True)
    mode: Literal["text", "visual", "circuit", "stepwise"]
