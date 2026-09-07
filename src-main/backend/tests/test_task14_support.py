"""Durable explicit support requests remain scoped and do not change assessment content."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from test_task14_lifecycle import setup_episode, supported

from app.models.episode import EpisodeHelpUse
from app.schemas.episode import EpisodeHelpUseWrite
from app.schemas.lms import DraftWrite
from app.services.task_review import TaskReviewError


def test_hint_requests_are_durable_unlimited_idempotent_and_safe_after_transfer(db_session):
    lms, student, task, started = setup_episode(db_session)
    request = EpisodeHelpUseWrite(
        assessment_work_start_id=started.assessment_work_start_id,
        kind="conceptual_hint",
        item_index=0,
        request_key="hint-first",
    )
    initial = lms.episode_state(student, task.id)
    assert initial["supported_hints"] == ["Conceptual hint 1"]
    assert "Consider how H" not in str(initial)
    first = lms.episode_help_use(student, task.id, request)
    assert first["content"] == "Consider how H changes the input state."
    assert lms.episode_help_use(student, task.id, request)["record"].id == first["record"].id
    second = lms.episode_help_use(
        student, task.id, request.model_copy(update={"request_key": "hint-second"})
    )
    assert first["record"].id != second["record"].id
    db_session.expire_all()
    page = lms.episode_help_history(student, task.id, limit=1)
    assert len(page["items"]) == 1 and page["next_offset"] == 1
    assert len(lms.episode_help_history(student, task.id, offset=1)["items"]) == 1
    assert "Consider how H" not in str(page)
    with pytest.raises(TaskReviewError, match="already used"):
        lms.episode_help_use(student, task.id, request.model_copy(update={"kind": "accessibility"}))
    db_session.rollback()
    for change in (
        {"item_index": 99, "request_key": "wrong-index"},
        {"assessment_work_start_id": "foreign"},
        {"stage_start_id": "foreign"},
    ):
        with pytest.raises(TaskReviewError):
            lms.episode_help_use(student, task.id, request.model_copy(update=change))
        db_session.rollback()
    checkpoint = lms.episode_checkpoint(student, task.id, supported(started), "supported", None)
    payload = DraftWrite.model_validate(
        checkpoint["draft"].model_dump(exclude={"id", "task_id", "updated_at"})
    )
    state = lms.episode_transfer(student, task.id, payload)
    assert lms.episode_help_use(student, task.id, request)["content"] is None
    with pytest.raises(TaskReviewError, match="unavailable"):
        lms.episode_help_use(
            student,
            task.id,
            request.model_copy(
                update={
                    "stage_start_id": state["transfer"]["stage_start_id"],
                    "request_key": "after-transfer",
                }
            ),
        )
    db_session.rollback()
    accessibility = request.model_copy(
        update={
            "kind": "accessibility",
            "request_key": "access",
            "stage_start_id": state["transfer"]["stage_start_id"],
        }
    )
    access = lms.episode_help_use(student, task.id, accessibility)
    assert access["content"] == "Text circuit and keyboard controls"
    assert lms.get_draft(student, task.id).episode == payload.episode
    assert lms.episode_state(student, task.id)["supported_hints"] == []
    assert len(lms.episode_help_history(student, task.id)["items"]) == 3
    assert "Consider how H" not in str(lms.episode_help_history(student, task.id))


def test_help_history_scope_and_append_only_guards(db_session):
    lms, student, task, started = setup_episode(db_session)
    request = EpisodeHelpUseWrite(
        assessment_work_start_id=started.assessment_work_start_id,
        kind="accessibility",
        item_index=0,
        request_key="explicit-access",
    )
    receipt = lms.episode_help_use(student, task.id, request)
    identifier = receipt["record"].id
    for sql in (
        "UPDATE episode_help_uses SET item_index=1 WHERE id=:id",
        "DELETE FROM episode_help_uses WHERE id=:id",
        "INSERT OR REPLACE INTO episode_help_uses SELECT * FROM episode_help_uses WHERE id=:id",
    ):
        with pytest.raises(IntegrityError, match="protected"):
            db_session.execute(text(sql), {"id": identifier})
        db_session.rollback()
    assert db_session.scalar(select(EpisodeHelpUse)).item_index == 0
    from app.models.lms import Enrollment
    from app.models.user import User, UserRole
    from app.services.lms import LmsServiceError

    other = User(
        email="episode-other@example.test",
        full_name="Other learner",
        password_hash="unused",
        role=UserRole.STUDENT,
    )
    db_session.add(other)
    db_session.commit()
    with pytest.raises(LmsServiceError):
        lms.episode_help_history(other, task.id)
    db_session.rollback()
    db_session.add(Enrollment(course_id=task.course_id, student_id=other.id))
    db_session.commit()
    assert lms.episode_help_history(other, task.id)["items"] == []
    with pytest.raises(TaskReviewError, match="does not match"):
        lms.episode_help_use(other, task.id, request)
