"""Versioned matching and sequencing definitions and lossless response evidence."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

Identifier = Annotated[str, Field(strict=True, min_length=1, max_length=100)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StructuredItem(Contract):
    id: Identifier
    text: Annotated[str, Field(strict=True, min_length=1, max_length=2000)]
    source_references: Annotated[list[Identifier], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def nonblank(self):
        if not self.text.strip() or not self.id.strip():
            raise ValueError("Item labels and IDs must not be blank")
        return self


Items = Annotated[list[StructuredItem], Field(min_length=2, max_length=20)]


class MatchingDefinition(Contract):
    schema_version: Literal["learnlens.matching.v1"] = "learnlens.matching.v1"
    task_type: Literal["matching"] = "matching"
    prompts: Items
    options: Items


class SequencingDefinition(Contract):
    schema_version: Literal["learnlens.sequencing.v1"] = "learnlens.sequencing.v1"
    task_type: Literal["sequencing"] = "sequencing"
    items: Items


StructuredDefinition = Annotated[
    MatchingDefinition | SequencingDefinition, Field(discriminator="task_type")
]
DEFINITION = TypeAdapter(StructuredDefinition)


class MatchingResponse(Contract):
    schema_version: Literal["learnlens.matching-response.v1"] = "learnlens.matching-response.v1"
    pairs: dict[Identifier, Identifier] = Field(max_length=20)
    labels: dict[
        Annotated[str, Field(strict=True, max_length=110)], Annotated[str, Field(max_length=2000)]
    ] = Field(default_factory=dict, max_length=40)


class SequencingResponse(Contract):
    schema_version: Literal["learnlens.sequencing-response.v1"] = "learnlens.sequencing-response.v1"
    order: list[Identifier] = Field(max_length=20)
    labels: dict[
        Annotated[str, Field(strict=True, max_length=110)], Annotated[str, Field(max_length=2000)]
    ] = Field(default_factory=dict, max_length=20)


def definition_for(task_type: str, criteria: dict, sources: list[str]):
    if task_type not in {"matching", "sequencing"}:
        if "structured_task" in criteria:
            raise ValueError("Structured definition does not match the task type")
        return None
    definition = DEFINITION.validate_python(criteria.get("structured_task"))
    if definition.task_type != task_type:
        raise ValueError("Structured definition does not match the task type")
    groups = (
        [definition.prompts, definition.options]
        if isinstance(definition, MatchingDefinition)
        else [definition.items]
    )
    for items in groups:
        if len({item.id for item in items}) != len(items):
            raise ValueError("Item IDs must be unique within each group")
        if any(not set(item.source_references) <= set(sources) for item in items):
            raise ValueError("Every item must cite a declared task source")
    if isinstance(definition, MatchingDefinition) and len(definition.prompts) != len(
        definition.options
    ):
        raise ValueError("Matching uses one option per prompt")
    return definition


def response_for(definition, answer: str, *, complete: bool):
    if not answer and not complete:
        return None
    if isinstance(definition, MatchingDefinition):
        response = MatchingResponse.model_validate_json(answer)
        prompts = {item.id for item in definition.prompts}
        options = {item.id for item in definition.options}
        if not set(response.pairs) <= prompts or not set(response.pairs.values()) <= options:
            raise ValueError("Response contains an unknown matching item")
        if len(set(response.pairs.values())) != len(response.pairs):
            raise ValueError("Each matching option may be used once")
        if complete and set(response.pairs) != prompts:
            raise ValueError("Match every prompt before submitting")
        labels = {
            **{f"prompt:{item.id}": item.text for item in definition.prompts},
            **{f"option:{item.id}": item.text for item in definition.options},
        }
    else:
        response = SequencingResponse.model_validate_json(answer)
        items = {item.id for item in definition.items}
        if len(set(response.order)) != len(response.order) or not set(response.order) <= items:
            raise ValueError("Sequence items must be known and unique")
        if complete and set(response.order) != items:
            raise ValueError("Order every item before submitting")
        labels = {f"item:{item.id}": item.text for item in definition.items}
    if response.labels and response.labels != labels:
        raise ValueError("Saved item labels must match the reviewed task")
    return response
