from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models.audit import AuditAction, AuditOutcome

NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
AuditActor = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=255,
        pattern=r"^(?:v1_[0-9a-f]{64}|system(?:_[a-z0-9.-]{1,64})?)$",
    ),
]
ShortLabel = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9_.-]*$",
    ),
]
UuidString = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-"
            r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
        ),
    ),
]


def _normalise_datetime(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    return value


class AuditContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True, strict=True)


class AuditEventCommand(AuditContract):
    actor_reference: AuditActor
    action: AuditAction
    outcome: AuditOutcome
    correlation_id: UuidString
    resource_type: ShortLabel
    resource_id: UuidString
    failure_category: ShortLabel | None = None
    deduplication_key: NonEmptyText
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("occurred_at", mode="before")
    @classmethod
    def normalise_occurred_at(cls, value: Any) -> Any:
        return _normalise_datetime(value)

    @model_validator(mode="after")
    def validate_outcome(self) -> "AuditEventCommand":
        if (self.outcome is AuditOutcome.FAILURE) != (self.failure_category is not None):
            raise ValueError("failed audit events require one sanitized failure category")
        return self


class AuditEventReceipt(AuditEventCommand):
    id: UuidString
    created: bool
