"""Regression checks for removal of the insecure prototype student API."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_legacy_student_identity_routes_are_not_mounted() -> None:
    client = TestClient(create_app())

    assert client.get("/api/v1/students/demo").status_code == 404
    assert client.get("/api/v1/students/arbitrary-id/dashboard").status_code == 404
    assert (
        client.get("/api/v1/students/arbitrary-id/tasks/arbitrary-task/submission").status_code
        == 404
    )
    assert client.get("/api/v1/students/educator-progress").status_code == 404


def test_canonical_student_routes_require_authentication() -> None:
    client = TestClient(create_app())

    assert client.get("/api/v1/students/me/dashboard").status_code == 401
    assert client.get("/api/v1/students/me/tasks/arbitrary-task").status_code == 401
    assert client.post("/api/v1/students/me/simulate", json={}).status_code == 401
