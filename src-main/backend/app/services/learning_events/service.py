from __future__ import annotations

import hashlib
import hmac
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from uuid import UUID, uuid4, uuid5

from sqlalchemy.orm import Session, sessionmaker

from app.models.enums import LearningEventType
from app.schemas.learning_events import (
    CompletionMetadata,
    CompletionStatus,
    FeedbackViewMetadata,
    LearningEventReceipt,
    SubmissionMetadata,
    validate_learning_event_metadata,
)
from app.services.learning_events.contracts import (
    LearningEventCommand,
    LearningEventRecordResult,
    LearningEventSink,
    LearningEventWrite,
)
from app.services.learning_events.errors import InvalidPseudonymizationSecretError
from app.services.learning_events.repository import SqlAlchemyLearningEventRepository

PSEUDONYM_VERSION = "v1"
MINIMUM_PSEUDONYM_SECRET_BYTES = 32
_FEEDBACK_VIEW_NAMESPACE = UUID("d791d4f3-b575-4c72-968d-d1a8e9c64e0f")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HmacSha256Pseudonymizer:
    """Create stable, versioned pseudonyms with explicit namespace separation."""

    def __init__(self, secret: str | bytes) -> None:
        secret_bytes = secret.encode("utf-8") if isinstance(secret, str) else secret
        if len(secret_bytes) < MINIMUM_PSEUDONYM_SECRET_BYTES:
            raise InvalidPseudonymizationSecretError(
                "the pseudonymization secret must be at least 32 bytes"
            )
        self._secret = secret_bytes

    def pseudonymize(self, namespace: str, reference: str) -> str:
        normalized_namespace = namespace.strip().casefold()
        normalized_reference = reference.strip()
        if not normalized_namespace or not normalized_reference:
            raise ValueError("pseudonym namespace and reference are required")
        message = (
            b"quantumlearn\x00"
            + PSEUDONYM_VERSION.encode("ascii")
            + b"\x00"
            + normalized_namespace.encode("utf-8")
            + b"\x00"
            + normalized_reference.encode("utf-8")
        )
        digest = hmac.new(self._secret, message, hashlib.sha256).hexdigest()
        return f"{PSEUDONYM_VERSION}_{digest}"


class LearningEventRecorder:
    """Strict event writer that owns a fresh transaction for every event."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        pseudonymizer: HmacSha256Pseudonymizer,
        *,
        now: Callable[[], datetime] = _utc_now,
        uuid_factory: Callable[[], str] = lambda: str(uuid4()),
    ) -> None:
        self._session_factory = session_factory
        self._pseudonymizer = pseudonymizer
        self._now = now
        self._uuid_factory = uuid_factory

    def record(self, command: LearningEventCommand) -> LearningEventRecordResult:
        actor_reference = _external_id(command.actor_reference, "actor reference")
        course_id = _external_id(command.course_id, "course ID")
        task_id = _external_id(command.task_id, "task ID")
        client_event_id = _uuid(command.client_event_id, "client event ID")
        correlation_id = _uuid(command.correlation_id, "correlation ID")
        if command.event_type is LearningEventType.FEEDBACK_VIEW:
            if command.workflow_reference is None:
                raise ValueError("feedback-view events require a workflow reference")
            workflow_reference = _uuid(
                command.workflow_reference,
                "workflow reference",
            )
        else:
            if command.workflow_reference is not None:
                raise ValueError("workflow references are only valid for feedback-view events")
            workflow_reference = None
        metadata = validate_learning_event_metadata(command.event_type, command.metadata)
        pseudonym = self._pseudonymizer.pseudonymize("learning-actor", actor_reference)
        occurred_at = self._now()
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        else:
            occurred_at = occurred_at.astimezone(timezone.utc)

        write = LearningEventWrite(
            id=_uuid(self._uuid_factory(), "learning event ID"),
            pseudonymous_user_id=pseudonym,
            course_id=course_id,
            task_id=task_id,
            event_type=command.event_type,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            workflow_reference=workflow_reference,
            metadata=metadata,
            deduplication_key=_deduplication_key(
                pseudonym,
                command.event_type,
                client_event_id,
            ),
        )
        # Never reuse the caller's request-scoped session: analytics persistence must
        # neither commit nor roll back the primary student transaction.
        with self._session_factory() as session:
            return SqlAlchemyLearningEventRepository(session).record(write)


class BestEffortLearningEventSink:
    """Non-blocking adapter for student paths where analytics must not break work."""

    def __init__(
        self,
        recorder: LearningEventRecorder,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._recorder = recorder
        self._logger = logger or logging.getLogger(__name__)

    def record(self, command: LearningEventCommand) -> LearningEventRecordResult | None:
        try:
            return self._recorder.record(command)
        except Exception:
            # Deliberately omit actor, task, course, metadata, and exception text.
            self._logger.warning(
                "learning_event_recording_failed",
                extra={
                    "correlation_id": command.correlation_id,
                    "stage": "learning_event_recording",
                    "failure_category": "analytics_persistence_unavailable",
                },
            )
            return None


class TrustedLearningEventHooks:
    """Typed hooks for server-owned submission, completion, and feedback events."""

    def __init__(self, sink: LearningEventSink) -> None:
        self._sink = sink

    def record_submission(
        self,
        *,
        actor_reference: str,
        course_id: str,
        task_id: str,
        source_event_id: str,
        correlation_id: str,
        attempt_number: int,
        score: float | None = None,
    ) -> LearningEventReceipt | None:
        # Parse the old input shape so existing server callers fail consistently
        # for invalid values, but never copy a numeric score into newly emitted
        # metadata.  Formal assessment results remain Person A's responsibility.
        SubmissionMetadata(attempt_number=attempt_number, score=score)
        return self._record(
            LearningEventCommand(
                actor_reference=actor_reference,
                course_id=course_id,
                task_id=task_id,
                event_type=LearningEventType.SUBMISSION,
                client_event_id=source_event_id,
                correlation_id=correlation_id,
                metadata=SubmissionMetadata(attempt_number=attempt_number).model_dump(
                    mode="json", exclude_none=True
                ),
            )
        )

    def record_completion(
        self,
        *,
        actor_reference: str,
        course_id: str,
        task_id: str,
        source_event_id: str,
        correlation_id: str,
        completion_status: str,
        score: float | None = None,
    ) -> LearningEventReceipt | None:
        # Old ``passed``/``failed`` values are accepted as legacy input, yet new
        # event production records only a server-owned completion occurrence.
        CompletionMetadata(
            completion_status=CompletionStatus(completion_status).value,
            score=score,
        )
        return self._record(
            LearningEventCommand(
                actor_reference=actor_reference,
                course_id=course_id,
                task_id=task_id,
                event_type=LearningEventType.COMPLETION,
                client_event_id=source_event_id,
                correlation_id=correlation_id,
                metadata=CompletionMetadata(
                    completion_status=CompletionStatus.COMPLETED.value
                ).model_dump(mode="json", exclude_none=True),
            )
        )

    def record_feedback_view(
        self,
        *,
        actor_reference: str,
        course_id: str,
        task_id: str,
        workflow_run_id: str,
        correlation_id: str,
        feedback_status: str,
    ) -> LearningEventReceipt | None:
        # UUIDv5 gives every actor the same stable source event for a workflow;
        # actor separation is added by the recorder's deduplication key.
        source_event_id = str(uuid5(_FEEDBACK_VIEW_NAMESPACE, f"workflow:{workflow_run_id}"))
        return self._record(
            LearningEventCommand(
                actor_reference=actor_reference,
                course_id=course_id,
                task_id=task_id,
                event_type=LearningEventType.FEEDBACK_VIEW,
                client_event_id=source_event_id,
                correlation_id=correlation_id,
                workflow_reference=workflow_run_id,
                metadata=FeedbackViewMetadata(feedback_status=feedback_status).model_dump(
                    mode="json"
                ),
            )
        )

    def _record(self, command: LearningEventCommand) -> LearningEventReceipt | None:
        result = self._sink.record(command)
        return result.receipt if result is not None else None


class BestEffortFeedbackViewTracker:
    """Route adapter that can never make terminal feedback retrieval fail."""

    def __init__(
        self,
        hooks: TrustedLearningEventHooks,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._hooks = hooks
        self._logger = logger or logging.getLogger(__name__)

    def record_terminal_view(
        self,
        *,
        actor_reference: str,
        course_id: str,
        task_id: str,
        workflow_run_id: str,
        correlation_id: str,
        feedback_status: str,
    ) -> None:
        try:
            self._hooks.record_feedback_view(
                actor_reference=actor_reference,
                course_id=course_id,
                task_id=task_id,
                workflow_run_id=workflow_run_id,
                correlation_id=correlation_id,
                feedback_status=feedback_status,
            )
        except Exception:
            self._logger.warning(
                "feedback_view_event_recording_failed",
                extra={
                    "correlation_id": correlation_id,
                    "stage": "feedback_view_recording",
                    "failure_category": "analytics_persistence_unavailable",
                },
            )


class NoOpFeedbackViewTracker:
    """Fail-safe default used until event persistence is configured."""

    def record_terminal_view(
        self,
        *,
        actor_reference: str,
        course_id: str,
        task_id: str,
        workflow_run_id: str,
        correlation_id: str,
        feedback_status: str,
    ) -> None:
        return None


def _deduplication_key(
    pseudonymous_actor: str,
    event_type: LearningEventType,
    client_event_id: str,
) -> str:
    value = "\x00".join(
        (
            "quantumlearn-learning-event",
            PSEUDONYM_VERSION,
            pseudonymous_actor,
            event_type.value,
            client_event_id.casefold(),
        )
    )
    return f"{PSEUDONYM_VERSION}_{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _external_id(value: str, label: str) -> str:
    normalized = value.strip()
    if not 1 <= len(normalized) <= 255:
        raise ValueError(f"{label} must contain between 1 and 255 characters")
    return normalized


def _uuid(value: str, label: str) -> str:
    try:
        return str(UUID(value))
    except (AttributeError, TypeError, ValueError):
        raise ValueError(f"{label} must be a UUID") from None
