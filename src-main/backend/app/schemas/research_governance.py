"""Versioned governance commands; none of these records opens the production gate."""

from typing import Annotated, Literal, get_args

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
FieldPath = Literal[
    "case_id",
    "pseudonymous_user_id",
    "course_id",
    "task_id",
    "task_type",
    "submission_reference",
    "experimental_condition",
    "judge_decision",
    "correctness_score",
    "relevance_score",
    "grounding_score",
    "actionability_score",
    "safety_score",
    "unsupported_claim_count",
    "latency_ms",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "estimated_cost",
    "regeneration_count",
    "fallback_used",
    "status",
    "comparable",
    "usage_complete",
    "measurement_schema_version",
    "created_at",
    "completed_at",
    "processing.technical_pair",
    "processing.provider_input",
    "processing.generated_output",
    "processing.judge_result",
    "processing.input_references",
    "processing.retrieved_sources",
    "processing.simulation_reference",
]
# The existing paired processor persists this fixed measurement contract. Partial
# permission denies the pair; it must not silently collect unapproved metrics.
PROCESSING_FIELDS = frozenset(get_args(FieldPath))


class GovernanceContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RetentionClass(GovernanceContract):
    record_class: Code
    authority_reference: Code
    authority_version: Code
    owner_reference: Code
    trigger: Code
    retention_rule: Code
    review_at: AwareDatetime


class StudyScope(GovernanceContract):
    kind: Literal["scope"] = "scope"
    protocol_version: Code
    data_plan_version: Code
    consent_version: Code
    eligibility_rule_version: Code
    withdrawal_rule_reference: Code
    processing_researcher_id: int = Field(gt=0)
    course_ids: list[Code] = Field(min_length=1, max_length=100)
    fields: list[FieldPath] = Field(min_length=1, max_length=64)
    purposes: list[Literal["technical_pair", "provider_processing"]] = Field(min_length=1)
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    retention: list[RetentionClass] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def window(self):
        if self.valid_until <= self.valid_from:
            raise ValueError("invalid study window")
        classes = {item.record_class for item in self.retention}
        if not {"governance", "identity_mapping", "technical_pairs", "export_audit"} <= classes:
            raise ValueError("required retention classes are missing")
        if len(classes) != len(self.retention):
            raise ValueError("duplicate retention class")
        return self


class ApprovalDecision(GovernanceContract):
    kind: Literal["approval"] = "approval"
    scope_id: Code
    state: Literal["approved", "suspended", "revoked", "pending"]
    authority_reference: Code
    evidence_reference: Code
    valid_from: AwareDatetime
    valid_until: AwareDatetime


class ConsentDecision(GovernanceContract):
    kind: Literal["consent"] = "consent"
    scope_id: Code
    course_id: Code
    subject_user_id: int = Field(gt=0)
    decision: Literal["consented", "declined", "withdrawn"]
    consent_version: Code
    fields: list[FieldPath] = Field(default_factory=list, max_length=64)
    purposes: list[Literal["technical_pair", "provider_processing"]] = Field(default_factory=list)


class EligibilityDecision(GovernanceContract):
    kind: Literal["eligibility"] = "eligibility"
    scope_id: Code
    course_id: Code
    subject_user_id: int = Field(gt=0)
    eligible: bool
    rule_version: Code
    evidence_reference: Code
    valid_until: AwareDatetime


class ResearchGrant(GovernanceContract):
    kind: Literal["grant"] = "grant"
    scope_id: Code
    course_id: Code
    subject_user_id: int = Field(gt=0)
    fields: list[FieldPath] = Field(min_length=1, max_length=64)
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    revoked: bool = False
    authority_reference: Code
    evidence_reference: Code


class RetentionHold(GovernanceContract):
    kind: Literal["hold"] = "hold"
    scope_id: Code
    record_class: Code
    hold_reference: Code
    authority_reference: Code
    active: bool


GovernanceDecision = Annotated[
    StudyScope
    | ApprovalDecision
    | ConsentDecision
    | EligibilityDecision
    | ResearchGrant
    | RetentionHold,
    Field(discriminator="kind"),
]


class GovernanceCommand(GovernanceContract):
    request_key: Code
    expected_revision: int = Field(ge=0)
    reason: Code
    decision: GovernanceDecision


class GovernanceReceipt(GovernanceContract):
    id: str
    study_id: str
    revision: int
    kind: str
    recorded_at: AwareDatetime
    production_active: Literal[False] = False


class GovernanceHistoryEntry(GovernanceReceipt):
    actor_user_id: int
    command: GovernanceCommand


class ParticipationRead(GovernanceContract):
    study_id: str
    scope_id: str
    revision: int
    scope: StudyScope
    consent: ConsentDecision | None
    production_active: Literal[False] = False
