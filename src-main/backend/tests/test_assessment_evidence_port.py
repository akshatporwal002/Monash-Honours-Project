"""Tests for Person B's ORM-free assessment evidence boundary."""

from __future__ import annotations

import ast
import inspect
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.assessment import (
    AssessmentResult,
    AssessmentVersionReference,
    EvidenceReference,
    EvidenceReferenceResolution,
    FormalResultSummary,
    MissingEvidenceReference,
    ResolvedEvidenceReference,
    ResultState,
)
from app.services.evidence.assessment_port import AssessmentEvidencePort


def assessment_reference(**overrides: object) -> AssessmentVersionReference:
    values: dict[str, object] = {
        "course_id": "course-1",
        "assessment_definition_id": "assessment-1",
        "assessment_definition_version": 1,
        "outcome_id": "outcome-1",
        "outcome_version": 1,
        "bloom_target_id": "bloom-1",
        "bloom_target_version": 1,
        "criterion_set_id": "criteria-1",
        "criterion_set_version": 1,
        "pass_rule_id": "rule-1",
        "pass_rule_version": 1,
        "task_id": "task-1",
        "task_form_version": 1,
        "assessment_attempt_id": "attempt-1",
        "response_version_id": "response-1",
    }
    values.update(overrides)
    return AssessmentVersionReference.model_validate(values)


def evidence_reference(**overrides: object) -> EvidenceReference:
    values: dict[str, object] = {
        "assessment": assessment_reference(),
        "evidence_id": "evidence-1",
        "evidence_type": "learner_response",
        "schema_version": "learner-response.v1",
        "record_version": 1,
        "content_digest": f"sha256:{'a' * 64}",
        "source_record_id": "response-1",
        "source_record_version": 1,
        "occurred_at": datetime(2026, 8, 16, 1, 2, 3, tzinfo=UTC),
    }
    values.update(overrides)
    return EvidenceReference.model_validate(values)


class StubResolver:
    def __init__(self, resolution: EvidenceReferenceResolution) -> None:
        self.resolution = resolution
        self.calls: list[tuple[AssessmentVersionReference, str]] = []

    def resolve(
        self,
        *,
        assessment: AssessmentVersionReference,
        evidence_id: str,
    ) -> EvidenceReferenceResolution:
        self.calls.append((assessment, evidence_id))
        return self.resolution


def test_port_creates_a_frozen_reference_from_the_exact_version_scope() -> None:
    assessment = assessment_reference(task_form_version=2, response_version_id="response-2")
    port = AssessmentEvidencePort(
        StubResolver(ResolvedEvidenceReference(reference=evidence_reference()))
    )

    reference = port.create_reference(
        assessment=assessment,
        evidence_id="evidence-2",
        evidence_type="reflection",
        schema_version="reflection.v1",
        record_version=3,
        content_digest=f"sha256:{'b' * 64}",
        source_record_id="record-2",
        source_record_version=2,
        occurred_at=datetime(2026, 8, 16, 2, 3, 4, tzinfo=UTC),
    )

    assert reference.assessment == assessment
    assert reference.assessment.response_version_id == "response-2"
    assert reference.assessment.task_form_version == 2
    assert (
        reference.model_dump_json()
        == EvidenceReference.model_validate(reference.model_dump()).model_dump_json()
    )
    with pytest.raises(ValidationError, match="frozen"):
        reference.evidence_id = "changed"  # type: ignore[misc]


def test_port_preserves_valid_resolution_and_typed_missing_state() -> None:
    assessment = assessment_reference()
    resolved = ResolvedEvidenceReference(reference=evidence_reference(assessment=assessment))
    resolver = StubResolver(resolved)

    assert (
        AssessmentEvidencePort(resolver).resolve(assessment=assessment, evidence_id="evidence-1")
        == resolved
    )
    assert resolver.calls == [(assessment, "evidence-1")]

    missing = MissingEvidenceReference(
        assessment=assessment,
        evidence_id="evidence-missing",
        reason_code="NOT_FOUND",
    )
    result = AssessmentEvidencePort(StubResolver(missing)).resolve(
        assessment=assessment,
        evidence_id="evidence-missing",
    )

    assert isinstance(result, MissingEvidenceReference)
    assert result.status == "MISSING"


def test_port_fails_closed_for_stale_cross_course_and_wrong_id_resolutions() -> None:
    assessment = assessment_reference()
    stale_reference = evidence_reference(
        assessment=assessment_reference(task_form_version=2),
    )
    stale = AssessmentEvidencePort(
        StubResolver(ResolvedEvidenceReference(reference=stale_reference))
    ).resolve(
        assessment=assessment,
        evidence_id="evidence-1",
    )
    assert stale.status == "STALE"
    assert stale.mismatched_fields == ("task_form_version",)

    cross_course_reference = evidence_reference(
        assessment=assessment_reference(course_id="course-2"),
    )
    denied = AssessmentEvidencePort(
        StubResolver(ResolvedEvidenceReference(reference=cross_course_reference))
    ).resolve(assessment=assessment, evidence_id="evidence-1")
    assert denied.status == "ACCESS_DENIED"

    wrong_id = AssessmentEvidencePort(
        StubResolver(
            ResolvedEvidenceReference(reference=evidence_reference(evidence_id="evidence-2"))
        )
    ).resolve(assessment=assessment, evidence_id="evidence-1")
    assert wrong_id.status == "INVALID"


def test_port_accepts_no_forbidden_formal_result_inputs() -> None:
    signature = inspect.signature(AssessmentEvidencePort.create_reference)
    forbidden = {"score", "research_condition", "confidence", "access_support", "result"}

    assert forbidden.isdisjoint(signature.parameters)
    with pytest.raises(TypeError, match="unexpected keyword"):
        AssessmentEvidencePort.create_reference(  # type: ignore[call-arg]
            assessment=assessment_reference(),
            evidence_id="evidence-1",
            evidence_type="learner_response",
            schema_version="learner-response.v1",
            record_version=1,
            content_digest=f"sha256:{'a' * 64}",
            source_record_id="response-1",
            source_record_version=1,
            occurred_at=datetime(2026, 8, 16, tzinfo=UTC),
            score=100,
        )


def test_formal_result_provider_is_read_only_and_missing_is_not_incomplete() -> None:
    protocol_source = inspect.getsource(
        __import__(
            "app.services.evidence.assessment_port",
            fromlist=["ProgressFormalResultSummaryProvider"],
        ).ProgressFormalResultSummaryProvider
    )

    assert "read_summary" in protocol_source
    assert all(action not in protocol_source for action in ("confirm", "override", "void", "write"))

    summary = FormalResultSummary(
        course_id="course-1",
        assessment_definition_id="assessment-1",
        assessment_attempt_id="attempt-1",
        response_version_id="response-1",
        result_state=ResultState.NOT_ASSESSED,
    )
    assert summary.result is None
    assert AssessmentResult.INCOMPLETE.value == "INCOMPLETE"


def test_person_b_evidence_package_imports_no_orm_or_result_mutation_service() -> None:
    command = """
import sys
from app.services.evidence.assessment_port import AssessmentEvidencePort
forbidden = sorted(
    name for name in sys.modules
    if name == 'app.models' or name.startswith('app.models.') or name.startswith('app.services.assessment')
)
print(','.join(forbidden))
raise SystemExit(bool(forbidden))
"""
    result = subprocess.run(
        [sys.executable, "-c", command],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout or result.stderr


def test_no_existing_person_b_service_imports_the_read_only_result_provider() -> None:
    service_root = Path(__file__).parents[1] / "app" / "services"
    allowed_port = service_root / "evidence" / "assessment_port.py"
    offenders: list[Path] = []

    for path in service_root.rglob("*.py"):
        if path == allowed_port or "assessment" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            isinstance(node, ast.ImportFrom)
            and node.module == "app.services.evidence.assessment_port"
            and any(alias.name == "ProgressFormalResultSummaryProvider" for alias in node.names)
            for node in ast.walk(tree)
        ):
            offenders.append(path)

    assert offenders == []
