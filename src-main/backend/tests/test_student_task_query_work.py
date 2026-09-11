"""Task projection reuse must preserve current authorization and view events."""

from collections import Counter

import pytest
from sqlalchemy import event, select
from support.learning_loop import seed_learning_loop

from app.models import LearningEvent, LearningEventType, LearningTask, User, UserRole
from app.models.source_history import SourcePassage, SourceRevision
from app.services.lms import LmsService, LmsServiceError
from app.services.rag.source_history import record_approval
from app.services.task_review import TaskReviewError, TaskReviewService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


@pytest.fixture
def task_context(db_session):
    fixture = seed_learning_loop(db_session)
    student = db_session.get(User, fixture["student_id"])
    task = db_session.get(LearningTask, fixture["task_id"])
    return LmsService(db_session), student, task, fixture


def test_task_projection_reduces_repeated_reads_and_keeps_view_event_boundary(
    db_session, task_context, monkeypatch
):
    service, student, task, _ = task_context
    counts = Counter()

    def capture(connection, cursor, statement, parameters, context, many):
        counts[statement.split()[0]] += 1

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        expected = service._task_read(service._require_student_task(student, task.id), student)
        baseline_selects = counts["SELECT"]
        counts.clear()
        result = service.get_student_task(student, task.id)
        assert result.model_dump(mode="json") == expected.model_dump(mode="json")
        assert counts["SELECT"] < baseline_selects
        assert counts["INSERT"] == 1
        assert not counts["UPDATE"] and not counts["DELETE"]

        original_event = service._learning_event

        def record_view(actor, current_task, event_type, metadata):
            # The event phase must perform fresh validation even before it adds
            # pending writes; it cannot inherit the projection's successful read.
            before = counts["SELECT"]
            TaskReviewService(db_session).source_approvals(current_task, required=True)
            assert counts["SELECT"] > before
            return original_event(actor, current_task, event_type, metadata)

        monkeypatch.setattr(service, "_learning_event", record_view)
        assert service.get_student_task(student, task.id) == result
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    views = db_session.scalars(
        select(LearningEvent).where(
            LearningEvent.task_id == task.id,
            LearningEvent.event_type == LearningEventType.TASK_VIEW,
        )
    ).all()
    assert len(views) == 2
    assert len({view.id for view in views}) == 2
    assert all(view.metadata_payload == {"source": "task-page"} for view in views)


@pytest.mark.parametrize("change", ["revoke_source", "renew_source", "edit_task"])
def test_task_projection_rechecks_publication_after_committed_change(
    db_session, task_context, change
):
    service, student, task, fixture = task_context
    service.get_student_task(student, task.id)
    if change == "edit_task":
        task.description += " Changed teaching instruction."
        TaskReviewService(db_session).capture(task, fixture["teacher_id"])
    else:
        passage = db_session.get(SourcePassage, task.source_references[0])
        revision = db_session.get(SourceRevision, passage.revision_id)
        record_approval(
            db_session,
            course_id=task.course_id,
            material_id=revision.material_id,
            revision_id=revision.id,
            actor_id=str(fixture["teacher_id"]),
            state="REVOKED" if change == "revoke_source" else "APPROVED",
            reason="Synthetic changed source review; teaching approval must be renewed.",
        )
    db_session.commit()
    with pytest.raises(TaskReviewError):
        service.get_student_task(student, task.id)
    assert (
        len(
            db_session.scalars(
                select(LearningEvent).where(
                    LearningEvent.task_id == task.id,
                    LearningEvent.event_type == LearningEventType.TASK_VIEW,
                )
            ).all()
        )
        == 1
    )


def test_task_projection_does_not_reuse_another_learners_authorization(db_session, task_context):
    service, student, task, _ = task_context
    service.get_student_task(student, task.id)
    outsider = User(
        email="outside-task-projection@example.com",
        full_name="Synthetic outside learner",
        password_hash=student.password_hash,
        role=UserRole.STUDENT,
    )
    db_session.add(outsider)
    db_session.commit()
    with pytest.raises(LmsServiceError) as denied:
        service.get_student_task(outsider, task.id)
    assert denied.value.status_code == 403
    assert service.get_student_task(student, task.id).id == task.id
