from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class GateOperation(BaseModel):
    gate: Literal["h", "x", "cx"]
    targets: list[Annotated[int, Field(ge=0, strict=True)]]

    @model_validator(mode="after")
    def validate_targets(self) -> "GateOperation":
        required = 2 if self.gate == "cx" else 1
        if len(self.targets) != required or len(set(self.targets)) != required:
            raise ValueError(f"{self.gate} requires {required} distinct target(s)")
        return self


class SimulationRequest(BaseModel):
    prediction_checkpoint_id: str | None = Field(default=None, min_length=1, max_length=255)
    episode_stage_start_id: str | None = Field(default=None, min_length=1, max_length=255)
    episode_part_id: str | None = Field(default=None, min_length=1, max_length=255)
    qubits: Annotated[int, Field(ge=1, le=5, strict=True)] = 2
    operations: list[GateOperation] = Field(default_factory=list, max_length=30)
    shots: Annotated[int, Field(ge=1, le=4096, strict=True)] = 1024
    seed: Annotated[int, Field(ge=0, le=4294967295, strict=True)] = 42
    task_id: str | None = Field(default=None, min_length=1, max_length=255)
    request_key: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_qubits(self) -> "SimulationRequest":
        if any(target >= self.qubits for op in self.operations for target in op.targets):
            raise ValueError("gate target is outside the circuit")
        return self


class SimulationRead(BaseModel):
    counts: dict[str, int]
    probabilities: dict[str, float]
    circuit_text: str
    engine: str
    sampled_frequencies: dict[str, float] = Field(default_factory=dict)
    statevector: list[list[float]] = Field(default_factory=list)
    engine_versions: dict[str, str] = Field(default_factory=dict)
    qubit_order: list[int] = Field(default_factory=list)
    measurement_mapping: list[list[int]] = Field(default_factory=list)
    seed: int = 42
    shots: int = 1024
    probability_method: Literal["exact_statevector"] = "exact_statevector"
    policy_version: str = "ideal-h-x-cx-v1"


class SimulationRunRead(BaseModel):
    prediction_checkpoint_id: str | None = None
    episode_stage_start_id: str | None = None
    run_id: str
    owner_id: int
    task_id: str | None
    course_id: str | None
    circuit_version_id: str
    content_digest: str
    circuit: dict
    submission_id: str | None
    purpose: Literal["practice", "task", "feedback"]
    seed: int
    shots: int
    policy_version: str
    engine_versions: dict[str, str]
    created_at: datetime
    deadline_at: datetime
    finished_at: datetime | None
    status: Literal["pending", "completed", "failed", "timed_out", "interrupted"]
    error_code: str | None
    result: SimulationRead | None
