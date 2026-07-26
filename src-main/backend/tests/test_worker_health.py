from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy import text

from app.core.config import Settings
from app.core.readiness import (
    MIGRATION_HEAD,
    ReadinessProbe,
    SqlAlchemyWorkerHeartbeatRepository,
    WorkerHealthRegistry,
)
from app.db.base import Base
from app.db.session import create_db_engine
from app.models.worker import WORKER_HEARTBEAT_SLOT, WorkerHeartbeat

NOW = datetime(2026, 7, 26, 9, 0, tzinfo=UTC)


def test_readiness_observes_a_heartbeat_from_another_registry(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "worker-health.db"
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

    repository = SqlAlchemyWorkerHeartbeatRepository(engine)
    writer_id = str(uuid4())
    writer = WorkerHealthRegistry(
        now=lambda: NOW,
        worker_id=writer_id,
        repository=repository,
    )
    reader_clock = [NOW]
    reader = WorkerHealthRegistry(
        now=lambda: reader_clock[0],
        repository=repository,
    )
    writer.heartbeat()

    settings = Settings(
        database_url=database_url,
        learning_event_pseudonym_secret=SecretStr("s" * 32),
        worker_stale_seconds=120,
    )
    result = ReadinessProbe(engine, settings, reader).check()

    assert result.status == "ready"
    assert result.checks["worker"] == "ready"
    with engine.connect() as connection:
        row = (
            connection.execute(
                text("SELECT slot, worker_id, last_heartbeat_at FROM worker_heartbeats")
            )
            .mappings()
            .one()
        )
    assert row["slot"] == WORKER_HEARTBEAT_SLOT
    assert row["worker_id"] == writer_id
    assert UUID(row["worker_id"]).version == 4

    reader_clock[0] = NOW + timedelta(seconds=121)
    stale = ReadinessProbe(engine, settings, reader).check()
    assert stale.status == "not_ready"
    assert stale.checks["worker"] == "not_ready"

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_missing_sqlite_database_is_not_created_by_a_heartbeat(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "not-migrated.db"
    engine = create_db_engine(f"sqlite:///{database_path.as_posix()}")
    repository = SqlAlchemyWorkerHeartbeatRepository(engine)

    assert repository.record(str(uuid4()), NOW) is False
    assert repository.latest() is None
    assert database_path.exists() is False

    engine.dispose()


def test_readiness_does_not_create_a_missing_sqlite_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "missing-readiness.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    engine = create_db_engine(database_url)
    repository = SqlAlchemyWorkerHeartbeatRepository(engine)
    settings = Settings(
        database_url=database_url,
        learning_event_pseudonym_secret=SecretStr("s" * 32),
    )

    result = ReadinessProbe(
        engine,
        settings,
        WorkerHealthRegistry(repository=repository),
    ).check()

    assert result.status == "not_ready"
    assert result.checks["database"] == "not_ready"
    assert result.checks["migrations"] == "not_ready"
    assert database_path.exists() is False
    engine.dispose()


def test_worker_heartbeat_singleton_rejects_non_primary_rows(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "worker-health-constraint.db"
    engine = create_db_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        failed = False
        try:
            connection.execute(
                WorkerHeartbeat.__table__.insert().values(
                    slot="secondary",
                    worker_id=str(uuid4()),
                    last_heartbeat_at=NOW,
                )
            )
        except Exception:
            failed = True
    assert failed is True

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_fresh_worker_owner_cannot_be_overwritten_and_can_release(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "worker-exclusive.db"
    engine = create_db_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyWorkerHeartbeatRepository(engine)
    first_id = str(uuid4())
    second_id = str(uuid4())
    first = WorkerHealthRegistry(
        now=lambda: NOW,
        worker_id=first_id,
        repository=repository,
        ownership_timeout=timedelta(seconds=120),
    )
    second = WorkerHealthRegistry(
        now=lambda: NOW,
        worker_id=second_id,
        repository=repository,
        ownership_timeout=timedelta(seconds=120),
    )

    assert first.heartbeat() is True
    assert second.heartbeat() is False
    assert repository.latest() == (first_id, NOW)
    assert first.release() is True
    assert second.heartbeat() is True
    assert repository.latest() == (second_id, NOW)

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_stale_worker_owner_is_taken_over_and_old_owner_is_fenced(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "worker-stale-takeover.db"
    engine = create_db_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyWorkerHeartbeatRepository(engine)
    first_clock = [NOW]
    second_clock = [NOW + timedelta(seconds=121)]
    first = WorkerHealthRegistry(
        now=lambda: first_clock[0],
        worker_id=str(uuid4()),
        repository=repository,
        ownership_timeout=timedelta(seconds=120),
    )
    second = WorkerHealthRegistry(
        now=lambda: second_clock[0],
        worker_id=str(uuid4()),
        repository=repository,
        ownership_timeout=timedelta(seconds=120),
    )

    assert first.heartbeat() is True
    assert second.heartbeat() is True
    winner = repository.latest()
    assert winner is not None
    first_clock[0] = NOW + timedelta(seconds=122)
    assert first.heartbeat() is False
    assert repository.latest() == winner
    assert first.release() is False

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_concurrent_worker_start_allows_exactly_one_owner(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "worker-owner-race.db"
    engine = create_db_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)

    def acquire(worker_id: str) -> bool:
        return WorkerHealthRegistry(
            now=lambda: NOW,
            worker_id=worker_id,
            repository=SqlAlchemyWorkerHeartbeatRepository(engine),
            ownership_timeout=timedelta(seconds=120),
        ).heartbeat()

    worker_ids = [str(uuid4()), str(uuid4())]
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(acquire, worker_ids))

    assert sorted(results) == [False, True]
    latest = SqlAlchemyWorkerHeartbeatRepository(engine).latest()
    assert latest is not None
    assert latest[0] in worker_ids

    Base.metadata.drop_all(engine)
    engine.dispose()
