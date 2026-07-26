from __future__ import annotations

import asyncio
import importlib
import logging
import re
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast
from uuid import uuid4

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, settings
from app.core.readiness import (
    SqlAlchemyWorkerHeartbeatRepository,
    WorkerHealthRegistry,
)
from app.db.session import SessionLocal
from app.db.session import engine as application_engine
from app.schemas.feedback import FeedbackContext, GeneratedFeedback, JudgeEvaluationOutcome
from app.services.audit import BestEffortAuditSink, IndependentAuditRecorder
from app.services.audit_events import FeedbackAuditEvents
from app.services.continuation import (
    ContinuationWorker,
    NextTaskRecommender,
    NextTaskRequest,
    ProgressPersistenceAdapter,
    ProgressUpdate,
    SqlAlchemyContinuationRepository,
)
from app.services.feedback.application import (
    InProcessFeedbackExecutor,
    PipelineFactory,
)
from app.services.feedback.worker import FeedbackRecoveryWorker
from app.services.research import (
    BaselineContextProvider,
    BaselineFeedbackGenerator,
    BaselineJobExecutor,
    BaselineMeasurementJudge,
    SqlAlchemyResearchJobRepository,
)
from app.services.terminal_integrations.worker import TerminalIntegrationWorker

_FACTORY_PATH = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*:"
    r"[A-Za-z_][A-Za-z0-9_]*$"
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class WorkerConfigurationError(RuntimeError):
    """The worker cannot start without every required integration adapter."""


class WorkerOwnershipError(RuntimeError):
    """The durable singleton worker slot is owned by another live process."""


class WorkerPass(Protocol):
    async def run_once(self) -> object: ...


class WorkerOwnership(Protocol):
    def heartbeat(self) -> bool: ...

    def release(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkerAdapters:
    feedback_pipeline_factory: PipelineFactory
    baseline_context_provider: BaselineContextProvider
    baseline_generator: BaselineFeedbackGenerator
    baseline_judge: BaselineMeasurementJudge
    progress_adapter: ProgressPersistenceAdapter
    next_task_recommender: NextTaskRecommender
    feedback_audit_events: FeedbackAuditEvents | None = None
    terminal_reconciliation: WorkerPass | None = None


class _OfflineBaselineContextProvider:
    async def get_context(self, workflow_run_id: str) -> FeedbackContext | None:
        del workflow_run_id
        return None


class _OfflineBaselineGenerator:
    async def generate(
        self,
        context: FeedbackContext,
        *,
        expected_provider: str,
        expected_model: str,
    ) -> GeneratedFeedback:
        del context, expected_provider, expected_model
        raise RuntimeError("research baseline generation is disabled")


class _OfflineBaselineJudge:
    async def evaluate(
        self,
        context: FeedbackContext,
        feedback: GeneratedFeedback,
    ) -> JudgeEvaluationOutcome:
        del context, feedback
        raise RuntimeError("research baseline evaluation is disabled")


class _OfflineProgressAdapter:
    async def record_terminal_feedback(self, update: ProgressUpdate) -> None:
        del update


class _OfflineNextTaskRecommender:
    async def recommend_next_task(self, request: NextTaskRequest) -> str:
        # The LMS records progress synchronously. Reusing the completed task's
        # opaque reference is a deterministic terminal handoff for the MVP.
        return request.completed_task_reference


def build_offline_worker_adapters(configured_settings: Settings) -> WorkerAdapters:
    """Build the durable worker using only adapters shipped with the MVP."""
    if configured_settings.research_enabled:
        raise WorkerConfigurationError(
            "the offline worker adapters require research processing to be disabled"
        )
    from app.services.feedback.runtime import build_feedback_pipeline_for_repository

    return WorkerAdapters(
        feedback_pipeline_factory=build_feedback_pipeline_for_repository,
        baseline_context_provider=_OfflineBaselineContextProvider(),
        baseline_generator=_OfflineBaselineGenerator(),
        baseline_judge=_OfflineBaselineJudge(),
        progress_adapter=_OfflineProgressAdapter(),
        next_task_recommender=_OfflineNextTaskRecommender(),
    )


class _BaselineDatabasePass:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        adapters: WorkerAdapters,
        *,
        now: Callable[[], datetime],
        lease_duration: timedelta,
        provider_timeout_seconds: float,
        maximum_attempts: int,
    ) -> None:
        self._session_factory = session_factory
        self._adapters = adapters
        self._now = now
        self._lease_duration = lease_duration
        self._provider_timeout_seconds = provider_timeout_seconds
        self._maximum_attempts = maximum_attempts

    async def run_once(self) -> bool:
        with self._session_factory() as session:
            executor = BaselineJobExecutor(
                SqlAlchemyResearchJobRepository(
                    session,
                    lease_duration=self._lease_duration,
                ),
                self._adapters.baseline_context_provider,
                self._adapters.baseline_generator,
                self._adapters.baseline_judge,
                provider_timeout_seconds=self._provider_timeout_seconds,
                now=self._now,
                maximum_attempts=self._maximum_attempts,
            )
            return await executor.run_once()


class _ContinuationDatabasePass:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        adapters: WorkerAdapters,
        *,
        now: Callable[[], datetime],
        lease_duration: timedelta,
        provider_timeout_seconds: float,
        maximum_attempts: int,
    ) -> None:
        self._session_factory = session_factory
        self._adapters = adapters
        self._now = now
        self._lease_duration = lease_duration
        self._provider_timeout_seconds = provider_timeout_seconds
        self._maximum_attempts = maximum_attempts

    async def run_once(self) -> object:
        with self._session_factory() as session:
            executor = ContinuationWorker(
                SqlAlchemyContinuationRepository(session),
                self._adapters.progress_adapter,
                self._adapters.next_task_recommender,
                now=self._now,
                lease_duration=self._lease_duration,
                maximum_attempts=self._maximum_attempts,
                adapter_timeout_seconds=self._provider_timeout_seconds,
            )
            return await executor.run_once()


class _TerminalIntegrationDatabasePass:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        now: Callable[[], datetime],
        lease_duration: timedelta,
        maximum_attempts: int,
        additional_pass: WorkerPass | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._now = now
        self._lease_duration = lease_duration
        self._maximum_attempts = maximum_attempts
        self._additional_pass = additional_pass

    async def run_once(self) -> bool:
        with self._session_factory() as session:
            outcome = await TerminalIntegrationWorker(
                session,
                now=self._now,
                lease_duration=self._lease_duration,
                maximum_attempts=self._maximum_attempts,
            ).run_once()
        processed = outcome.processed
        if self._additional_pass is not None:
            processed = _processed(await self._additional_pass.run_once()) or processed
        return processed


class DatabaseWorker:
    """Runs all SQLite job families serially under one durable ownership lease."""

    def __init__(
        self,
        feedback: WorkerPass,
        baseline: WorkerPass,
        continuation: WorkerPass,
        ownership: WorkerOwnership,
        *,
        terminal_reconciliation: WorkerPass | None = None,
        poll_interval_seconds: float = 1,
        heartbeat_interval_seconds: float = 30,
        logger: logging.Logger | None = None,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        if heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be positive")
        passes: list[tuple[str, WorkerPass]] = [("feedback", feedback)]
        if terminal_reconciliation is not None:
            passes.append(("terminal_reconciliation", terminal_reconciliation))
        passes.extend(
            [
                ("baseline", baseline),
                ("continuation", continuation),
            ]
        )
        self._passes = tuple(passes)
        self._ownership = ownership
        self._poll_interval_seconds = poll_interval_seconds
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._logger = logger or logging.getLogger(__name__)

    async def run_once(self) -> bool:
        if not self._ownership.heartbeat():
            raise WorkerOwnershipError("database worker ownership is unavailable")
        return await self._run_passes()

    async def run_forever(self, stop_event: asyncio.Event | None = None) -> None:
        stop = stop_event or asyncio.Event()
        ownership_lost = asyncio.Event()
        if not self._ownership.heartbeat():
            raise WorkerOwnershipError("database worker ownership is unavailable")
        heartbeat_task = asyncio.create_task(self._maintain_ownership(stop, ownership_lost))
        try:
            while not stop.is_set():
                if ownership_lost.is_set():
                    raise WorkerOwnershipError("database worker ownership was lost")
                processed = await self._run_passes()
                if ownership_lost.is_set():
                    raise WorkerOwnershipError("database worker ownership was lost")
                if not processed:
                    try:
                        await asyncio.wait_for(
                            stop.wait(),
                            timeout=self._poll_interval_seconds,
                        )
                    except TimeoutError:
                        pass
                else:
                    await asyncio.sleep(0)
        finally:
            stop.set()
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task
            self._ownership.release()

    async def _run_passes(self) -> bool:
        processed = False
        for queue_name, worker_pass in self._passes:
            try:
                outcome = await worker_pass.run_once()
            except Exception:
                self._log_pass_failure(queue_name)
                continue
            processed = _processed(outcome) or processed
        return processed

    async def _maintain_ownership(
        self,
        stop: asyncio.Event,
        ownership_lost: asyncio.Event,
    ) -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(
                    stop.wait(),
                    timeout=self._heartbeat_interval_seconds,
                )
            except TimeoutError:
                if not self._ownership.heartbeat():
                    ownership_lost.set()
                    return

    def _log_pass_failure(self, queue_name: str) -> None:
        try:
            self._logger.warning(
                "database_worker_pass_failed",
                extra={
                    "stage": queue_name,
                    "failure_category": "worker_pass_unavailable",
                },
            )
        except Exception:
            pass


def _processed(outcome: object) -> bool:
    if isinstance(outcome, bool):
        return outcome
    return getattr(outcome, "processed", False) is True


def build_database_worker(
    adapters: WorkerAdapters,
    *,
    configured_settings: Settings = settings,
    engine: Engine = application_engine,
    session_factory: sessionmaker[Session] = SessionLocal,
    now: Callable[[], datetime] = _utc_now,
    worker_id: str | None = None,
) -> DatabaseWorker:
    lease_duration = timedelta(seconds=configured_settings.feedback_job_lease_seconds)
    audit_events = adapters.feedback_audit_events
    if audit_events is None:
        recorder = IndependentAuditRecorder(session_factory)
        audit_events = FeedbackAuditEvents(BestEffortAuditSink(lambda: recorder))
    feedback_executor = InProcessFeedbackExecutor(
        session_factory,
        adapters.feedback_pipeline_factory,
        now=now,
        audit_events=audit_events,
    )
    feedback_pass = FeedbackRecoveryWorker(
        session_factory,
        feedback_executor,
        now=now,
        lease_duration=lease_duration,
        audit_events=audit_events,
    )
    baseline_pass = _BaselineDatabasePass(
        session_factory,
        adapters,
        now=now,
        lease_duration=lease_duration,
        provider_timeout_seconds=configured_settings.provider_timeout_seconds,
        maximum_attempts=configured_settings.max_infrastructure_attempts,
    )
    continuation_pass = _ContinuationDatabasePass(
        session_factory,
        adapters,
        now=now,
        lease_duration=lease_duration,
        provider_timeout_seconds=configured_settings.provider_timeout_seconds,
        maximum_attempts=configured_settings.max_infrastructure_attempts,
    )
    terminal_reconciliation = _TerminalIntegrationDatabasePass(
        session_factory,
        now=now,
        lease_duration=lease_duration,
        maximum_attempts=configured_settings.max_infrastructure_attempts,
        additional_pass=adapters.terminal_reconciliation,
    )
    ownership = WorkerHealthRegistry(
        now=now,
        worker_id=worker_id or str(uuid4()),
        repository=SqlAlchemyWorkerHeartbeatRepository(engine),
        ownership_timeout=timedelta(seconds=configured_settings.worker_stale_seconds),
    )
    return DatabaseWorker(
        feedback_pass,
        baseline_pass,
        continuation_pass,
        ownership,
        terminal_reconciliation=terminal_reconciliation,
        poll_interval_seconds=configured_settings.worker_poll_seconds,
        heartbeat_interval_seconds=configured_settings.worker_heartbeat_seconds,
    )


def load_worker_adapters(
    factory_path: str,
    configured_settings: Settings,
) -> WorkerAdapters:
    if not _FACTORY_PATH.fullmatch(factory_path):
        raise WorkerConfigurationError("worker adapter factory is not configured")
    module_name, factory_name = factory_path.split(":", 1)
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, factory_name)
        adapters = factory(configured_settings)
    except Exception:
        raise WorkerConfigurationError("worker adapter factory is unavailable") from None
    if not isinstance(adapters, WorkerAdapters) or not _valid_adapters(adapters):
        raise WorkerConfigurationError("worker adapter factory returned an invalid value")
    return cast(WorkerAdapters, adapters)


def _valid_adapters(adapters: WorkerAdapters) -> bool:
    required_methods = (
        (adapters.baseline_context_provider, "get_context"),
        (adapters.baseline_generator, "generate"),
        (adapters.baseline_judge, "evaluate"),
        (adapters.progress_adapter, "record_terminal_feedback"),
        (adapters.next_task_recommender, "recommend_next_task"),
    )
    return callable(adapters.feedback_pipeline_factory) and all(
        callable(getattr(adapter, method, None)) for adapter, method in required_methods
    )


def create_configured_worker(
    configured_settings: Settings = settings,
) -> DatabaseWorker:
    adapters = load_worker_adapters(
        configured_settings.worker_adapter_factory,
        configured_settings,
    )
    return build_database_worker(
        adapters,
        configured_settings=configured_settings,
    )


def main() -> int:
    try:
        worker = create_configured_worker()
        asyncio.run(worker.run_forever())
    except KeyboardInterrupt:
        return 0
    except WorkerConfigurationError:
        logging.getLogger(__name__).error(
            "database_worker_start_failed",
            extra={"failure_category": "worker_configuration_unavailable"},
        )
        return 2
    except WorkerOwnershipError:
        logging.getLogger(__name__).error(
            "database_worker_start_failed",
            extra={"failure_category": "worker_ownership_unavailable"},
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
