import pytest
from sqlalchemy import select
from test_lms_core_api import lms_context as lms_context
from test_lms_core_api import login

from app.models import Course, CourseModule, CourseState, LearningOutcome, LearningTask
from app.models.task_review import TaskReviewEvent, TaskRevision
from app.services.lms import LmsService, LmsServiceError, bootstrap_demo

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def _create(client, session, *, circuit=False):
    module = session.scalar(select(CourseModule))
    outcome = session.scalar(select(LearningOutcome).where(LearningOutcome.module_id == module.id))
    login(client, "educator")
    response = client.post(
        f"/api/v1/courses/{module.course_id}/tasks",
        json={
            "module_id": module.id,
            "learning_outcome_id": outcome.id,
            "title": "Review gate task",
            "prompt": "Predict H on zero",
            "instructions": "Explain and apply",
            "difficulty": "beginner",
            "task_type": "quantum_circuit" if circuit else "short_answer",
            "position": 50,
            "expected_answer": "Equal probabilities",
            "marking_criteria": {"starter_circuit": {"qubits": 6, "operations": []}}
            if circuit
            else {},
        },
    )
    assert response.status_code == 201, response.text
    return response.json(), module.course_id


def _review(client, task_id, state):
    url = f"/api/v1/tasks/{task_id}/review"
    current = client.get(url).json()
    return client.post(
        url,
        json={
            "expected_revision_id": current["revision_id"],
            "expected_review_version": current["review_version"],
            "state": state,
            "reason": "Educator reviewed the saved teaching content",
        },
    )


def test_unreviewed_task_hidden_and_blocked_then_approved_through_real_api(lms_context):
    client, session = lms_context
    task, course_id = _create(client, session)
    task_id = task["id"]
    assert client.post(f"/api/v1/courses/{course_id}/publish").status_code == 409
    login(client, "student")
    assert task_id not in [
        row["id"] for row in client.get(f"/api/v1/courses/{course_id}/tasks").json()
    ]
    dashboard = client.get("/api/v1/students/me/dashboard").json()
    assert task_id not in [row["id"] for row in dashboard["tasks"]]
    assert task_id not in [row["task_id"] for row in dashboard["recommendations"]]
    for path in (f"/tasks/{task_id}", f"/students/me/tasks/{task_id}"):
        assert client.get("/api/v1" + path).status_code == 409
    assert (
        client.put(
            f"/api/v1/students/me/tasks/{task_id}/draft", json={"answer": "Not yet"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/students/me/tasks/{task_id}/submissions", json={"answer": "Not yet"}
        ).status_code
        == 409
    )
    login(client, "educator")
    assert _review(client, task_id, "SUBMITTED").status_code == 200
    assert _review(client, task_id, "APPROVED").status_code == 200
    assert client.post(f"/api/v1/courses/{course_id}/publish").status_code == 200
    login(client, "student")
    assert client.get(f"/api/v1/students/me/tasks/{task_id}").status_code == 200
    assert task_id in [row["id"] for row in client.get(f"/api/v1/courses/{course_id}/tasks").json()]


def test_withdrawal_blocks_new_work_but_preserves_owned_draft_and_attempt_history(lms_context):
    client, session = lms_context
    task, _ = _create(client, session)
    task_id = task["id"]
    _review(client, task_id, "SUBMITTED")
    _review(client, task_id, "APPROVED")
    login(client, "student")
    assert (
        client.put(
            f"/api/v1/students/me/tasks/{task_id}/draft", json={"answer": "Equal probabilities"}
        ).status_code
        == 200
    )
    submitted = client.post(
        f"/api/v1/students/me/tasks/{task_id}/submissions", json={"answer": "Equal probabilities"}
    )
    assert submitted.status_code == 201, submitted.text
    history_url = f"/api/v1/students/me/tasks/{task_id}/submissions"
    before = client.get(history_url).json()
    login(client, "educator")
    assert _review(client, task_id, "WITHDRAWN").status_code == 200
    login(client, "student")
    assert client.get(f"/api/v1/students/me/tasks/{task_id}").status_code == 409
    assert client.get(history_url).json() == before
    assert (
        client.get(f"/api/v1/students/me/tasks/{task_id}/draft").json()["answer"]
        == "Equal probabilities"
    )
    assert (
        client.put(
            f"/api/v1/students/me/tasks/{task_id}/draft", json={"answer": "Replacement"}
        ).status_code
        == 409
    )
    assert client.post(history_url, json={"answer": "Replacement"}).status_code == 409


def test_unsupported_circuit_cannot_reach_learners_or_simulation(lms_context):
    client, session = lms_context
    task, course_id = _create(client, session, circuit=True)
    task_id = task["id"]
    _review(client, task_id, "SUBMITTED")
    assert _review(client, task_id, "APPROVED").status_code == 422
    assert client.post(f"/api/v1/courses/{course_id}/publish").status_code == 409
    login(client, "student")
    assert (
        client.post(
            "/api/v1/students/me/simulate",
            json={
                "task_id": task_id,
                "qubits": 1,
                "operations": [{"gate": "h", "targets": [0]}],
            },
        ).status_code
        == 409
    )
    login(client, "educator")
    assert (
        client.patch(
            f"/api/v1/tasks/{task_id}",
            json={
                "marking_criteria": {
                    "starter_circuit": {"qubits": 1, "operations": []},
                    "required_gates": ["h"],
                }
            },
        ).status_code
        == 200
    )
    _review(client, task_id, "SUBMITTED")
    assert _review(client, task_id, "APPROVED").status_code == 200
    login(client, "student")
    run = client.post(
        "/api/v1/students/me/simulate",
        json={
            "task_id": task_id,
            "qubits": 1,
            "operations": [{"gate": "h", "targets": [0]}],
        },
    )
    assert run.status_code == 200, run.text
    login(client, "educator")
    _review(client, task_id, "WITHDRAWN")
    login(client, "student")
    assert client.get(f"/api/v1/students/me/tasks/{task_id}/simulations").json() == [run.json()]


def test_bootstrap_creates_reviewable_drafts_without_implicit_approvals(db_session):
    users, course = bootstrap_demo(db_session)
    assert course.state is CourseState.DRAFT
    assert db_session.query(TaskRevision).count() == db_session.query(LearningTask).count() == 6
    assert db_session.query(TaskReviewEvent).count() == 0
    owner = next(user for user in users if user.id == course.educator_id)
    with pytest.raises(LmsServiceError, match="Every task needs current educator approval"):
        LmsService(db_session).set_course_state(owner, course.id, CourseState.PUBLISHED)
    db_session.rollback()
    assert db_session.get(Course, course.id).state is CourseState.DRAFT


def test_source_revocation_removes_a_published_task_and_reapproval_needs_new_review(lms_context):
    from test_task_review import _source

    client, session = lms_context
    task, course_id = _create(client, session)
    saved_task = session.get(LearningTask, task["id"])
    material, revision = _source(session, saved_task)
    source_url = (
        f"/api/v1/courses/{course_id}/materials/{material.id}/revisions/{revision.id}/approvals"
    )
    assert (
        client.post(
            source_url, json={"state": "APPROVED", "reason": "Checked source content"}
        ).status_code
        == 201
    )
    assert (
        client.patch(
            f"/api/v1/tasks/{task['id']}", json={"source_references": saved_task.source_references}
        ).status_code
        == 200
    )
    _review(client, task["id"], "SUBMITTED")
    assert _review(client, task["id"], "APPROVED").status_code == 200
    assert client.post(f"/api/v1/courses/{course_id}/publish").status_code == 200
    login(client, "student")
    task_url = f"/api/v1/students/me/tasks/{task['id']}"
    assert client.get(task_url).status_code == 200
    login(client, "educator")
    assert (
        client.post(
            source_url, json={"state": "REVOKED", "reason": "Source needs correction"}
        ).status_code
        == 201
    )
    login(client, "student")
    assert client.get(task_url).status_code == 409
    assert task["id"] not in [
        row["id"] for row in client.get(f"/api/v1/courses/{course_id}/tasks").json()
    ]
    login(client, "educator")
    assert (
        client.post(
            source_url, json={"state": "APPROVED", "reason": "Source checked again"}
        ).status_code
        == 201
    )
    assert client.post(f"/api/v1/courses/{course_id}/publish").status_code == 409
    _review(client, task["id"], "WITHDRAWN")
    _review(client, task["id"], "SUBMITTED")
    assert _review(client, task["id"], "APPROVED").status_code == 200
    login(client, "student")
    assert client.get(task_url).status_code == 200
