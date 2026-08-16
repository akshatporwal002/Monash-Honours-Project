"""Validate frozen evidence-port resolutions before criterion evaluation."""

from __future__ import annotations

from collections.abc import Iterable

from app.schemas.assessment import (
    AccessDeniedEvidenceReference,
    AssessmentVersionReference,
    ConflictingEvidenceReference,
    EvidenceReference,
    EvidenceReferenceResolution,
    InvalidEvidenceReference,
    MissingEvidenceReference,
    ResolvedEvidenceReference,
    StaleEvidenceReference,
)


class EvidenceValidationError(ValueError):
    """Evidence cannot be used for this exact criterion evaluation."""


class FrozenEvidenceValidator:
    """Accept only resolved, course-scoped evidence from the Person B boundary."""

    def validate(
        self,
        resolutions: Iterable[EvidenceReferenceResolution],
        *,
        assessment: AssessmentVersionReference,
        allowed_types: Iterable[str],
    ) -> tuple[EvidenceReference, ...]:
        allowed = set(allowed_types)
        references: list[EvidenceReference] = []
        for resolution in resolutions:
            if not isinstance(resolution, ResolvedEvidenceReference):
                raise EvidenceValidationError(self._failure_message(resolution))
            reference = resolution.reference
            mismatched = self._mismatched_fields(reference.assessment, assessment)
            if mismatched:
                fields = ", ".join(mismatched)
                raise EvidenceValidationError(f"evidence reference has mismatched fields: {fields}")
            if reference.evidence_type not in allowed:
                raise EvidenceValidationError("evidence type is not approved for this criterion")
            references.append(reference)
        if not references:
            raise EvidenceValidationError(
                "criterion evaluation requires one or more evidence references"
            )
        return tuple(references)

    @staticmethod
    def _mismatched_fields(
        actual: AssessmentVersionReference,
        expected: AssessmentVersionReference,
    ) -> tuple[str, ...]:
        actual_values = actual.model_dump()
        expected_values = expected.model_dump()
        return tuple(
            field for field, value in expected_values.items() if actual_values[field] != value
        )

    @staticmethod
    def _failure_message(resolution: EvidenceReferenceResolution) -> str:
        messages = {
            MissingEvidenceReference: "evidence reference is missing",
            StaleEvidenceReference: "evidence reference is stale",
            ConflictingEvidenceReference: "evidence references conflict",
            AccessDeniedEvidenceReference: "evidence access is denied",
            InvalidEvidenceReference: "evidence reference is invalid",
        }
        for resolution_type, message in messages.items():
            if isinstance(resolution, resolution_type):
                return message
        return "evidence reference is unresolved"
