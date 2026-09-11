"""New workflow adapters enforce session roles, ownership and CSRF."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from support.assessment_review import seed_review_context

from app.api.dependencies.authentication import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.main import create_app
from app.models.escalation import EscalationCase
from app.models.gamification import GamificationPreference
from app.models.reassessment import OutcomeResultPolicy
from app.models.user import User

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def test_new_mutations_reject_missing_csrf_without_writing_history(db_session, monkeypatch):
    fixture = seed_review_context(db_session)
    student = db_session.scalar(select(User).where(User.email == fixture["student_email"]))
    owner = db_session.scalar(select(User).where(User.email == fixture["educator_email"]))
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: student
    client = TestClient(app)
    prefix = "/api/v1"
    assert client.get(f"{prefix}/students/me/gamification").headers["Cache-Control"] == "no-store"
    assert (
        client.get(
            f"{prefix}/students/me/responses/{fixture['response_id']}/outcome-result"
        ).status_code
        == 200
    )
    monkeypatch.setattr(settings, "csrf_enabled", True)
    client.cookies.set(settings.csrf_cookie_name, "test-csrf")
    assert (
        client.put(
            f"{prefix}/students/me/gamification",
            json={"enabled": False, "expected_revision": 0, "idempotency_key": "csrf"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"{prefix}/escalations/reports",
            json={
                "source_kind": "TUTOR",
                "source_id": "unknown",
                "queue_kind": "TECHNICAL",
                "reason": "Concern",
                "idempotency_key": "csrf",
            },
        ).status_code
        == 403
    )
    app.dependency_overrides[get_current_user] = lambda: owner
    samples = client.get(f"{prefix}/escalations/courses/{fixture['course_id']}/samples")
    assert samples.status_code == 200
    assert samples.json() == []
    assert (
        client.get(f"{prefix}/assessment/decisions/{fixture['decision_id']}/reassessment").headers[
            "Cache-Control"
        ]
        == "no-store"
    )
    assert (
        client.post(
            f"{prefix}/assessment/definitions/{fixture['definition_id']}/outcome-policy",
            json={"selection_rule": "LATEST_VALID", "reason": "Approved rule"},
        ).status_code
        == 403
    )
    assert db_session.scalar(select(GamificationPreference)) is None
    assert db_session.scalar(select(OutcomeResultPolicy)) is None
    assert db_session.scalar(select(EscalationCase)) is None
    assert client.get(f"{prefix}/students/me/gamification").status_code == 403
    app.dependency_overrides.pop(get_current_user)
    assert client.get(f"{prefix}/escalations/queues").status_code == 401
