"""Optional reminders respect current access, submitted work and individual deadlines."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.models.lms import (
    Course,
    CourseState,
    Enrollment,
    EnrollmentStatus,
    Reminder,
    SubmissionAttempt,
    SystemSetting,
)
from app.models.persistence import LearningTask
from app.models.reminders import DeadlineArrangement, ReminderPreference
from app.models.user import User, UserRole
from app.schemas.reminders import (
    DeadlineArrangementRead,
    DeadlineArrangementWrite,
    LearnerDeadlineRead,
    ReminderPreferenceRead,
    ReminderPreferenceWrite,
)


class ReminderError(ValueError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def aware(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


def course_instant(local: datetime, time_zone: str, fold: int | None) -> datetime:
    zone = ZoneInfo(time_zone)
    candidates = [local.replace(tzinfo=zone, fold=value) for value in (0, 1)]
    valid = [
        value
        for value in candidates
        if value.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == local
    ]
    if not valid:
        raise ReminderError(422, "That local time does not exist because the clocks move forward")
    if len({value.utcoffset() for value in valid}) > 1 and fold is None:
        raise ReminderError(
            422, "That local time occurs twice. Choose the first or second occurrence"
        )
    selected = candidates[fold or 0]
    return selected.astimezone(UTC)


@dataclass(frozen=True)
class ReminderBatch:
    scanned: int
    created: int
    cursor: tuple[int, str] | None


class ReminderService:
    def __init__(self, session: Session, *, now: datetime | None = None):
        self.session = session
        self.now = aware(now) or datetime.now(UTC)

    def _lock(self, student_id: int) -> None:
        self.session.execute(text("UPDATE users SET id=id WHERE id=:id"), {"id": student_id})
        self.session.expire_all()

    def preference(self, student_id: int) -> ReminderPreferenceRead:
        latest = self.session.scalar(
            select(ReminderPreference)
            .where(ReminderPreference.student_id == student_id)
            .order_by(ReminderPreference.revision.desc())
            .limit(1)
        )
        return ReminderPreferenceRead.model_validate(latest) if latest else ReminderPreferenceRead()

    def save_preference(
        self, student_id: int, command: ReminderPreferenceWrite
    ) -> ReminderPreferenceRead:
        self._lock(student_id)
        existing = self.session.scalar(
            select(ReminderPreference).where(
                ReminderPreference.student_id == student_id,
                ReminderPreference.request_key == command.idempotency_key,
            )
        )
        if existing:
            if (
                existing.revision != command.expected_revision + 1
                or existing.enabled != command.enabled
                or aware(existing.paused_until) != command.paused_until
            ):
                raise ReminderError(
                    409, "This request key was already used for different preferences"
                )
            return ReminderPreferenceRead.model_validate(existing)
        if self.preference(student_id).revision != command.expected_revision:
            raise ReminderError(409, "Reminder preferences changed. Reload before saving")
        if command.paused_until is not None and command.paused_until <= self.now:
            raise ReminderError(422, "Choose a future pause end or clear the pause")
        record = ReminderPreference(
            student_id=student_id,
            revision=command.expected_revision + 1,
            request_key=command.idempotency_key,
            enabled=command.enabled,
            paused_until=command.paused_until.astimezone(UTC) if command.paused_until else None,
            created_at=self.now,
        )
        self.session.add(record)
        self.session.commit()
        return ReminderPreferenceRead.model_validate(record)

    def _latest_arrangement(self, student_id: int, task_id: str) -> DeadlineArrangement | None:
        return self.session.scalar(
            select(DeadlineArrangement)
            .where(
                DeadlineArrangement.student_id == student_id, DeadlineArrangement.task_id == task_id
            )
            .order_by(DeadlineArrangement.revision.desc())
            .limit(1)
        )

    def _staff_context(
        self, actor: User, student_id: int, task_id: str
    ) -> tuple[LearningTask, Course]:
        task = self.session.get(LearningTask, task_id)
        course = self.session.get(Course, task.course_id) if task else None
        if (
            not actor.is_active
            or actor.role != UserRole.EDUCATOR
            or course is None
            or course.educator_id != actor.id
        ):
            raise ReminderError(403, "Only the course owner can manage this deadline")
        enrolled = self.session.scalar(
            select(Enrollment.id).where(
                Enrollment.course_id == course.id, Enrollment.student_id == student_id
            )
        )
        if enrolled is None:
            raise ReminderError(404, "This learner is not enrolled in the course")
        return task, course

    def history(
        self, actor: User, student_id: int, task_id: str, *, limit: int = 20, offset: int = 0
    ) -> list[DeadlineArrangementRead]:
        self._staff_context(actor, student_id, task_id)
        rows = self.session.scalars(
            select(DeadlineArrangement)
            .where(
                DeadlineArrangement.student_id == student_id, DeadlineArrangement.task_id == task_id
            )
            .order_by(DeadlineArrangement.revision.desc())
            .limit(limit)
            .offset(offset)
        )
        return [DeadlineArrangementRead.model_validate(row) for row in rows]

    def save_arrangement(
        self, actor: User, student_id: int, task_id: str, command: DeadlineArrangementWrite
    ) -> DeadlineArrangementRead:
        self._lock(student_id)
        task, course = self._staff_context(actor, student_id, task_id)
        existing = self.session.scalar(
            select(DeadlineArrangement).where(
                DeadlineArrangement.student_id == student_id,
                DeadlineArrangement.task_id == task_id,
                DeadlineArrangement.request_key == command.idempotency_key,
            )
        )
        due_at = (
            course_instant(command.local_due_at, command.time_zone, command.fold)
            if command.local_due_at
            else None
        )
        values = {
            "kind": command.kind,
            "active": command.active,
            "due_at": due_at,
            "reminders_paused": command.reminders_paused,
            "time_zone": command.time_zone,
            "reason": command.reason,
            "learner_notice": command.learner_notice,
        }
        if existing:
            if existing.revision != command.expected_revision + 1 or any(
                (aware(getattr(existing, name)) if name == "due_at" else getattr(existing, name))
                != value
                for name, value in values.items()
            ):
                raise ReminderError(
                    409, "This request key was already used for a different arrangement"
                )
            return DeadlineArrangementRead.model_validate(existing)
        if course.state == CourseState.ARCHIVED:
            raise ReminderError(409, "Archived courses cannot receive new deadline arrangements")
        if course.time_zone != command.time_zone:
            raise ReminderError(409, "The course time zone changed. Reload before saving")
        latest = self._latest_arrangement(student_id, task_id)
        if (latest.revision if latest else 0) != command.expected_revision:
            raise ReminderError(409, "The deadline arrangement changed. Reload before saving")
        if not command.active and (latest is None or not latest.active):
            raise ReminderError(409, "There is no active arrangement to revoke")
        if due_at is not None and task.due_at is not None and due_at < aware(task.due_at):
            raise ReminderError(
                422, "An individual deadline cannot be earlier than the course deadline"
            )
        record = DeadlineArrangement(
            student_id=student_id,
            task_id=task_id,
            actor_id=actor.id,
            revision=command.expected_revision + 1,
            request_key=command.idempotency_key,
            created_at=self.now,
            **values,
        )
        self.session.add(record)
        self.session.commit()
        return DeadlineArrangementRead.model_validate(record)

    def deadline(self, student_id: int, task: LearningTask) -> LearnerDeadlineRead:
        course = self.session.get(Course, task.course_id)
        latest = self._latest_arrangement(student_id, task.id)
        due_at = aware(task.due_at)
        if latest and latest.active and latest.due_at:
            due_at = max(value for value in (due_at, aware(latest.due_at)) if value is not None)
        return LearnerDeadlineRead(
            task_id=task.id,
            time_zone=course.time_zone,
            original_due_at=task.due_at,
            effective_due_at=due_at,
            reminders_paused=bool(latest and latest.active and latest.reminders_paused),
            arrangement_active=bool(latest and latest.active),
            learner_notice=latest.learner_notice if latest else None,
        )

    def send(
        self,
        student_id: int,
        task_id: str,
        message: str | None = None,
        *,
        title: str | None = None,
        overdue_only: bool = False,
    ) -> Reminder | None:
        from app.services.lms import LmsService, LmsServiceError
        from app.services.task_review import TaskReviewError

        self._lock(student_id)
        setting = self.session.scalar(
            select(SystemSetting).where(SystemSetting.key == "reminders_enabled")
        )
        if setting is not None and not bool(setting.value):
            return None
        preference = self.preference(student_id)
        if not preference.enabled or (
            preference.paused_until and preference.paused_until > self.now
        ):
            return None
        learner = self.session.get(User, student_id)
        if learner is None or not learner.is_active or learner.role != UserRole.STUDENT:
            return None
        try:
            read = LmsService(self.session).get_task_for_actor(learner, task_id)
        except (LmsServiceError, TaskReviewError):
            return None
        if read.access_status not in {"available", "in_progress"}:
            return None
        # Accepted work is awaiting its normal feedback/review workflow, not a reminder.
        if self.session.scalar(
            select(SubmissionAttempt.id)
            .where(SubmissionAttempt.student_id == student_id, SubmissionAttempt.task_id == task_id)
            .limit(1)
        ):
            return None
        task = self.session.get(LearningTask, task_id)
        deadline = self.deadline(student_id, task)
        if deadline.reminders_paused:
            return None
        if overdue_only and (
            deadline.effective_due_at is None
            or deadline.effective_due_at > self.now - timedelta(hours=24)
        ):
            return None
        if (
            deadline.arrangement_active
            and deadline.effective_due_at
            and deadline.effective_due_at > self.now
        ):
            return None
        previous = self.session.scalar(
            select(Reminder.id)
            .where(
                Reminder.student_id == student_id,
                Reminder.task_id == task_id,
                Reminder.created_at > self.now - timedelta(hours=24),
            )
            .limit(1)
        )
        if previous:
            return None
        record = Reminder(
            student_id=student_id,
            task_id=task_id,
            title=(title or f"Overdue: {task.title}")[:150],
            message=message or f"{task.title} is overdue. Resume it when you are ready.",
            dedupe_window=self.now.isoformat(),
            created_at=self.now,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def process_due(
        self, *, after: tuple[int, str] | None = None, limit: int = 25
    ) -> ReminderBatch:
        query = (
            select(User.id, LearningTask.id)
            .join(Enrollment, Enrollment.student_id == User.id)
            .join(Course, Course.id == Enrollment.course_id)
            .join(LearningTask, LearningTask.course_id == Course.id)
            .where(
                User.is_active.is_(True),
                User.role == UserRole.STUDENT,
                Enrollment.status == EnrollmentStatus.ACTIVE,
                Course.state == CourseState.PUBLISHED,
                or_(
                    LearningTask.due_at.is_(None),
                    LearningTask.due_at <= self.now - timedelta(hours=24),
                ),
            )
        )
        if after is not None:
            query = query.where(
                or_(User.id > after[0], and_(User.id == after[0], LearningTask.id > after[1]))
            )
        rows = self.session.execute(query.order_by(User.id, LearningTask.id).limit(limit)).all()
        created = 0
        for student_id, task_id in rows:
            if self.send(student_id, task_id, overdue_only=True) is not None:
                created += 1
            self.session.commit()
        return ReminderBatch(len(rows), created, tuple(rows[-1]) if len(rows) == limit else None)


class ReminderWorker:
    def __init__(self, session_factory: sessionmaker[Session], *, now: Callable[[], datetime]):
        self.session_factory = session_factory
        self.now = now
        self.cursor: tuple[int, str] | None = None
        self.next_scan: datetime | None = None

    async def run_once(self) -> bool:
        now = self.now()
        if self.next_scan is not None and now < self.next_scan:
            return False
        with self.session_factory() as session:
            result = ReminderService(session, now=now).process_due(after=self.cursor)
        self.cursor = result.cursor
        if self.cursor is None:
            self.next_scan = now + timedelta(minutes=1)
        return result.scanned > 0
