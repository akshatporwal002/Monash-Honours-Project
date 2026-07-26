from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.services.analytics.metrics import (
    MAX_ANALYTICS_FILTER_VALUES,
    AnalyticsFilterSnapshot,
    InactiveLearner,
    MetricValue,
)

ExternalId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class AnalyticsApiContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class AnalyticsFilterOptions(AnalyticsApiContract):
    schema_version: str = "analytics-filter-options-v1"
    generated_at: datetime
    courses: list[ExternalId] = Field(
        default_factory=list,
        max_length=MAX_ANALYTICS_FILTER_VALUES,
    )
    task_types: list[ExternalId] = Field(
        default_factory=list,
        max_length=MAX_ANALYTICS_FILTER_VALUES,
    )
    models: list[ExternalId] = Field(
        default_factory=list,
        max_length=MAX_ANALYTICS_FILTER_VALUES,
    )
    experimental_conditions: list[ExternalId] = Field(
        default_factory=list,
        max_length=MAX_ANALYTICS_FILTER_VALUES,
    )
    judge_decisions: list[ExternalId] = Field(
        default_factory=list,
        max_length=MAX_ANALYTICS_FILTER_VALUES,
    )


class InactiveLearnerPage(AnalyticsApiContract):
    schema_version: str = "inactive-learners-v1"
    filters: AnalyticsFilterSnapshot = Field(default_factory=AnalyticsFilterSnapshot)
    generated_at: datetime
    inactive_learner_count: MetricValue
    excluded_incomplete_count: int = Field(default=0, ge=0)
    items: list[InactiveLearner] = Field(max_length=100)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
