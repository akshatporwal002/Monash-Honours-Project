"""Application service for learner annotations and educator correction reviews."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.services.evidence.safety import (
    EvidenceAuditAction,
    EvidenceAuditEvent,
    EvidenceAuditSink,
    opaque_fingerprint,
    safe_correction_audit_failure_category,
)
from app.services.learner_model.correction_contracts import (
    EducatorCorrectionReviewCommand,
    EducatorCorrectionReviewPayload,
    LearnerAnnotationCommand,
    LearnerAnnotationPayload,
)
from app.services.learner_model.repository import (
    LearnerModelCorrectionHistory,
    SqlAlchemyLearnerModelRepository,
)
from app.services.learner_model.safety import LearnerModelCorrectionNotFoundError

_UNAVAILABLE_AUDIT_FINGERPRINT = "evidence-audit-v1:unavailable"


class CorrectionAccessPolicy(Protocol):
    """Optional caller policy that can narrow, but never widen, repository access."""

    def can_annotate(self, command: LearnerAnnotationCommand) -> bool: ...

    def can_review(self, command: EducatorCorrectionReviewCommand) -> bool: ...

    def can_read_history(
        self,
        *,
        actor_reference: str,
        course_id: str,
        learner_id: str,
        outcome_id: str,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class LearnerAnnotationResult:
    annotation: LearnerAnnotationPayload
    created: bool
    audit_recorded: bool
    audit_failure_category: str | None = None


@dataclass(frozen=True, slots=True)
class EducatorCorrectionReviewResult:
    review: EducatorCorrectionReviewPayload
    created: bool
    audit_recorded: bool
    audit_failure_category: str | None = None


class LearnerModelCorrectionService:
    """Coordinate correction commands without exposing target existence across scopes."""

    def __init__(
        self,
        repository: SqlAlchemyLearnerModelRepository,
        access_policy: CorrectionAccessPolicy | None = None,
        audit_sink: EvidenceAuditSink | None = None,
        *,
        audit_fingerprinter: Callable[[str], str] = opaque_fingerprint,
    ) -> None:
        self._repository = repository
        self._access_policy = access_policy
        self._audit_sink = audit_sink
        self._audit_fingerprinter = audit_fingerprinter

    def annotate(self, command: LearnerAnnotationCommand) -> LearnerAnnotationResult:
        if self._access_policy is not None and not self._access_policy.can_annotate(command):
            raise LearnerModelCorrectionNotFoundError("correction target is unavailable")
        stored = self._repository.create_annotation(command)
        audit_recorded, failure_category = self._record_audit(
            action=EvidenceAuditAction.LEARNER_ANNOTATION,
            actor_reference=command.actor_reference,
            correlation_id=stored.annotation.correlation_id,
            resource_reference=stored.annotation.annotation_id,
            schema_version=stored.annotation.contract_version,
            record_version=stored.annotation.record_version,
            occurred_at=stored.annotation.occurred_at,
            created=stored.created,
        )
        return LearnerAnnotationResult(
            annotation=stored.annotation,
            created=stored.created,
            audit_recorded=audit_recorded,
            audit_failure_category=failure_category,
        )

    def review(
        self,
        command: EducatorCorrectionReviewCommand,
    ) -> EducatorCorrectionReviewResult:
        if self._access_policy is not None and not self._access_policy.can_review(command):
            raise LearnerModelCorrectionNotFoundError("correction target is unavailable")
        stored = self._repository.create_correction_review(command)
        audit_recorded, failure_category = self._record_audit(
            action=EvidenceAuditAction.EDUCATOR_CORRECTION,
            actor_reference=command.actor_reference,
            correlation_id=stored.review.correlation_id,
            resource_reference=stored.review.review_id,
            schema_version=stored.review.contract_version,
            record_version=stored.review.review_version,
            occurred_at=stored.review.occurred_at,
            created=stored.created,
        )
        return EducatorCorrectionReviewResult(
            review=stored.review,
            created=stored.created,
            audit_recorded=audit_recorded,
            audit_failure_category=failure_category,
        )

    def history(
        self,
        *,
        actor_reference: str,
        course_id: str,
        learner_id: str,
        outcome_id: str,
    ) -> tuple[LearnerModelCorrectionHistory, ...]:
        if self._access_policy is not None and not self._access_policy.can_read_history(
            actor_reference=actor_reference,
            course_id=course_id,
            learner_id=learner_id,
            outcome_id=outcome_id,
        ):
            raise LearnerModelCorrectionNotFoundError("correction history is unavailable")
        return self._repository.correction_history(
            actor_reference=actor_reference,
            course_id=course_id,
            learner_id=learner_id,
            outcome_id=outcome_id,
        )

    def _record_audit(
        self,
        *,
        action: EvidenceAuditAction,
        actor_reference: str,
        correlation_id: str,
        resource_reference: str,
        schema_version: str,
        record_version: int,
        occurred_at: datetime,
        created: bool,
    ) -> tuple[bool, str | None]:
        if self._audit_sink is None:
            return False, safe_correction_audit_failure_category()
        try:
            actor_fingerprint = self._audit_fingerprinter(actor_reference)
            resource_fingerprint = self._audit_fingerprinter(resource_reference)
        except Exception as error:
            failure_category = safe_correction_audit_failure_category(error)
            return (
                self._record_fallback_audit(
                    action=action,
                    correlation_id=correlation_id,
                    schema_version=schema_version,
                    record_version=record_version,
                    occurred_at=occurred_at,
                    failure_category=failure_category,
                ),
                failure_category,
            )
        event = EvidenceAuditEvent(
            action=action,
            actor_fingerprint=actor_fingerprint,
            agent_reference=None,
            correlation_id=correlation_id,
            resource_fingerprint=resource_fingerprint,
            schema_version=schema_version,
            record_version=record_version,
            occurred_at=occurred_at,
            outcome="created" if created else "replayed",
        )
        try:
            self._audit_sink.record(event)
        except Exception as error:
            return False, safe_correction_audit_failure_category(error)
        return True, None

    def _record_fallback_audit(
        self,
        *,
        action: EvidenceAuditAction,
        correlation_id: str,
        schema_version: str,
        record_version: int,
        occurred_at: datetime,
        failure_category: str,
    ) -> bool:
        if self._audit_sink is None:
            return False
        try:
            self._audit_sink.record(
                EvidenceAuditEvent(
                    action=action,
                    actor_fingerprint=_UNAVAILABLE_AUDIT_FINGERPRINT,
                    agent_reference=None,
                    correlation_id=correlation_id,
                    resource_fingerprint=_UNAVAILABLE_AUDIT_FINGERPRINT,
                    schema_version=schema_version,
                    record_version=record_version,
                    occurred_at=occurred_at,
                    outcome="audit_fallback",
                    failure_category=failure_category,
                )
            )
        except Exception:
            return False
        return True


__all__ = [
    "CorrectionAccessPolicy",
    "EducatorCorrectionReviewResult",
    "LearnerAnnotationResult",
    "LearnerModelCorrectionService",
]
