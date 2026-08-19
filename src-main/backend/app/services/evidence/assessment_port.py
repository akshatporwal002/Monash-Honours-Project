"""Read-only Person A assessment contract boundary for Person B evidence services."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.schemas.assessment import (
    AccessDeniedEvidenceReference,
    AssessmentVersionReference,
    EvidenceReference,
    EvidenceReferenceResolution,
    FormalResultSummary,
    InvalidEvidenceReference,
    ResolvedEvidenceReference,
    StaleEvidenceReference,
)


class EvidenceReferenceResolver(Protocol):
    """Resolve one opaque evidence ID in the exact assessment/version scope."""

    def resolve(
        self,
        *,
        assessment: AssessmentVersionReference,
        evidence_id: str,
    ) -> EvidenceReferenceResolution:
        """Return a typed resolution without exposing an ORM session."""


class ProgressFormalResultSummaryProvider(Protocol):
    """Read-only formal-result input reserved for a future progress projection."""

    def read_summary(
        self,
        *,
        assessment: AssessmentVersionReference,
    ) -> FormalResultSummary:
        """Return the frozen summary; this protocol has no result-mutation operation."""


class AssessmentEvidencePort:
    """Create and resolve immutable evidence references without assessment-service imports."""

    def __init__(self, resolver: EvidenceReferenceResolver) -> None:
        self._resolver = resolver

    @staticmethod
    def create_reference(
        *,
        assessment: AssessmentVersionReference,
        evidence_id: str,
        evidence_type: str,
        schema_version: str,
        record_version: int,
        content_digest: str,
        source_record_id: str,
        source_record_version: int,
        occurred_at: datetime,
    ) -> EvidenceReference:
        """Construct the frozen cross-workstream value from opaque/versioned metadata only."""

        return EvidenceReference(
            assessment=assessment,
            evidence_id=evidence_id,
            evidence_type=evidence_type,
            schema_version=schema_version,
            record_version=record_version,
            content_digest=content_digest,
            source_record_id=source_record_id,
            source_record_version=source_record_version,
            occurred_at=occurred_at,
        )

    def resolve(
        self,
        *,
        assessment: AssessmentVersionReference,
        evidence_id: str,
    ) -> EvidenceReferenceResolution:
        """Fail closed when a resolver returns a reference outside the requested scope."""

        resolution = self._resolver.resolve(assessment=assessment, evidence_id=evidence_id)
        if not isinstance(resolution, ResolvedEvidenceReference):
            return resolution

        reference = resolution.reference
        if reference.evidence_id != evidence_id:
            return InvalidEvidenceReference(
                reference_id=evidence_id,
                reason_code="EVIDENCE_ID_MISMATCH",
            )

        mismatched_fields = tuple(
            field
            for field, expected in assessment.model_dump().items()
            if reference.assessment.model_dump()[field] != expected
        )
        if not mismatched_fields:
            return resolution
        if "course_id" in mismatched_fields:
            return AccessDeniedEvidenceReference(
                assessment=assessment,
                reference_id=evidence_id,
                reason_code="COURSE_ACCESS_DENIED",
            )
        return StaleEvidenceReference(
            reference=reference,
            mismatched_fields=mismatched_fields,
            reason_code="ASSESSMENT_REFERENCE_MISMATCH",
        )


__all__ = [
    "AssessmentEvidencePort",
    "EvidenceReferenceResolver",
    "ProgressFormalResultSummaryProvider",
]
