"""Pure bounded checks for approved circuit structure, never conceptual mastery."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.assessment import BloomProcess, CriterionDecision


class CircuitOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    gate: Literal["h", "x", "cx"]
    targets: list[Annotated[int, Field(ge=0, le=4)]] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def valid_targets(self) -> "CircuitOperation":
        size = 2 if self.gate == "cx" else 1
        if len(self.targets) != size or len(set(self.targets)) != size:
            raise ValueError("gate requires the declared number of distinct targets")
        return self


class CircuitStructure(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    qubits: Annotated[int, Field(ge=1, le=5)]
    operations: list[CircuitOperation] = Field(max_length=30)

    @model_validator(mode="after")
    def valid_qubits(self) -> "CircuitStructure":
        if any(target >= self.qubits for op in self.operations for target in op.targets):
            raise ValueError("gate target is outside the declared circuit")
        return self


class CircuitResponseStructure(CircuitStructure):
    shots: Annotated[int, Field(ge=1, le=4096)] | None = None
    seed: Annotated[int, Field(ge=0, le=4294967295)] | None = None


class CircuitRuleSettings(CircuitStructure):
    """An approved exact structural claim about one named response stage."""

    kind: Literal["circuit_v1"]
    stage: Literal["supported", "transfer"]


def validate_circuit_settings(anchors: object, bloom_process: BloomProcess) -> CircuitRuleSettings:
    if bloom_process is not BloomProcess.APPLY:
        raise ValueError("circuit structure rules support APPLY; reasoning needs human assessment")
    return CircuitRuleSettings.model_validate(anchors)


def evaluate_circuit_structure(
    settings: CircuitRuleSettings, circuit: object | None
) -> tuple[CriterionDecision, str]:
    """Compare exact saved operations; malformed learner content stays inspectable."""
    if circuit is None:
        return CriterionDecision.NOT_EVALUABLE, "The approved stage has no circuit response."
    try:
        payload = CircuitResponseStructure.model_validate(circuit)
        actual = CircuitStructure(qubits=payload.qubits, operations=payload.operations)
    except ValueError:
        return (
            CriterionDecision.NOT_EVALUABLE,
            "The saved circuit requires human inspection because its structure is unsupported.",
        )
    expected = CircuitStructure(qubits=settings.qubits, operations=settings.operations)
    if actual == expected:
        return (
            CriterionDecision.MET,
            "The saved circuit matches the approved qubit count and ordered gate operations. "
            "This check makes no claim about the learner's explanation.",
        )
    return (
        CriterionDecision.NOT_MET,
        "The saved circuit differs from the approved qubit count or ordered gate operations. "
        "An assessor may inspect an equivalent method.",
    )
