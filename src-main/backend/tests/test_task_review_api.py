from sqlalchemy import select
from test_lms_core_api import lms_context as lms_context
from test_lms_core_api import login

from app.models import CourseModule, LearningOutcome


def test_author_edit_review_and_private_history_through_mounted_api(lms_context):
    client, session = lms_context
    module = session.scalar(select(CourseModule))
    outcome = session.scalar(select(LearningOutcome).where(LearningOutcome.module_id == module.id))
    login(client, "educator")
    created = client.post(
        f"/api/v1/courses/{module.course_id}/tasks",
        json={
            "module_id": module.id,
            "learning_outcome_id": outcome.id,
            "title": "Reviewed practice",
            "prompt": "Predict the measurement",
            "instructions": "Explain your prediction",
            "task_type": "short_answer",
            "difficulty": "beginner",
            "position": 50,
            "expected_answer": "Private marking anchor",
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    url = f"/api/v1/tasks/{task_id}/review"
    summary = client.get(url).json()
    assert summary["state"] == "DRAFT"
    assert summary["revision"] == 1
    assert not summary["available"]
    for state in ("SUBMITTED", "APPROVED"):
        response = client.post(
            url,
            json={
                "expected_revision_id": summary["revision_id"],
                "expected_review_version": summary["review_version"],
                "state": state,
                "reason": "Educator checked this exact content",
            },
        )
        assert response.status_code == 200, response.text
        summary = client.get(url).json()
    assert summary["available"]
    approved_revision_id = summary["revision_id"]
    stale = client.post(
        url,
        json={
            "expected_revision_id": summary["revision_id"],
            "expected_review_version": 0,
            "state": "WITHDRAWN",
            "reason": "Stale browser tab",
        },
    )
    assert stale.status_code == 409
    edited = client.patch(f"/api/v1/tasks/{task_id}", json={"prompt": "A fresh prediction"})
    assert edited.status_code == 200, edited.text
    summary = client.get(url).json()
    assert summary["revision"] == 2
    assert summary["state"] == "DRAFT"
    assert not summary["available"]
    stale_edit = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={
            "expected_revision_id": approved_revision_id,
            "prompt": "An outdated overwrite",
        },
    )
    assert stale_edit.status_code == 409
    history = client.get(url + "/history").json()
    assert len(history) == 2
    assert history[0]["revision"]["created_at"].endswith("Z")
    assert history[1]["events"][-1]["created_at"].endswith("Z")
    assert history[0]["revision"]["snapshot"]["description"] == "A fresh prediction"
    assert history[1]["revision"]["snapshot"]["description"] == "Predict the measurement"
    assert history[1]["events"][-1]["state"] == "APPROVED"
    assert len(client.get(url + "/history?limit=1&offset=1").json()) == 1
    assert client.get(url + "/history?limit=101").status_code == 422
    login(client, "student")
    assert client.get(url).status_code == 403
    assert client.get(url + "/history").status_code == 403
    assert (
        client.post(
            url,
            json={
                "expected_revision_id": summary["revision_id"],
                "expected_review_version": 0,
                "state": "SUBMITTED",
                "reason": "Attempted learner review",
            },
        ).status_code
        == 403
    )
    login(client, "admin")
    assert client.get(url + "/history").status_code == 200
    assert (
        client.post(
            url,
            json={
                "expected_revision_id": summary["revision_id"],
                "expected_review_version": 0,
                "state": "SUBMITTED",
                "reason": "Attempted administrator review",
            },
        ).status_code
        == 403
    )
