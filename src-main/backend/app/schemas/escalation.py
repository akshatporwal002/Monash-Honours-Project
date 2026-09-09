from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

QueueKind = Literal["ASSESSOR", "TECHNICAL"]
Severity = Literal["NORMAL", "HIGH", "CRITICAL"]
CaseStatus = Literal["OPEN", "ACKNOWLEDGED", "ACTIONED", "RESOLVED", "CLOSED"]
SourceKind = Literal["FEEDBACK", "TUTOR", "ASSESSMENT"]


class EscalationContract(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, str_strip_whitespace=True)

    @field_validator(
        "created_at", "at", "acknowledgement_due_at", "resolution_due_at", check_fields=False
    )
    @classmethod
    def utc_timestamp(cls, value):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class QueueWrite(EscalationContract):
    expected_revision: int = Field(ge=0)
    primary_user_id: int = Field(gt=0)
    backup_user_id: int = Field(gt=0)
    acknowledgement_target: str = Field(min_length=1, max_length=500)
    resolution_target: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=2000)


class QueueRead(EscalationContract):
    id: str
    revision: int
    primary_user_id: int
    backup_user_id: int
    acknowledgement_target: str
    resolution_target: str


class QueueMember(EscalationContract):
    id: int
    name: str


class EscalationQueueRead(EscalationContract):
    course_id: str
    course_title: str
    kind: QueueKind
    configuration: QueueRead | None
    eligible_members: list[QueueMember]


class OutputReportWrite(EscalationContract):
    source_kind: Literal["FEEDBACK", "TUTOR"]
    source_id: str = Field(min_length=1, max_length=36)
    queue_kind: QueueKind
    severity: Severity = "NORMAL"
    reason: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(min_length=1, max_length=128)


class EscalationActionWrite(EscalationContract):
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=128)
    status: CaseStatus
    severity: Severity
    owner_user_id: int = Field(gt=0)
    acknowledgement_due_at: AwareDatetime
    resolution_due_at: AwareDatetime
    reason: str = Field(min_length=1, max_length=2000)
    learner_notice: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def deadline_order(self):
        if self.resolution_due_at < self.acknowledgement_due_at:
            raise ValueError("Resolution target cannot precede acknowledgement target")
        return self


class EscalationNotice(EscalationContract):
    revision: int
    status: CaseStatus
    learner_notice: str
    created_at: datetime


class EscalationRead(EscalationContract):
    id: str
    task_id: str
    source_kind: SourceKind
    source_id: str
    queue_kind: QueueKind
    status: CaseStatus
    revision: int
    severity: Severity
    created_at: datetime
    acknowledgement_due_at: datetime | None
    resolution_due_at: datetime | None
    notices: list[EscalationNotice]


class EscalationHistoryEntry(EscalationContract):
    revision: int
    status: CaseStatus
    reason: str
    actor_user_id: int
    owner_user_id: int
    queue_revision_id: str
    at: datetime


class EscalationStaffRead(EscalationRead):
    attention: Literal[
        "NEEDS_TRIAGE", "ACKNOWLEDGEMENT_OVERDUE", "RESOLUTION_OVERDUE", "ON_TARGET", "COMPLETE"
    ]
    trigger: str
    reason: str
    owner_user_id: int | None
    backup_user_id: int | None
    history: list[EscalationHistoryEntry]


class SamplingWrite(EscalationContract):
    feedback_id: str = Field(min_length=1, max_length=36)
    reason: str = Field(min_length=1, max_length=2000)
