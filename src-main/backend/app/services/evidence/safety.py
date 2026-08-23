"""Access, audit, and error boundaries for Person B evidence services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256
from typing import Protocol


class EvidenceError(Exception):
    """Base class for safe evidence-service failures."""


class EvidenceConflictError(EvidenceError):
    """An idempotency key was reused with different immutable evidence."""


class EvidenceNotFoundError(EvidenceError):
    """A missing or unauthorized record; callers map both cases to the same response."""


class EvidencePersistenceError(EvidenceError):
    """Evidence storage could not complete without revealing the underlying failure."""


class EvidenceScopeError(EvidenceError):
    """Evidence references do not form a valid single-course learner scope."""


class EvidenceAuditAction(str, Enum):
    EVIDENCE_CREATED = "evidence_created"
    LEARNER_ANNOTATION = "learner_annotation"
    EDUCATOR_CORRECTION = "educator_correction"
    RETRY = "retry"
    FALLBACK = "fallback"


@dataclass(frozen=True, slots=True)
class EvidenceAccessScope:
    """The actor and intended resource scope supplied to an injected policy."""

    actor_reference: str
    role: str
    course_id: str
    learner_id: str


class EvidenceAccessPolicy(Protocol):
    """Authorize reads and writes without coupling evidence to route or ORM policy code."""

    def can_write(self, scope: EvidenceAccessScope) -> bool:
        """Return whether this actor may create evidence in the requested scope."""

    def can_read_timeline(self, scope: EvidenceAccessScope) -> bool:
        """Return whether this actor may read metadata-only evidence history."""

    def can_read_artifact(self, scope: EvidenceAccessScope) -> bool:
        """Return whether this actor may read protected learner content."""


@dataclass(frozen=True, slots=True)
class EvidenceAuditEvent:
    """Bounded Person B audit data with no content or direct learner identifiers."""

    action: EvidenceAuditAction
    actor_fingerprint: str
    agent_reference: str | None
    correlation_id: str
    resource_fingerprint: str
    schema_version: str
    occurred_at: datetime
    outcome: str
    record_version: int | None = None
    failure_category: str | None = None


class EvidenceAuditSink(Protocol):
    """Durably queue or persist one bounded evidence audit event."""

    def record(self, event: EvidenceAuditEvent) -> None:
        """Store the event or raise a controlled infrastructure failure."""


def opaque_fingerprint(value: str) -> str:
    """Create a deterministic, non-reversible reference safe for audit metadata."""

    digest = sha256(f"learnlens-evidence-audit\x00{value}".encode("utf-8")).hexdigest()
    return f"evidence-audit-v1:{digest}"


def safe_failure_category(error: BaseException) -> str:
    """Classify failure without forwarding error text, content, IDs, or access details."""

    if isinstance(error, EvidencePersistenceError):
        return "evidence_persistence_unavailable"
    if isinstance(error, EvidenceScopeError):
        return "evidence_scope_invalid"
    return "evidence_audit_unavailable"


def safe_correction_audit_failure_category(_: BaseException | None = None) -> str:
    """Report correction-audit degradation without forwarding private error details."""

    return "correction_audit_unavailable"


__all__ = [
    "EvidenceAccessPolicy",
    "EvidenceAccessScope",
    "EvidenceAuditAction",
    "EvidenceAuditEvent",
    "EvidenceAuditSink",
    "EvidenceConflictError",
    "EvidenceError",
    "EvidenceNotFoundError",
    "EvidencePersistenceError",
    "EvidenceScopeError",
    "opaque_fingerprint",
    "safe_correction_audit_failure_category",
    "safe_failure_category",
]
