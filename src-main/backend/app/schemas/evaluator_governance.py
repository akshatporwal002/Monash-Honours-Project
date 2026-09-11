"""Explicit, default-closed D-07 approval and imported suggestion contracts."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.domain.assessment import CriterionDecision
from app.schemas.category_review import CategoryAssessment

Reference = Annotated[str, Field(min_length=1, max_length=2000, pattern=r"\S")]
Fingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class GovernanceWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ExpertRecord(GovernanceWrite):
    name: Reference
    appointment_reference: Reference
    expertise_reference: Reference
    training_reference: Reference


class AssessmentGateEvidence(GovernanceWrite):
    provenance: Literal["EXPERT_RECORDED"]
    experts: list[ExpertRecord] = Field(min_length=2)
    approved_population_reference: Reference
    approved_statistic_reference: Reference
    uncertainty_reference: Reference
    task_type_coverage_reference: Reference
    alternate_form_reference: Reference
    concise_style_reference: Reference
    unusual_method_reference: Reference
    relevant_group_reference: Reference
    review_triggers_reference: Reference
    adjudication_reference: Reference
    baseline_statistic: Reference
    baseline_value: float = Field(ge=-1, le=1, allow_inf_nan=False)
    approved_minimum_baseline: float = Field(ge=-1, le=1, allow_inf_nan=False)
    case_count: int = Field(gt=0, strict=True)
    approved_minimum_case_count: int = Field(gt=0, strict=True)

    @model_validator(mode="after")
    def approved_gate(self):
        if len({expert.name.casefold() for expert in self.experts}) != len(self.experts):
            raise ValueError("Independent experts must be different named people")
        if self.case_count < self.approved_minimum_case_count:
            raise ValueError("Assessment sample does not meet its approved minimum")
        if self.baseline_value < self.approved_minimum_baseline:
            raise ValueError("Human agreement does not meet its approved minimum")
        return self


class EvaluatorReleaseWrite(GovernanceWrite):
    idempotency_key: Annotated[str, Field(min_length=1, max_length=128)]
    validation_id: Annotated[str, Field(min_length=1, max_length=36)]
    expected_fingerprint: Fingerprint
    authority_name: Reference
    authority_role: Reference
    approval_reference: Reference
    approved_at: AwareDatetime
    expires_at: AwareDatetime
    task_form_version_ids: list[str] = Field(min_length=1, max_length=1000)
    provider: Reference
    model: Reference
    prompt_version: Reference
    retrieval_version: Reference

    @model_validator(mode="after")
    def scope(self):
        if len(set(self.task_form_version_ids)) != len(self.task_form_version_ids):
            raise ValueError("Release scope cannot repeat a task form")
        if self.expires_at <= self.approved_at:
            raise ValueError("Release expiry must follow its approval")
        return self


class EvaluatorRevokeWrite(GovernanceWrite):
    idempotency_key: Annotated[str, Field(min_length=1, max_length=128)]
    expected_validation_id: Annotated[str, Field(min_length=1, max_length=36)]
    reason: Reference
    authority_reference: Reference


class SuggestedCriterion(GovernanceWrite):
    criterion_version_id: str
    decision: CriterionDecision
    reason: Annotated[str, Field(min_length=1, max_length=2000)]
    evidence_ids: list[str] = Field(min_length=1, max_length=100)


class SuggestionImportWrite(GovernanceWrite):
    idempotency_key: Annotated[str, Field(min_length=1, max_length=128)]
    release_id: str
    expected_fingerprint: Fingerprint
    response_digest: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$|^[0-9a-f]{64}$")]
    provider: Reference
    model: Reference
    prompt_version: Reference
    retrieval_version: Reference
    output_reference: Reference
    generated_at: AwareDatetime
    criteria: list[SuggestedCriterion] = Field(min_length=1, max_length=100)
    quality_review: CategoryAssessment | None = None
