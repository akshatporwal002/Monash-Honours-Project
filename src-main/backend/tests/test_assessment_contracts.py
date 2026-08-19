"""Contract tests for the Person A assessment boundary."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from app.domain.assessment import public_assessment_reason_code
from app.schemas.assessment import (
    AccessDeniedEvidenceReference,
    AssessmentReasonCode,
    AssessmentResult,
    AssessmentVersionReference,
    ConflictingEvidenceReference,
    EvidenceReference,
    EvidenceReferenceResolution,
    EvidenceReferenceResolutionEnvelope,
    FormalResultSummary,
    InvalidEvidenceReference,
    MisconceptionState,
    MissingEvidenceReference,
    QualityReviewDecision,
    ResolvedEvidenceReference,
    ResultState,
    StaleEvidenceReference,
    legacy_judge_decision_to_quality_review,
)
from scripts.export_openapi import rendered_contract


def assessment_reference() -> AssessmentVersionReference:
    return AssessmentVersionReference(
        course_id="course-1",
        assessment_definition_id="assessment-1",
        assessment_definition_version=1,
        outcome_id="outcome-1",
        outcome_version=2,
        bloom_target_id="bloom-1",
        bloom_target_version=3,
        criterion_set_id="criteria-1",
        criterion_set_version=4,
        pass_rule_id="pass-rule-1",
        pass_rule_version=5,
        task_id="task-1",
        task_form_version=6,
        assessment_attempt_id="attempt-1",
        response_version_id="response-1",
    )


def evidence_reference() -> EvidenceReference:
    return EvidenceReference(
        assessment=assessment_reference(),
        evidence_id="evidence-1",
        evidence_type="learner_response",
        schema_version="learner-response.v1",
        record_version=1,
        content_digest=f"sha256:{'a' * 64}",
        source_record_id="submission-1",
        source_record_version=1,
        occurred_at=datetime(2026, 8, 15, 1, 2, 3, tzinfo=UTC),
    )


def assessed_result(**overrides: object) -> FormalResultSummary:
    values: dict[str, object] = {
        "course_id": "course-1",
        "assessment_definition_id": "assessment-1",
        "assessment_attempt_id": "attempt-1",
        "response_version_id": "response-1",
        "decision_id": "decision-1",
        "result": AssessmentResult.PASS,
        "result_state": ResultState.PROVISIONAL,
        "reason_code": AssessmentReasonCode.TARGET_EVIDENCE_MET,
        "decided_at": datetime(2026, 8, 15, 1, 2, 3, tzinfo=UTC),
    }
    values.update(overrides)
    return FormalResultSummary.model_validate(values)


def test_only_pass_and_incomplete_are_valid_results() -> None:
    adapter = TypeAdapter(AssessmentResult)

    assert adapter.validate_python("PASS") is AssessmentResult.PASS
    assert adapter.validate_python("INCOMPLETE") is AssessmentResult.INCOMPLETE
    for forbidden in ("FAIL", "pass", "incomplete", "NOT_ASSESSED", 1):
        with pytest.raises(ValidationError):
            adapter.validate_python(forbidden)


def test_formal_result_reason_codes_match_the_product_contract() -> None:
    assert [code.value for code in AssessmentReasonCode] == [
        "TARGET_EVIDENCE_MET",
        "MISSING_REQUIRED_EVIDENCE",
        "CRITERIA_NOT_MET",
        "TARGET_BLOOM_ACTION_NOT_SHOWN",
        "CRITICAL_CONCEPT_GAP",
        "INDEPENDENT_EVIDENCE_NOT_SHOWN",
        "TRANSFER_EVIDENCE_NOT_SHOWN",
        "UNRESOLVED_EVIDENCE_CONFLICT",
        "TASK_UNDER_HUMAN_REVIEW",
    ]
    with pytest.raises(ValidationError):
        assessed_result(reason_code="REQUIRED_CRITERION_EVIDENCE_MISSING")
    with pytest.raises(ValueError, match="unknown assessment reason code"):
        public_assessment_reason_code("UNKNOWN_REASON")


def test_active_assessed_result_requires_a_reason_code() -> None:
    with pytest.raises(ValidationError, match="require a reason code"):
        assessed_result(reason_code=None)


def test_missing_result_is_distinct_from_incomplete() -> None:
    not_assessed = FormalResultSummary(
        course_id="course-1",
        assessment_definition_id="assessment-1",
        assessment_attempt_id="attempt-1",
        response_version_id="response-1",
        result_state=ResultState.NOT_ASSESSED,
    )
    incomplete = assessed_result(result=AssessmentResult.INCOMPLETE)

    assert not_assessed.result is None
    assert incomplete.result is AssessmentResult.INCOMPLETE
    with pytest.raises(ValidationError, match="NOT_ASSESSED"):
        assessed_result(result_state=ResultState.NOT_ASSESSED)
    with pytest.raises(ValidationError, match="assessed states require"):
        assessed_result(result=None)


def test_void_keeps_reviewed_decision_metadata_without_an_active_result() -> None:
    reviewed_at = datetime(2026, 8, 15, 2, 3, 4, tzinfo=UTC)
    void = assessed_result(
        result=None,
        result_state=ResultState.VOID,
        reason_code=None,
        assessor_reviewed_at=reviewed_at,
    )

    assert void.decision_id == "decision-1"
    assert void.result is None
    assert void.reason_code is None
    assert void.assessor_reviewed_at == reviewed_at

    with pytest.raises(ValidationError, match="active result"):
        assessed_result(
            result_state=ResultState.VOID,
            assessor_reviewed_at=reviewed_at,
        )
    with pytest.raises(ValidationError, match="review time"):
        assessed_result(result=None, result_state=ResultState.VOID, reason_code=None)


def test_quality_review_namespace_and_legacy_mapping_are_separate() -> None:
    assert legacy_judge_decision_to_quality_review("pass") is QualityReviewDecision.APPROVED
    assert legacy_judge_decision_to_quality_review("fail") is QualityReviewDecision.REJECTED

    with pytest.raises(ValueError, match="unsupported legacy"):
        legacy_judge_decision_to_quality_review("PASS")
    with pytest.raises(ValueError):
        AssessmentResult("fail")
    with pytest.raises(ValueError):
        QualityReviewDecision("PASS")


def test_misconception_states_match_controlled_hypothesis_flow() -> None:
    assert [state.value for state in MisconceptionState] == [
        "PERSISTED",
        "WEAKENED",
        "CORRECTED",
        "UNCERTAIN",
    ]
    with pytest.raises(ValueError):
        MisconceptionState("CONFIRMED")


def test_evidence_reference_is_immutable_and_serializes_deterministically() -> None:
    reference = evidence_reference()

    assert reference.model_dump_json() == evidence_reference().model_dump_json()
    assert json.loads(reference.model_dump_json()) == {
        "contract_version": "learnlens.assessment-evidence.v1",
        "assessment": {
            "course_id": "course-1",
            "assessment_definition_id": "assessment-1",
            "assessment_definition_version": 1,
            "outcome_id": "outcome-1",
            "outcome_version": 2,
            "bloom_target_id": "bloom-1",
            "bloom_target_version": 3,
            "criterion_set_id": "criteria-1",
            "criterion_set_version": 4,
            "pass_rule_id": "pass-rule-1",
            "pass_rule_version": 5,
            "task_id": "task-1",
            "task_form_version": 6,
            "assessment_attempt_id": "attempt-1",
            "response_version_id": "response-1",
        },
        "evidence_id": "evidence-1",
        "evidence_type": "learner_response",
        "schema_version": "learner-response.v1",
        "record_version": 1,
        "content_digest": f"sha256:{'a' * 64}",
        "source_record_id": "submission-1",
        "source_record_version": 1,
        "occurred_at": "2026-08-15T01:02:03Z",
    }
    with pytest.raises(ValidationError, match="frozen"):
        reference.evidence_id = "changed"  # type: ignore[misc]

    invalid = reference.model_dump()
    invalid["occurred_at"] = datetime(2026, 8, 15, 1, 2, 3)
    with pytest.raises(ValidationError, match="timezone"):
        EvidenceReference.model_validate(invalid)


def test_stale_missing_conflict_access_denied_and_invalid_are_distinct() -> None:
    assessment = assessment_reference()
    reference = evidence_reference()
    resolutions: tuple[EvidenceReferenceResolution, ...] = (
        ResolvedEvidenceReference(reference=reference),
        MissingEvidenceReference(
            assessment=assessment,
            evidence_id="evidence-missing",
            reason_code="NOT_FOUND",
        ),
        StaleEvidenceReference(
            reference=reference,
            mismatched_fields=("record_version",),
            reason_code="VERSION_MISMATCH",
        ),
        ConflictingEvidenceReference(
            assessment=assessment,
            evidence_ids=("evidence-1", "evidence-2"),
            reason_code="MULTIPLE_ACTIVE_RECORDS",
        ),
        AccessDeniedEvidenceReference(
            assessment=assessment,
            reference_id="evidence-private",
            reason_code="COURSE_ACCESS_DENIED",
        ),
        InvalidEvidenceReference(
            reference_id="bad-reference",
            reason_code="MALFORMED_REFERENCE",
        ),
    )

    assert {resolution.status for resolution in resolutions} == {
        "RESOLVED",
        "MISSING",
        "STALE",
        "CONFLICT",
        "ACCESS_DENIED",
        "INVALID",
    }
    adapter = TypeAdapter(EvidenceReferenceResolution)
    for resolution in resolutions:
        envelope = EvidenceReferenceResolutionEnvelope(resolution=resolution)
        parsed = adapter.validate_python(envelope.resolution.model_dump(mode="json"))
        assert parsed.status == resolution.status


def test_forbidden_formal_result_inputs_are_rejected() -> None:
    base = evidence_reference().model_dump()
    for field, value in (
        ("score", 0.9),
        ("research_condition", "control"),
        ("confidence", 0.8),
        ("access_support", "extra_time"),
    ):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            EvidenceReference.model_validate({**base, field: value})

    with pytest.raises(ValidationError):
        EvidenceReference.model_validate({**base, "record_version": 0})
    with pytest.raises(ValidationError):
        EvidenceReference.model_validate({**base, "content_digest": "sha256:abc"})
    with pytest.raises(ValidationError):
        EvidenceReference.model_validate({**base, "contract_version": "assessment-evidence.v2"})
    with pytest.raises(ValidationError):
        assessed_result(contract_version="formal-result-summary.v2")


def test_assessment_schema_import_does_not_load_orm_modules() -> None:
    command = """
import sys
from app.schemas.assessment import EvidenceReference
forbidden = sorted(
    name for name in sys.modules
    if name == 'app.models' or name.startswith('app.models.') or name.startswith('app.services.')
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


def test_openapi_export_includes_frozen_assessment_contracts() -> None:
    schemas = json.loads(rendered_contract())["components"]["schemas"]

    assert schemas["AssessmentResult"]["enum"] == ["PASS", "INCOMPLETE"]
    assert "EvidenceReference" in schemas
    assert "EvidenceReferenceResolutionEnvelope" in schemas
    assert "FormalResultSummary" in schemas
