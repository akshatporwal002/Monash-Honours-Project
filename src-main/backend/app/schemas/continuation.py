from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

OpaqueReference = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=255,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
WorkflowId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
            r"4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-"
            r"[0-9a-fA-F]{12}$"
        ),
    ),
]


class ContinuationAvailability(str, Enum):
    PROCESSING = "processing"
    READY = "ready"
    UNAVAILABLE = "unavailable"


class ContinuationResponse(BaseModel):
    """Route-ready continuation state exposed by the owning learning workflow."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    workflow_run_id: WorkflowId
    status: ContinuationAvailability
    next_task_reference: OpaqueReference | None = None
    retryable: bool = False

    @model_validator(mode="after")
    def validate_status_shape(self) -> "ContinuationResponse":
        if self.status is ContinuationAvailability.READY:
            if self.next_task_reference is None:
                raise ValueError("ready continuation requires a next-task reference")
        elif self.next_task_reference is not None:
            raise ValueError("only ready continuation can expose a next-task reference")
        if self.status is not ContinuationAvailability.UNAVAILABLE and self.retryable:
            raise ValueError("only unavailable continuation can be retryable")
        return self
