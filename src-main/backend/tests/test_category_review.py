"""Category review gates and exact provenance; all reviews are synthetic."""

import pytest
from pydantic import ValidationError

from app.domain.assessment import QualityReviewDecision
from app.schemas.category_review import (
    CategoryAssessment,
    CategoryReviewRequest,
    DimensionFinding,
    OutputCategory,
    ReviewDimension,
    ReviewEvidence,
    ReviewProvenance,
)
from app.services.category_review import (
    request_digest,
    require_approved,
    review_output,
    review_prompt,
)


@pytest.fixture
def review_case():
    return CategoryReviewRequest(
        category=OutputCategory.TASK,
        course_id="synthetic-course",
        subject_id="synthetic-revision",
        output={"prompt": "Explain the supplied example"},
        evidence=(
            ReviewEvidence(
                reference="passage",
                version="source-v1",
                kind="approved_content",
                approval_reference="synthetic-approval",
                content="Approved synthetic example",
            ),
        ),
        versions={"task": "task-v1", "prompt": "generator-v1", "model": "fixture-v1"},
    )


def human_assessment(review_case):
    return CategoryAssessment(
        request_digest=request_digest(review_case),
        reviewer=ReviewProvenance(
            kind="human", reference="user:synthetic", version="review-policy-v1"
        ),
        findings=tuple(
            DimensionFinding(
                dimension=dimension,
                outcome="SATISFIED",
                basis="human",
                reason=f"Synthetic explicit review of {dimension.value}",
                evidence_references=("passage",),
            )
            for dimension in ReviewDimension
        ),
    )


def test_explicit_complete_review_retains_every_dimension_and_exact_binding(review_case):
    assessment = human_assessment(review_case)
    result = review_output(review_case, lambda _: assessment)
    assert result.decision is QualityReviewDecision.APPROVED
    assert result.assessment == assessment
    assert len(result.assessment.findings) == 10
    assert result.evidence[0]["approval_reference"] == "synthetic-approval"
    assert "Approved synthetic example" not in result.model_dump_json()
    require_approved(result, review_case)
    assert review_prompt(review_case)["request_digest"] == result.request_digest


@pytest.mark.parametrize(
    "field,value",
    [
        ("output", {"prompt": "Another task"}),
        ("course_id", "foreign-course"),
        ("subject_id", "other-revision"),
        ("versions", {"model": "changed"}),
        ("evidence", ()),
    ],
)
def test_review_cannot_be_reused_after_any_binding_changes(review_case, field, value):
    prior = human_assessment(review_case)
    changed = review_case.model_copy(update={field: value})
    assert review_output(changed, lambda _: prior).decision is QualityReviewDecision.REJECTED
    with pytest.raises(ValueError):
        require_approved(review_output(review_case, lambda _: prior), changed)


@pytest.mark.parametrize("outcome", ["UNVERIFIED", "VIOLATED"])
def test_unresolved_dimension_rejects_with_original_reason(review_case, outcome):
    assessment = human_assessment(review_case).model_dump(mode="json")
    assessment["findings"][0].update(outcome=outcome, reason="Actual factual basis is missing")
    result = review_output(review_case, lambda _: assessment)
    assert result.decision is QualityReviewDecision.REJECTED
    assert result.unresolved_dimensions == (ReviewDimension.FACTUAL_ACCURACY,)
    assert result.assessment.findings[0].reason == "Actual factual basis is missing"


@pytest.mark.parametrize(
    "fault",
    ["missing_dimension", "duplicate_dimension", "foreign_evidence", "no_evidence", "false_basis"],
)
def test_malformed_or_unsupported_review_never_approves(review_case, fault):
    assessment = human_assessment(review_case).model_dump(mode="json")
    if fault == "missing_dimension":
        assessment["findings"].pop()
    elif fault == "duplicate_dimension":
        assessment["findings"][0] = assessment["findings"][1]
    elif fault == "foreign_evidence":
        assessment["findings"][0]["evidence_references"] = ["foreign-passage"]
    elif fault == "no_evidence":
        assessment["findings"][0]["evidence_references"] = []
    else:
        assessment["findings"][0]["basis"] = "model"
    result = review_output(review_case, lambda _: assessment)
    assert result.decision is QualityReviewDecision.REJECTED
    assert result.assessment is None


def test_no_reviewer_and_provider_fault_fail_closed_without_exception_text(review_case):
    assert review_output(review_case).decision is QualityReviewDecision.REJECTED

    def failed(_):
        raise RuntimeError("private provider credentials and payload")

    result = review_output(review_case, failed)
    assert result.reason == "review_invalid_or_failed"
    assert "credentials" not in result.model_dump_json()


@pytest.mark.parametrize("outcome", ["SATISFIED", "NOT_APPLICABLE"])
def test_structural_check_cannot_clear_new_content_quality(review_case, outcome):
    assessment = human_assessment(review_case).model_dump(mode="json")
    assessment["reviewer"]["kind"] = "deterministic"
    for finding in assessment["findings"]:
        finding.update(basis="structural", outcome=outcome)
    assert (
        review_output(review_case, lambda _: assessment).decision is QualityReviewDecision.REJECTED
    )


def test_model_review_requires_model_and_prompt_provenance():
    with pytest.raises(ValidationError):
        ReviewProvenance(kind="model", reference="provider", version="policy-v1")


@pytest.mark.parametrize(
    "field,value",
    [
        ("course_id", "foreign"),
        ("subject_id", "foreign"),
        ("category", OutputCategory.FEEDBACK),
        ("scope", "reviewed_selection"),
        ("versions", {"model": "forged"}),
        ("evidence", ()),
        ("reason", "forged"),
        ("unresolved_dimensions", (ReviewDimension.FACTUAL_ACCURACY,)),
    ],
)
def test_receipt_metadata_cannot_be_forged_separately_from_assessment(review_case, field, value):
    record = review_output(review_case, human_assessment)
    with pytest.raises(ValueError):
        require_approved(record.model_copy(update={field: value}), review_case)
