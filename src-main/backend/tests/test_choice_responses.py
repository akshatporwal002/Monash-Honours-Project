"""New choice writes are canonical; immutable legacy evidence remains readable."""

import json

import pytest
from sqlalchemy import select
from support.task_review import approve_fixture_task
from test_lms_core_api import lms_context as lms_context
from test_lms_core_api import login

from app.models import LearningTask, TaskType


@pytest.mark.parametrize("kind", ["multiple_choice", "multiple_answer"])
def test_choice_api_rejects_noncanonical_writes_and_preserves_history(lms_context, kind):
    client, session = lms_context
    task = session.scalar(
        select(LearningTask).where(LearningTask.task_type == TaskType.MULTIPLE_CHOICE)
    )
    task.task_type = TaskType(kind)
    task.prerequisite_task_ids = []
    task.marking_criteria = {
        "choices": [{"id": "a", "text": "First"}, {"id": "b", "text": "Second"}]
    }
    task.expected_answer = "a" if kind == "multiple_choice" else '["a"]'
    session.commit()
    approve_fixture_task(session, task)
    login(client, "student")
    base = f"/api/v1/students/me/tasks/{task.id}"
    invalid = (
        ["unknown", "A", " a", '["a"]']
        if kind == "multiple_choice"
        else [
            "a",
            "a,b",
            '"a"',
            '["a", "a"]',
            '["unknown"]',
            "[true]",
            "[1]",
            '{"a":true}',
            '["A"]',
        ]
    )
    for answer in invalid:
        for method, suffix in ((client.put, "/draft"), (client.post, "/submissions")):
            response = method(base + suffix, json={"answer": answer})
            assert response.status_code == 422, (answer, suffix, response.text)
    empty = "" if kind == "multiple_choice" else "[]"
    assert client.put(base + "/draft", json={"answer": empty}).status_code == 200
    assert client.post(base + "/submissions", json={"answer": empty}).status_code == 422
    # An incorrect but well-formed selection is evidence, not a shape error.
    answer = "b" if kind == "multiple_choice" else '["b", "a"]'
    saved = client.post(base + "/submissions", json={"answer": answer})
    assert saved.status_code == 201, saved.text
    assert saved.json()["answer"] == answer
    assert client.get(base + "/submissions").json()[0]["answer"] == answer
    # Seed an immutable pre-validation record; history must retain its original shape.
    from app.models.lms import SubmissionAttempt

    original = session.get(SubmissionAttempt, saved.json()["id"])
    legacy_answer = " B " if kind == "multiple_choice" else "a,b"
    historical = SubmissionAttempt(
        draft_id=original.draft_id,
        student_id=original.student_id,
        task_id=task.id,
        attempt_number=2,
        status=original.status,
        answer=legacy_answer,
        feedback="Legacy recorded response",
    )
    session.add(historical)
    session.commit()
    history = client.get(base + "/submissions")
    assert history.status_code == 200, history.text
    assert (
        next(item for item in history.json() if item["id"] == historical.id)["answer"]
        == legacy_answer
    )
    assert client.post(base + "/submissions", json={"answer": legacy_answer}).status_code == 422
    client.post("/api/v1/auth/logout")
    login(client, "educator")
    invalid_update = client.patch(f"/api/v1/tasks/{task.id}", json={"expected_answer": "unknown"})
    assert invalid_update.status_code == 422, invalid_update.text
    session.expire_all()
    assert session.get(LearningTask, task.id).expected_answer != "unknown"


@pytest.mark.parametrize(
    "bad",
    [
        [],
        [{"id": "a", "text": "Only"}],
        [{"id": "a", "text": "First"}, {"id": "a", "text": "Duplicate"}],
        ["First", "Second"],
        [{"id": 1, "text": "First"}, {"id": "b", "text": "Second"}],
        [{"id": "a", "text": " "}, {"id": "b", "text": "Second"}],
    ],
)
def test_choice_authoring_rejects_invalid_definitions(lms_context, bad):
    client, session = lms_context
    task = session.scalar(
        select(LearningTask).where(LearningTask.task_type == TaskType.MULTIPLE_CHOICE)
    )
    login(client, "educator")
    payload = {
        "module_id": task.module_id,
        "learning_outcome_id": task.learning_outcome_id,
        "title": "Canonical choices",
        "prompt": "Choose one",
        "instructions": "Select a choice",
        "task_type": "multiple_choice",
        "difficulty": "beginner",
        "position": 20,
        "marking_criteria": {"choices": bad},
        "expected_answer": "a",
    }
    result = client.post(f"/api/v1/courses/{task.course_id}/tasks", json=payload)
    assert result.status_code == 422, result.text


def test_choice_answer_keys_reject_unknown_and_disagreeing_ids():
    from app.schemas.choice_tasks import validate_choice_key

    choices = {"choices": [{"id": "a", "text": "First"}, {"id": "b", "text": "Second"}]}
    for kind, criteria, answer in (
        ("multiple_choice", choices, "unknown"),
        ("multiple_answer", choices, '["a", "a"]'),
        ("multiple_answer", {**choices, "correct_answers": ["unknown"]}, None),
        ("multiple_answer", {**choices, "correct_answers": ["b"]}, json.dumps(["a"])),
    ):
        with pytest.raises(ValueError):
            validate_choice_key(kind, criteria, answer)


@pytest.mark.parametrize("kind", ["multiple_choice", "multiple_answer"])
def test_formal_choice_api_requires_canonical_evidence_before_human_review(db_session, kind):
    from dataclasses import replace

    from fastapi.testclient import TestClient
    from support.task_review import bootstrap_reviewed_demo
    from test_assessment_definitions import _draft, _service, _setup

    from app.api.dependencies.authentication import get_current_user
    from app.db.session import get_db
    from app.domain.assessment import BloomProcess
    from app.main import create_app
    from app.models.assessment import TaskFormVersion
    from app.models.lms import Course, CourseState, Enrollment
    from app.models.user import UserRole
    from app.services.lms import LmsService

    course_id, outcome_id, owner_id, outcome_version_id = _setup(db_session)
    task = db_session.scalar(select(LearningTask).where(LearningTask.course_id == course_id))
    task.task_type = TaskType(kind)
    task.marking_criteria = {
        "choices": [{"id": "a", "text": "First"}, {"id": "b", "text": "Second"}]
    }
    task.expected_answer = "a" if kind == "multiple_choice" else '["a"]'
    db_session.commit()
    approve_fixture_task(db_session, task)
    service = _service(db_session)
    definition = service.create_draft(
        course_id=course_id,
        learning_outcome_id=outcome_id,
        actor_user_id=owner_id,
        draft=replace(
            _draft(
                outcome_version_id=outcome_version_id, task_id=task.id, task_processes=["REMEMBER"]
            ),
            formal_result_eligible=True,
            bloom_process=BloomProcess.REMEMBER,
            transfer_rule={"required": False},
        ),
    )
    service.approve(
        course_id=course_id,
        assessment_definition_id=definition.assessment_definition_id,
        expected_version=1,
        actor_user_id=owner_id,
        approval_reason="Synthetic canonical response test",
    )
    form = db_session.scalar(
        select(TaskFormVersion).where(
            TaskFormVersion.assessment_definition_version_id == definition.id
        )
    )
    users, _ = bootstrap_reviewed_demo(db_session)
    student = next(user for user in users if user.role is UserRole.STUDENT)
    db_session.get(Course, course_id).state = CourseState.PUBLISHED
    db_session.add(Enrollment(course_id=course_id, student_id=student.id))
    db_session.commit()
    started = LmsService(db_session).start_assessment_work(student, task.id, form.id)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: student
    with TestClient(app) as client:
        url = f"/api/v1/students/me/tasks/{task.id}/submissions"
        common = {
            "assessment_work_start_id": started.assessment_work_start_id,
            "idempotency_key": "canonical",
        }
        rejected = client.post(url, json={**common, "answer": "unknown"})
        assert rejected.status_code == 422, rejected.text
        answer = "b" if kind == "multiple_choice" else '["b"]'
        saved = client.post(url, json={**common, "answer": answer})
        assert saved.status_code == 201, saved.text
        assert saved.json()["formal_assessment"]["result"] is None
        assert saved.json()["answer"] == answer
        assert saved.json()["assessment_work_start_id"] == started.assessment_work_start_id
