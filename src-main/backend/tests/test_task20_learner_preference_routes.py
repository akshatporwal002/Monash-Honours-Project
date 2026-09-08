"""Mounted learner-self route tests for Task 20."""

import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies.roles import require_student
from app.api.security_dependencies import get_request_security_guard
from app.db.session import get_db
from app.main import create_app
from app.models.lms import PlatformAuditEvent
from app.models.user import User, UserRole


class _AllowSecurity:
    async def enforce(self, *_args, **_kwargs):
        return None


def test_routes_derive_learner_scope_and_reject_stale_writes(db_session):
    first = User(
        email="route-one@test.example",
        password_hash="unused",
        full_name="One",
        role=UserRole.STUDENT,
    )
    second = User(
        email="route-two@test.example",
        password_hash="unused",
        full_name="Two",
        role=UserRole.STUDENT,
    )
    db_session.add_all([first, second])
    db_session.commit()
    current = {"user": first}
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_student] = lambda: current["user"]
    app.dependency_overrides[get_request_security_guard] = lambda: _AllowSecurity()
    client = TestClient(app)

    initial = client.get("/api/v1/students/me/preferences")
    assert initial.status_code == 200 and initial.json()["revision"] == 0
    assert initial.headers["cache-control"] == "no-store"
    payload = {
        "pace": "SLOWER",
        "format": "TEXT",
        "explanation_detail": "DETAILED",
        "optional_breaks_enabled": True,
        "repeat_practice_enabled": True,
        "personalisation_enabled": False,
        "expected_revision": 0,
        "idempotency_key": "route-key",
    }
    assert client.put("/api/v1/students/me/preferences", json=payload).status_code == 201
    assert client.put("/api/v1/students/me/preferences", json=payload).status_code == 200
    assert (
        client.put(
            "/api/v1/students/me/preferences", json={**payload, "idempotency_key": "stale-key"}
        ).status_code
        == 409
    )

    current["user"] = second
    assert client.get("/api/v1/students/me/preferences").json()["revision"] == 0
    assert client.get("/api/v1/students/me/preferences/history").json() == []


def test_preferences_require_student_authentication():
    response = TestClient(create_app()).get("/api/v1/students/me/preferences")
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


def test_preference_save_and_replay_are_audited_without_preference_values(db_session):
    student = User(
        email="preference-audit@test.example",
        password_hash="unused",
        full_name="Audit Learner",
        role=UserRole.STUDENT,
    )
    db_session.add(student)
    db_session.commit()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_student] = lambda: student
    app.dependency_overrides[get_request_security_guard] = lambda: _AllowSecurity()
    client = TestClient(app)
    payload = {
        "pace": "SLOWER",
        "format": "TEXT",
        "explanation_detail": "DETAILED",
        "optional_breaks_enabled": True,
        "repeat_practice_enabled": True,
        "personalisation_enabled": False,
        "expected_revision": 0,
        "idempotency_key": "audit-replay-key",
    }

    assert client.put("/api/v1/students/me/preferences", json=payload).status_code == 201
    assert client.put("/api/v1/students/me/preferences", json=payload).status_code == 200

    events = db_session.scalars(
        select(PlatformAuditEvent)
        .where(PlatformAuditEvent.action == "learner_preferences.saved")
        .order_by(PlatformAuditEvent.occurred_at, PlatformAuditEvent.id)
    ).all()
    assert [(event.actor_id, event.outcome, event.details["outcome"]) for event in events] == [
        (student.id, "success", "created"),
        (student.id, "success", "replayed"),
    ]
    assert all(event.occurred_at is not None for event in events)
    stored = json.dumps(
        [
            {
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "details": event.details,
            }
            for event in events
        ]
    )
    for value in ("SLOWER", "TEXT", "DETAILED", "optional_breaks_enabled", "repeat_practice_enabled"):
        assert value not in stored
