"""Application boundary for protected learner-model correction operations."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.evidence.safety import (
    EvidenceAuditAction,
    EvidenceAuditEvent,
    EvidenceAuditSink,
    opaque_fingerprint,
)
from app.services.learner_model.correction_contracts import (
    EducatorCorrectionReviewCommand,
    EducatorCorrectionReviewPayload,
    LearnerAnnotationCommand,
    LearnerAnnotationPayload,
)
from app.services.learner_model.correction_repository import (
    CorrectionHistory,
    SqlAlchemyLearnerModelCorrectionRepository,
)


@dataclass(frozen=True, slots=True)
class AnnotationResult:
    annotation: LearnerAnnotationPayload
    created: bool
    audit_recorded: bool
    audit_failure_category: str | None


@dataclass(frozen=True, slots=True)
class ReviewResult:
    review: EducatorCorrectionReviewPayload
    created: bool
    audit_recorded: bool
    audit_failure_category: str | None


class LearnerModelCorrectionService:
    """Persist first, then best-effort record privacy-bounded operational audit data."""

    def __init__(
        self,
        repository: SqlAlchemyLearnerModelCorrectionRepository,
        audit_sink: EvidenceAuditSink | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink

    def annotate(self, command: LearnerAnnotationCommand) -> AnnotationResult:
        stored = self._repository.annotate(command)
        audit_recorded, category = self._audit(
            EvidenceAuditAction.LEARNER_ANNOTATION,
            command.actor_reference,
            stored.annotation.annotation_id,
            stored.annotation.correlation_id,
            stored.annotation.contract_version,
            stored.annotation.occurred_at,
            "created" if stored.created else "replayed",
        )
        return AnnotationResult(stored.annotation, stored.created, audit_recorded, category)

    def review(self, command: EducatorCorrectionReviewCommand) -> ReviewResult:
        stored = self._repository.review(command)
        audit_recorded, category = self._audit(
            EvidenceAuditAction.EDUCATOR_CORRECTION,
            command.actor_reference,
            stored.review.review_id,
            stored.review.correlation_id,
            stored.review.contract_version,
            stored.review.occurred_at,
            "created" if stored.created else "replayed",
        )
        return ReviewResult(stored.review, stored.created, audit_recorded, category)

    def history(self, **scope: str) -> tuple[CorrectionHistory, ...]:
        return self._repository.history(**scope)

    def _audit(
        self,
        action: EvidenceAuditAction,
        actor_reference: str,
        resource_reference: str,
        correlation_id: str,
        schema_version: str,
        occurred_at,
        outcome: str,
    ) -> tuple[bool, str | None]:
        if self._audit_sink is None:
            return False, "audit_unavailable"
        try:
            self._audit_sink.record(
                EvidenceAuditEvent(
                    action=action,
                    actor_fingerprint=opaque_fingerprint(actor_reference),
                    agent_reference=None,
                    correlation_id=correlation_id,
                    resource_fingerprint=opaque_fingerprint(resource_reference),
                    schema_version=schema_version,
                    occurred_at=occurred_at,
                    outcome=outcome,
                )
            )
        except Exception:
            return False, "audit_unavailable"
        return True, None


__all__ = ["AnnotationResult", "LearnerModelCorrectionService", "ReviewResult"]
