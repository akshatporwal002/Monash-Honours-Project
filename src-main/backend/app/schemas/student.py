from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.enums import NotificationKind, SubmissionStatus, TaskType

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StudentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TaskRead(StudentSchema):
    id: str
    slug: str
    title: str
    module: str
    description: str
    instructions: str
    task_type: TaskType
    difficulty: str
    points: int
    position: int
    starter_code: str | None
    due_at: datetime | None
    course_id: str | None = None
    module_id: str | None = None
    learning_outcome_id: str | None = None
    marking_criteria: dict | list | None = None
    source_references: list[str] = Field(default_factory=list)
    prerequisite_task_ids: list[str] = Field(default_factory=list)
    generation_provider: str | None = None
    generation_model: str | None = None
    generation_prompt_version: str | None = None
    generation_input_tokens: int = 0
    generation_output_tokens: int = 0
    generation_total_tokens: int = 0
    generation_estimated_cost: Decimal = Decimal(0)
    status: SubmissionStatus | None = None
    score: int | None = None


class SubmissionWrite(BaseModel):
    answer: str = ""
    code: str | None = None
    circuit: dict | None = None
    submit: bool = True


class SubmissionRead(StudentSchema):
    id: str
    student_id: str
    task_id: str
    answer: str
    code: str | None
    circuit: dict | None
    status: SubmissionStatus
    score: int
    feedback: str | None
    attempts: int
    submitted_at: datetime | None
    updated_at: datetime


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


class AchievementRead(BaseModel):
    code: str
    name: str
    description: str
    icon: str
    earned_at: datetime | None = None


class NotificationRead(StudentSchema):
    id: str
    kind: NotificationKind
    title: str
    message: str
    is_read: bool
    created_at: datetime


class RecommendationRead(BaseModel):
    task_id: str
    title: str
    reason: str
    priority: Literal["high", "medium", "low"]


class ProgressRead(BaseModel):
    student_id: str
    display_name: str
    completed_tasks: int
    total_tasks: int
    completion_percent: int
    average_score: int
    points: int
    streak_days: int
    level: int
    level_progress: int
    achievements: list[AchievementRead]
    module_progress: dict[str, int]


class DashboardRead(BaseModel):
    progress: ProgressRead
    tasks: list[TaskRead]
    recommendations: list[RecommendationRead]
    notifications: list[NotificationRead]


class EducatorStudentRead(BaseModel):
    student_id: str
    display_name: str
    completed_tasks: int
    total_tasks: int
    completion_percent: int
    average_score: int
    last_active: datetime | None
