"""Reviewer-only contracts; snapshots include protected marking guidance."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.category_review import (
    CategoryReviewRecord,
    CategoryReviewRequest,
    DimensionFinding,
)


class TaskCategoryReviewSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    findings: list[DimensionFinding]


class TaskCategoryReviewContext(BaseModel):
    required: bool
    request_digest: str
    request: CategoryReviewRequest


class TaskReviewWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_id: str = Field(min_length=1, max_length=36)
    expected_review_version: int = Field(ge=0, strict=True)
    state: Literal["SUBMITTED", "APPROVED", "REJECTED", "WITHDRAWN"]
    reason: str = Field(min_length=1, max_length=2000)
    quality_review: TaskCategoryReviewSubmission | None = None


class TaskReviewSummary(BaseModel):
    quality_review_required: bool = False
    revision_id: str | None
    revision: int
    content_digest: str | None
    state: Literal["DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "WITHDRAWN"]
    review_version: int
    available: bool
    issues: list[str]


class TaskHistoryRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class TaskRevisionRead(TaskHistoryRecord):
    id: str
    task_id: str
    course_id: str
    version: int
    snapshot: dict[str, Any]
    content_digest: str
    provenance: Literal["AUTHORED", "GENERATED", "LEGACY"]
    actor_user_id: int | None


class TaskReviewEventRead(TaskHistoryRecord):
    id: str
    task_revision_id: str
    course_id: str
    version: int
    state: Literal["SUBMITTED", "APPROVED", "REJECTED", "WITHDRAWN"]
    actor_user_id: int
    reason: str
    source_approvals: dict[str, str]
    policy_version: str


class TaskCategoryReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_revision_id: str
    task_review_event_id: str
    reviewer_id: int
    receipt: CategoryReviewRecord


class TaskReviewHistoryRead(BaseModel):
    revision: TaskRevisionRead
    events: list[TaskReviewEventRead]
    quality_reviews: list[TaskCategoryReviewRead] = Field(default_factory=list)
