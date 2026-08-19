"""Authorized application service for Person B append-only evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.schemas.evidence import EvidenceArtifact, EvidenceRecordReference
from app.services.evidence.repository import (
    EvidenceCapture,
    EvidenceTimelineItem,
    EvidenceWriteResult,
    SqlAlchemyEvidenceRepository,
)
from app.services.evidence.safety import (
    EvidenceAccessPolicy,
    EvidenceAccessScope,
    EvidenceAuditAction,
    EvidenceAuditEvent,
    EvidenceAuditSink,
    EvidenceNotFoundError,
    EvidencePersistenceError,
    opaque_fingerprint,
    safe_failure_category,
)


class EvidenceCaptureState(str, Enum):
    STORED = "stored"
    PENDING_RECONCILIATION = "pending_reconciliation"


@dataclass(frozen=True, slots=True)
class EvidenceCaptureResult:
    """A durable result or safe pending state that never exposes provider failures."""

    state: EvidenceCaptureState
    reference: EvidenceRecordReference | None
    created: bool
    audit_recorded: bool
    failure_category: str | None = None


class EvidenceService:
    """Combine injected authorization, transactional persistence, and bounded audit output."""

    def __init__(
        self,
        repository: SqlAlchemyEvidenceRepository,
        access_policy: EvidenceAccessPolicy,
        audit_sink: EvidenceAuditSink,
    ) -> None:
        self._repository = repository
        self._access_policy = access_policy
        self._audit_sink = audit_sink

    def capture(
        self,
        scope: EvidenceAccessScope,
        capture: EvidenceCapture,
        *,
        action: EvidenceAuditAction = EvidenceAuditAction.EVIDENCE_CREATED,
    ) -> EvidenceCaptureResult:
        """Write evidence once; audit unavailability never erases an accepted evidence record."""

        self._require(self._access_policy.can_write(scope))
        self._require(
            capture.record.course_id == scope.course_id
            and capture.record.learner_id == scope.learner_id
        )
        try:
            stored = self._repository.capture(capture)
        except EvidencePersistenceError as error:
            audit_recorded = self._record_audit(
                scope,
                capture,
                action=EvidenceAuditAction.FALLBACK,
                outcome="failure",
                failure_category=safe_failure_category(error),
            )
            return EvidenceCaptureResult(
                state=EvidenceCaptureState.PENDING_RECONCILIATION,
                reference=None,
                created=False,
                audit_recorded=audit_recorded,
                failure_category=safe_failure_category(error),
            )

        audit_recorded = self._record_audit(
            scope,
            capture,
            action=action,
            outcome="success",
            failure_category=None,
        )
        return _stored_result(stored, audit_recorded=audit_recorded)

    def timeline(self, scope: EvidenceAccessScope) -> tuple[EvidenceTimelineItem, ...]:
        """Return metadata-only history only to callers authorized for the exact scope."""

        self._require(self._access_policy.can_read_timeline(scope))
        return self._repository.timeline(course_id=scope.course_id, learner_id=scope.learner_id)

    def artifact(self, scope: EvidenceAccessScope, artifact_id: str) -> EvidenceArtifact:
        """Return protected content only after a separate artefact-read authorization check."""

        self._require(self._access_policy.can_read_artifact(scope))
        return self._repository.artifact(
            artifact_id=artifact_id,
            course_id=scope.course_id,
            learner_id=scope.learner_id,
        )

    def _record_audit(
        self,
        scope: EvidenceAccessScope,
        capture: EvidenceCapture,
        *,
        action: EvidenceAuditAction,
        outcome: str,
        failure_category: str | None,
    ) -> bool:
        try:
            self._audit_sink.record(
                EvidenceAuditEvent(
                    action=action,
                    actor_fingerprint=opaque_fingerprint(scope.actor_reference),
                    agent_reference=capture.record.agent_reference,
                    correlation_id=capture.record.correlation_id,
                    resource_fingerprint=opaque_fingerprint(capture.record.evidence_id),
                    schema_version=capture.record.schema_version,
                    occurred_at=capture.record.occurred_at,
                    outcome=outcome,
                    failure_category=failure_category,
                )
            )
        except Exception:
            return False
        return True

    @staticmethod
    def _require(authorized: bool) -> None:
        if not authorized:
            # The same error is used for a missing and an inaccessible record so a
            # future API adapter can produce non-enumerating 404 behaviour.
            raise EvidenceNotFoundError("evidence record is unavailable")


def _stored_result(stored: EvidenceWriteResult, *, audit_recorded: bool) -> EvidenceCaptureResult:
    return EvidenceCaptureResult(
        state=EvidenceCaptureState.STORED,
        reference=stored.reference,
        created=stored.created,
        audit_recorded=audit_recorded,
    )


__all__ = ["EvidenceCaptureResult", "EvidenceCaptureState", "EvidenceService"]
