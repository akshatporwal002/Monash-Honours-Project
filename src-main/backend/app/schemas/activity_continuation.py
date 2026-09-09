"""Scope comes from authentication and the saved workflow, never these commands."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActivityAction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    expected_version: int = Field(ge=0)
    request_key: str = Field(min_length=1, max_length=100)
    action: Literal["accept", "defer", "replace", "educator_override"]
    task_id: str | None = Field(default=None, min_length=1, max_length=255)
    reason: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def shape(self):
        if self.action in {"replace", "educator_override"} and not self.task_id:
            raise ValueError("Choose an approved activity")
        if self.action in {"accept", "defer"} and self.task_id is not None:
            raise ValueError("This action uses the saved suggestion")
        if self.action == "educator_override" and not self.reason:
            raise ValueError("An educator override requires a reason")
        return self


class ActivityOption(BaseModel):
    task_id: str
    title: str
    support_level: str | None


class ActivityHistory(BaseModel):
    version: int
    action: str
    task_id: str | None
    reason: str
    educator: bool
    created_at: datetime


class ActivityRead(BaseModel):
    learner_label: str = "Learner"
    workflow_id: str
    state: str
    reason: str
    uncertainty: float | None = None
    snapshot_id: str | None = None
    rule_version: str = "approved-activity.v1"
    evidence_ids: list[str] = Field(default_factory=list)
    preference_version: int | None = None
    pathway_id: str | None = None
    next_task_id: str | None = None
    options: list[ActivityOption] = Field(default_factory=list)
    version: int = 0
    history: list[ActivityHistory] = Field(default_factory=list)
    can_override: bool = False
