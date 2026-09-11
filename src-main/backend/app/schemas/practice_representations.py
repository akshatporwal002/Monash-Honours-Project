"""Reviewed optional practice content; no assessment or equivalence approval implied."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from app.schemas.support_representations import SupportRepresentation

Identifier = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")]


class PracticeRepresentation(SupportRepresentation):
    representation_id: Identifier
    explanation_detail: Literal["brief", "detailed"]
    support_kind: Literal["instructional", "accessibility"]
    instructional_support_level: int = Field(ge=0, le=4, strict=True)

    @model_validator(mode="after")
    def separate_access(self):
        if (self.support_kind == "accessibility") != (self.instructional_support_level == 0):
            raise ValueError(
                "Access representations must declare level 0; instructional content needs a support level"
            )
        return self


def practice_representations(marking: dict, sources: list[str]) -> list[PracticeRepresentation]:
    items = TypeAdapter(list[PracticeRepresentation]).validate_python(
        marking.get("practice_representations", [])
    )
    if len(items) > 20 or len({item.representation_id for item in items}) != len(items):
        raise ValueError("Use at most twenty representations with distinct IDs")
    if any(not set(item.source_references) <= set(sources) for item in items):
        raise ValueError("Practice representations must cite declared task sources")
    return items


class PracticeRepresentationChoice(BaseModel):
    representation_id: str
    title: str
    mode: str
    explanation_detail: Literal["brief", "detailed"]
    support_kind: Literal["instructional", "accessibility"]
    instructional_support_level: int


class PracticeRepresentationCatalog(BaseModel):
    revision_id: str
    review_event_id: str
    preference_version: int
    on_request: bool
    recommended_id: str | None
    selected_id: str | None
    selection: Literal["preference", "override"]
    explanation: str
    choices: list[PracticeRepresentationChoice]


class PracticeRepresentationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    revision_id: Identifier
    representation_id: Identifier
    preference_version: int = Field(ge=0)
    request_key: Identifier
    selection: Literal["preference", "override"]


class PracticeRepresentationReceipt(BaseModel):
    evidence_id: str
    revision_id: str
    review_event_id: str
    preference_version: int
    selection: Literal["preference", "override"]
    delivered_at: datetime
    representation: PracticeRepresentation
