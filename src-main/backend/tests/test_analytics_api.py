from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.analytics_dependencies import (
    get_analytics_access_policy,
    get_analytics_application,
)
from app.api.feedback_dependencies import get_authenticated_actor
from app.main import app
from app.schemas.analytics import InactiveLearnerPage
from app.schemas.feedback_api import AuthenticatedActor
from app.services.analytics import (
    AnalyticsFilterSnapshot,
    MetricValue,
    calculate_learning_metrics,
    calculate_research_metrics,
)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


class Policy:
    def __init__(self, courses: set[str]) -> None:
        self.courses = courses

    async def authorized_course_ids(self, actor_reference: str) -> set[str]:
        assert actor_reference == "educator-1"
        return self.courses


class Application:
    async def learning(self, query):
        return calculate_learning_metrics(
            [],
            released_workflow_ids=set(),
            roster=[],
            as_of=NOW,
            filters=AnalyticsFilterSnapshot(
                course_ids=list(query.course_ids),
                start_at=query.start_at,
                end_at=query.end_at,
            ),
            generated_at=NOW,
        )

    def research(self, query):
        return calculate_research_metrics(
            [],
            filters=AnalyticsFilterSnapshot(
                course_ids=list(query.course_ids),
                start_at=query.start_at,
                end_at=query.end_at,
            ),
            generated_at=NOW,
        )

    async def inactive_learners(self, query, *, page, page_size):
        return InactiveLearnerPage(
            filters=AnalyticsFilterSnapshot(
                course_ids=list(query.course_ids),
                start_at=query.start_at,
                end_at=query.end_at,
            ),
            generated_at=NOW,
            inactive_learner_count=MetricValue(
                value=0,
                numerator=0,
                denominator=0,
                sample_size=0,
                unit="learners",
            ),
            items=[],
            page=page,
            page_size=page_size,
            total=0,
        )


@pytest.fixture(autouse=True)
def overrides():
    app.dependency_overrides[get_authenticated_actor] = lambda: AuthenticatedActor(
        actor_reference="educator-1",
        role="educator",
    )
    app.dependency_overrides[get_analytics_application] = lambda: Application()
    yield
    app.dependency_overrides.clear()


def test_research_analytics_intersects_course_scope_and_returns_contract() -> None:
    app.dependency_overrides[get_analytics_access_policy] = lambda: Policy({"course-1"})
    response = TestClient(app).get(
        "/api/v1/analytics/research",
        params={
            "course_id": "course-1",
            "date_from": (NOW - timedelta(days=30)).isoformat(),
            "date_to": NOW.isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.json()["schema_version"] == "research-metrics-v1"
    assert response.json()["filters"]["course_ids"] == ["course-1"]
    assert response.headers["cache-control"] == "no-store"
    UUID(response.headers["x-correlation-id"])


def test_learning_summary_returns_only_bounded_inactive_aggregate() -> None:
    app.dependency_overrides[get_analytics_access_policy] = lambda: Policy({"course-1"})

    response = TestClient(app).get(
        "/api/v1/analytics/learning",
        params={"course_id": "course-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["inactive_learner_count"]["value"] == 0
    assert "inactive_learners" not in payload


def test_analytics_denies_cross_course_and_sanitizes_invalid_pagination() -> None:
    app.dependency_overrides[get_analytics_access_policy] = lambda: Policy({"course-1"})
    denied = TestClient(app).get(
        "/api/v1/analytics/research",
        params={"course_id": "course-private"},
    )
    invalid = TestClient(app).get(
        "/api/v1/analytics/inactive-learners",
        params={"course_id": "course-1", "page_size": 101},
    )

    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "analytics_forbidden"
    assert "course-private" not in denied.text
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_analytics_request"


def test_inactive_page_has_complete_metric_envelope() -> None:
    app.dependency_overrides[get_analytics_access_policy] = lambda: Policy({"course-1"})

    response = TestClient(app).get(
        "/api/v1/analytics/inactive-learners",
        params={"course_id": "course-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "inactive-learners-v1"
    assert payload["filters"]["course_ids"] == ["course-1"]
    assert payload["inactive_learner_count"] == {
        "value": 0.0,
        "numerator": 0.0,
        "denominator": 0,
        "sample_size": 0,
        "unit": "learners",
    }
    assert payload["excluded_incomplete_count"] == 0


def test_filter_options_reject_unbounded_authorization_scope() -> None:
    app.dependency_overrides[get_analytics_access_policy] = lambda: Policy(
        {f"course-{index}" for index in range(1_001)}
    )

    response = TestClient(app).get("/api/v1/analytics/filter-options")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "analytics_scope_unavailable"
