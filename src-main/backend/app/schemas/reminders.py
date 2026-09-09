"""Reminder controls use absolute instants and explicit course-local deadlines."""

from datetime import UTC, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


def validate_time_zone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("Use a valid IANA time zone, such as Australia/Sydney") from error
    return value


TimeZone = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
    AfterValidator(validate_time_zone),
]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ReminderSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ReminderPreferenceRead(ReminderSchema):
    revision: int = 0
    enabled: bool = True
    paused_until: datetime | None = None

    @field_validator("paused_until")
    @classmethod
    def utc(cls, value):
        return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


class ReminderPreferenceWrite(ReminderSchema):
    expected_revision: int = Field(ge=0, strict=True)
    idempotency_key: str = Field(min_length=1, max_length=128)
    enabled: bool
    paused_until: AwareDatetime | None = None


class DeadlineArrangementWrite(ReminderSchema):
    expected_revision: int = Field(ge=0, strict=True)
    idempotency_key: str = Field(min_length=1, max_length=128)
    kind: Literal["EXTENSION", "ACCESS_PLAN"]
    time_zone: TimeZone
    active: bool = True
    local_due_at: datetime | None = None
    fold: Literal[0, 1] | None = None
    reminders_paused: bool = False
    reason: Reason
    learner_notice: Reason

    @model_validator(mode="after")
    def consistent(self):
        if self.local_due_at is not None and self.local_due_at.tzinfo is not None:
            raise ValueError("Enter the deadline in the course's local time without an offset")
        if not self.active and (self.local_due_at is not None or self.reminders_paused):
            raise ValueError("A revoked arrangement cannot set a deadline or pause reminders")
        if self.active and self.local_due_at is None and not self.reminders_paused:
            raise ValueError("Set an extended deadline or pause reminders under an access plan")
        if self.reminders_paused and self.kind != "ACCESS_PLAN":
            raise ValueError("A task reminder pause requires an access plan")
        return self


class DeadlineArrangementRead(ReminderSchema):
    id: str
    revision: int
    kind: Literal["EXTENSION", "ACCESS_PLAN"]
    active: bool
    due_at: datetime | None
    reminders_paused: bool
    time_zone: str
    reason: str
    learner_notice: str
    created_at: datetime

    @field_validator("due_at", "created_at")
    @classmethod
    def utc(cls, value):
        return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


class LearnerDeadlineRead(ReminderSchema):
    task_id: str
    time_zone: str
    original_due_at: datetime | None
    effective_due_at: datetime | None
    reminders_paused: bool
    arrangement_active: bool = False
    learner_notice: str | None = None

    @field_validator("original_due_at", "effective_due_at")
    @classmethod
    def utc(cls, value):
        return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value
