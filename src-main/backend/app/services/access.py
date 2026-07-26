"""Database-backed course access rules shared by materials and generation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LearningTask
from app.models.lms import Course, Enrollment, EnrollmentStatus
from app.models.user import User, UserRole
from app.schemas.feedback_api import AuthenticatedActor
from app.services.learning_events import LearningEventScope
from app.services.rag.errors import CourseAccessDeniedError


class SqlAlchemyCourseAccessPolicy:
    def __init__(self, session: Session) -> None:
        self._session = session

    def require_read(self, actor_id: str, course_id: str) -> None:
        user, course = self._context(actor_id, course_id)
        if user.role is UserRole.ADMINISTRATOR:
            return
        if user.role is UserRole.EDUCATOR and course.educator_id == user.id:
            return
        if user.role is UserRole.STUDENT:
            enrollment = self._session.scalar(
                select(Enrollment).where(
                    Enrollment.course_id == course.id,
                    Enrollment.student_id == user.id,
                    Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
                )
            )
            if enrollment is not None:
                return
        raise CourseAccessDeniedError()

    def require_manage(self, actor_id: str, course_id: str) -> None:
        user, course = self._context(actor_id, course_id)
        if user.role is UserRole.ADMINISTRATOR:
            return
        if user.role is UserRole.EDUCATOR and course.educator_id == user.id:
            return
        raise CourseAccessDeniedError()

    def _context(self, actor_id: str, course_id: str) -> tuple[User, Course]:
        try:
            user_id = int(actor_id)
        except ValueError:
            raise CourseAccessDeniedError() from None
        user = self._session.get(User, user_id)
        course = self._session.get(Course, course_id)
        if user is None or not user.is_active or course is None:
            raise CourseAccessDeniedError()
        return user, course


class SqlAlchemyAnalyticsAccessPolicy:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def authorized_course_ids(self, actor_reference: str) -> set[str]:
        user = _active_user(self._session, actor_reference)
        if user is None:
            return set()
        if user.role is UserRole.ADMINISTRATOR:
            return set(self._session.scalars(select(Course.id)).all())
        if user.role is UserRole.EDUCATOR:
            return set(
                self._session.scalars(select(Course.id).where(Course.educator_id == user.id)).all()
            )
        return set()


class SqlAlchemyRosterAdapter:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def learner_references(self, course_ids: set[str]) -> list[str]:
        if not course_ids:
            return []
        student_ids = self._session.scalars(
            select(Enrollment.student_id)
            .where(
                Enrollment.course_id.in_(course_ids),
                Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
            )
            .distinct()
        ).all()
        return [str(student_id) for student_id in student_ids]


class SqlAlchemyLearningEventAccessPolicy:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def resolve_task_scope(
        self,
        actor: AuthenticatedActor,
        task_id: str,
    ) -> LearningEventScope | None:
        user = _active_user(self._session, actor.actor_reference)
        task = self._session.get(LearningTask, task_id)
        if user is None or task is None or task.course_id is None:
            return None
        course = self._session.get(Course, task.course_id)
        if course is None:
            return None
        if user.role is UserRole.ADMINISTRATOR:
            return LearningEventScope(course.id, task.id)
        if user.role is UserRole.EDUCATOR and course.educator_id == user.id:
            return LearningEventScope(course.id, task.id)
        if user.role is not UserRole.STUDENT:
            return None
        enrollment = self._session.scalar(
            select(Enrollment.id).where(
                Enrollment.course_id == course.id,
                Enrollment.student_id == user.id,
                Enrollment.status == EnrollmentStatus.ACTIVE,
            )
        )
        if enrollment is None:
            return None
        return LearningEventScope(course.id, task.id)


class SqlAlchemyResearchExportAccessPolicy:
    def __init__(self, session: Session) -> None:
        self._analytics_policy = SqlAlchemyAnalyticsAccessPolicy(session)

    async def authorized_course_ids(
        self,
        actor: AuthenticatedActor,
    ) -> set[str]:
        return await self._analytics_policy.authorized_course_ids(actor.actor_reference)


def _active_user(session: Session, actor_reference: str) -> User | None:
    try:
        user_id = int(actor_reference)
    except ValueError:
        return None
    user = session.get(User, user_id)
    return user if user is not None and user.is_active else None
