"""Trusted capture boundary between protected evidence and research analytics."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from app.domain.platform_enums import EvidenceType
from app.schemas.learning_events import TrustedEvidenceAnalyticsMetadata
from app.services.evidence.repository import EvidenceCapture
from app.services.evidence.safety import EvidenceAccessScope
from app.services.evidence.service import (
    EvidenceCaptureResult,
    EvidenceCaptureState,
    EvidenceService,
)
from app.services.learning_events.contracts import (
    EvidenceAnalyticsSink,
    TrustedEvidenceAnalyticsEvent,
)


class EvidenceAnalyticsState(str, Enum):
    """Bounded status for a metadata-only analytics side effect."""

    RECORDED = "recorded"
    NOT_EMITTED_REPLAY = "not_emitted_replay"
    NOT_ATTEMPTED_RECONCILIATION = "not_attempted_reconciliation"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class TrustedEvidenceCaptureCommand:
    """Server-constructed capture only; browser request models cannot create it."""

    scope: EvidenceAccessScope
    capture: EvidenceCapture


@dataclass(frozen=True, slots=True)
class TrustedEvidenceCaptureResult:
    """Separate durable-evidence and best-effort-analytics outcomes."""

    evidence: EvidenceCaptureResult
    analytics_state: EvidenceAnalyticsState


_TRUSTED_CAPTURE_TYPES = frozenset(
    {
        EvidenceType.PREDICTION,
        EvidenceType.RESPONSE,
        EvidenceType.REVISION,
        EvidenceType.REASONING,
        EvidenceType.CONFIDENCE,
        EvidenceType.HINT,
        EvidenceType.SCAFFOLD,
        EvidenceType.REFLECTION,
        EvidenceType.SIMULATION,
        EvidenceType.TRANSFER,
        EvidenceType.MISCONCEPTION_CHECK,
    }
)


class TrustedEvidenceCaptureAdapter:
    """Persist protected evidence first, then emit a safe best-effort projection.

    This adapter is intentionally a server-side construction boundary rather
    than an API request model.  It therefore cannot turn a browser payload into
    a submission, completion, support, or assessment-linked event.
    """

    def __init__(
        self,
        evidence_service: EvidenceService,
        analytics_sink: EvidenceAnalyticsSink,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._evidence_service = evidence_service
        self._analytics_sink = analytics_sink
        self._logger = logger or logging.getLogger(__name__)

    def capture(self, command: TrustedEvidenceCaptureCommand) -> TrustedEvidenceCaptureResult:
        record = command.capture.record
        if record.evidence_type not in _TRUSTED_CAPTURE_TYPES:
            raise ValueError("evidence type is not supported by the trusted capture adapter")

        evidence_result = self._evidence_service.capture(command.scope, command.capture)
        if evidence_result.state is EvidenceCaptureState.PENDING_RECONCILIATION:
            return TrustedEvidenceCaptureResult(
                evidence=evidence_result,
                analytics_state=EvidenceAnalyticsState.NOT_ATTEMPTED_RECONCILIATION,
            )
        if not evidence_result.created:
            return TrustedEvidenceCaptureResult(
                evidence=evidence_result,
                analytics_state=EvidenceAnalyticsState.NOT_EMITTED_REPLAY,
            )

        reference = evidence_result.reference
        if reference is None:  # Defensive: a stored result must always be referencable.
            raise RuntimeError("stored evidence did not return an opaque reference")
        event = TrustedEvidenceAnalyticsEvent(
            event_id=reference.evidence_id,
            course_id=record.course_id,
            outcome_id=record.outcome_id,
            activity_id=record.activity_id,
            task_id=record.task_id,
            occurred_at=record.occurred_at,
            correlation_id=record.correlation_id,
            metadata=TrustedEvidenceAnalyticsMetadata(
                evidence_id=reference.evidence_id,
                evidence_type=reference.evidence_type,
                evidence_schema_version=reference.schema_version,
                evidence_record_version=reference.record_version,
                content_digest=reference.content_digest,
                source_version=record.source_version,
            ),
        )
        try:
            self._analytics_sink.record(event)
        except Exception:
            # Analytics cannot undo accepted protected evidence.  Keep even this
            # log bounded: no actor, learner, content, IDs, or exception text.
            self._logger.warning(
                "trusted_evidence_analytics_recording_failed",
                extra={
                    "correlation_id": record.correlation_id,
                    "stage": "trusted_evidence_analytics",
                    "failure_category": "analytics_persistence_unavailable",
                },
            )
            return TrustedEvidenceCaptureResult(
                evidence=evidence_result,
                analytics_state=EvidenceAnalyticsState.UNAVAILABLE,
            )
        return TrustedEvidenceCaptureResult(
            evidence=evidence_result,
            analytics_state=EvidenceAnalyticsState.RECORDED,
        )


__all__ = [
    "EvidenceAnalyticsState",
    "TrustedEvidenceCaptureAdapter",
    "TrustedEvidenceCaptureCommand",
    "TrustedEvidenceCaptureResult",
]
