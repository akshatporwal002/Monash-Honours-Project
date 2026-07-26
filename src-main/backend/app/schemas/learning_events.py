from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
)

from app.models.enums import LearningEventType

MAX_LEARNING_EVENT_METADATA_BYTES = 1024
MAX_LEARNING_EVENT_TEXT_LENGTH = 100

ExternalId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
EventUuid = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
            r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
        ),
    ),
]
SourceSlug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_LEARNING_EVENT_TEXT_LENGTH,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]

_SENSITIVE_KEY_PARTS = frozenset(
    {
        "accesstoken",
        "answer",
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "draft",
        "email",
        "feedbacktext",
        "name",
        "password",
        "prompt",
        "rawresponse",
        "secret",
        "sourcechunk",
        "submittedanswer",
        "token",
    }
)
_KEY_NORMALIZER = re.compile(r"[^a-z0-9]+")


class CompletionStatus(str, Enum):
    COMPLETED = "completed"
    PASSED = "passed"
    FAILED = "failed"


class LearningEventContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class TaskViewMetadata(LearningEventContract):
    source: SourceSlug | None = None


class DraftSaveMetadata(LearningEventContract):
    duration_ms: Annotated[int, Field(ge=0, le=86_400_000)] | None = None


class SubmissionMetadata(LearningEventContract):
    attempt_number: Annotated[int, Field(ge=1, le=10_000)]
    score: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)] | None = None


class FeedbackViewMetadata(LearningEventContract):
    feedback_status: Literal["validated", "fallback"]


class CompletionMetadata(LearningEventContract):
    completion_status: Literal["completed", "passed", "failed"]
    score: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)] | None = None


LearningEventMetadata: TypeAlias = (
    TaskViewMetadata
    | DraftSaveMetadata
    | SubmissionMetadata
    | FeedbackViewMetadata
    | CompletionMetadata
)

_METADATA_ADAPTERS: dict[LearningEventType, TypeAdapter[Any]] = {
    LearningEventType.TASK_VIEW: TypeAdapter(TaskViewMetadata),
    LearningEventType.DRAFT_SAVE: TypeAdapter(DraftSaveMetadata),
    LearningEventType.SUBMISSION: TypeAdapter(SubmissionMetadata),
    LearningEventType.FEEDBACK_VIEW: TypeAdapter(FeedbackViewMetadata),
    LearningEventType.COMPLETION: TypeAdapter(CompletionMetadata),
}


def validate_learning_event_metadata(
    event_type: LearningEventType,
    metadata: Mapping[str, object] | LearningEventMetadata,
) -> dict[str, object]:
    """Return canonical, flat metadata for the supplied event type.

    The recursive inspection happens before Pydantic validation so sensitive keys are
    rejected even when hidden inside an otherwise-invalid nested object.
    """

    if isinstance(metadata, BaseModel):
        raw: object = metadata.model_dump(mode="json", exclude_none=True)
    else:
        raw = dict(metadata)
    _inspect_metadata(raw)
    parsed = _METADATA_ADAPTERS[event_type].validate_python(raw, strict=True)
    canonical = parsed.model_dump(mode="json", exclude_none=True)
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(encoded.encode("utf-8")) > MAX_LEARNING_EVENT_METADATA_BYTES:
        raise ValueError("learning-event metadata is too large")
    return canonical


def _inspect_metadata(value: object, *, nested: bool = False) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("learning-event metadata must be an object")
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError("learning-event metadata keys must be strings")
        normalized_key = _KEY_NORMALIZER.sub("", key.casefold())
        if any(part in normalized_key for part in _SENSITIVE_KEY_PARTS):
            raise ValueError("learning-event metadata contains a sensitive key")
        if isinstance(item, Mapping) or isinstance(item, (list, tuple, set)):
            if isinstance(item, Mapping):
                _inspect_metadata(item, nested=True)
            raise ValueError("learning-event metadata must be flat")
        if isinstance(item, str) and len(item) > MAX_LEARNING_EVENT_TEXT_LENGTH:
            raise ValueError("learning-event metadata contains an oversized value")
    if nested:
        raise ValueError("learning-event metadata must be flat")


class TaskViewLearningEventRequest(LearningEventContract):
    event_id: EventUuid
    event_type: Literal["task_view"]
    task_id: ExternalId
    metadata: TaskViewMetadata = Field(default_factory=TaskViewMetadata)


class DraftSaveLearningEventRequest(LearningEventContract):
    event_id: EventUuid
    event_type: Literal["draft_save"]
    task_id: ExternalId
    metadata: DraftSaveMetadata = Field(default_factory=DraftSaveMetadata)


# Browser-originated events are deliberately limited to these two low-risk types.
BrowserLearningEventRequest: TypeAlias = Annotated[
    TaskViewLearningEventRequest | DraftSaveLearningEventRequest,
    Field(discriminator="event_type"),
]


class LearningEventReceipt(LearningEventContract):
    learning_event_id: EventUuid
    status: Literal["recorded"] = "recorded"
    occurred_at: datetime
