"""FR17 reviews are output-bound quality decisions, never assessment results."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.assessment import QualityReviewDecision


class OutputCategory(StrEnum):
    TASK = "task"
    EXPLANATION = "explanation"
    SUGGESTION = "suggestion"
    FEEDBACK = "feedback"
    PROVISIONAL_ASSESSMENT = "provisional_assessment"
    SUPPORT_REPRESENTATION = "support_representation"


class ReviewDimension(StrEnum):
    FACTUAL_ACCURACY = "factual_accuracy"
    GROUNDING = "grounding_and_source_use"
    RELEVANCE = "relevance"
    OUTCOME_ALIGNMENT = "outcome_and_bloom_alignment"
    EVIDENCE_ALIGNMENT = "evidence_rule_alignment"
    SUPPORT = "support_and_answer_leakage"
    CLARITY = "clarity_and_next_steps"
    ACCESSIBILITY = "accessibility_and_inclusive_wording"
    LEARNER_SAFETY = "bias_and_unsupported_learner_claims"
    INDEPENDENCE = "reflection_and_independent_work"


class ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ReviewEvidence(ReviewModel):
    reference: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=200)
    kind: Literal["approved_content", "observation", "policy"]
    approval_reference: str | None = Field(default=None, min_length=1, max_length=200)
    content: dict[str, Any] | list[Any] | str

    @model_validator(mode="after")
    def require_content_approval(self):
        if self.kind == "approved_content" and not self.approval_reference:
            raise ValueError("Approved content requires its exact approval reference")
        return self


class CategoryReviewRequest(ReviewModel):
    category: OutputCategory
    course_id: str = Field(min_length=1, max_length=100)
    subject_id: str = Field(min_length=1, max_length=200)
    output: dict[str, Any] | list[Any] | str
    evidence: tuple[ReviewEvidence, ...] = ()
    versions: dict[str, str] = Field(min_length=1)
    scope: Literal["new_content", "reviewed_selection"] = "new_content"

    @model_validator(mode="after")
    def unique_evidence(self):
        if len({item.reference for item in self.evidence}) != len(self.evidence):
            raise ValueError("Review evidence references must be unique")
        if any(not key.strip() or not value.strip() for key, value in self.versions.items()):
            raise ValueError("Review versions must be explicit")
        if self.scope == "reviewed_selection" and self.category != OutputCategory.SUGGESTION:
            raise ValueError("Reviewed selection applies only to curriculum suggestions")
        return self


class DimensionFinding(ReviewModel):
    dimension: ReviewDimension
    outcome: Literal["SATISFIED", "VIOLATED", "UNVERIFIED", "NOT_APPLICABLE"]
    basis: Literal["human", "model", "structural", "reviewed_content_inheritance"]
    reason: str = Field(min_length=1, max_length=2000)
    evidence_references: tuple[str, ...] = ()


class ReviewProvenance(ReviewModel):
    kind: Literal["human", "model", "deterministic"]
    reference: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=200)
    model_version: str | None = Field(default=None, min_length=1, max_length=200)
    prompt_version: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def model_has_versions(self):
        if self.kind == "model" and (not self.model_version or not self.prompt_version):
            raise ValueError("Model reviews require exact model and prompt versions")
        return self


class CategoryAssessment(ReviewModel):
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewer: ReviewProvenance
    findings: tuple[DimensionFinding, ...]

    @model_validator(mode="after")
    def complete_dimensions(self):
        dimensions = [item.dimension for item in self.findings]
        if len(dimensions) != len(ReviewDimension) or set(dimensions) != set(ReviewDimension):
            raise ValueError("Exactly one finding is required for every FR17 dimension")
        return self


class CategoryReviewRecord(ReviewModel):
    schema_version: Literal["category-review.v1"] = "category-review.v1"
    policy_version: Literal["fr17-complete-review.v1"] = "fr17-complete-review.v1"
    category: OutputCategory
    course_id: str
    subject_id: str
    request_digest: str
    output_digest: str
    versions: dict[str, str]
    evidence: tuple[dict[str, str | None], ...]
    scope: Literal["new_content", "reviewed_selection"]
    decision: QualityReviewDecision
    reason: str
    assessment: CategoryAssessment | None
    unresolved_dimensions: tuple[ReviewDimension, ...]
    reviewed_at: datetime
