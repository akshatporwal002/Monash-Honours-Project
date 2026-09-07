"""Pure, lossless learning episode contracts. No application or database imports."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from app.schemas.assessment import EvidenceReference, OpaqueId

Text = Annotated[str, Field(strict=True, max_length=100_000)]
NonBlankText = Annotated[str, Field(strict=True, min_length=1, max_length=100_000)]


class EpisodeContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ResponseContent(EpisodeContract):
    answer: Text = ""
    code: Text | None = None
    circuit: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def bounded_circuit(self) -> ResponseContent:
        import json

        if self.circuit is not None and len(json.dumps(self.circuit, allow_nan=False)) > 100_000:
            raise ValueError("Circuit payload exceeds 100000 characters")
        return self


class SimulationReference(EpisodeContract):
    run_id: OpaqueId
    circuit_version_id: OpaqueId


class EpisodeRevision(EpisodeContract):
    previous_response_version_id: OpaqueId
    reason: NonBlankText

    @model_validator(mode="after")
    def nonblank_reason(self) -> EpisodeRevision:
        if not self.reason.strip():
            raise ValueError("A revision reason is required")
        return self


class EpisodeStageResponseV1(EpisodeContract):
    prediction: ResponseContent | None = None
    reasoning: Text | None = None
    explanation: Text | None = None
    revision: EpisodeRevision | None = None
    reflection: Text | None = None
    prediction_checkpoint_id: OpaqueId | None = None
    simulation_references: Annotated[tuple[SimulationReference, ...], Field(max_length=100)] = ()


class TransferResponseV1(EpisodeContract):
    stage_start_id: OpaqueId
    part_id: OpaqueId
    content: ResponseContent
    process: EpisodeStageResponseV1


class EpisodePayloadV1(EpisodeContract):
    schema_version: Literal["learnlens.episode.v1"] = "learnlens.episode.v1"
    supported: EpisodeStageResponseV1
    transfer: TransferResponseV1 | None = None


class FrozenResponseRead(EpisodeContract):
    reference: EvidenceReference
    assessment_work_start_id: OpaqueId | None
    task_form_version_id: OpaqueId | None
    content: ResponseContent
    episode: EpisodePayloadV1 | None
    declared_conditions: dict[str, Any]


class EpisodeTransferPlanV1(EpisodeContract):
    part_id: OpaqueId = "transfer"
    prompt: NonBlankText
    instructions: Text = "Complete this fresh application without instructional hints."
    starter_code: Text | None = None
    starter_circuit: dict[str, JsonValue] | None = None
    solution: ResponseContent | None = None


class EpisodePlanV1(EpisodeContract):
    schema_version: Literal["learnlens.episode-plan.v1"] = "learnlens.episode-plan.v1"
    supported_part_id: OpaqueId = "supported"
    prediction_required: bool = True
    required_responses: Annotated[
        tuple[Literal["prediction", "reasoning", "explanation", "reflection"], ...],
        Field(max_length=4),
    ] = ("prediction", "reasoning", "explanation", "reflection")
    transfer: EpisodeTransferPlanV1
    supported_hints: Annotated[tuple[Text, ...], Field(max_length=100)] = ()
    accessibility_support: Annotated[tuple[Text, ...], Field(max_length=100)] = ()

    @model_validator(mode="after")
    def valid_parts(self) -> EpisodePlanV1:
        if self.supported_part_id == self.transfer.part_id:
            raise ValueError("Supported and transfer part IDs must differ")
        if len(set(self.required_responses)) != len(self.required_responses):
            raise ValueError("Required responses must be unique")
        if self.prediction_required and "prediction" not in self.required_responses:
            raise ValueError("Prediction must be required before revealing results")
        if not self.transfer.prompt.strip():
            raise ValueError("The fresh transfer prompt is required")
        return self
