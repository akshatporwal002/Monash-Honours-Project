from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.domain.assessment import AssessmentPurpose, BloomKnowledge, BloomProcess
from app.models.assessment import AssessmentApprovalState, CriterionEvaluatorType
from app.models.enums import MaterialIndexStatus, TaskType
from app.models.lms import (
    AttemptStatus,
    CourseState,
    EnrollmentStatus,
    OutcomeKind,
)
from app.models.user import ScopedRole, UserRole

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
UuidString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=36, max_length=36)]


class LmsSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class CourseCreate(LmsSchema):
    code: (
        Annotated[
            str,
            StringConstraints(
                strip_whitespace=True,
                to_upper=True,
                min_length=2,
                max_length=30,
                pattern=r"^[A-Z0-9][A-Z0-9-]*$",
            ),
        ]
        | None
    ) = None
    title: Title
    description: Annotated[str, Field(max_length=5_000)] = ""
    enrollment_open: bool = True


class CourseUpdate(LmsSchema):
    code: (
        Annotated[
            str,
            StringConstraints(
                strip_whitespace=True,
                to_upper=True,
                min_length=2,
                max_length=30,
                pattern=r"^[A-Z0-9][A-Z0-9-]*$",
            ),
        ]
        | None
    ) = None
    title: Title | None = None
    description: Annotated[str, Field(max_length=5_000)] | None = None
    enrollment_open: bool | None = None


class CourseRead(LmsSchema):
    id: str
    educator_id: int
    code: str
    title: str
    description: str
    state: CourseState
    enrollment_open: bool
    created_at: datetime
    updated_at: datetime
    module_count: int = 0
    student_count: int = 0
    progress_percentage: int = 0


class CourseProgressRead(LmsSchema):
    id: str
    code: str
    title: str
    description: str
    state: CourseState
    progress_percentage: int


class ModuleCreate(LmsSchema):
    title: Title
    description: Annotated[str, Field(max_length=5_000)] = ""
    position: Annotated[int, Field(gt=0)]


class ModuleUpdate(LmsSchema):
    title: Title | None = None
    description: Annotated[str, Field(max_length=5_000)] | None = None
    position: Annotated[int, Field(gt=0)] | None = None


class ModuleRead(LmsSchema):
    id: str
    course_id: str
    title: str
    description: str
    position: int
    created_at: datetime
    updated_at: datetime


class OutcomeCreate(LmsSchema):
    title: Title
    statement: NonEmpty
    kind: OutcomeKind
    week_number: Annotated[int, Field(gt=0)] | None = None
    position: Annotated[int, Field(gt=0)]

    @model_validator(mode="after")
    def validate_kind(self) -> OutcomeCreate:
        if self.kind is OutcomeKind.WEEKLY and self.week_number is None:
            raise ValueError("weekly outcomes require week_number")
        if self.kind is OutcomeKind.TOPIC and self.week_number is not None:
            raise ValueError("topic outcomes must not define week_number")
        return self


class OutcomeUpdate(LmsSchema):
    title: Title | None = None
    statement: NonEmpty | None = None
    kind: OutcomeKind | None = None
    week_number: Annotated[int, Field(gt=0)] | None = None
    position: Annotated[int, Field(gt=0)] | None = None


class OutcomeRead(LmsSchema):
    id: str
    module_id: str
    title: str
    statement: str
    kind: OutcomeKind
    week_number: int | None
    position: int
    created_at: datetime
    updated_at: datetime


class ScopedRoleAssignmentCreate(LmsSchema):
    subject_user_id: Annotated[int, Field(gt=0)]
    role: ScopedRole
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)]


class ScopedRoleAssignmentRevoke(LmsSchema):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)]


class ScopedRoleAssignmentRead(LmsSchema):
    id: str
    subject_user_id: int
    course_id: str
    role: ScopedRole
    version: int
    reason: str
    assigned_by_user_id: int
    assigned_at: datetime
    valid_from: datetime
    valid_until: datetime | None
    revoked_at: datetime | None


class AssessmentCriterionDraft(LmsSchema):
    stable_key: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    learner_description: NonEmpty
    evidence_description: NonEmpty
    mandatory: bool
    evidence_source_types: list[NonEmpty]
    met_rule: NonEmpty
    not_met_rule: NonEmpty
    not_evaluable_rule: NonEmpty
    approved_anchors: dict[str, Any] | list[Any]
    critical_error_rules: dict[str, Any] | list[Any]
    evaluator_type: CriterionEvaluatorType = CriterionEvaluatorType.RULES


class AssessmentTaskFormDraft(LmsSchema):
    learning_task_id: UuidString
    source_version: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    source_digest: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    task_family: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    context: dict[str, Any] | list[Any]
    constraints: dict[str, Any] | list[Any]


class AssessmentDefinitionDraftCreate(LmsSchema):
    claim: NonEmpty
    supporting_evidence: dict[str, Any] | list[Any]
    contradicting_evidence: dict[str, Any] | list[Any]
    insufficient_evidence: dict[str, Any] | list[Any]
    task_conditions: dict[str, Any] | list[Any]
    next_action_contract: dict[str, Any] | list[Any]
    purpose: AssessmentPurpose
    permitted_tools: dict[str, Any] | list[Any]
    instructional_support: dict[str, Any] | list[Any]
    access_conditions: dict[str, Any] | list[Any]
    transfer_rule: dict[str, Any] | list[Any]
    evidence_sufficiency: dict[str, Any] | list[Any]
    formal_result_eligible: bool
    bloom_process: BloomProcess
    knowledge_dimension: BloomKnowledge
    criteria: list[AssessmentCriterionDraft]
    pass_rule_expression: dict[str, Any]
    task_forms: list[AssessmentTaskFormDraft]


class AssessmentDefinitionApproval(LmsSchema):
    expected_version: Annotated[int, Field(ge=1)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)]


class AssessmentTaskCriterionRead(LmsSchema):
    id: str
    stable_key: str
    version: int
    learner_description: str
    evidence_description: str
    mandatory: bool
    evidence_source_types: list[str]
    met_rule: str
    not_met_rule: str
    not_evaluable_rule: str
    evaluator_type: CriterionEvaluatorType


class AssessmentTaskFormRead(LmsSchema):
    id: str
    learning_task_id: str
    version: int
    source_version: str
    source_digest: str
    task_family: str
    context: dict[str, Any] | list[Any]
    constraints: dict[str, Any] | list[Any]


class AssessmentDefinitionRead(LmsSchema):
    id: str
    assessment_definition_id: str
    course_id: str
    outcome_version_id: str
    version: int
    approval_state: AssessmentApprovalState
    purpose: AssessmentPurpose
    bloom_process: BloomProcess
    knowledge_dimension: BloomKnowledge
    claim: str
    supporting_evidence: dict[str, Any] | list[Any]
    contradicting_evidence: dict[str, Any] | list[Any]
    insufficient_evidence: dict[str, Any] | list[Any]
    task_conditions: dict[str, Any] | list[Any]
    next_action_contract: dict[str, Any] | list[Any]
    permitted_tools: dict[str, Any] | list[Any]
    instructional_support: dict[str, Any] | list[Any]
    access_conditions: dict[str, Any] | list[Any]
    transfer_rule: dict[str, Any] | list[Any]
    evidence_sufficiency: dict[str, Any] | list[Any]
    criteria: list[AssessmentTaskCriterionRead]
    pass_rule_expression: dict[str, Any]
    task_forms: list[AssessmentTaskFormRead]
    formal_result_eligible: bool | None
    approved_at: datetime | None
    approved_by_user_id: int | None


class EnrollmentCreate(LmsSchema):
    student_id: Annotated[int, Field(gt=0)]


class EnrollmentRead(LmsSchema):
    id: str
    course_id: str
    student_id: int
    status: EnrollmentStatus
    enrolled_at: datetime
    student_name: str
    student_email: EmailStr


class TaskChoice(LmsSchema):
    id: str
    text: str


class TaskCreate(LmsSchema):
    module_id: UuidString
    learning_outcome_id: UuidString
    title: Title
    prompt: NonEmpty
    instructions: NonEmpty
    task_type: TaskType
    difficulty: Annotated[
        Literal["beginner", "intermediate", "advanced"],
        StringConstraints(to_lower=True),
    ]
    points: Annotated[int, Field(ge=0, le=10_000)] = 100
    position: Annotated[int, Field(gt=0)]
    starter_code: str | None = None
    expected_answer: str | None = None
    marking_criteria: dict[str, Any] = Field(default_factory=dict)
    source_references: list[str] = Field(default_factory=list)
    prerequisite_task_ids: list[str] = Field(default_factory=list)
    due_at: datetime | None = None

    @model_validator(mode="after")
    def require_answer_or_criteria(self) -> TaskCreate:
        if not self.expected_answer and not self.marking_criteria:
            raise ValueError("expected_answer or marking_criteria is required")
        if len(set(self.prerequisite_task_ids)) != len(self.prerequisite_task_ids):
            raise ValueError("prerequisite_task_ids must be unique")
        return self


class TaskUpdate(LmsSchema):
    title: Title | None = None
    prompt: NonEmpty | None = None
    instructions: NonEmpty | None = None
    difficulty: Literal["beginner", "intermediate", "advanced"] | None = None
    points: Annotated[int, Field(ge=0, le=10_000)] | None = None
    position: Annotated[int, Field(gt=0)] | None = None
    starter_code: str | None = None
    expected_answer: str | None = None
    marking_criteria: dict[str, Any] | None = None
    source_references: list[str] | None = None
    prerequisite_task_ids: list[str] | None = None
    due_at: datetime | None = None


class TaskGenerateRequest(LmsSchema):
    learning_outcome_id: UuidString
    task_count: Annotated[int, Field(ge=3, le=6)] = 6
    task_types: list[TaskType] = Field(
        default_factory=lambda: [
            TaskType.MULTIPLE_CHOICE,
            TaskType.MULTIPLE_ANSWER,
            TaskType.SHORT_ANSWER,
            TaskType.CODE_EXPLANATION,
            TaskType.CODE_COMPLETION,
            TaskType.QUANTUM_CIRCUIT,
        ]
    )
    due_at: datetime | None = None

    @field_validator("task_types")
    @classmethod
    def require_task_types(cls, value: list[TaskType]) -> list[TaskType]:
        if not value:
            raise ValueError("at least one task type is required")
        return value


class LatestAttemptSummary(LmsSchema):
    id: str
    attempt_number: int
    status: AttemptStatus
    score: int
    submitted_at: datetime


class AssessmentCriterionRead(LmsSchema):
    description: str
    mandatory: bool


class AssessmentConditionsRead(LmsSchema):
    purpose: AssessmentPurpose
    bloom_process: BloomProcess
    knowledge_dimension: BloomKnowledge
    claim: str
    criteria: list[AssessmentCriterionRead]
    task_conditions: dict[str, Any] | list[Any]
    permitted_tools: dict[str, Any] | list[Any]
    instructional_support: dict[str, Any] | list[Any]
    access_conditions: dict[str, Any] | list[Any]
    transfer_rule: dict[str, Any] | list[Any]
    review_rule: str


class TaskRead(LmsSchema):
    id: str
    title: str
    prompt: str
    instructions: str
    task_type: TaskType
    difficulty: str
    points: int
    position: int
    starter_code: str | None
    due_at: datetime | None
    course_id: str
    module_id: str
    module_title: str
    learning_outcome_id: str
    source_references: list[str]
    prerequisite_task_ids: list[str]
    choices: list[TaskChoice] = Field(default_factory=list)
    starter_circuit: dict[str, Any] | None = None
    access_status: Literal["locked", "available", "in_progress", "completed"]
    attempt_count: int = 0
    latest_score: int | None = None
    latest_attempt: LatestAttemptSummary | None = None
    assessment: AssessmentConditionsRead | None = None


class DraftWrite(LmsSchema):
    answer: str = ""
    code: str | None = None
    circuit: dict[str, Any] | None = None


class DraftRead(LmsSchema):
    id: str
    task_id: str
    answer: str
    code: str | None
    circuit: dict[str, Any] | None
    updated_at: datetime


class SubmissionCreate(DraftWrite):
    idempotency_key: Annotated[str | None, Field(min_length=1, max_length=255)] = None


class AttemptRead(LmsSchema):
    id: str
    task_id: str
    attempt_number: int
    status: AttemptStatus
    score: int | None
    answer: str
    code: str | None
    circuit: dict[str, Any] | None
    feedback: str
    feedback_reference: str | None
    points_awarded: int
    submitted_at: datetime


class ReminderRead(LmsSchema):
    id: str
    task_id: str
    title: str
    message: str
    is_read: bool
    created_at: datetime


class RecommendationRead(LmsSchema):
    task_id: str
    title: str
    reason: str
    priority: Literal["high", "medium", "low"]
    updated_at: datetime


class AchievementRead(LmsSchema):
    code: str
    name: str
    description: str
    icon: str
    earned_at: datetime


class StudentIdentityRead(LmsSchema):
    id: str
    user_id: int
    display_name: str


class StudentSummaryRead(LmsSchema):
    completed_tasks: int
    total_tasks: int
    completion_percentage: int
    average_score: int
    points: int
    level: int
    next_level_points: int


class StudentDashboardRead(LmsSchema):
    student: StudentIdentityRead
    summary: StudentSummaryRead
    courses: list[CourseProgressRead]
    tasks: list[TaskRead]
    recommendations: list[RecommendationRead]
    reminders: list[ReminderRead]
    achievements: list[AchievementRead]


class EducatorStudentRead(LmsSchema):
    student_id: str
    user_id: int
    display_name: str
    email: EmailStr
    course_id: str
    course_title: str
    completed_tasks: int
    total_tasks: int
    completion_percentage: int
    average_score: int
    last_active: datetime | None
    at_risk: bool
    overdue_tasks: int


class RecentActivityRead(LmsSchema):
    student_name: str
    task_title: str
    score: int
    occurred_at: datetime


class WeeklyEngagementRead(LmsSchema):
    label: str
    active_students: int
    submissions: int


class LabelScoreRead(LmsSchema):
    label: str
    score: int


class LeaderboardEntryRead(LmsSchema):
    student_id: str
    display_name: str
    points: int
    completed_tasks: int


class EducatorDashboardRead(LmsSchema):
    courses: list[CourseRead]
    total_students: int
    at_risk_students: int
    completion_percentage: int
    weekly_engagement: list[WeeklyEngagementRead]
    task_type_performance: list[LabelScoreRead]
    concept_mastery: list[LabelScoreRead]
    leaderboard: list[LeaderboardEntryRead]
    recent_activity: list[RecentActivityRead]


class BulkReminderCreate(LmsSchema):
    student_ids: list[UuidString] = Field(min_length=1)
    task_id: UuidString | None = None
    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)
    ]


class MaterialLinkCreate(LmsSchema):
    source_url: AnyUrl
    module_id: UuidString | None = None

    @field_validator("source_url")
    @classmethod
    def require_https(cls, value: AnyUrl) -> AnyUrl:
        if value.scheme != "https":
            raise ValueError("source_url must use HTTPS")
        return value


class MaterialRead(LmsSchema):
    id: str
    course_id: str
    module_id: str | None
    original_filename: str | None
    source_url: str | None
    mime_type: str
    indexing_status: MaterialIndexStatus
    file_size_bytes: int | None
    created_at: datetime


class AdminUserCreate(LmsSchema):
    email: EmailStr
    full_name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
    ]
    password: Annotated[str, Field(min_length=8, max_length=256)]
    role: UserRole


class AdminUserUpdate(LmsSchema):
    email: EmailStr | None = None
    full_name: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
        ]
        | None
    ) = None
    role: UserRole | None = None


class AdminUserRead(LmsSchema):
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    student_profile_id: str | None = None


class SettingsUpdate(LmsSchema):
    at_risk_threshold: Annotated[int, Field(ge=0, le=100)] | None = None
    passing_score: Annotated[int, Field(ge=0, le=100)] | None = None
    points_per_level: Annotated[int, Field(gt=0, le=100_000)] | None = None
    llm_provider: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
        ]
        | None
    ) = None
    llm_model: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
        ]
        | None
    ) = None
    reminders_enabled: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> SettingsUpdate:
        if not self.model_fields_set:
            raise ValueError("at least one setting is required")
        return self


class SettingsRead(LmsSchema):
    at_risk_threshold: int
    passing_score: int
    points_per_level: int
    llm_provider: str
    llm_model: str
    reminders_enabled: bool


class BootstrapRead(LmsSchema):
    users: list[AdminUserRead]
    course: CourseRead
