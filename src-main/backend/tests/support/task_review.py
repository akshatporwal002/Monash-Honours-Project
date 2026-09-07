"""Explicit teaching-content approvals for test fixtures, never live policy."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, CourseState, LearningTask, User
from app.services.lms import LmsService, bootstrap_demo
from app.services.task_review import TaskReviewService


def approve_fixture_task(session: Session, task: LearningTask) -> None:
    course = session.get(Course, task.course_id)
    actor = session.get(User, course.educator_id)
    review = TaskReviewService(session)
    revision = review.capture(task, actor.id)
    session.commit()
    summary = review.summary(task)
    if summary["available"]:
        return
    if summary["state"] == "APPROVED":
        review.record(
            actor,
            task.id,
            expected_revision_id=revision.id,
            expected_review_version=summary["review_version"],
            state="WITHDRAWN",
            reason="Test fixture approval needs refreshing",
        )
        summary = review.summary(task)
    if summary["state"] != "SUBMITTED":
        review.record(
            actor,
            task.id,
            expected_revision_id=revision.id,
            expected_review_version=summary["review_version"],
            state="SUBMITTED",
            reason="Test fixture teaching content submitted for review",
        )
        summary = review.summary(task)
    review.record(
        actor,
        task.id,
        expected_revision_id=revision.id,
        expected_review_version=summary["review_version"],
        state="APPROVED",
        reason="Test fixture teaching content approved for this test only",
    )


def bootstrap_reviewed_demo(session: Session):
    users, course = bootstrap_demo(session)
    for task in session.scalars(select(LearningTask).where(LearningTask.course_id == course.id)):
        approve_fixture_task(session, task)
    LmsService(session).set_course_state(
        session.get(User, course.educator_id), course.id, CourseState.PUBLISHED
    )
    return users, course
