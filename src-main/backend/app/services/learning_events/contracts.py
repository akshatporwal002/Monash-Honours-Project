from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Protocol

from app.models.enums import LearningEventType
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.learning_events import LearningEventReceipt, TrustedEvidenceAnalyticsMetadata


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


@dataclass(frozen=True, slots=True)
class TrustedEvidenceAnalyticsEvent:
    """Content-free event sent only after an evidence record is durable.

    ``event_id`` is the globally unique append-only evidence ID.  It lets an
    analytics persistence adapter deduplicate without receiving a learner ID or
    the protected artefact content.
    """

    event_id: str
    course_id: str
    outcome_id: str | None
    activity_id: str
    task_id: str
    occurred_at: datetime
    correlation_id: str
    metadata: TrustedEvidenceAnalyticsMetadata


class LearningEventAccessPolicy(Protocol):
    async def resolve_task_scope(
        self,
        actor: AuthenticatedActor,
        task_id: str,
    ) -> LearningEventScope | None:
        """Return the authorized canonical task scope, or None without leaking it."""


class LearningEventSink(Protocol):
    def record(self, command: LearningEventCommand) -> LearningEventRecordResult | None: ...


class EvidenceAnalyticsSink(Protocol):
    """Best-effort persistence port for metadata-only trusted evidence events."""

    def record(self, event: TrustedEvidenceAnalyticsEvent) -> None: ...


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
