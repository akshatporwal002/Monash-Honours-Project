"""Bounded curriculum contracts. Diagnostic observations are never formal results."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Identifier = Annotated[
    str, StringConstraints(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PathStep(StrictContract):
    task_id: Identifier
    concept: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    prerequisites: list[Identifier] = Field(max_length=30)
    support_level: Literal["guided", "concept_cue", "independent"]
    faded_support_level: Literal["guided", "concept_cue", "independent"]
    exit_rule: Literal["accepted_response"] = "accepted_response"
    evidence_rule: Text


class PathwayPublish(StrictContract):
    expected_version: int = Field(ge=0)
    request_key: Identifier
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    steps: list[PathStep] = Field(min_length=3, max_length=30)
    diagnostic_prompt: Text
    diagnostic_task_id: Identifier
    independent_conditions: Text
    reason: Text

    @model_validator(mode="after")
    def valid_graph(self):
        seen = set()
        levels = {"guided": 2, "concept_cue": 1, "independent": 0}
        for step in self.steps:
            if step.task_id in seen or len(set(step.prerequisites)) != len(step.prerequisites):
                raise ValueError("Task and prerequisite links must be unique")
            if not set(step.prerequisites) <= seen:
                raise ValueError("Prerequisites must name earlier tasks in this pathway")
            if levels[step.faded_support_level] > levels[step.support_level]:
                raise ValueError("Fading cannot increase support")
            seen.add(step.task_id)
        if self.diagnostic_task_id not in seen:
            raise ValueError("The diagnostic must link to a pathway task")
        return self


class DiagnosticStart(StrictContract):
    request_key: Identifier
    pathway_id: Identifier
    purpose: Literal["initial", "prior_mastery"]
    target_task_id: Identifier


class DiagnosticSubmit(StrictContract):
    request_key: Identifier
    prior_knowledge: Text
    reasoning: Text
    confidence: Literal["unsure", "somewhat_sure", "sure"]
    concept_uncertainty: Literal["none_reported", "needs_checking", "unsure"]
    requested_support: Literal["none", "concept_cue", "guided"]
    independent_conditions_met: bool


class DiagnosticConfirm(StrictContract):
    request_key: Identifier
    decision: Literal["retain", "advance"]
    independent_verified: bool
    reason: Text


class PathBinding(BaseModel):
    title: str
    task_revision_id: str
    review_event_id: str
    source_approvals: dict[str, str]
    difficulty: str
    task_form: str
    assessment: dict[str, str] | None


class PathwayRead(BaseModel):
    id: str
    outcome_id: str
    course_id: str
    version: int
    title: str
    steps: list[PathStep]
    diagnostic_prompt: str
    diagnostic_task_id: str
    independent_conditions: str
    bindings: dict[str, PathBinding]


class DiagnosticRead(BaseModel):
    id: str
    learner_id: int
    learner_name: str
    target_title: str
    pathway_id: str
    purpose: str
    target_task_id: str
    state: Literal["started", "needs_review", "retain", "advance"]
    prompt: str
    independent_conditions: str
    evidence_id: str | None
    response: DiagnosticSubmit | None
    reason: str | None
