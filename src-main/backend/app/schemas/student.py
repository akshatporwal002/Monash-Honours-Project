from datetime import datetime
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
    targets: list[Annotated[int, Field(ge=0)]]

    @model_validator(mode="after")
    def validate_targets(self) -> "GateOperation":
        required = 2 if self.gate == "cx" else 1
        if len(self.targets) != required or len(set(self.targets)) != required:
            raise ValueError(f"{self.gate} requires {required} distinct target(s)")
        return self


class SimulationRequest(BaseModel):
    qubits: Annotated[int, Field(ge=1, le=5)] = 2
    operations: list[GateOperation] = Field(default_factory=list, max_length=30)
    shots: Annotated[int, Field(ge=1, le=8192)] = 1024

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
