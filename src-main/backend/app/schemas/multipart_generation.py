"""Draft-only multipart design. Runtime evidence references are never generated."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.episode import EpisodePlanV1
from app.schemas.lms import AssessmentDefinitionDraftCreate

STAGES = ("prediction", "reasoning", "explanation", "reflection", "transfer")


class SourceAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_reference: str = Field(min_length=1, max_length=100)
    quote: str = Field(min_length=1, max_length=4000)


class MultipartCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["learnlens.multipart-candidate.v1"] = "learnlens.multipart-candidate.v1"
    family: Literal["hadamard_basis_transfer", "source_application_transfer"]
    prior_work_policy: Literal["revision_after_real_same_work_response"]
    source_anchors: list[SourceAnchor] = Field(min_length=1, max_length=10)
    criterion_sources: dict[str, list[str]]
    episode_plan: EpisodePlanV1
    assessment_design: AssessmentDefinitionDraftCreate

    @model_validator(mode="after")
    def coherent_draft(self):
        plan, design = self.episode_plan, self.assessment_design
        if set(plan.required_responses) != set(STAGES[:-1]) or not plan.prediction_required:
            raise ValueError(
                "Multipart candidates require prediction, reasoning, explanation and reflection"
            )
        if plan.supported_hints:
            raise ValueError(
                "Generated support must use the typed source-grounded representation contract"
            )
        if design.task_forms or design.formal_result_eligible:
            raise ValueError(
                "Generated designs cannot bind task forms or declare formal eligibility"
            )
        if (
            design.purpose.value != "SUMMATIVE"
            or design.bloom_process.value != "APPLY"
            or design.knowledge_dimension.value != "PROCEDURAL"
        ):
            raise ValueError(
                "This candidate family proposes summative Apply/procedural evidence only"
            )
        criteria = design.criteria
        if len(criteria) != len(STAGES) or {item.stable_key for item in criteria} != set(STAGES):
            raise ValueError("Every required multipart stage needs its own criterion")
        if any(not item.mandatory or item.evaluator_type.value != "human" for item in criteria):
            raise ValueError("Candidate criteria must remain mandatory human-review drafts")
        expected_rule = {"operator": "ALL_OF", "clauses": [{"criterion": key} for key in STAGES]}
        if design.pass_rule_expression != expected_rule:
            raise ValueError("The candidate rule must require every stage criterion exactly once")
        sources = {anchor.source_reference for anchor in self.source_anchors}
        if set(self.criterion_sources) != set(STAGES) or any(
            not refs or not set(refs) <= sources for refs in self.criterion_sources.values()
        ):
            raise ValueError("Every criterion must cite the candidate's source anchors")
        for criterion in criteria:
            anchors = criterion.approved_anchors
            if not isinstance(anchors, dict) or any(
                not isinstance(anchors.get(name), list)
                or not anchors[name]
                or any(not isinstance(text, str) or not text.strip() for text in anchors[name])
                for name in ("met", "not_met")
            ):
                raise ValueError("Each criterion requires proposed met and not-met anchors")
        if design.transfer_rule != {"required": True, "independence": "unaided fresh input"}:
            raise ValueError("The proposed rule must retain separate unaided transfer")
        if design.access_conditions != {"review_required": True}:
            raise ValueError("Generated access equivalence must await human verification")
        forbidden = {
            "previous_response_version_id",
            "prediction_checkpoint_id",
            "stage_start_id",
            "run_id",
            "circuit_version_id",
            "task_approval_id",
            "approved_by",
        }

        def reject_references(value):
            if isinstance(value, dict):
                if forbidden & set(value):
                    raise ValueError(
                        "Generated candidates cannot invent runtime evidence or approval references"
                    )
                for item in value.values():
                    reject_references(item)
            elif isinstance(value, list):
                for item in value:
                    reject_references(item)

        reject_references(design.model_dump(mode="json"))
        return self
