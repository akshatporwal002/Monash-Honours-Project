from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import Engine, delete, or_, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import BUILTIN_OFFLINE_WORKER_ADAPTER_FACTORY, Settings
from app.db.session import engine as application_engine
from app.models.worker import WORKER_HEARTBEAT_SLOT, WorkerHeartbeat
from app.schemas.health import ReadinessResponse

MIGRATION_HEAD = "20260816_0021"


class WorkerHeartbeatRepository(Protocol):
    def acquire(
        self,
        worker_id: str,
        observed_at: datetime,
        ownership_timeout: timedelta,
    ) -> bool: ...

    def renew(self, worker_id: str, observed_at: datetime) -> bool: ...

    def release(self, worker_id: str) -> bool: ...

    def latest(self) -> tuple[str, datetime] | None: ...


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _valid_uuid4(value: str) -> bool:
    try:
        parsed = UUID(value)
    except ValueError:
        return False
    return parsed.version == 4 and str(parsed) == value.lower()


def _database_exists(engine: Engine) -> bool:
    if engine.url.get_backend_name() != "sqlite":
        return True
    database = engine.url.database
    if database in {None, "", ":memory:"}:
        return True
    return Path(database).exists()


class SqlAlchemyWorkerHeartbeatRepository:
    """Owns the singleton worker slot without surfacing database errors."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def acquire(
        self,
        worker_id: str,
        observed_at: datetime,
        ownership_timeout: timedelta,
    ) -> bool:
        if (
            not _valid_uuid4(worker_id)
            or ownership_timeout <= timedelta(0)
            or not self._database_exists()
        ):
            return False
        timestamp = _as_utc(observed_at)
        stale_before = timestamp - ownership_timeout
        with Session(self._engine) as session:
            try:
                result = session.execute(
                    update(WorkerHeartbeat)
                    .where(
                        WorkerHeartbeat.slot == WORKER_HEARTBEAT_SLOT,
                        or_(
                            WorkerHeartbeat.worker_id == worker_id,
                            WorkerHeartbeat.last_heartbeat_at <= stale_before,
                        ),
                    )
                    .values(
                        worker_id=worker_id,
                        last_heartbeat_at=timestamp,
                    )
                )
                if result.rowcount == 1:
                    session.commit()
                    return True
                existing = session.get(WorkerHeartbeat, WORKER_HEARTBEAT_SLOT)
                if existing is None:
                    session.add(
                        WorkerHeartbeat(
                            slot=WORKER_HEARTBEAT_SLOT,
                            worker_id=worker_id,
                            last_heartbeat_at=timestamp,
                        )
                    )
                else:
                    session.rollback()
                    return False
                session.commit()
                return True
            except IntegrityError:
                session.rollback()
                return False
            except SQLAlchemyError:
                session.rollback()
                return False

    def renew(self, worker_id: str, observed_at: datetime) -> bool:
        if not _valid_uuid4(worker_id) or not self._database_exists():
            return False
        with Session(self._engine) as session:
            try:
                result = session.execute(
                    update(WorkerHeartbeat)
                    .where(
                        WorkerHeartbeat.slot == WORKER_HEARTBEAT_SLOT,
                        WorkerHeartbeat.worker_id == worker_id,
                    )
                    .values(last_heartbeat_at=_as_utc(observed_at))
                )
                session.commit()
                return result.rowcount == 1
            except SQLAlchemyError:
                session.rollback()
                return False

    def release(self, worker_id: str) -> bool:
        if not _valid_uuid4(worker_id) or not self._database_exists():
            return False
        with Session(self._engine) as session:
            try:
                result = session.execute(
                    delete(WorkerHeartbeat).where(
                        WorkerHeartbeat.slot == WORKER_HEARTBEAT_SLOT,
                        WorkerHeartbeat.worker_id == worker_id,
                    )
                )
                session.commit()
                return result.rowcount == 1
            except SQLAlchemyError:
                session.rollback()
                return False

    def record(self, worker_id: str, observed_at: datetime) -> bool:
        """Compatibility helper that cannot replace a fresh different owner."""
        return self.acquire(
            worker_id,
            observed_at,
            timedelta(seconds=120),
        )

    def latest(self) -> tuple[str, datetime] | None:
        if not self._database_exists():
            return None
        with Session(self._engine) as session:
            try:
                heartbeat = session.get(
                    WorkerHeartbeat,
                    WORKER_HEARTBEAT_SLOT,
                )
            except SQLAlchemyError:
                session.rollback()
                return None
            if heartbeat is None:
                return None
            return heartbeat.worker_id, _as_utc(heartbeat.last_heartbeat_at)

    def _database_exists(self) -> bool:
        return _database_exists(self._engine)


class WorkerHealthRegistry:
    def __init__(
        self,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        worker_id: str | None = None,
        repository: WorkerHeartbeatRepository | None = None,
        ownership_timeout: timedelta = timedelta(seconds=120),
    ) -> None:
        self._now = now
        self._worker_id = worker_id or str(uuid4())
        if not _valid_uuid4(self._worker_id):
            raise ValueError("worker_id must be a UUIDv4")
        if ownership_timeout <= timedelta(0):
            raise ValueError("ownership_timeout must be positive")
        self._repository = repository
        self._ownership_timeout = ownership_timeout
        self._last_heartbeat: datetime | None = None
        self._owns_slot = False
        self._lock = Lock()

    def heartbeat(self) -> bool:
        observed_at = _as_utc(self._now())
        with self._lock:
            owns_slot = self._owns_slot
        if self._repository is None:
            updated = True
        elif owns_slot:
            updated = self._repository.renew(self._worker_id, observed_at)
        else:
            updated = self._repository.acquire(
                self._worker_id,
                observed_at,
                self._ownership_timeout,
            )
        with self._lock:
            self._owns_slot = updated
            self._last_heartbeat = observed_at if updated else None
        return updated

    def release(self) -> bool:
        with self._lock:
            owned = self._owns_slot
            self._owns_slot = False
            self._last_heartbeat = None
        if self._repository is None:
            return owned
        return owned and self._repository.release(self._worker_id)

    def healthy(self, maximum_age: timedelta) -> bool:
        if maximum_age <= timedelta(0):
            return False
        observed_at = _as_utc(self._now())
        with self._lock:
            heartbeat = self._last_heartbeat
        if heartbeat is not None and self._fresh(
            observed_at,
            heartbeat,
            maximum_age,
        ):
            return True
        if self._repository is None:
            return False
        durable = self._repository.latest()
        if durable is None:
            return False
        worker_id, heartbeat = durable
        return _valid_uuid4(worker_id) and self._fresh(
            observed_at,
            heartbeat,
            maximum_age,
        )

    @staticmethod
    def _fresh(
        observed_at: datetime,
        heartbeat: datetime,
        maximum_age: timedelta,
    ) -> bool:
        age = observed_at - _as_utc(heartbeat)
        return -timedelta(seconds=5) <= age <= maximum_age


class ReadinessProbe:
    def __init__(
        self,
        engine: Engine,
        settings: Settings,
        worker_health: WorkerHealthRegistry,
    ) -> None:
        self._engine = engine
        self._settings = settings
        self._worker_health = worker_health

    def check(self) -> ReadinessResponse:
        checks = {
            "database": self._database_ready(),
            "migrations": self._migration_ready(),
            "worker": self._worker_health.healthy(
                timedelta(seconds=self._settings.worker_stale_seconds)
            ),
            "pseudonym_secret": self._secret_ready(),
            "production_adapters": (
                self._production_adapters_ready() if self._settings.production else True
            ),
            "llm_credentials": (
                self._llm_credentials_ready() if self._settings.production else True
            ),
        }
        return ReadinessResponse(
            status="ready" if all(checks.values()) else "not_ready",
            checks={name: "ready" if ready else "not_ready" for name, ready in checks.items()},
        )

    def _database_ready(self) -> bool:
        if not _database_exists(self._engine):
            return False
        try:
            with self._engine.connect() as connection:
                return connection.execute(text("SELECT 1")).scalar_one() == 1
        except Exception:
            return False

    def _migration_ready(self) -> bool:
        if not _database_exists(self._engine):
            return False
        try:
            with self._engine.connect() as connection:
                version = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
            return version == MIGRATION_HEAD
        except Exception:
            return False

    def _secret_ready(self) -> bool:
        secret = self._settings.learning_event_pseudonym_secret
        return secret is not None and len(secret.get_secret_value().encode("utf-8")) >= 32

    def _production_adapters_ready(self) -> bool:
        return self._settings.production_adapters_ready or (
            not self._settings.research_enabled
            and self._settings.worker_adapter_factory == BUILTIN_OFFLINE_WORKER_ADAPTER_FACTORY
        )

    def _llm_credentials_ready(self) -> bool:
        if not self._settings.research_enabled:
            return True
        key = self._settings.llm_api_key
        return bool(key and key.get_secret_value())


worker_health = WorkerHealthRegistry(
    repository=SqlAlchemyWorkerHeartbeatRepository(application_engine)
)
