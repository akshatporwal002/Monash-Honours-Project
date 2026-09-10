"""Real authentication, CSRF and role checks for the mounted teaching workflow."""

from fastapi.testclient import TestClient
from test_misconceptions import context

from app.api.security_dependencies import get_request_security_guard
from app.core.config import settings
from app.db.session import get_db
from app.main import create_app


def test_mounted_routes_enforce_authentication_roles_and_csrf(db_session, monkeypatch):
    fixture, _, _, _, _, _, _, saved = context(db_session)
    monkeypatch.setattr(settings, "csrf_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    get_request_security_guard.cache_clear()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    path = f"/api/v1/misconceptions/{saved.id}"
    try:
        assert client.get(path).status_code == 401
        login = client.post(
            "/api/v1/auth/login",
            json={"email": fixture["student_email"], "password": fixture["student_password"]},
        )
        assert login.status_code == 200
        read = client.get(path)
        assert read.status_code == 200 and read.headers["cache-control"] == "no-store"
        assert read.json()["fresh_question"] is None
        assert client.get("/api/v1/misconceptions/teaching").status_code == 403
        body = {
            "request_key": "api-response",
            "expected_version": 0,
            "stage": "PROBE",
            "answer": "Sampling may vary",
            "reasoning": "The circuit stays fixed",
            "confidence": 0.5,
            "help_used": False,
        }
        assert client.post(f"{path}/responses", json=body).status_code == 403
        headers = {
            settings.csrf_header_name: client.cookies.get(settings.csrf_cookie_name),
            "Origin": settings.allowed_cors_origins[0],
        }
        response = client.post(f"{path}/responses", json=body, headers=headers)
        assert response.status_code == 201
        assert response.json()["version"] == 1
        assert client.post(f"{path}/responses", json=body, headers=headers).json()["version"] == 1
        wrong_role = client.post(f"{path}/reviews", json={}, headers=headers)
        assert wrong_role.status_code == 403
    finally:
        client.close()
        get_request_security_guard.cache_clear()
