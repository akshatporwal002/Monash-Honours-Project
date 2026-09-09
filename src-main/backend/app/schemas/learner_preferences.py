"""Explicit choices, separate from evidence and inferred learner traits."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PreferenceValues(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    pace: Literal["self_paced", "stepwise"] = "self_paced"
    format: Literal["text", "stepwise"] = "text"
    explanation_detail: Literal["brief", "detailed"] = "brief"
    breaks: bool = False
    repeat_practice: bool = False
    personalisation_enabled: bool = True
    support_amount: Literal["standard", "on_request"] = "standard"
    feedback_form: Literal["inline", "expandable"] = "inline"


class PreferenceRead(BaseModel):
    version: int
    values: PreferenceValues


class PreferenceReset(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_version: int = Field(ge=0)
    request_key: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")


class PreferenceUpdate(PreferenceReset):
    values: PreferenceValues


class PreferenceRevision(PreferenceRead):
    action: Literal["save", "reset"]
    created_at: datetime


class PreferenceHistory(BaseModel):
    items: list[PreferenceRevision]
    next_offset: int | None


class EffectivePreferences(PreferenceRead):
    requested: PreferenceValues
    transfer: bool
    repeat_allowed: bool
    limitations: list[str]
    pathway_support_level: Literal["guided", "concept_cue", "independent"] | None = None
