from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Protocol

from app.models.enums import LearningEventType
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.learning_events import LearningEventReceipt


@dataclass(frozen=True, slots=True)
class LearningEventScope:
    course_id: str
    task_id: str


@dataclass(frozen=True, slots=True)
class LearningEventCommand:
    actor_reference: str
    course_id: str
    task_id: str
    event_type: LearningEventType
    client_event_id: str
    correlation_id: str
    metadata: Mapping[str, object]
    workflow_reference: str | None = None


@dataclass(frozen=True, slots=True)
class LearningEventWrite:
    id: str
    pseudonymous_user_id: str
    course_id: str
    task_id: str
    event_type: LearningEventType
    occurred_at: datetime
    correlation_id: str
    workflow_reference: str | None
    metadata: dict[str, object]
    deduplication_key: str


@dataclass(frozen=True, slots=True)
class LearningEventRecordResult:
    receipt: LearningEventReceipt
    created: bool


class LearningEventAccessPolicy(Protocol):
    async def resolve_task_scope(
        self,
        actor: AuthenticatedActor,
        task_id: str,
    ) -> LearningEventScope | None:
        """Return the authorized canonical task scope, or None without leaking it."""


class LearningEventSink(Protocol):
    def record(self, command: LearningEventCommand) -> LearningEventRecordResult | None: ...


class FeedbackViewTracker(Protocol):
    def record_terminal_view(
        self,
        *,
        actor_reference: str,
        course_id: str,
        task_id: str,
        workflow_run_id: str,
        correlation_id: str,
        feedback_status: str,
    ) -> None: ...
