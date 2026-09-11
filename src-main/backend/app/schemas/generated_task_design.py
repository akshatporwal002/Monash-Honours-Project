"""Declared teaching design for generated drafts; formal approval is separate."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GeneratedTaskDesign(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["learnlens.generated-design.v1"] = "learnlens.generated-design.v1"
    assessment_purpose: Literal["FORMATIVE"]
    difficulty_basis: str = Field(min_length=1, max_length=2000)
    intended_evidence: str = Field(min_length=1, max_length=2000)
    expected_response_features: list[str] = Field(min_length=1, max_length=20)
    permitted_tools: list[str] = Field(max_length=20)
    instructional_support: str = Field(min_length=1, max_length=2000)
    access_modes: list[str] = Field(min_length=1, max_length=20)
    equivalent_formats: list[str] = Field(max_length=20)
    rubric_version: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def nonblank(self):
        values = [
            self.difficulty_basis,
            self.intended_evidence,
            self.instructional_support,
            self.rubric_version,
            *self.expected_response_features,
            *self.permitted_tools,
            *self.access_modes,
            *self.equivalent_formats,
        ]
        if any(not value.strip() or len(value) > 2000 for value in values):
            raise ValueError("Generated teaching design fields must contain concise nonblank text")
        return self


def local_design(task_type, outcome, difficulty):
    return GeneratedTaskDesign(
        assessment_purpose="FORMATIVE",
        difficulty_basis=f"Draft {difficulty} scaffold; educator must verify demand against the source and outcome.",
        intended_evidence=f"{task_type.replace('_', ' ')} response linked to {outcome[:1000]}",
        expected_response_features=[
            "Use the cited source accurately",
            "Complete the declared response structure",
        ],
        permitted_tools=["Cited course material"],
        instructional_support="Educator-reviewed conceptual support; no formal result from this draft.",
        access_modes=["Keyboard", "Text equivalent"],
        equivalent_formats=[],
        rubric_version="local-scaffold-review-v1",
    ).model_dump(mode="json")
