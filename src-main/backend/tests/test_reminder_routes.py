from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_reminder_controls import NOW, context

from app.api.dependencies.authentication import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.main import create_app
from app.models.reminders import DeadlineArrangement, ReminderPreference


def test_reminder_routes_enforce_csrf_roles_and_private_projection(db_session, monkeypatch):
    student, task, owner = context(db_session)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: student
    monkeypatch.setattr(settings, "csrf_enabled", True)
    client = TestClient(app)
    client.cookies.set(settings.csrf_cookie_name, "reminder-csrf")
    headers = {settings.csrf_header_name: "reminder-csrf"}
    preferences = "/api/v1/students/me/reminder-preferences"
    payload = {"enabled": False, "expected_revision": 0, "idempotency_key": "first"}
    assert client.put(preferences, json=payload).status_code == 403
    assert db_session.scalar(select(func.count()).select_from(ReminderPreference)) == 0
    saved = client.put(preferences, json=payload, headers=headers)
    assert saved.status_code == 200
    assert saved.headers["Cache-Control"] == "no-store"
    assert client.get(preferences).json()["enabled"] is False
    path = f"/api/v1/tasks/{task.id}/deadline-arrangements/{student.id}"
    arrangement = {
        "expected_revision": 0,
        "idempotency_key": "extension",
        "kind": "EXTENSION",
        "time_zone": "UTC",
        "local_due_at": (NOW + timedelta(days=4)).replace(tzinfo=None).isoformat(),
        "reason": "Staff scheduling record",
        "learner_notice": "Your extension is approved.",
    }
    assert client.put(path, json=arrangement, headers=headers).status_code == 403
    assert client.get(path).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: owner
    assert client.put(path, json=arrangement).status_code == 403
    assert db_session.scalar(select(func.count()).select_from(DeadlineArrangement)) == 0
    saved = client.put(path, json=arrangement, headers=headers)
    assert saved.status_code == 200, saved.text
    assert client.put(path, json=arrangement, headers=headers).json() == saved.json()
    assert client.get(path).json()[0]["reason"] == "Staff scheduling record"
    assert client.get(preferences).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: student
    deadline = client.get(f"/api/v1/students/me/tasks/{task.id}/deadline")
    assert deadline.status_code == 200
    assert deadline.headers["Cache-Control"] == "no-store"
    assert deadline.json()["learner_notice"] == "Your extension is approved."
    assert "Staff scheduling record" not in deadline.text
    assert "reason" not in deadline.json()
    app.dependency_overrides.pop(get_current_user)
    assert client.get(preferences).status_code == 401
