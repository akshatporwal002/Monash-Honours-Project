"""Recover course metadata without rewinding protected learning/source records."""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import Course, CourseModule, Enrollment, LearningMaterial
from app.models.intake_history import CourseRevision

FIELDS = ("code", "title", "description", "state", "enrollment_open", "time_zone")


def lock_course(session: Session, course: Course) -> None:
    session.execute(
        update(Course)
        .where(Course.id == course.id)
        .values(id=Course.id, updated_at=Course.updated_at)
    )
    session.refresh(course)


def snapshot(
    session: Session,
    course: Course,
    actor_id: str | None,
    action: str,
    reason: str = "",
    restored_from_id: str | None = None,
) -> CourseRevision:
    session.flush()
    version = (
        session.scalar(
            select(func.max(CourseRevision.version)).where(CourseRevision.course_id == course.id)
        )
        or 0
    ) + 1
    revision = CourseRevision(
        course_id=course.id,
        version=version,
        metadata_snapshot={name: getattr(course, name) for name in FIELDS},
        context_snapshot={
            "modules": [
                {"id": m.id, "title": m.title, "description": m.description, "position": m.position}
                for m in session.scalars(
                    select(CourseModule)
                    .where(CourseModule.course_id == course.id)
                    .order_by(CourseModule.position)
                )
            ],
            "enrollments": [
                {"id": e.id, "student_id": e.student_id, "status": e.status}
                for e in session.scalars(
                    select(Enrollment)
                    .where(Enrollment.course_id == course.id)
                    .order_by(Enrollment.id)
                )
            ],
            "sources": [
                {
                    "material_id": m.id,
                    "revision_id": m.current_source_revision_id,
                    "content_hash": m.content_hash,
                    "retired": m.retired_at is not None,
                }
                for m in session.scalars(
                    select(LearningMaterial)
                    .where(LearningMaterial.course_id == course.id)
                    .order_by(LearningMaterial.id)
                )
            ],
        },
        actor_id=actor_id,
        action=action,
        reason=reason,
        restored_from_id=restored_from_id,
    )
    session.add(revision)
    session.flush()
    return revision


def preserve_initial(session: Session, course: Course) -> None:
    lock_course(session, course)
    if not session.scalar(select(CourseRevision.id).where(CourseRevision.course_id == course.id)):
        snapshot(
            session, course, None, "LEGACY_SNAPSHOT", "First recorded state; original actor unknown"
        )
