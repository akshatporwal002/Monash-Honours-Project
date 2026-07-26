from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app.core.config import BUILTIN_OFFLINE_WORKER_ADAPTER_FACTORY, Settings
from app.core.readiness import (
    MIGRATION_HEAD,
    ReadinessProbe,
    SqlAlchemyWorkerHeartbeatRepository,
    WorkerHealthRegistry,
)
from app.db.base import Base
from app.db.session import create_db_engine
from app.worker import WorkerConfigurationError, load_worker_adapters


def _production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "app_env": "production",
        "frontend_origin": "https://learn.example.edu",
        "cors_allowed_origins": "https://learn.example.edu",
        "learning_event_pseudonym_secret": "p" * 32,
        "session_secret_key": "s" * 32,
        "session_cookie_secure": True,
        "research_enabled": False,
        "worker_adapter_factory": BUILTIN_OFFLINE_WORKER_ADAPTER_FACTORY,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"session_secret_key": "short"}, "at least 32 bytes"),
        ({"session_secret_key": "p" * 32}, "distinct"),
        ({"frontend_origin": "http://learn.example.edu"}, "must use HTTPS"),
        (
            {"cors_allowed_origins": "https://learn.example.edu,http://admin.example.edu"},
            "must use HTTPS",
        ),
    ],
)
def test_production_settings_reject_weak_secrets_and_http_origins(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        _production_settings(**overrides)


def test_builtin_worker_factory_is_offline_and_fails_if_research_is_enabled() -> None:
    adapters = load_worker_adapters(
        BUILTIN_OFFLINE_WORKER_ADAPTER_FACTORY,
        Settings(_env_file=None, research_enabled=False),
    )

    assert callable(adapters.feedback_pipeline_factory)
    assert callable(adapters.progress_adapter.record_terminal_feedback)
    assert callable(adapters.next_task_recommender.recommend_next_task)

    with pytest.raises(WorkerConfigurationError, match="factory is unavailable"):
        load_worker_adapters(
            BUILTIN_OFFLINE_WORKER_ADAPTER_FACTORY,
            Settings(_env_file=None, research_enabled=True),
        )


def test_hosted_readiness_accepts_builtin_offline_worker_without_model_credentials(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "hosted-ready.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    engine = create_db_engine(database_url)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
        )
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:head)"),
            {"head": MIGRATION_HEAD},
        )

    observed_at = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
    repository = SqlAlchemyWorkerHeartbeatRepository(engine)
    writer = WorkerHealthRegistry(
        now=lambda: observed_at,
        worker_id=str(uuid4()),
        repository=repository,
    )
    reader = WorkerHealthRegistry(now=lambda: observed_at, repository=repository)
    assert writer.heartbeat()

    configured = _production_settings(database_url=database_url)
    result = ReadinessProbe(engine, configured, reader).check()

    assert result.status == "ready"
    assert result.checks["worker"] == "ready"
    assert result.checks["production_adapters"] == "ready"
    assert result.checks["llm_credentials"] == "ready"

    writer.release()
    Base.metadata.drop_all(engine)
    engine.dispose()
