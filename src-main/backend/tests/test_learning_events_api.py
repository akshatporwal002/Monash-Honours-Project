from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.feedback_dependencies import get_authenticated_actor
from app.api.learning_event_dependencies import (
    get_learning_event_access_policy,
    get_learning_event_recorder,
)
from app.db.base import Base
from app.db.session import create_db_engine, create_session_factory
from app.main import app
from app.models import LearningEvent
from app.schemas.feedback_api import AuthenticatedActor
from app.services.learning_events import (
    HmacSha256Pseudonymizer,
    LearningEventRecorder,
    LearningEventScope,
)

SECRET = "api-event-secret-that-is-at-least-32-bytes"
ACTOR = AuthenticatedActor(actor_reference="student-private", role="student")


class TaskScopePolicy:
    def __init__(self, scope: LearningEventScope | None) -> None:
        self.scope = scope
        self.calls: list[tuple[AuthenticatedActor, str]] = []

    async def resolve_task_scope(
        self,
        actor: AuthenticatedActor,
        task_id: str,
    ) -> LearningEventScope | None:
        self.calls.append((actor, task_id))
        return self.scope


@pytest.fixture
def api_event_store(
    tmp_path: Path,
) -> tuple[sessionmaker[Session], LearningEventRecorder]:
    database_path = tmp_path / "learning-events-api.db"
    engine = create_db_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    event_recorder = LearningEventRecorder(
        factory,
        HmacSha256Pseudonymizer(SECRET),
    )
    yield factory, event_recorder
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def reset_dependencies() -> None:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def configure(
    recorder: LearningEventRecorder,
    *,
    scope: LearningEventScope | None = LearningEventScope(
        course_id="course-private",
        task_id="task-1",
    ),
) -> TaskScopePolicy:
    policy = TaskScopePolicy(scope)
    app.dependency_overrides[get_authenticated_actor] = lambda: ACTOR
    app.dependency_overrides[get_learning_event_access_policy] = lambda: policy
    app.dependency_overrides[get_learning_event_recorder] = lambda: recorder
    return policy


def event_body(*, event_id: str | None = None, source: str = "task-page") -> dict[str, object]:
    return {
        "event_id": event_id or str(uuid4()),
        "event_type": "task_view",
        "task_id": "task-1",
        "metadata": {"source": source},
    }


def test_browser_endpoint_derives_private_scope_and_exact_replay_is_idempotent(
    api_event_store: tuple[sessionmaker[Session], LearningEventRecorder],
) -> None:
    factory, event_recorder = api_event_store
    policy = configure(event_recorder)
    body = event_body()
    correlation_id = str(uuid4())
    client = TestClient(app)

    first = client.post(
        "/api/v1/learning-events",
        json=body,
        headers={"X-Correlation-ID": correlation_id},
    )
    second = client.post("/api/v1/learning-events", json=body)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["occurred_at"].endswith("Z")
    assert first.headers["cache-control"] == "no-store"
    assert first.headers["x-correlation-id"] == correlation_id
    assert policy.calls == [(ACTOR, "task-1"), (ACTOR, "task-1")]

    with factory() as session:
        stored = session.scalar(select(LearningEvent))
        assert stored is not None
        assert stored.course_id == "course-private"
        assert stored.task_id == "task-1"
        assert stored.correlation_id == correlation_id
        assert stored.metadata_payload == {"source": "task-page"}
        assert stored.pseudonymous_user_id.startswith("v1_")
        assert "student-private" not in stored.pseudonymous_user_id


def test_conflicting_browser_event_uuid_returns_sanitized_409(
    api_event_store: tuple[sessionmaker[Session], LearningEventRecorder],
) -> None:
    _, event_recorder = api_event_store
    configure(event_recorder)
    event_id = str(uuid4())
    client = TestClient(app)
    assert (
        client.post(
            "/api/v1/learning-events",
            json=event_body(event_id=event_id, source="first"),
        ).status_code
        == 201
    )

    conflict = client.post(
        "/api/v1/learning-events",
        json=event_body(event_id=event_id, source="different"),
    )

    assert conflict.status_code == 409
    assert conflict.json() == {
        "error": {
            "code": "learning_event_conflict",
            "message": "The event identifier has already been used.",
        }
    }


def test_browser_cannot_supply_actor_course_timestamp_workflow_or_trusted_event_types(
    api_event_store: tuple[sessionmaker[Session], LearningEventRecorder],
) -> None:
    factory, event_recorder = api_event_store
    configure(event_recorder)
    private_marker = "PRIVATE-ANSWER-MARKER"
    client = TestClient(app)

    private_fields = client.post(
        "/api/v1/learning-events",
        json={
            **event_body(),
            "actor_reference": "other-student",
            "course_id": "other-course",
            "occurred_at": "2026-01-01T00:00:00Z",
            "workflow_reference": str(uuid4()),
            "metadata": {"answer": private_marker},
        },
    )
    trusted_type = client.post(
        "/api/v1/learning-events",
        json={
            "event_id": str(uuid4()),
            "event_type": "submission",
            "task_id": "task-1",
            "metadata": {"attempt_number": 1},
        },
    )

    assert private_fields.status_code == 422
    assert trusted_type.status_code == 422
    assert private_fields.json()["error"]["code"] == "invalid_learning_event"
    assert private_fields.headers["cache-control"] == "no-store"
    assert private_fields.headers["x-correlation-id"]
    assert private_marker not in private_fields.text
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(LearningEvent)) == 0


def test_task_scope_authorization_fails_closed_without_resource_leak(
    api_event_store: tuple[sessionmaker[Session], LearningEventRecorder],
) -> None:
    _, event_recorder = api_event_store
    configure(event_recorder, scope=None)

    denied = TestClient(app).post("/api/v1/learning-events", json=event_body())

    assert denied.status_code == 404
    assert denied.json()["error"] == {
        "code": "learning_event_task_not_found",
        "message": "The task was not found.",
    }


def test_unconfigured_endpoint_fails_closed() -> None:
    response = TestClient(app).post("/api/v1/learning-events", json=event_body())

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "authentication_unavailable"
