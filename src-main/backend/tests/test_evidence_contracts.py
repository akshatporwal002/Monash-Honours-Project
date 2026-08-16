"""Tests for strict Person B evidence contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.platform_enums import (
    AccessSupportState,
    EvidenceLinkRelation,
    EvidenceType,
    InstructionalSupportLevel,
)
from app.schemas.evidence import EvidenceArtifact, EvidenceLink, EvidenceRecord
from app.services.evidence.contracts import reference_from_record


def artifact(**overrides: object) -> EvidenceArtifact:
    values: dict[str, object] = {
        "artifact_id": "artifact-1",
        "course_id": "course-1",
        "learner_id": "learner-1",
        "content": "A learner explanation of the observed circuit behaviour.",
        "content_digest": f"sha256:{'a' * 64}",
        "content_format": "plain-text.v1",
        "record_version": 1,
        "occurred_at": datetime(2026, 8, 16, 1, 2, 3, tzinfo=UTC),
    }
    values.update(overrides)
    return EvidenceArtifact.model_validate(values)


def record(**overrides: object) -> EvidenceRecord:
    values: dict[str, object] = {
        "evidence_id": "evidence-1",
        "course_id": "course-1",
        "learner_id": "learner-1",
        "outcome_id": "outcome-1",
        "activity_id": "activity-1",
        "task_id": "task-1",
        "response_version_id": "response-1",
        "source_interaction_id": "source-1",
        "task_conditions_version": 1,
        "evidence_type": EvidenceType.REASONING,
        "provenance": "LEARNER",
        "observation_type": "DIRECT",
        "instructional_support_level": InstructionalSupportLevel.CONCEPT_CUE,
        "access_support_state": AccessSupportState.PROVIDED,
        "artifact_id": "artifact-1",
        "actor_reference": "learner-1",
        "agent_reference": "evidence-agent.v1",
        "schema_version": "evidence-record.v1",
        "record_version": 1,
        "idempotency_key": "event-1",
        "occurred_at": datetime(2026, 8, 16, 1, 2, 3, tzinfo=UTC),
    }
    values.update(overrides)
    return EvidenceRecord.model_validate(values)


def test_contracts_cover_every_required_evidence_kind() -> None:
    assert {evidence_type.value for evidence_type in EvidenceType} == {
        "PREDICTION",
        "EXPLANATION",
        "REASONING",
        "RESPONSE",
        "REVISION",
        "CONFIDENCE",
        "HINT",
        "SCAFFOLD",
        "FEEDBACK_INTERACTION",
        "REFLECTION",
        "SIMULATION",
        "MISCONCEPTION_CHECK",
        "TRANSFER",
        "DIAGNOSTIC",
        "SYSTEM_FAULT",
    }
    for evidence_type in EvidenceType:
        assert record(evidence_type=evidence_type).evidence_type is evidence_type


def test_opaque_reference_is_stable_and_excludes_protected_content_and_results() -> None:
    result = reference_from_record(record(), artifact=artifact())

    assert result.contract_version == "learnlens.evidence.v1"
    assert (
        result.model_dump_json()
        == reference_from_record(record(), artifact=artifact()).model_dump_json()
    )
    assert "content" not in result.model_dump()
    assert "learner_id" not in result.model_dump()
    assert "result" not in result.model_dump()


def test_access_and_instructional_support_use_distinct_namespaces() -> None:
    item = record(
        instructional_support_level=InstructionalSupportLevel.NARROWING_HINT,
        access_support_state=AccessSupportState.PROVIDED,
    )

    assert item.instructional_support_level == InstructionalSupportLevel.NARROWING_HINT
    assert item.access_support_state is AccessSupportState.PROVIDED
    assert InstructionalSupportLevel.NARROWING_HINT.value == 3


def test_contradicting_evidence_is_a_valid_link_not_a_learner_result() -> None:
    link = EvidenceLink(
        evidence_id="evidence-1",
        linked_evidence_id="evidence-2",
        relation=EvidenceLinkRelation.CONTRADICTS,
        actor_reference="evidence-agent.v1",
        occurred_at=datetime(2026, 8, 16, 1, 2, 3, tzinfo=UTC),
    )

    assert link.relation is EvidenceLinkRelation.CONTRADICTS
    assert "INCOMPLETE" not in link.model_dump_json()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("score", 100),
        ("grade", "A"),
        ("research_condition", "control"),
        ("diagnosis", "dyslexia"),
        ("demographic", "private"),
        ("mastery_percentage", 0.9),
    ],
)
def test_forbidden_fields_and_oversized_or_naive_values_are_rejected(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EvidenceRecord.model_validate({**record().model_dump(), field: value})
    with pytest.raises(ValidationError, match="timezone"):
        EvidenceRecord.model_validate(
            {**record().model_dump(), "occurred_at": datetime(2026, 8, 16, 1, 2, 3)}
        )
    with pytest.raises(ValidationError):
        EvidenceArtifact.model_validate({**artifact().model_dump(), "content": "x" * 65_537})


def test_reference_creation_fails_closed_when_artifact_scope_or_id_differs() -> None:
    with pytest.raises(ValueError, match="scope"):
        reference_from_record(record(), artifact=artifact(course_id="course-2"))
    with pytest.raises(ValueError, match="ID"):
        reference_from_record(record(), artifact=artifact(artifact_id="artifact-2"))
