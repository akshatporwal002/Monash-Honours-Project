from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.assessment import AssessmentResult

SelectionRule = Literal["LATEST_VALID", "ANY_VALID_PASS", "ALL_REQUIRED_FORMS"]


class ReassessmentContract(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, str_strip_whitespace=True)


class OutcomePolicyWrite(ReassessmentContract):
    selection_rule: SelectionRule
    required_form_ids: list[str] = Field(default_factory=list, max_length=100)
    reason: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def required_forms(self):
        if (self.selection_rule == "ALL_REQUIRED_FORMS") != bool(self.required_form_ids):
            raise ValueError("Only the all-required-forms rule requires a nonempty form list")
        if len(set(self.required_form_ids)) != len(self.required_form_ids):
            raise ValueError("Required forms must be distinct")
        return self


class OutcomePolicyRead(OutcomePolicyWrite):
    id: str
    definition_version_id: str
    created_at: datetime


class ReassessmentWrite(ReassessmentContract):
    task_form_version_id: str = Field(min_length=1, max_length=36)
    expected_decision_revision: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=2000)
    learner_notice: str = Field(min_length=1, max_length=2000)


class ReassessmentRead(ReassessmentContract):
    id: str
    task_id: str
    task_title: str
    learner_notice: str
    created_at: datetime
    replacement_response_id: str | None
    available: bool


class EquivalentFormRead(ReassessmentContract):
    id: str
    task_id: str
    task_title: str


class ReassessmentSetup(ReassessmentContract):
    definition_version_id: str
    policy: OutcomePolicyRead | None
    forms: list[EquivalentFormRead]
    policy_forms: list[EquivalentFormRead]
    authorisation: ReassessmentRead | None
    fresh_tasks: list["FreshTaskRead"]


class FreshTaskRead(ReassessmentContract):
    task_id: str
    title: str
    prompt: str
    instructions: str
    revision_id: str


class EquivalentFormWrite(ReassessmentContract):
    task_id: str = Field(min_length=1, max_length=36)
    revision_id: str = Field(min_length=1, max_length=36)
    template_form_id: str = Field(min_length=1, max_length=36)
    reason: str = Field(min_length=1, max_length=2000)


class OutcomeResultRead(ReassessmentContract):
    definition_version_id: str
    result: AssessmentResult | None
    status: str
    selection_rule: SelectionRule | None
    evidence_response_ids: list[str]
    explanation: str
    authorisations: list[ReassessmentRead]
