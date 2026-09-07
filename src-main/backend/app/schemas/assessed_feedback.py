"""Learner-safe, evidence-linked assessed feedback. No assessment decisions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import AssessmentVersionReference


class SafeFeedbackContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ResponseFieldEvidence(SafeFeedbackContract):
    response_version_id: str
    content_digest: str
    path: str
    recorded: bool
    statement: str


class CriterionFeedback(SafeFeedbackContract):
    criterion_id: str
    criterion_version_id: str
    criterion_version: int
    learner_description: str
    evidence: list[ResponseFieldEvidence]
    guidance: str
    simulation_references: list[str]


class GroundedSourceClaim(SafeFeedbackContract):
    source_id: str
    source_label: str
    document_id: str
    chunk_id: str
    source_revision_id: str
    source_digest: str
    passage_digest: str
    approval_id: str
    retrieval_request_id: str
    retrieval_version: str
    support_quote: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    claim: str


class SimulationProvenance(SafeFeedbackContract):
    run_id: str
    circuit_version_id: str
    prediction_checkpoint_id: str | None
    episode_stage_start_id: str | None
    status: str
    result_digest: str
    policy_version: str
    engine_versions: dict[str, str]


class AssessedFeedbackView(SafeFeedbackContract):
    contract_version: Literal["learnlens.assessed-feedback.v1"] = "learnlens.assessed-feedback.v1"
    assessment: AssessmentVersionReference
    assessment_attempt_id: str
    response_version_id: str
    content_digest: str
    task_revision_id: str
    task_form_id: str
    task_form_version: int
    task_form_version_id: str | None
    current_human_action_id: str | None
    summary: str
    criteria: list[CriterionFeedback]
    source_claims: list[GroundedSourceClaim]
    simulation_evidence: list[SimulationProvenance]
    approved_hints: list[str]
    reflection_prompt: str
    permitted_next_action: str
    help_use_ids: list[str]
    rule_policy_version: str
    prompt_version: str
    model_version: str
