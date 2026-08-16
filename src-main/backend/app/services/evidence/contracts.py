"""Pure Person B transformations for safe evidence references."""

from app.schemas.evidence import EvidenceArtifact, EvidenceRecord, EvidenceRecordReference


def reference_from_record(
    record: EvidenceRecord,
    *,
    artifact: EvidenceArtifact | None = None,
) -> EvidenceRecordReference:
    """Create an opaque projection without exposing protected learner content."""

    if artifact is not None:
        if artifact.course_id != record.course_id or artifact.learner_id != record.learner_id:
            raise ValueError("evidence artifact scope does not match the evidence record")
        if record.artifact_id != artifact.artifact_id:
            raise ValueError("evidence artifact ID does not match the evidence record")
        if artifact.content_digest != record.content_digest:
            raise ValueError("evidence artifact digest does not match the evidence record")
    return EvidenceRecordReference(
        evidence_id=record.evidence_id,
        course_id=record.course_id,
        evidence_type=record.evidence_type,
        schema_version=record.schema_version,
        record_version=record.record_version,
        content_digest=record.content_digest,
        occurred_at=record.occurred_at,
    )
