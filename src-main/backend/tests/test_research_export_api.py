from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.analytics_dependencies import get_analytics_pseudonymizer
from app.api.feedback_dependencies import get_authenticated_actor
from app.api.research_export_dependencies import (
    get_research_export_access_policy,
    get_research_export_service,
)
from app.main import app
from app.schemas.feedback_api import AuthenticatedActor
from app.services.research_export import PreparedResearchExport

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
ACTOR = f"v1_{'d' * 64}"


class Policy:
    async def authorized_course_ids(
        self,
        actor: AuthenticatedActor,
    ) -> set[str]:
        assert actor.actor_reference == "researcher-1"
        return {"course-1"}


class OversizedPolicy:
    async def authorized_course_ids(
        self,
        actor: AuthenticatedActor,
    ) -> set[str]:
        assert actor.actor_reference == "researcher-1"
        return {f"course-{index}" for index in range(1_001)}


class Pseudonymizer:
    def pseudonymize(self, namespace: str, reference: str) -> str:
        assert namespace == "audit-actor"
        assert reference == "researcher-1"
        return ACTOR


class Service:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def prepare(self, **values: object) -> PreparedResearchExport:
        self.calls.append(values)
        return PreparedResearchExport(
            export_id="00000000-0000-4000-8000-000000000501",
            filename="quantumlearn-research-20260725T120000Z.csv",
            media_type="text/csv; charset=utf-8",
            body=[b'"case_id"\r\n'],
            record_count=0,
        )


@pytest.fixture(autouse=True)
def overrides():
    service = Service()
    app.dependency_overrides[get_authenticated_actor] = lambda: AuthenticatedActor(
        actor_reference="researcher-1",
        role="researcher",
    )
    app.dependency_overrides[get_research_export_access_policy] = lambda: Policy()
    app.dependency_overrides[get_analytics_pseudonymizer] = lambda: Pseudonymizer()
    app.dependency_overrides[get_research_export_service] = lambda: service
    yield service
    app.dependency_overrides.clear()


def test_export_authorizes_audits_before_stream_and_returns_safe_headers(
    overrides: Service,
) -> None:
    response = TestClient(app).get(
        "/api/v1/research/exports",
        params={
            "format": "csv",
            "course_id": "course-1",
            "date_from": (NOW - timedelta(days=1)).isoformat(),
            "date_to": NOW.isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.content == b'"case_id"\r\n'
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="quantumlearn-research-'
    )
    UUID(response.headers["x-correlation-id"])
    assert overrides.calls[0]["actor_reference"] == ACTOR
    filters = overrides.calls[0]["filters"]
    assert filters.course_ids == ["course-1"]


def test_export_denies_cross_course_and_invalid_ranges_without_preparation(
    overrides: Service,
) -> None:
    denied = TestClient(app).get(
        "/api/v1/research/exports",
        params={"format": "json", "course_id": "private-course"},
    )
    invalid = TestClient(app).get(
        "/api/v1/research/exports",
        params={
            "format": "json",
            "course_id": "course-1",
            "date_from": (NOW - timedelta(days=366)).isoformat(),
            "date_to": NOW.isoformat(),
        },
    )

    assert denied.status_code == 403
    assert "private-course" not in denied.text
    assert invalid.status_code == 422
    assert overrides.calls == []


def test_export_rejects_unbounded_authorization_scope(
    overrides: Service,
) -> None:
    app.dependency_overrides[get_research_export_access_policy] = lambda: OversizedPolicy()

    response = TestClient(app).get(
        "/api/v1/research/exports",
        params={"format": "json"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "research_export_scope_unavailable"
    assert overrides.calls == []
