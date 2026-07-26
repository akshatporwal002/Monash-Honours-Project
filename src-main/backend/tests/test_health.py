from fastapi.testclient import TestClient

from app.api.routes.health import get_readiness_probe
from app.main import app
from app.schemas.health import ReadinessResponse


def test_health_check() -> None:
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_is_fail_closed_and_sanitized() -> None:
    class Probe:
        def check(self) -> ReadinessResponse:
            return ReadinessResponse(
                status="not_ready",
                checks={
                    "database": "ready",
                    "migrations": "not_ready",
                    "worker": "not_ready",
                },
            )

    app.dependency_overrides[get_readiness_probe] = lambda: Probe()
    try:
        response = TestClient(app).get("/api/v1/ready")
    finally:
        app.dependency_overrides.pop(get_readiness_probe, None)

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["status"] == "not_ready"
    assert "exception" not in response.text.casefold()
