"""Closed public contracts for explicit, correctable preferences."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.platform_enums import ExplanationDetail, PreferenceFormat, PreferencePace


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LearnerPreferencesWrite(_Contract):
    pace: PreferencePace
    format: PreferenceFormat
    explanation_detail: ExplanationDetail
    optional_breaks_enabled: bool
    repeat_practice_enabled: bool
    personalisation_enabled: bool
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=255)


class LearnerPreferencesRead(_Contract):
    pace: PreferencePace
    format: PreferenceFormat
    explanation_detail: ExplanationDetail
    optional_breaks_enabled: bool
    repeat_practice_enabled: bool
    personalisation_enabled: bool
    revision: int
    saved: bool
    schema_version: str = "learnlens.learner-preferences.v1"
    saved_at: datetime | None = None

    @classmethod
    def defaults(cls) -> "LearnerPreferencesRead":
        return cls(
            pace=PreferencePace.DEFAULT,
            format=PreferenceFormat.NO_PREFERENCE,
            explanation_detail=ExplanationDetail.STANDARD,
            optional_breaks_enabled=False,
            repeat_practice_enabled=False,
            personalisation_enabled=True,
            revision=0,
            saved=False,
        )
