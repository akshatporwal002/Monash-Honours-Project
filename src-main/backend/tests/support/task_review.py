"""Explicit teaching-content approvals for test fixtures, never live policy."""

import hashlib
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, CourseState, LearningMaterial, LearningTask, User
from app.models.assessment import TaskFormVersion
from app.models.source_history import SourcePassage, SourceRevision
from app.models.task_review import TaskReviewEvent
from app.services.lms import LmsService, bootstrap_demo
from app.services.rag.source_history import record_approval
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


def approve_sourced_fixture_task(
    session: Session, task: LearningTask, *, source_text: str | None = None
) -> None:
    """Create explicit synthetic source and task reviews before formal fixture authoring."""
    token = uuid4().hex
    content = (
        f"Synthetic source for the task: {source_text or task.description}. "
        f"Fixture reference {token}."
    )
    digest = hashlib.sha256(content.encode()).hexdigest()
    material = LearningMaterial(
        course_id=task.course_id,
        original_filename=f"fixture-{token}.txt",
        content_hash=digest,
        mime_type="text/plain",
    )
    session.add(material)
    session.flush()
    from support.material_scanning import record_synthetic_scan

    record_synthetic_scan(session, material)
    revision = SourceRevision(
        material_id=material.id,
        course_id=task.course_id,
        version=1,
        source_label="Synthetic formal fixture source",
        mime_type="text/plain",
        content_hash=digest,
        extracted_blocks=[],
        extraction_version="test-fixture-v1",
        provenance="EXTRACTED",
    )
    session.add(revision)
    session.flush()
    passage = SourcePassage(
        id=str(uuid4()),
        revision_id=revision.id,
        course_id=task.course_id,
        chunk_index=0,
        chunk_text=content,
        chunk_hash=digest,
    )
    session.add(passage)
    session.flush()
    course = session.get(Course, task.course_id)
    record_approval(
        session,
        course_id=course.id,
        material_id=material.id,
        revision_id=revision.id,
        actor_id=str(course.educator_id),
        state="APPROVED",
        reason="Synthetic source explicitly reviewed for this test only",
        expected_sequence=0,
    )
    task.source_references = [passage.id]
    session.commit()
    approve_fixture_task(session, task)


def bind_reviewed_fixture_form(session: Session, form: TaskFormVersion) -> TaskReviewEvent:
    """Bind a draft fixture to explicit source and teaching approvals before publication."""
    task = session.get(LearningTask, form.learning_task_id)
    assert task is not None
    if not task.source_references:
        approve_sourced_fixture_task(session, task)
    else:
        approve_fixture_task(session, task)
    review = TaskReviewService(session)
    revision = review.latest_revision(task.id)
    event = review.latest_event(revision.id)
    assert event is not None and event.state == "APPROVED"
    form.task_revision_id = revision.id
    form.source_version = f"task-revision:{revision.id}"
    form.source_digest = revision.content_digest
    session.commit()
    return event
