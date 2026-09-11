"""Versioned authority records; study release also requires explicit deployment opt-in."""

from typing import Annotated, Literal, get_args

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
TechnicalPairField = Literal[
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
PROCESSING_FIELDS = frozenset(get_args(TechnicalPairField))
InstrumentField = Literal[
    "instrument.define",
    "instrument.collect",
    "instrument.read",
    "instrument.export",
    "instrument.record_id",
    "instrument.participant_id",
    "instrument.course_ref",
    "instrument.sequence_id",
    "instrument.form_id",
    "instrument.form_version",
    "instrument.item_id",
    "instrument.stage",
    "instrument.outcome_ref",
    "instrument.task_ref",
    "instrument.response_ref",
    "instrument.choice_code",
    "instrument.integer_value",
    "instrument.response_text",
    "instrument.missing_reason",
    "instrument.event_kind",
    "instrument.reason_code",
    "instrument.revision",
    "instrument.supersedes_id",
    "instrument.correction_reason_code",
]
INSTRUMENT_FIELDS = frozenset(get_args(InstrumentField))
StudyField = Literal[
    "study.prepare",
    "study.allocate",
    "study.packet",
    "study.rate",
    "study.outcome",
    "study.read",
    "study.export",
    "study.record_id",
    "study.participant_id",
    "study.sequence_id",
    "study.stage",
    "study.condition",
    "study.plan_id",
    "study.record_kind",
    "study.instrument_record_id",
    "study.packet_id",
    "study.rubric_code",
    "study.value_code",
    "study.missing_reason",
    "study.redacted_evidence",
    "study.provenance",
]
STUDY_FIELDS = frozenset(get_args(StudyField))
OperationalField = Literal[
    "operational.episode",
    "operational.adaptation_reasons",
    "operational.override_reasons",
    "operational.reserved_cost",
    "operational.exposure_cost",
    "operational.response_text",
    "operational.code",
    "operational.evidence",
    "operational.model_references",
    "operational.adaptations",
    "operational.overrides",
    "operational.source_references",
    "operational.ai_output",
    "operational.judge_result",
    "operational.simulation",
    "operational.latency_ms",
    "operational.input_tokens",
    "operational.output_tokens",
    "operational.estimated_cost",
    "operational.actual_cost",
    "operational.outcome",
    "operational.moderation",
]
OperationalPermission = Literal["operational.collect", "operational.read", "operational.export"]
OPERATIONAL_FIELDS = frozenset(get_args(OperationalField))
FieldPath = (
    TechnicalPairField | InstrumentField | StudyField | OperationalField | OperationalPermission
)
ResearchPurpose = Literal[
    "technical_pair", "provider_processing", "study_instruments", "study_operational_evidence"
]


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
    fields: list[FieldPath] = Field(min_length=1, max_length=128)
    purposes: list[ResearchPurpose] = Field(min_length=1)
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    retention: list[RetentionClass] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def window(self):
        if self.valid_until <= self.valid_from:
            raise ValueError("invalid study window")
        classes = {item.record_class for item in self.retention}
        required = {"governance", "identity_mapping", "export_audit"}
        if {"technical_pair", "provider_processing"} & set(self.purposes):
            required.add("technical_pairs")
        if not required <= classes:
            raise ValueError("required retention classes are missing")
        if len(classes) != len(self.retention):
            raise ValueError("duplicate retention class")
        if (
            "study_instruments" in self.purposes
            and not {
                "instrument_definitions",
                "instrument_records",
                "restricted_instrument_evidence",
            }
            <= classes
        ):
            raise ValueError("instrument retention classes are missing")
        if (
            "study_operational_evidence" in self.purposes
            and "study_operational_manifests" not in classes
        ):
            raise ValueError("operational manifest retention class is missing")
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
    fields: list[FieldPath] = Field(default_factory=list, max_length=128)
    purposes: list[ResearchPurpose] = Field(default_factory=list)


class InstrumentApprovalDecision(GovernanceContract):
    kind: Literal["instrument_approval"] = "instrument_approval"
    scope_id: Code
    form_id: Code
    content_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    state: Literal["approved", "suspended", "revoked"]
    authority_reference: Code
    evidence_reference: Code
    valid_from: AwareDatetime
    valid_until: AwareDatetime


class StudyReleaseDecision(GovernanceContract):
    kind: Literal["release"] = "release"
    scope_id: Code
    approval_id: Code
    plan_ids: list[Code] = Field(default_factory=list, max_length=128)
    instrument_approval_ids: list[Code] = Field(default_factory=list, max_length=128)
    state: Literal["active", "suspended", "revoked"]
    authority_reference: Code
    evidence_reference: Code
    valid_from: AwareDatetime
    valid_until: AwareDatetime

    @model_validator(mode="after")
    def unique_references(self):
        if len(set(self.plan_ids)) != len(self.plan_ids) or len(
            set(self.instrument_approval_ids)
        ) != len(self.instrument_approval_ids):
            raise ValueError("release references must be unique")
        return self


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
    fields: list[FieldPath] = Field(min_length=1, max_length=128)
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


class DisposalAuthorization(GovernanceContract):
    kind: Literal["disposal_authorization"] = "disposal_authorization"
    scope_id: Code
    record_class: Literal["restricted_instrument_evidence"]
    record_ids: list[Code] = Field(min_length=1, max_length=200)
    manifest_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    executor_user_id: int = Field(gt=0)
    state: Literal["authorized", "revoked"]
    method: Literal["delete_restricted_text"]
    authority_reference: Code
    evidence_reference: Code
    not_before: AwareDatetime
    valid_until: AwareDatetime

    @model_validator(mode="after")
    def bounded_authority(self):
        if self.not_before >= self.valid_until or len(set(self.record_ids)) != len(self.record_ids):
            raise ValueError(
                "disposal authority requires an exact unique inventory and valid window"
            )
        return self


class DisposedEvidence(GovernanceContract):
    evidence_id: Code
    record_id: Code
    content_digest: str


class DisposalExecution(GovernanceContract):
    kind: Literal["disposal_execution"] = "disposal_execution"
    scope_id: Code
    authorization_id: Code
    manifest_digest: str
    records: list[DisposedEvidence]


class DisposalPreview(GovernanceContract):
    record_ids: list[Code] = Field(min_length=1, max_length=200)


class DisposalExecute(GovernanceContract):
    authorization_id: Code
    request_key: Code


GovernanceDecision = Annotated[
    StudyScope
    | ApprovalDecision
    | ConsentDecision
    | InstrumentApprovalDecision
    | StudyReleaseDecision
    | EligibilityDecision
    | ResearchGrant
    | RetentionHold
    | DisposalAuthorization
    | DisposalExecution,
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
    production_active: bool = False


class GovernanceHistoryEntry(GovernanceReceipt):
    actor_user_id: int
    command: GovernanceCommand


class ParticipationRead(GovernanceContract):
    study_id: str
    scope_id: str
    revision: int
    scope: StudyScope
    consent: ConsentDecision | None
    production_active: bool = False
