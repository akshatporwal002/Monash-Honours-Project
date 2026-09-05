from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models import (
    Achievement,
    AssessmentApprovalState,
    AttemptStatus,
    Course,
    CourseModule,
    CourseState,
    Enrollment,
    EnrollmentStatus,
    LearningEvent,
    LearningEventType,
    LearningMaterial,
    LearningOutcome,
    LearningTask,
    MaterialChunk,
    MaterialIndexStatus,
    OutcomeKind,
    OutcomeVersion,
    PlatformAuditEvent,
    Recommendation,
    Reminder,
    StudentAchievement,
    StudentProfile,
    SubmissionAttempt,
    SubmissionDraft,
    SystemSetting,
    TaskPointAward,
    TaskType,
    User,
    UserRole,
    WorkflowRun,
    WorkflowStage,
)
from app.schemas.lms import (
    AchievementRead,
    AdminUserCreate,
    AdminUserRead,
    AdminUserUpdate,
    AssessmentConditionsRead,
    AssessmentTaskCriterionRead,
    AttemptRead,
    BulkReminderCreate,
    CourseCreate,
    CourseProgressRead,
    CourseRead,
    CourseUpdate,
    DraftRead,
    DraftWrite,
    EducatorDashboardRead,
    EducatorStudentRead,
    EnrollmentRead,
    LabelScoreRead,
    LatestAttemptSummary,
    LeaderboardEntryRead,
    MaterialLinkCreate,
    ModuleCreate,
    ModuleUpdate,
    OutcomeCreate,
    OutcomeUpdate,
    RecentActivityRead,
    RecommendationRead,
    ReminderRead,
    SettingsRead,
    SettingsUpdate,
    StudentDashboardRead,
    StudentIdentityRead,
    StudentSummaryRead,
    SubmissionCreate,
    TaskChoice,
    TaskCreate,
    TaskGenerateRequest,
    TaskRead,
    TaskUpdate,
    WeeklyEngagementRead,
)
from app.services.assessment.submissions import (
    AssessmentSubmissionService,
    AssessmentTaskDeclaration,
    FrozenAssessmentVersions,
)
from app.services.authentication import normalize_email
from app.services.gamification import GamificationService, ensure_default_achievements
from app.services.learning_events import HmacSha256Pseudonymizer
from app.services.rag.errors import RagError
from app.services.rag.storage import FileStorage
from app.services.rag.task_generation import GenerateTasksInput
from app.services.task_generation_runtime import build_grounded_task_generation_service
from app.services.task_types import (
    DEFAULT_TASK_TYPE_REGISTRY,
    InvalidTaskSubmissionError,
    TaskTypeRegistry,
    UnsupportedTaskTypeError,
)

DEFAULT_SETTINGS: dict[str, tuple[Any, str]] = {
    "at_risk_threshold": (
        70,
        "Students with recorded work below this percentage are flagged at risk.",
    ),
    "passing_score": (
        70,
        "Minimum score that completes a task and unlocks its dependants.",
    ),
    "points_per_level": (
        500,
        "Number of points required to advance one gamification level.",
    ),
    "llm_provider": (
        "openai",
        "Provider used by configurable AI workflows.",
    ),
    "llm_model": (
        "gpt-4.1-mini",
        "Model identifier used by configurable AI workflows.",
    ),
    "reminders_enabled": (
        True,
        "Whether overdue and educator reminders may be created.",
    ),
}

DEMO_PASSWORD = "quantumlearn-demo"
DEMO_ACCOUNTS: tuple[tuple[str, str, UserRole], ...] = (
    ("student@quantumlearn.demo", "Alex Morgan", UserRole.STUDENT),
    ("educator@quantumlearn.demo", "Dr Maya Chen", UserRole.EDUCATOR),
    ("admin@quantumlearn.demo", "Platform Admin", UserRole.ADMINISTRATOR),
)


class LmsServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _not_found(resource: str) -> LmsServiceError:
    return LmsServiceError(404, f"{resource} not found")


def _forbidden() -> LmsServiceError:
    return LmsServiceError(403, "You do not have access to this resource")


def _conflict(detail: str) -> LmsServiceError:
    return LmsServiceError(409, detail)


def _unprocessable(detail: str) -> LmsServiceError:
    return LmsServiceError(422, detail)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class LmsService:
    def __init__(
        self,
        session: Session,
        *,
        correlation_id: str | None = None,
        task_type_registry: TaskTypeRegistry = DEFAULT_TASK_TYPE_REGISTRY,
    ) -> None:
        self.session = session
        self.correlation_id = correlation_id or self._uuid()
        self.gamification = GamificationService(session)
        self.task_types = task_type_registry

    def list_courses(self, actor: User) -> list[CourseRead]:
        statement = select(Course)
        if actor.role is UserRole.EDUCATOR:
            statement = statement.where(Course.educator_id == actor.id)
        elif actor.role is UserRole.STUDENT:
            statement = (
                statement.join(Enrollment)
                .where(
                    Enrollment.student_id == actor.id,
                    Enrollment.status == EnrollmentStatus.ACTIVE,
                    Course.state == CourseState.PUBLISHED,
                )
                .distinct()
            )
        return [
            self._course_read(course)
            for course in self.session.scalars(statement.order_by(Course.created_at.desc())).all()
        ]

    def get_course_for_actor(self, actor: User, course_id: str) -> CourseRead:
        return self._course_read(self._require_course_read(actor, course_id))

    def create_course(self, educator: User, payload: CourseCreate) -> CourseRead:
        course = Course(
            educator_id=educator.id,
            code=payload.code or self._available_course_code(payload.title),
            title=payload.title,
            description=payload.description,
            enrollment_open=payload.enrollment_open,
        )
        self.session.add(course)
        self.session.flush()
        self._audit(educator, "course.created", "course", course.id)
        self._commit()
        return self._course_read(course)

    def update_course(
        self,
        educator: User,
        course_id: str,
        payload: CourseUpdate,
    ) -> CourseRead:
        course = self._require_course_owner(educator, course_id)
        self._require_not_archived(course)
        for name, value in payload.model_dump(
            exclude_unset=True,
            exclude_none=True,
        ).items():
            setattr(course, name, value)
        self._audit(educator, "course.updated", "course", course.id)
        self._commit()
        return self._course_read(course)

    def set_course_state(
        self,
        educator: User,
        course_id: str,
        state: CourseState,
    ) -> CourseRead:
        course = self._require_course_owner(educator, course_id)
        if state is CourseState.PUBLISHED:
            if course.state is CourseState.ARCHIVED:
                raise _conflict("Archived courses cannot be published")
            self._validate_publishable(course)
        course.state = state
        self._audit(educator, f"course.{state.value}", "course", course.id)
        self._commit()
        return self._course_read(course)

    def admin_archive_course(self, administrator: User, course_id: str) -> CourseRead:
        course = self._get_course(course_id)
        course.state = CourseState.ARCHIVED
        self._audit(administrator, "course.archived", "course", course.id)
        self._commit()
        return self._course_read(course)

    def list_modules(self, actor: User, course_id: str) -> list[CourseModule]:
        self._require_course_read(actor, course_id)
        return list(
            self.session.scalars(
                select(CourseModule)
                .where(CourseModule.course_id == course_id)
                .order_by(CourseModule.position)
            ).all()
        )

    def create_module(
        self,
        educator: User,
        course_id: str,
        payload: ModuleCreate,
    ) -> CourseModule:
        course = self._require_course_owner(educator, course_id)
        self._require_not_archived(course)
        module = CourseModule(course_id=course.id, **payload.model_dump())
        self.session.add(module)
        self.session.flush()
        self._audit(educator, "module.created", "module", module.id)
        self._commit()
        return module

    def update_module(
        self,
        educator: User,
        module_id: str,
        payload: ModuleUpdate,
    ) -> CourseModule:
        module = self._get_module(module_id)
        course = self._require_course_owner(educator, module.course_id)
        self._require_not_archived(course)
        for name, value in payload.model_dump(exclude_unset=True).items():
            setattr(module, name, value)
        self._audit(educator, "module.updated", "module", module.id)
        self._commit()
        return module

    def delete_module(self, educator: User, module_id: str) -> None:
        module = self._get_module(module_id)
        course = self._require_course_owner(educator, module.course_id)
        self._require_not_archived(course)
        task_count = self.session.scalar(
            select(func.count(LearningTask.id)).where(LearningTask.module_id == module.id)
        )
        if task_count:
            raise _conflict("Delete or move the module's tasks first")
        self._audit(educator, "module.deleted", "module", module.id)
        self.session.delete(module)
        self._commit()

    def list_outcomes(self, actor: User, module_id: str) -> list[LearningOutcome]:
        module = self._get_module(module_id)
        self._require_course_read(actor, module.course_id)
        return list(
            self.session.scalars(
                select(LearningOutcome)
                .where(LearningOutcome.module_id == module.id)
                .order_by(LearningOutcome.position)
            ).all()
        )

    def create_outcome(
        self,
        educator: User,
        module_id: str,
        payload: OutcomeCreate,
    ) -> LearningOutcome:
        module = self._get_module(module_id)
        course = self._require_course_owner(educator, module.course_id)
        self._require_not_archived(course)
        outcome = LearningOutcome(module_id=module.id, **payload.model_dump())
        self.session.add(outcome)
        self.session.flush()
        self._audit(educator, "outcome.created", "learning_outcome", outcome.id)
        self._commit()
        return outcome

    def create_assessment_outcome_version(
        self,
        educator: User,
        course_id: str,
        outcome_id: str,
    ) -> OutcomeVersion:
        """Freeze the course owner's current outcome wording for an assessment draft.

        This records the educator-approved course source. It does not approve a
        formal assessment definition or task form, which remains assessor-only.
        """

        course = self._require_course_owner(educator, course_id)
        self._require_not_archived(course)
        outcome = self._get_outcome(outcome_id)
        module = self._get_module(outcome.module_id)
        if module.course_id != course.id:
            raise _not_found("Learning outcome")
        current = self.session.scalar(
            select(func.max(OutcomeVersion.version)).where(
                OutcomeVersion.learning_outcome_id == outcome.id
            )
        )
        version_number = (current or 0) + 1
        now = datetime.now(UTC)
        version = OutcomeVersion(
            course_id=course.id,
            learning_outcome_id=outcome.id,
            version=version_number,
            owner_user_id=educator.id,
            created_by_user_id=educator.id,
            title=outcome.title,
            statement=outcome.statement,
            source_version=f"lms.outcome.v{version_number}",
            approval_state=AssessmentApprovalState.APPROVED,
            approved_at=now,
            approved_by_user_id=educator.id,
        )
        self.session.add(version)
        self.session.flush()
        self._audit(educator, "assessment.outcome_source_versioned", "outcome_version", version.id)
        return version

    def update_outcome(
        self,
        educator: User,
        outcome_id: str,
        payload: OutcomeUpdate,
    ) -> LearningOutcome:
        outcome = self._get_outcome(outcome_id)
        module = self._get_module(outcome.module_id)
        course = self._require_course_owner(educator, module.course_id)
        self._require_not_archived(course)
        values = payload.model_dump(exclude_unset=True)
        final_kind = values.get("kind", outcome.kind)
        final_week = values.get("week_number", outcome.week_number)
        if final_kind is OutcomeKind.WEEKLY and final_week is None:
            raise _unprocessable("Weekly outcomes require week_number")
        if final_kind is OutcomeKind.TOPIC and final_week is not None:
            raise _unprocessable("Topic outcomes must not define week_number")
        for name, value in values.items():
            setattr(outcome, name, value)
        self._audit(educator, "outcome.updated", "learning_outcome", outcome.id)
        self._commit()
        return outcome

    def delete_outcome(self, educator: User, outcome_id: str) -> None:
        outcome = self._get_outcome(outcome_id)
        module = self._get_module(outcome.module_id)
        course = self._require_course_owner(educator, module.course_id)
        self._require_not_archived(course)
        task_count = self.session.scalar(
            select(func.count(LearningTask.id)).where(
                LearningTask.learning_outcome_id == outcome.id
            )
        )
        if task_count:
            raise _conflict("Delete or move the outcome's tasks first")
        self._audit(educator, "outcome.deleted", "learning_outcome", outcome.id)
        self.session.delete(outcome)
        self._commit()

    def enroll_student(
        self,
        educator: User,
        course_id: str,
        student_id: int,
    ) -> EnrollmentRead:
        course = self._require_course_owner(educator, course_id)
        self._require_not_archived(course)
        student = self.session.get(User, student_id)
        if student is None or student.role is not UserRole.STUDENT:
            raise _unprocessable("student_id must identify a student account")
        enrollment = self.session.scalar(
            select(Enrollment).where(
                Enrollment.course_id == course.id,
                Enrollment.student_id == student.id,
            )
        )
        if enrollment is None:
            enrollment = Enrollment(course_id=course.id, student_id=student.id)
            self.session.add(enrollment)
            self.session.flush()
        else:
            enrollment.status = EnrollmentStatus.ACTIVE
        self._audit(educator, "enrollment.activated", "enrollment", enrollment.id)
        self._commit()
        return self._enrollment_read(enrollment, student)

    def list_enrollments(self, educator: User, course_id: str) -> list[EnrollmentRead]:
        self._require_course_owner(educator, course_id)
        rows = self.session.execute(
            select(Enrollment, User)
            .join(User, User.id == Enrollment.student_id)
            .where(Enrollment.course_id == course_id)
            .order_by(User.full_name)
        ).all()
        return [self._enrollment_read(enrollment, student) for enrollment, student in rows]

    def list_tasks(self, actor: User, course_id: str) -> list[TaskRead]:
        self._require_course_read(actor, course_id)
        tasks = list(
            self.session.scalars(
                select(LearningTask)
                .where(LearningTask.course_id == course_id)
                .order_by(LearningTask.position)
            ).all()
        )
        return [
            self._task_read(task, actor if actor.role is UserRole.STUDENT else None)
            for task in tasks
        ]

    def create_task(
        self,
        educator: User,
        course_id: str,
        payload: TaskCreate,
    ) -> TaskRead:
        course = self._require_course_owner(educator, course_id)
        self._require_not_archived(course)
        self._validate_task_context(course, payload.module_id, payload.learning_outcome_id)
        self._validate_prerequisites(
            course.id,
            payload.prerequisite_task_ids,
            payload.position,
        )
        task_id = self._uuid()
        task = LearningTask(
            id=task_id,
            slug=f"course-{course.id[:8]}-{task_id[:8]}",
            title=payload.title,
            module=self._get_module(payload.module_id).title,
            description=payload.prompt,
            instructions=payload.instructions,
            task_type=payload.task_type,
            difficulty=payload.difficulty,
            points=payload.points,
            position=payload.position,
            starter_code=payload.starter_code,
            expected_answer=payload.expected_answer,
            due_at=payload.due_at,
            course_id=course.id,
            module_id=payload.module_id,
            learning_outcome_id=payload.learning_outcome_id,
            marking_criteria=payload.marking_criteria,
            source_references=payload.source_references,
            prerequisite_task_ids=payload.prerequisite_task_ids,
        )
        self.session.add(task)
        self.session.flush()
        self._audit(educator, "task.created", "task", task.id)
        self._commit()
        return self._task_read(task)

    async def generate_scaffolded_tasks(
        self,
        educator: User,
        course_id: str,
        payload: TaskGenerateRequest,
    ) -> list[TaskRead]:
        course = self._require_course_owner(educator, course_id)
        self._require_not_archived(course)
        outcome = self._get_outcome(payload.learning_outcome_id)
        module = self._get_module(outcome.module_id)
        if module.course_id != course.id:
            raise _unprocessable("learning_outcome_id is outside this course")
        try:
            tasks = await build_grounded_task_generation_service(self.session).generate(
                GenerateTasksInput(
                    course_id=course.id,
                    module_id=module.id,
                    learning_outcome_id=outcome.id,
                    learning_outcome_text=outcome.statement,
                    task_count=payload.task_count,
                    allowed_task_types=tuple(payload.task_types),
                    difficulty_levels=("beginner", "intermediate", "advanced"),
                ),
                commit=False,
            )
        except RagError as error:
            raise _unprocessable(error.safe_message) from error
        except (UnsupportedTaskTypeError, ValueError) as error:
            raise _unprocessable(str(error)) from error
        for task in tasks:
            task.due_at = payload.due_at
            self._audit(educator, "task.generated", "task", task.id)
        self._commit()
        return [self._task_read(task) for task in tasks]

    def update_task(
        self,
        educator: User,
        task_id: str,
        payload: TaskUpdate,
    ) -> TaskRead:
        task = self._get_task(task_id)
        course = self._require_course_owner(educator, task.course_id or "")
        self._require_not_archived(course)
        values = payload.model_dump(exclude_unset=True)
        final_position = values.get("position", task.position)
        prerequisites = values.get("prerequisite_task_ids", task.prerequisite_task_ids)
        self._validate_prerequisites(course.id, prerequisites, final_position, task.id)
        if task.generation_provider is not None:
            values["source_references"] = self._validate_generated_source_references(
                course.id,
                values.get("source_references", task.source_references),
            )
        mapping = {"prompt": "description"}
        for name, value in values.items():
            setattr(task, mapping.get(name, name), value)
        self._audit(educator, "task.updated", "task", task.id)
        self._commit()
        return self._task_read(task)

    def get_task_for_actor(self, actor: User, task_id: str) -> TaskRead:
        task = self._get_task(task_id)
        if not task.course_id:
            raise _not_found("Task")
        self._require_course_read(actor, task.course_id)
        return self._task_read(task, actor if actor.role is UserRole.STUDENT else None)

    def get_student_task(self, student: User, task_id: str) -> TaskRead:
        task = self._require_student_task(student, task_id)
        result = self._task_read(task, student)
        self._learning_event(
            student,
            task,
            LearningEventType.TASK_VIEW,
            {"source": "task-page"},
        )
        self._commit()
        return result

    def save_draft(
        self,
        student: User,
        task_id: str,
        payload: DraftWrite,
    ) -> DraftRead:
        task = self._require_student_task(student, task_id)
        self._require_unlocked(student, task)
        draft = self._get_or_create_draft(student.id, task.id)
        draft.answer = payload.answer
        draft.code = payload.code
        draft.circuit = payload.circuit
        self._learning_event(
            student,
            task,
            LearningEventType.DRAFT_SAVE,
            {},
        )
        self._audit(student, "draft.saved", "task", task.id)
        self._commit()
        self.session.refresh(draft)
        return DraftRead.model_validate(draft)

    def get_draft(self, student: User, task_id: str) -> DraftRead | None:
        task = self._require_student_task(student, task_id)
        draft = self.session.scalar(
            select(SubmissionDraft).where(
                SubmissionDraft.student_id == student.id,
                SubmissionDraft.task_id == task.id,
            )
        )
        return DraftRead.model_validate(draft) if draft is not None else None

    def submit(
        self,
        student: User,
        task_id: str,
        payload: SubmissionCreate,
    ) -> AttemptRead:
        self._acquire_submission_sequence_lock(student.id)
        task = self._require_student_task(student, task_id)
        self._require_unlocked(student, task)
        assessment_submissions = AssessmentSubmissionService(self.session)
        frozen_versions = assessment_submissions.frozen_versions_for_task(task)
        payload_digest = self._submission_digest(payload)
        if payload.idempotency_key:
            existing = self.session.scalar(
                select(SubmissionAttempt).where(
                    SubmissionAttempt.student_id == student.id,
                    SubmissionAttempt.task_id == task.id,
                    SubmissionAttempt.idempotency_key == payload.idempotency_key,
                )
            )
            if existing is not None:
                if existing.content_digest == payload_digest:
                    return self._attempt_read(existing)
                raise _conflict("This idempotency key was already used for different content")
        previous = list(
            self.session.scalars(
                select(SubmissionAttempt)
                .where(
                    SubmissionAttempt.student_id == student.id,
                    SubmissionAttempt.task_id == task.id,
                )
                .order_by(SubmissionAttempt.attempt_number)
            ).all()
        )
        criteria = task.marking_criteria if isinstance(task.marking_criteria, dict) else {}
        if previous and criteria.get("allow_resubmission") is False:
            raise _conflict("This task does not permit resubmission")
        draft = self._get_or_create_draft(student.id, task.id)
        draft.answer = payload.answer
        draft.code = payload.code
        draft.circuit = payload.circuit
        score, _ = self._grade(task, payload) if frozen_versions is None else (None, "")
        passing_score = int(self._setting_value("passing_score"))
        attempt_id = self._uuid()
        submission_idempotency_key = payload.idempotency_key or f"submission:{attempt_id}"
        attempt = SubmissionAttempt(
            id=attempt_id,
            draft_id=draft.id,
            student_id=student.id,
            task_id=task.id,
            attempt_number=len(previous) + 1,
            status=(
                AttemptStatus.COMPLETED
                if score is not None and score >= passing_score
                else AttemptStatus.SUBMITTED
            ),
            answer=payload.answer,
            code=payload.code,
            circuit=payload.circuit,
            score=score,
            feedback="Submission recorded. Validated feedback is being prepared.",
            feedback_reference=attempt_id,
            task_form_version_id=(
                frozen_versions.task_form_version_id if frozen_versions else None
            ),
            response_schema_version=("assessment.response.v1" if frozen_versions else None),
            content_digest=payload_digest,
            idempotency_key=submission_idempotency_key,
            declared_conditions=(
                self._declared_conditions(task, frozen_versions) if frozen_versions else None
            ),
        )
        self.session.add(attempt)
        self.session.flush()
        if frozen_versions is not None:
            assessment_submissions.create_attempt(
                task=task,
                student_id=student.id,
                response=attempt,
                versions=frozen_versions,
            )
        self.session.add(
            WorkflowRun(
                id=self._uuid(),
                submission_id=attempt.id,
                current_stage=WorkflowStage.PENDING,
                regeneration_count=0,
                started_at=attempt.submitted_at,
                lease_expires_at=None,
                execution_token=None,
                execution_attempt_count=0,
                course_id=task.course_id,
                task_id=task.id,
            )
        )
        points_awarded = 0
        if attempt.status is AttemptStatus.COMPLETED:
            reward = self.gamification.award_completion(
                self._require_profile(student),
                task,
                attempt,
            )
            points_awarded = reward.points_awarded
        self._audit(
            student,
            "submission.created",
            "submission_attempt",
            attempt.id,
            {"task_id": task.id, "attempt_number": attempt.attempt_number},
        )
        correlation_id = self._uuid()
        self._learning_event(
            student,
            task,
            LearningEventType.SUBMISSION,
            {
                "attempt_number": attempt.attempt_number,
                "score": float(score) if score is not None else None,
            },
            correlation_id=correlation_id,
        )
        if attempt.status is AttemptStatus.COMPLETED:
            self._learning_event(
                student,
                task,
                LearningEventType.COMPLETION,
                {"completion_status": "passed", "score": float(score)},
                correlation_id=correlation_id,
            )
            self._audit(
                student,
                "progress.updated",
                "task",
                task.id,
                {"attempt_id": attempt.id},
            )
        student_tasks = self._student_tasks(student)
        self._persist_recommendations(
            student.id,
            self._calculate_recommendations(
                student,
                student_tasks,
                [self._task_read(item, student) for item in student_tasks],
            ),
        )
        self._commit()
        return self._attempt_read(attempt, points_awarded)

    def list_attempts(self, student: User, task_id: str) -> list[AttemptRead]:
        self._require_student_task(student, task_id)
        attempts = list(
            self.session.scalars(
                select(SubmissionAttempt)
                .where(
                    SubmissionAttempt.student_id == student.id,
                    SubmissionAttempt.task_id == task_id,
                )
                .order_by(SubmissionAttempt.attempt_number.desc())
            ).all()
        )
        return [self._attempt_read(attempt) for attempt in attempts]

    def mark_assessment_fault(self, response_version_id: str, reason: str) -> None:
        if AssessmentSubmissionService(self.session).mark_fault_for_response(
            response_version_id, reason
        ):
            self._commit()

    def student_dashboard(self, student: User) -> StudentDashboardRead:
        profile = self._require_profile(student)
        self._create_overdue_reminders(student)
        tasks = self._student_tasks(student)
        task_reads = [self._task_read(task, student) for task in tasks]
        completed = [task for task in task_reads if task.access_status == "completed"]
        latest_scores = [task.latest_score for task in task_reads if task.latest_score is not None]
        course_rows = self.list_courses(student)
        course_progress = []
        for course in course_rows:
            course_tasks = [task for task in task_reads if task.course_id == course.id]
            done = sum(task.access_status == "completed" for task in course_tasks)
            course_progress.append(
                CourseProgressRead(
                    id=course.id,
                    code=course.code,
                    title=course.title,
                    description=course.description,
                    state=course.state,
                    progress_percentage=round(done / len(course_tasks) * 100)
                    if course_tasks
                    else 0,
                )
            )
        points_per_level = int(self._setting_value("points_per_level"))
        calculated_recommendations = self._calculate_recommendations(
            student,
            tasks,
            task_reads,
        )
        self._persist_recommendations(student.id, calculated_recommendations)
        self._commit()
        recommendations = self._stored_recommendations(student.id)
        reminders = list(
            self.session.scalars(
                select(Reminder)
                .where(Reminder.student_id == student.id)
                .order_by(Reminder.created_at.desc())
                .limit(20)
            ).all()
        )
        achievements = self._achievement_reads(profile)
        return StudentDashboardRead(
            student=StudentIdentityRead(
                id=profile.id,
                user_id=student.id,
                display_name=profile.display_name,
            ),
            summary=StudentSummaryRead(
                completed_tasks=len(completed),
                total_tasks=len(task_reads),
                completion_percentage=round(len(completed) / len(task_reads) * 100)
                if task_reads
                else 0,
                average_score=round(sum(latest_scores) / len(latest_scores))
                if latest_scores
                else 0,
                points=profile.points,
                level=self.gamification.level(profile.points, points_per_level),
                next_level_points=points_per_level - profile.points % points_per_level,
            ),
            courses=course_progress,
            tasks=task_reads,
            recommendations=recommendations,
            reminders=[ReminderRead.model_validate(reminder) for reminder in reminders],
            achievements=achievements,
        )

    def _calculate_recommendations(
        self,
        student: User,
        tasks: list[LearningTask],
        task_reads: list[TaskRead],
    ) -> list[RecommendationRead]:
        reads_by_id = {task.id: task for task in task_reads}
        recommendations: list[RecommendationRead] = []
        recommended_ids: set[str] = set()

        first_locked = next(
            (task for task in task_reads if task.access_status == "locked"),
            None,
        )
        if first_locked is not None:
            missing = next(
                (
                    reads_by_id[task_id]
                    for task_id in first_locked.prerequisite_task_ids
                    if task_id in reads_by_id and reads_by_id[task_id].access_status != "completed"
                ),
                None,
            )
            if missing is not None:
                recommendations.append(
                    RecommendationRead(
                        task_id=missing.id,
                        title=missing.title,
                        reason=(f"Complete this prerequisite to unlock “{first_locked.title}”."),
                        priority="high",
                        updated_at=datetime.now(UTC),
                    )
                )
                recommended_ids.add(missing.id)

        latest = self._latest_attempts(student.id, [task.id for task in tasks])
        outcome_scores: dict[str, list[int]] = defaultdict(list)
        for task in tasks:
            attempt = latest.get(task.id)
            if attempt is not None and attempt.score is not None and task.learning_outcome_id:
                outcome_scores[task.learning_outcome_id].append(attempt.score)
        if outcome_scores:
            lowest_outcome_id, scores = min(
                outcome_scores.items(),
                key=lambda item: sum(item[1]) / len(item[1]),
            )
            outcome = self.session.get(LearningOutcome, lowest_outcome_id)
            candidate = next(
                (
                    read
                    for read in task_reads
                    if read.learning_outcome_id == lowest_outcome_id
                    and read.access_status in {"available", "in_progress"}
                    and read.id not in recommended_ids
                ),
                None,
            )
            if candidate is not None:
                average = round(sum(scores) / len(scores))
                recommendations.append(
                    RecommendationRead(
                        task_id=candidate.id,
                        title=candidate.title,
                        reason=(
                            f"Your {average}% average for "
                            f"“{outcome.title if outcome else 'this outcome'}” "
                            "is your lowest-performing learning outcome."
                        ),
                        priority="high" if not recommendations else "medium",
                        updated_at=datetime.now(UTC),
                    )
                )
                recommended_ids.add(candidate.id)

        for task in task_reads:
            if (
                len(recommendations) >= 3
                or task.id in recommended_ids
                or task.access_status not in {"available", "in_progress"}
            ):
                continue
            recommendations.append(
                RecommendationRead(
                    task_id=task.id,
                    title=task.title,
                    reason=(
                        "Continue your saved work."
                        if task.access_status == "in_progress"
                        else "This is the next unlocked task in your pathway."
                    ),
                    priority=("high", "medium", "low")[len(recommendations)],
                    updated_at=datetime.now(UTC),
                )
            )
        return recommendations

    def _persist_recommendations(
        self,
        student_id: int,
        recommendations: list[RecommendationRead],
    ) -> None:
        existing = {
            recommendation.task_id: recommendation
            for recommendation in self.session.scalars(
                select(Recommendation).where(Recommendation.student_id == student_id)
            ).all()
        }
        active_ids: set[str] = set()
        for rank, recommendation in enumerate(recommendations, start=1):
            active_ids.add(recommendation.task_id)
            record = existing.get(recommendation.task_id)
            if record is None:
                record = Recommendation(
                    student_id=student_id,
                    task_id=recommendation.task_id,
                    reason=recommendation.reason,
                    priority=recommendation.priority,
                    rank=rank,
                )
                self.session.add(record)
            else:
                record.reason = recommendation.reason
                record.priority = recommendation.priority
                record.rank = rank
                record.is_active = True
                record.updated_at = datetime.now(UTC)
        for task_id, record in existing.items():
            if task_id not in active_ids:
                record.is_active = False
                record.updated_at = datetime.now(UTC)

    def _stored_recommendations(self, student_id: int) -> list[RecommendationRead]:
        rows = self.session.execute(
            select(Recommendation, LearningTask)
            .join(LearningTask, LearningTask.id == Recommendation.task_id)
            .where(
                Recommendation.student_id == student_id,
                Recommendation.is_active.is_(True),
            )
            .order_by(Recommendation.rank)
        ).all()
        return [
            RecommendationRead(
                task_id=recommendation.task_id,
                title=task.title,
                reason=recommendation.reason,
                priority=recommendation.priority,
                updated_at=recommendation.updated_at,
            )
            for recommendation, task in rows
        ]

    def mark_reminder_read(self, student: User, reminder_id: str) -> ReminderRead:
        reminder = self.session.get(Reminder, reminder_id)
        if reminder is None or reminder.student_id != student.id:
            raise _not_found("Reminder")
        reminder.is_read = True
        self._commit()
        return ReminderRead.model_validate(reminder)

    def educator_students(
        self,
        educator: User,
        course_id: str | None = None,
    ) -> list[EducatorStudentRead]:
        courses = self._educator_courses(educator, course_id)
        threshold = int(self._setting_value("at_risk_threshold"))
        now = datetime.now(UTC)
        result: list[EducatorStudentRead] = []
        for course in courses:
            tasks = list(
                self.session.scalars(
                    select(LearningTask).where(LearningTask.course_id == course.id)
                ).all()
            )
            enrollments = self.session.execute(
                select(Enrollment, User, StudentProfile)
                .join(User, User.id == Enrollment.student_id)
                .join(StudentProfile, StudentProfile.user_id == User.id)
                .where(
                    Enrollment.course_id == course.id,
                    Enrollment.status == EnrollmentStatus.ACTIVE,
                )
                .order_by(User.full_name)
            ).all()
            for _, student, profile in enrollments:
                attempts = self._latest_attempts(student.id, [task.id for task in tasks])
                completed_ids = {
                    attempt.task_id
                    for attempt in attempts.values()
                    if attempt.status is AttemptStatus.COMPLETED
                }
                scores = [attempt.score for attempt in attempts.values() if attempt.score is not None]
                overdue = sum(
                    task.id not in completed_ids
                    and task.due_at is not None
                    and _aware(task.due_at) < now
                    for task in tasks
                )
                average = round(sum(scores) / len(scores)) if scores else 0
                result.append(
                    EducatorStudentRead(
                        student_id=profile.id,
                        user_id=student.id,
                        display_name=student.full_name,
                        email=student.email,
                        course_id=course.id,
                        course_title=course.title,
                        completed_tasks=len(completed_ids),
                        total_tasks=len(tasks),
                        completion_percentage=(
                            round(len(completed_ids) / len(tasks) * 100) if tasks else 0
                        ),
                        average_score=average,
                        last_active=max(
                            (attempt.submitted_at for attempt in attempts.values()),
                            default=None,
                        ),
                        at_risk=bool(attempts) and (average < threshold or overdue > 0),
                        overdue_tasks=overdue,
                    )
                )
        return result

    def educator_dashboard(self, educator: User) -> EducatorDashboardRead:
        courses = self._educator_courses(educator)
        course_reads = [self._course_read(course) for course in courses]
        students = self.educator_students(educator)
        unique_students = {student.student_id for student in students}
        total_tasks = sum(student.total_tasks for student in students)
        completed_tasks = sum(student.completed_tasks for student in students)
        task_ids = (
            list(
                self.session.scalars(
                    select(LearningTask.id).where(
                        LearningTask.course_id.in_([course.id for course in courses])
                    )
                ).all()
            )
            if courses
            else []
        )
        attempts = (
            list(
                self.session.scalars(
                    select(SubmissionAttempt)
                    .where(SubmissionAttempt.task_id.in_(task_ids))
                    .order_by(SubmissionAttempt.submitted_at.desc())
                ).all()
            )
            if task_ids
            else []
        )
        tasks = (
            {
                task.id: task
                for task in self.session.scalars(
                    select(LearningTask).where(LearningTask.id.in_(task_ids))
                ).all()
            }
            if task_ids
            else {}
        )
        users = (
            {
                user.id: user
                for user in self.session.scalars(
                    select(User).where(User.id.in_({attempt.student_id for attempt in attempts}))
                ).all()
            }
            if attempts
            else {}
        )
        today = datetime.now(UTC).date()
        weekly: list[WeeklyEngagementRead] = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            day_attempts = [
                attempt for attempt in attempts if _aware(attempt.submitted_at).date() == day
            ]
            weekly.append(
                WeeklyEngagementRead(
                    label=day.strftime("%a"),
                    active_students=len({attempt.student_id for attempt in day_attempts}),
                    submissions=len(day_attempts),
                )
            )
        by_type: dict[str, list[int]] = defaultdict(list)
        by_outcome: dict[str, list[int]] = defaultdict(list)
        for attempt in attempts:
            task = tasks.get(attempt.task_id)
            if task is None:
                continue
            if attempt.score is not None:
                by_type[task.task_type.value].append(attempt.score)
            if attempt.score is not None and task.learning_outcome_id:
                by_outcome[task.learning_outcome_id].append(attempt.score)
        outcomes = (
            {
                outcome.id: outcome.title
                for outcome in self.session.scalars(
                    select(LearningOutcome).where(LearningOutcome.id.in_(by_outcome))
                ).all()
            }
            if by_outcome
            else {}
        )
        profiles = (
            {
                profile.user_id: profile
                for profile in self.session.scalars(
                    select(StudentProfile).where(
                        StudentProfile.user_id.in_({student.user_id for student in students})
                    )
                ).all()
            }
            if students
            else {}
        )
        completed_by_profile: dict[str, int] = defaultdict(int)
        for row in students:
            completed_by_profile[row.student_id] += row.completed_tasks
        leaderboard = sorted(
            (
                LeaderboardEntryRead(
                    student_id=row.student_id,
                    display_name=row.display_name,
                    points=profiles[row.user_id].points if row.user_id in profiles else 0,
                    completed_tasks=completed_by_profile[row.student_id],
                )
                for row in {item.student_id: item for item in students}.values()
            ),
            key=lambda entry: (-entry.points, -entry.completed_tasks, entry.display_name),
        )
        return EducatorDashboardRead(
            courses=course_reads,
            total_students=len(unique_students),
            at_risk_students=len({row.student_id for row in students if row.at_risk}),
            completion_percentage=round(completed_tasks / total_tasks * 100) if total_tasks else 0,
            weekly_engagement=weekly,
            task_type_performance=[
                LabelScoreRead(
                    label=task_type.replace("_", " ").title(),
                    score=round(sum(scores) / len(scores)),
                )
                for task_type, scores in sorted(by_type.items())
            ],
            concept_mastery=[
                LabelScoreRead(
                    label=outcomes.get(outcome_id, "Learning outcome"),
                    score=round(sum(scores) / len(scores)),
                )
                for outcome_id, scores in by_outcome.items()
            ],
            leaderboard=leaderboard,
            recent_activity=[
                RecentActivityRead(
                    student_name=users[attempt.student_id].full_name,
                    task_title=tasks[attempt.task_id].title,
                    score=attempt.score,
                    occurred_at=attempt.submitted_at,
                )
                for attempt in attempts[:10]
                if attempt.student_id in users and attempt.task_id in tasks
            ],
        )

    def send_bulk_reminders(
        self,
        educator: User,
        payload: BulkReminderCreate,
    ) -> list[ReminderRead]:
        task = self._get_task(payload.task_id) if payload.task_id else None
        if task is not None:
            course = self._require_course_owner(educator, task.course_id or "")
            courses = [course]
        else:
            courses = self._educator_courses(educator)
            if not courses:
                raise _unprocessable("The educator has no courses")
        profiles = list(
            self.session.scalars(
                select(StudentProfile).where(StudentProfile.id.in_(payload.student_ids))
            ).all()
        )
        if len(profiles) != len(set(payload.student_ids)):
            raise _unprocessable("One or more student_ids are invalid")
        course_ids = [course.id for course in courses]
        enrolled_ids = set(
            self.session.scalars(
                select(Enrollment.student_id).where(
                    Enrollment.course_id.in_(course_ids),
                    Enrollment.status == EnrollmentStatus.ACTIVE,
                )
            ).all()
        )
        if any(profile.user_id not in enrolled_ids for profile in profiles):
            raise _forbidden()
        reminders: list[Reminder] = []
        for profile in profiles:
            if profile.user_id is None:
                continue
            selected_task = task or self._next_incomplete_task(
                profile.user_id,
                course_ids,
            )
            if selected_task is None:
                continue
            reminder = self._create_reminder(
                profile.user_id,
                selected_task,
                payload.message,
                title=f"Reminder: {selected_task.title}",
            )
            if reminder is not None:
                reminders.append(reminder)
        self._audit(
            educator,
            "reminder.bulk_created",
            "educator",
            str(educator.id),
            {"created_count": len(reminders)},
        )
        self._commit()
        return [ReminderRead.model_validate(reminder) for reminder in reminders]

    def list_materials(self, actor: User, course_id: str) -> list[LearningMaterial]:
        self._require_course_read(actor, course_id)
        return list(
            self.session.scalars(
                select(LearningMaterial)
                .where(LearningMaterial.course_id == course_id)
                .order_by(LearningMaterial.created_at.desc())
            ).all()
        )

    def get_material_for_actor(
        self,
        actor: User,
        course_id: str,
        material_id: str,
    ) -> LearningMaterial:
        self._require_course_read(actor, course_id)
        material = self.session.scalar(
            select(LearningMaterial).where(
                LearningMaterial.id == material_id,
                LearningMaterial.course_id == course_id,
            )
        )
        if material is None:
            raise _not_found("Learning material")
        return material

    def register_material_link(
        self,
        educator: User,
        course_id: str,
        payload: MaterialLinkCreate,
    ) -> LearningMaterial:
        course = self._require_course_owner(educator, course_id)
        self._require_not_archived(course)
        if payload.module_id is not None:
            module = self._get_module(payload.module_id)
            if module.course_id != course.id:
                raise _unprocessable("module_id is outside this course")
        source_url = str(payload.source_url)
        extension = Path(urlparse(source_url).path).suffix.casefold()
        mime_types = {
            ".pdf": "application/pdf",
            ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        }
        content_hash = f"url:{hashlib.sha256(source_url.encode()).hexdigest()}"
        if self.session.scalar(
            select(LearningMaterial).where(
                LearningMaterial.course_id == course.id,
                LearningMaterial.content_hash == content_hash,
            )
        ):
            raise _conflict("This material is already linked to the course")
        material = LearningMaterial(
            course_id=course.id,
            module_id=payload.module_id,
            source_url=source_url,
            mime_type=mime_types.get(extension, "text/html"),
            content_hash=content_hash,
            indexing_status=MaterialIndexStatus.PENDING,
        )
        self.session.add(material)
        self.session.flush()
        self._audit(educator, "material.linked", "learning_material", material.id)
        self._commit()
        return material

    def upload_material(
        self,
        educator: User,
        course_id: str,
        module_id: str | None,
        filename: str | None,
        source: Any,
        storage: FileStorage,
    ) -> LearningMaterial:
        course = self._require_course_owner(educator, course_id)
        self._require_not_archived(course)
        if module_id is not None:
            module = self._get_module(module_id)
            if module.course_id != course.id:
                raise _unprocessable("module_id is outside this course")
        if Path(filename or "").suffix.casefold() not in {".pdf", ".docx", ".pptx"}:
            raise _unprocessable("Uploads must be PDF, DOCX, or PPTX")
        staged = storage.stage_upload(filename, source)
        duplicate = self.session.scalar(
            select(LearningMaterial).where(
                LearningMaterial.course_id == course.id,
                LearningMaterial.content_hash == staged.content_hash,
            )
        )
        if duplicate is not None:
            staged.temporary_path.unlink(missing_ok=True)
            raise _conflict("This material is already attached to the course")
        material = LearningMaterial(
            course_id=course.id,
            module_id=module_id,
            original_filename=filename or f"source{staged.safe_extension}",
            mime_type=staged.mime_type,
            content_hash=staged.content_hash,
            indexing_status=MaterialIndexStatus.PENDING,
            file_size_bytes=staged.file_size_bytes,
        )
        try:
            self.session.add(material)
            self.session.flush()
            material.storage_key = storage.commit(staged, material.id)
            self._audit(educator, "material.uploaded", "learning_material", material.id)
            self._commit()
            return material
        except Exception:
            staged.temporary_path.unlink(missing_ok=True)
            self.session.rollback()
            raise

    def list_users(self) -> list[AdminUserRead]:
        return [
            self._admin_user_read(user)
            for user in self.session.scalars(select(User).order_by(User.full_name)).all()
        ]

    def create_user(
        self,
        administrator: User,
        payload: AdminUserCreate,
    ) -> AdminUserRead:
        email = normalize_email(str(payload.email))
        if self.session.scalar(select(User).where(User.email == email)):
            raise _conflict("An account with this email already exists")
        user = User(
            email=email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
            role=payload.role,
        )
        self.session.add(user)
        self.session.flush()
        if user.role is UserRole.STUDENT:
            self.session.add(StudentProfile(user_id=user.id, display_name=user.full_name))
        self._audit(administrator, "account.created", "user", str(user.id))
        self._commit()
        return self._admin_user_read(user)

    def update_user(
        self,
        administrator: User,
        user_id: int,
        payload: AdminUserUpdate,
    ) -> AdminUserRead:
        user = self._get_user(user_id)
        values = payload.model_dump(exclude_unset=True)
        if "email" in values:
            values["email"] = normalize_email(str(values["email"]))
            duplicate = self.session.scalar(
                select(User).where(User.email == values["email"], User.id != user.id)
            )
            if duplicate:
                raise _conflict("An account with this email already exists")
        for name, value in values.items():
            setattr(user, name, value)
        profile = self.session.scalar(
            select(StudentProfile).where(StudentProfile.user_id == user.id)
        )
        if user.role is UserRole.STUDENT and profile is None:
            profile = StudentProfile(user_id=user.id, display_name=user.full_name)
            self.session.add(profile)
        elif profile is not None and "full_name" in values:
            profile.display_name = user.full_name
        self._audit(administrator, "account.updated", "user", str(user.id))
        self._commit()
        return self._admin_user_read(user)

    def set_user_active(
        self,
        administrator: User,
        user_id: int,
        active: bool,
    ) -> AdminUserRead:
        user = self._get_user(user_id)
        if user.id == administrator.id and not active:
            raise _conflict("Administrators cannot deactivate their own account")
        user.is_active = active
        action = "account.reactivated" if active else "account.deactivated"
        self._audit(administrator, action, "user", str(user.id))
        self._commit()
        return self._admin_user_read(user)

    def read_settings(self) -> SettingsRead:
        return SettingsRead(**{key: self._setting_value(key) for key in DEFAULT_SETTINGS})

    def update_settings(
        self,
        administrator: User,
        payload: SettingsUpdate,
    ) -> SettingsRead:
        for key, value in payload.model_dump(exclude_unset=True).items():
            setting = self.session.scalar(select(SystemSetting).where(SystemSetting.key == key))
            if setting is None:
                setting = SystemSetting(
                    key=key,
                    value=value,
                    description=DEFAULT_SETTINGS[key][1],
                )
                self.session.add(setting)
            else:
                setting.value = value
            setting.updated_by = administrator.id
            self._audit(administrator, "setting.updated", "system_setting", key)
        self._commit()
        return self.read_settings()

    def _require_course_read(self, actor: User, course_id: str) -> Course:
        course = self._get_course(course_id)
        if actor.role is UserRole.ADMINISTRATOR:
            return course
        if actor.role is UserRole.EDUCATOR and course.educator_id == actor.id:
            return course
        if actor.role is UserRole.STUDENT and course.state is CourseState.PUBLISHED:
            enrollment = self.session.scalar(
                select(Enrollment.id).where(
                    Enrollment.course_id == course.id,
                    Enrollment.student_id == actor.id,
                    Enrollment.status == EnrollmentStatus.ACTIVE,
                )
            )
            if enrollment:
                return course
        raise _forbidden()

    def _require_course_owner(self, educator: User, course_id: str) -> Course:
        course = self._get_course(course_id)
        if educator.role is not UserRole.EDUCATOR or course.educator_id != educator.id:
            raise _forbidden()
        return course

    def _educator_courses(
        self,
        educator: User,
        course_id: str | None = None,
    ) -> list[Course]:
        statement = select(Course).where(Course.educator_id == educator.id)
        if course_id is not None:
            statement = statement.where(Course.id == course_id)
        courses = list(self.session.scalars(statement.order_by(Course.created_at.desc())).all())
        if course_id is not None and not courses:
            if self.session.get(Course, course_id):
                raise _forbidden()
            raise _not_found("Course")
        return courses

    def _get_course(self, course_id: str) -> Course:
        course = self.session.get(Course, course_id)
        if course is None:
            raise _not_found("Course")
        return course

    def _get_module(self, module_id: str) -> CourseModule:
        module = self.session.get(CourseModule, module_id)
        if module is None:
            raise _not_found("Module")
        return module

    def _get_outcome(self, outcome_id: str) -> LearningOutcome:
        outcome = self.session.get(LearningOutcome, outcome_id)
        if outcome is None:
            raise _not_found("Learning outcome")
        return outcome

    def _get_task(self, task_id: str) -> LearningTask:
        task = self.session.get(LearningTask, task_id)
        if task is None:
            raise _not_found("Task")
        return task

    def _get_user(self, user_id: int) -> User:
        user = self.session.get(User, user_id)
        if user is None:
            raise _not_found("User")
        return user

    def _require_profile(self, student: User) -> StudentProfile:
        profile = self.session.scalar(
            select(StudentProfile).where(StudentProfile.user_id == student.id)
        )
        if profile is None:
            raise _conflict("Student profile setup is incomplete")
        return profile

    def _require_student_task(self, student: User, task_id: str) -> LearningTask:
        task = self._get_task(task_id)
        if not task.course_id:
            raise _not_found("Task")
        self._require_course_read(student, task.course_id)
        return task

    def _require_unlocked(self, student: User, task: LearningTask) -> None:
        completed = set(
            self.session.scalars(
                select(SubmissionAttempt.task_id)
                .where(
                    SubmissionAttempt.student_id == student.id,
                    SubmissionAttempt.status == AttemptStatus.COMPLETED,
                )
                .distinct()
            ).all()
        )
        missing = set(task.prerequisite_task_ids or []) - completed
        if missing:
            raise LmsServiceError(
                423,
                "Complete the prerequisite tasks before attempting this task",
            )

    def _student_tasks(self, student: User) -> list[LearningTask]:
        course_ids = list(
            self.session.scalars(
                select(Enrollment.course_id)
                .join(Course, Course.id == Enrollment.course_id)
                .where(
                    Enrollment.student_id == student.id,
                    Enrollment.status == EnrollmentStatus.ACTIVE,
                    Course.state == CourseState.PUBLISHED,
                )
            ).all()
        )
        if not course_ids:
            return []
        return list(
            self.session.scalars(
                select(LearningTask)
                .where(LearningTask.course_id.in_(course_ids))
                .order_by(LearningTask.position)
            ).all()
        )

    def _get_or_create_draft(self, student_id: int, task_id: str) -> SubmissionDraft:
        draft = self.session.scalar(
            select(SubmissionDraft).where(
                SubmissionDraft.student_id == student_id,
                SubmissionDraft.task_id == task_id,
            )
        )
        if draft is None:
            draft = SubmissionDraft(
                id=self._uuid(),
                student_id=student_id,
                task_id=task_id,
            )
            self.session.add(draft)
            self.session.flush()
        return draft

    def _task_read(self, task: LearningTask, student: User | None = None) -> TaskRead:
        criteria = task.marking_criteria if isinstance(task.marking_criteria, dict) else {}
        choices: list[TaskChoice] = []
        for index, value in enumerate(criteria.get("choices", [])):
            if isinstance(value, dict):
                choices.append(
                    TaskChoice(
                        id=str(value.get("id", index)),
                        text=str(value.get("text", "")),
                    )
                )
            else:
                choices.append(TaskChoice(id=str(index), text=str(value)))
        latest: SubmissionAttempt | None = None
        attempt_count = 0
        access_status = "available"
        if student is not None:
            attempts = list(
                self.session.scalars(
                    select(SubmissionAttempt)
                    .where(
                        SubmissionAttempt.student_id == student.id,
                        SubmissionAttempt.task_id == task.id,
                    )
                    .order_by(SubmissionAttempt.attempt_number.desc())
                ).all()
            )
            latest = attempts[0] if attempts else None
            attempt_count = len(attempts)
            completed_ids = set(
                self.session.scalars(
                    select(SubmissionAttempt.task_id)
                    .where(
                        SubmissionAttempt.student_id == student.id,
                        SubmissionAttempt.status == AttemptStatus.COMPLETED,
                    )
                    .distinct()
                ).all()
            )
            if task.id in completed_ids:
                access_status = "completed"
            elif set(task.prerequisite_task_ids or []) - completed_ids:
                access_status = "locked"
            elif attempts or self.session.scalar(
                select(SubmissionDraft.id).where(
                    SubmissionDraft.student_id == student.id,
                    SubmissionDraft.task_id == task.id,
                )
            ):
                access_status = "in_progress"
        if not task.course_id or not task.module_id or not task.learning_outcome_id:
            raise _not_found("Task")
        assessment = AssessmentSubmissionService(self.session).declaration_for_task(task)
        return TaskRead(
            id=task.id,
            title=task.title,
            prompt=task.description,
            instructions=task.instructions,
            task_type=task.task_type,
            difficulty=task.difficulty.casefold(),
            points=task.points,
            position=task.position,
            starter_code=task.starter_code,
            due_at=task.due_at,
            course_id=task.course_id,
            module_id=task.module_id,
            module_title=task.module,
            learning_outcome_id=task.learning_outcome_id,
            source_references=list(task.source_references or []),
            prerequisite_task_ids=list(task.prerequisite_task_ids or []),
            choices=choices,
            starter_circuit=criteria.get("starter_circuit"),
            access_status=access_status,
            attempt_count=attempt_count,
            latest_score=latest.score if latest else None,
            latest_attempt=LatestAttemptSummary.model_validate(latest) if latest else None,
            assessment=self._assessment_conditions_read(assessment),
        )

    @staticmethod
    def _assessment_conditions_read(
        declaration: AssessmentTaskDeclaration | None,
    ) -> AssessmentConditionsRead | None:
        if declaration is None:
            return None
        return AssessmentConditionsRead(
            purpose=declaration.purpose,
            bloom_process=declaration.bloom_process,
            knowledge_dimension=declaration.knowledge_dimension,
            claim=declaration.claim,
            criteria=[
                AssessmentTaskCriterionRead(description=description, mandatory=mandatory)
                for description, mandatory in declaration.criteria
            ],
            task_conditions=declaration.task_conditions,
            permitted_tools=declaration.permitted_tools,
            instructional_support=declaration.instructional_support,
            access_conditions=declaration.access_conditions,
            transfer_rule=declaration.transfer_rule,
            review_rule=(
                "A formal result remains subject to assessor confirmation, correction, or override."
            ),
        )

    def _grade(
        self,
        task: LearningTask,
        payload: SubmissionCreate,
    ) -> tuple[int, str]:
        try:
            correct = self.task_types.is_correct(task.task_type, task, payload)
        except (InvalidTaskSubmissionError, UnsupportedTaskTypeError) as error:
            raise _unprocessable(str(error)) from error
        if correct:
            return 100, "Correct. You can continue to the next unlocked task."
        return (
            40,
            "Review the learning outcome, correct the highlighted concept, and try again.",
        )

    @staticmethod
    def _submission_digest(payload: SubmissionCreate) -> str:
        canonical = json.dumps(
            {"answer": payload.answer, "code": payload.code, "circuit": payload.circuit},
            sort_keys=True,
            separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _declared_conditions(
        task: LearningTask,
        versions: FrozenAssessmentVersions,
    ) -> dict[str, Any]:
        return {
            "course_id": task.course_id,
            "task_form_version_id": versions.task_form_version_id,
            "response_schema_version": "assessment.response.v1",
        }

    def _attempt_read(
        self,
        attempt: SubmissionAttempt,
        points_awarded: int | None = None,
    ) -> AttemptRead:
        if points_awarded is None:
            award = self.session.scalar(
                select(TaskPointAward).where(TaskPointAward.attempt_id == attempt.id)
            )
            points_awarded = award.points if award else 0
        return AttemptRead(
            id=attempt.id,
            task_id=attempt.task_id,
            attempt_number=attempt.attempt_number,
            status=attempt.status,
            score=attempt.score,
            answer=attempt.answer,
            code=attempt.code,
            circuit=attempt.circuit,
            feedback=attempt.feedback,
            feedback_reference=attempt.feedback_reference,
            points_awarded=points_awarded,
            submitted_at=attempt.submitted_at,
        )

    def _latest_attempts(
        self,
        student_id: int,
        task_ids: list[str],
    ) -> dict[str, SubmissionAttempt]:
        if not task_ids:
            return {}
        attempts = self.session.scalars(
            select(SubmissionAttempt)
            .where(
                SubmissionAttempt.student_id == student_id,
                SubmissionAttempt.task_id.in_(task_ids),
            )
            .order_by(
                SubmissionAttempt.task_id,
                SubmissionAttempt.attempt_number.desc(),
            )
        ).all()
        result: dict[str, SubmissionAttempt] = {}
        for attempt in attempts:
            result.setdefault(attempt.task_id, attempt)
        return result

    def _create_overdue_reminders(self, student: User) -> None:
        if not bool(self._setting_value("reminders_enabled")):
            return
        now = datetime.now(UTC)
        completed_ids = set(
            self.session.scalars(
                select(SubmissionAttempt.task_id)
                .where(
                    SubmissionAttempt.student_id == student.id,
                    SubmissionAttempt.status == AttemptStatus.COMPLETED,
                )
                .distinct()
            ).all()
        )
        created = False
        for task in self._student_tasks(student):
            if (
                task.id in completed_ids
                or task.due_at is None
                or _aware(task.due_at) > now - timedelta(hours=24)
            ):
                continue
            reminder = self._create_reminder(
                student.id,
                task,
                f"{task.title} is overdue. Resume it when you are ready.",
                title=f"Overdue: {task.title}",
            )
            created = created or reminder is not None
        if created:
            self._commit()

    def _create_reminder(
        self,
        student_id: int,
        task: LearningTask,
        message: str,
        *,
        title: str,
    ) -> Reminder | None:
        if not bool(self._setting_value("reminders_enabled")):
            return None
        now = datetime.now(UTC)
        existing = self.session.scalar(
            select(Reminder).where(
                Reminder.student_id == student_id,
                Reminder.task_id == task.id,
                Reminder.created_at >= now - timedelta(hours=24),
            )
        )
        if existing:
            return None
        reminder = Reminder(
            student_id=student_id,
            task_id=task.id,
            title=title,
            message=message,
            dedupe_window=str(int(now.timestamp() // (24 * 60 * 60))),
            created_at=now,
        )
        self.session.add(reminder)
        return reminder

    def _next_incomplete_task(
        self,
        student_id: int,
        course_ids: list[str],
    ) -> LearningTask | None:
        enrolled_course_ids = list(
            self.session.scalars(
                select(Enrollment.course_id).where(
                    Enrollment.student_id == student_id,
                    Enrollment.course_id.in_(course_ids),
                    Enrollment.status == EnrollmentStatus.ACTIVE,
                )
            ).all()
        )
        if not enrolled_course_ids:
            return None
        completed_ids = set(
            self.session.scalars(
                select(SubmissionAttempt.task_id)
                .where(
                    SubmissionAttempt.student_id == student_id,
                    SubmissionAttempt.status == AttemptStatus.COMPLETED,
                )
                .distinct()
            ).all()
        )
        tasks = self.session.scalars(
            select(LearningTask)
            .where(LearningTask.course_id.in_(enrolled_course_ids))
            .order_by(LearningTask.position)
        ).all()
        return next((task for task in tasks if task.id not in completed_ids), None)

    def _achievement_reads(self, profile: StudentProfile) -> list[AchievementRead]:
        rows = self.session.execute(
            select(StudentAchievement, Achievement)
            .join(Achievement, Achievement.id == StudentAchievement.achievement_id)
            .where(StudentAchievement.student_id == profile.id)
            .order_by(StudentAchievement.earned_at.desc())
        ).all()
        return [
            AchievementRead(
                code=achievement.code,
                name=achievement.name,
                description=achievement.description,
                icon=achievement.icon,
                earned_at=award.earned_at,
            )
            for award, achievement in rows
        ]

    def _validate_task_context(
        self,
        course: Course,
        module_id: str,
        outcome_id: str,
    ) -> None:
        module = self._get_module(module_id)
        outcome = self._get_outcome(outcome_id)
        if module.course_id != course.id or outcome.module_id != module.id:
            raise _unprocessable("Task module and outcome must belong to this course")

    def _validate_generated_source_references(
        self,
        course_id: str,
        source_references: list[str] | None,
    ) -> list[str]:
        normalized = list(
            dict.fromkeys(
                reference.strip()
                for reference in source_references or []
                if isinstance(reference, str) and reference.strip()
            )
        )
        if not normalized:
            raise _unprocessable(
                "Generated tasks require at least one authorised course source reference"
            )
        chunk_ids = set(
            self.session.scalars(
                select(MaterialChunk.id)
                .join(
                    LearningMaterial,
                    LearningMaterial.id == MaterialChunk.material_id,
                )
                .where(
                    LearningMaterial.course_id == course_id,
                    MaterialChunk.id.in_(normalized),
                    func.length(func.trim(MaterialChunk.chunk_text)) > 0,
                )
            ).all()
        )
        if set(normalized) != chunk_ids:
            raise _unprocessable(
                "Generated task source references must identify indexed chunks in this course"
            )
        return normalized

    def _validate_prerequisites(
        self,
        course_id: str,
        prerequisite_ids: list[str],
        position: int,
        task_id: str | None = None,
    ) -> None:
        if task_id and task_id in prerequisite_ids:
            raise _unprocessable("A task cannot require itself")
        prerequisites = (
            list(
                self.session.scalars(
                    select(LearningTask).where(LearningTask.id.in_(prerequisite_ids))
                ).all()
            )
            if prerequisite_ids
            else []
        )
        if len(prerequisites) != len(set(prerequisite_ids)):
            raise _unprocessable("One or more prerequisite_task_ids are invalid")
        if any(
            prerequisite.course_id != course_id or prerequisite.position >= position
            for prerequisite in prerequisites
        ):
            raise _unprocessable("Prerequisites must be earlier tasks in the same course")

    def _validate_publishable(self, course: Course) -> None:
        modules = list(
            self.session.scalars(
                select(CourseModule.id).where(CourseModule.course_id == course.id)
            ).all()
        )
        outcomes = (
            self.session.scalar(
                select(func.count(LearningOutcome.id)).where(LearningOutcome.module_id.in_(modules))
            )
            if modules
            else 0
        )
        tasks = self.session.scalar(
            select(func.count(LearningTask.id)).where(LearningTask.course_id == course.id)
        )
        if not modules or not outcomes or not tasks:
            raise _conflict("Add a module, learning outcome, and task before publishing")

    def _course_read(self, course: Course) -> CourseRead:
        module_count = (
            self.session.scalar(
                select(func.count(CourseModule.id)).where(CourseModule.course_id == course.id)
            )
            or 0
        )
        student_count = (
            self.session.scalar(
                select(func.count(Enrollment.id)).where(
                    Enrollment.course_id == course.id,
                    Enrollment.status == EnrollmentStatus.ACTIVE,
                )
            )
            or 0
        )
        task_ids = list(
            self.session.scalars(
                select(LearningTask.id).where(LearningTask.course_id == course.id)
            ).all()
        )
        possible_completions = len(task_ids) * student_count
        completed_count = (
            len(
                self.session.execute(
                    select(
                        SubmissionAttempt.student_id,
                        SubmissionAttempt.task_id,
                    )
                    .join(
                        Enrollment,
                        Enrollment.student_id == SubmissionAttempt.student_id,
                    )
                    .where(
                        Enrollment.course_id == course.id,
                        Enrollment.status == EnrollmentStatus.ACTIVE,
                        SubmissionAttempt.task_id.in_(task_ids),
                        SubmissionAttempt.status == AttemptStatus.COMPLETED,
                    )
                    .distinct()
                ).all()
            )
            if task_ids and student_count
            else 0
        )
        return CourseRead(
            id=course.id,
            educator_id=course.educator_id,
            code=course.code,
            title=course.title,
            description=course.description,
            state=course.state,
            enrollment_open=course.enrollment_open,
            created_at=course.created_at,
            updated_at=course.updated_at,
            module_count=module_count,
            student_count=student_count,
            progress_percentage=(
                round(completed_count / possible_completions * 100) if possible_completions else 0
            ),
        )

    @staticmethod
    def _enrollment_read(enrollment: Enrollment, student: User) -> EnrollmentRead:
        return EnrollmentRead(
            id=enrollment.id,
            course_id=enrollment.course_id,
            student_id=enrollment.student_id,
            status=enrollment.status,
            enrolled_at=enrollment.enrolled_at,
            student_name=student.full_name,
            student_email=student.email,
        )

    def _admin_user_read(self, user: User) -> AdminUserRead:
        profile_id = self.session.scalar(
            select(StudentProfile.id).where(StudentProfile.user_id == user.id)
        )
        return AdminUserRead(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            student_profile_id=profile_id,
        )

    def _setting_value(self, key: str) -> Any:
        setting = self.session.scalar(select(SystemSetting.value).where(SystemSetting.key == key))
        return setting if setting is not None else DEFAULT_SETTINGS[key][0]

    def _available_course_code(self, title: str) -> str:
        words = [
            "".join(character for character in word.upper() if character.isalnum())
            for word in title.split()
        ]
        base = "".join(word[:1] for word in words if word)[:8] or "COURSE"
        candidate = base
        suffix = 1
        while self.session.scalar(select(Course.id).where(Course.code == candidate)):
            suffix += 1
            candidate = f"{base}-{suffix}"
        return candidate

    def _audit(
        self,
        actor: User,
        action: str,
        resource_type: str,
        resource_id: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            PlatformAuditEvent(
                actor_id=actor.id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details or {},
                correlation_id=self.correlation_id,
            )
        )

    def _learning_event(
        self,
        student: User,
        task: LearningTask,
        event_type: LearningEventType,
        metadata: dict[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> None:
        secret_setting = settings.learning_event_pseudonym_secret
        secret = (
            secret_setting.get_secret_value()
            if secret_setting is not None
            else settings.session_secret_key.get_secret_value()
        )
        pseudonym = HmacSha256Pseudonymizer(secret).pseudonymize(
            "learning-actor",
            str(student.id),
        )
        event_id = self._uuid()
        self.session.add(
            LearningEvent(
                id=event_id,
                pseudonymous_user_id=pseudonym,
                course_id=task.course_id or "",
                task_id=task.id,
                event_type=event_type,
                occurred_at=datetime.now(UTC),
                correlation_id=correlation_id or self._uuid(),
                metadata_payload=metadata,
                deduplication_key=f"lms:{event_type.value}:{event_id}",
            )
        )

    def _commit(self) -> None:
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise _conflict("The change conflicts with an existing record") from error

    def _acquire_submission_sequence_lock(self, student_id: int) -> None:
        """Serialize attempt allocation for one submission transaction.

        SQLite is the MVP database and has one writer. ``BEGIN IMMEDIATE``
        reserves that writer before the attempt sequence is read, preventing
        two requests from both choosing the same next number. Other supported
        databases use the student's stable row as a per-learner row lock.
        """
        bind = self.session.get_bind()
        try:
            if bind.dialect.name == "sqlite":
                connection = self.session.connection()
                driver_connection = connection.connection.driver_connection
                if not driver_connection.in_transaction:
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                return
            self.session.execute(select(User.id).where(User.id == student_id).with_for_update())
        except OperationalError as error:
            self.session.rollback()
            raise _conflict("Another submission is being recorded; retry this request") from error

    @staticmethod
    def _require_not_archived(course: Course) -> None:
        if course.state is CourseState.ARCHIVED:
            raise _conflict("Archived courses are read-only")

    @staticmethod
    def _uuid() -> str:
        from uuid import uuid4

        return str(uuid4())


def bootstrap_demo(session: Session) -> tuple[list[User], Course]:
    """Create the documented local demo accounts and one compact course.

    This helper is deliberately never called by a read endpoint. Development
    setup and tests opt in explicitly.
    """

    users: dict[UserRole, User] = {}
    for email, full_name, role in DEMO_ACCOUNTS:
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                full_name=full_name,
                role=role,
                password_hash=hash_password(DEMO_PASSWORD),
            )
            session.add(user)
            session.flush()
        users[role] = user
    student = users[UserRole.STUDENT]
    profile = session.scalar(select(StudentProfile).where(StudentProfile.user_id == student.id))
    if profile is None:
        profile = StudentProfile(user_id=student.id, display_name=student.full_name)
        session.add(profile)
    for key, (value, description) in DEFAULT_SETTINGS.items():
        if not session.scalar(select(SystemSetting.id).where(SystemSetting.key == key)):
            session.add(SystemSetting(key=key, value=value, description=description))
    ensure_default_achievements(session)
    educator = users[UserRole.EDUCATOR]
    course = session.scalar(
        select(Course).where(
            Course.educator_id == educator.id,
            Course.title == "Quantum Computing Foundations",
        )
    )
    if course is None:
        course = Course(
            educator_id=educator.id,
            code="QL-101",
            title="Quantum Computing Foundations",
            description="A compact introduction to qubits, circuits, and measurement.",
            state=CourseState.PUBLISHED,
        )
        session.add(course)
        session.flush()
    module = session.scalar(
        select(CourseModule).where(
            CourseModule.course_id == course.id,
            CourseModule.position == 1,
        )
    )
    if module is None:
        module = CourseModule(
            course_id=course.id,
            title="Qubits and Circuits",
            description="Core concepts for the first quantum circuit.",
            position=1,
        )
        session.add(module)
        session.flush()
    outcome = session.scalar(
        select(LearningOutcome).where(
            LearningOutcome.module_id == module.id,
            LearningOutcome.position == 1,
        )
    )
    if outcome is None:
        outcome = LearningOutcome(
            module_id=module.id,
            title="Explain superposition",
            statement="Explain how a Hadamard gate creates a measurable superposition.",
            kind=OutcomeKind.WEEKLY,
            week_number=1,
            position=1,
        )
        session.add(outcome)
        session.flush()
    demo_tasks = list(
        session.scalars(
            select(LearningTask)
            .where(LearningTask.course_id == course.id)
            .order_by(LearningTask.position)
        ).all()
    )
    if not demo_tasks:
        task_specs = (
            (
                "Choose the superposition statement",
                "Which statement best describes a qubit after a Hadamard gate?",
                TaskType.MULTIPLE_CHOICE,
                "beginner",
                "b",
                {
                    "choices": [
                        {"id": "a", "text": "It is permanently zero."},
                        {
                            "id": "b",
                            "text": "It has amplitudes for both basis states until measurement.",
                        },
                        {"id": "c", "text": "It becomes two physical qubits."},
                    ]
                },
                None,
            ),
            (
                "Select measurement facts",
                "Select every statement that correctly describes quantum measurement.",
                TaskType.MULTIPLE_ANSWER,
                "intermediate",
                '["a","c"]',
                {
                    "choices": [
                        {"id": "a", "text": "Measurement returns a classical result."},
                        {"id": "b", "text": "Measurement preserves all amplitudes."},
                        {"id": "c", "text": "Repeated shots estimate a distribution."},
                    ],
                    "correct_answers": ["a", "c"],
                },
                None,
            ),
            (
                "Describe superposition",
                "Briefly explain how a Hadamard gate creates superposition.",
                TaskType.SHORT_ANSWER,
                "intermediate",
                "hadamard",
                {"required_keywords": ["hadamard", "superposition"]},
                None,
            ),
            (
                "Explain the Qiskit circuit",
                "Explain what the Hadamard and measurement operations do.",
                TaskType.CODE_EXPLANATION,
                "intermediate",
                "measurement",
                {"required_terms": ["measurement", "superposition"]},
                (
                    "from qiskit import QuantumCircuit\n\n"
                    "circuit = QuantumCircuit(1, 1)\n"
                    "circuit.h(0)\n"
                    "circuit.measure(0, 0)\n"
                ),
            ),
            (
                "Complete the Qiskit circuit",
                "Add the missing operation that creates superposition.",
                TaskType.CODE_COMPLETION,
                "advanced",
                "circuit.h",
                {"required_code_fragments": ["circuit.h"]},
                (
                    "from qiskit import QuantumCircuit\n\n"
                    "circuit = QuantumCircuit(1, 1)\n"
                    "# Add the missing gate\n"
                    "circuit.measure(0, 0)\n"
                ),
            ),
            (
                "Build a superposition circuit",
                "Drag a Hadamard gate onto the qubit before measurement.",
                TaskType.QUANTUM_CIRCUIT,
                "advanced",
                None,
                {
                    "required_gates": ["h"],
                    "starter_circuit": {"qubits": 1, "operations": []},
                },
                None,
            ),
        )
        previous_id: str | None = None
        for position, (
            title,
            prompt,
            task_type,
            difficulty,
            expected,
            criteria,
            starter_code,
        ) in enumerate(task_specs, start=1):
            task_id = LmsService._uuid()
            task = LearningTask(
                id=task_id,
                slug=f"demo-{position}-{task_id[:8]}",
                title=title,
                module=module.title,
                description=prompt,
                instructions="Complete the activity and submit your response.",
                task_type=task_type,
                difficulty=difficulty,
                points=position * 100,
                position=position,
                starter_code=starter_code,
                expected_answer=expected,
                due_at=datetime.now(UTC) + timedelta(days=position * 2),
                course_id=course.id,
                module_id=module.id,
                learning_outcome_id=outcome.id,
                marking_criteria=criteria,
                prerequisite_task_ids=[previous_id] if previous_id else [],
            )
            session.add(task)
            previous_id = task.id
    enrollment = session.scalar(
        select(Enrollment).where(
            Enrollment.course_id == course.id,
            Enrollment.student_id == student.id,
        )
    )
    if enrollment is None:
        session.add(Enrollment(course_id=course.id, student_id=student.id))
    session.commit()
    session.refresh(course)
    return [users[role] for role in UserRole], course
