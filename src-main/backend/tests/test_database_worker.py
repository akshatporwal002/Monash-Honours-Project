import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.db.base import Base
from app.db.session import create_db_engine, create_session_factory
from app.models import WorkflowRun, WorkflowStage
from app.models.audit import AuditAction, AuditEvent, AuditOutcome
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository
from app.services.feedback.worker import FeedbackRecoveryWorker
from app.worker import (
    DatabaseWorker,
    WorkerAdapters,
    WorkerConfigurationError,
    build_database_worker,
    load_worker_adapters,
)

NOW = datetime(2026, 7, 26, 12, 0, tzinfo=UTC)
LEASE = timedelta(minutes=5)


class RecordingFeedbackExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None, str | None]] = []

    async def execute(
        self,
        workflow_run_id: str,
        submission_id: str,
        execution_token: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        self.calls.append(
            (
                workflow_run_id,
                submission_id,
                execution_token,
                correlation_id,
            )
        )


def test_feedback_worker_reclaims_an_expired_claim_without_another_post(
    tmp_path: Path,
) -> None:
    engine = create_db_engine(f"sqlite:///{(tmp_path / 'feedback-recovery.db').as_posix()}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        repository = SqlAlchemyFeedbackWorkflowRepository(session)
        stale = repository.claim_workflow(
            "submission-expired",
            str(uuid4()),
            started_at=NOW,
            lease_expires_at=NOW + LEASE,
        )
        repository.record_stage(
            stale.workflow_run_id,
            WorkflowStage.GENERATING,
            execution_token=stale.execution_token,
        )

    executor = RecordingFeedbackExecutor()
    worker = FeedbackRecoveryWorker(
        session_factory,
        executor,
        now=lambda: NOW + LEASE,
        lease_duration=LEASE,
    )

    assert asyncio.run(worker.run_once()) is True
    assert len(executor.calls) == 1
    workflow_id, submission_id, execution_token, correlation_id = executor.calls[0]
    assert workflow_id == stale.workflow_run_id
    assert submission_id == "submission-expired"
    assert execution_token is not None
    assert execution_token != stale.execution_token
    assert correlation_id == workflow_id
    with session_factory() as session:
        stored = session.get(WorkflowRun, workflow_id)
        assert stored is not None
        assert stored.execution_attempt_count == 2
        assert stored.execution_token == execution_token

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_feedback_worker_claims_a_due_retry_without_another_post(
    tmp_path: Path,
) -> None:
    engine = create_db_engine(f"sqlite:///{(tmp_path / 'feedback-retry.db').as_posix()}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    retry_at = NOW + timedelta(seconds=5)
    with session_factory() as session:
        repository = SqlAlchemyFeedbackWorkflowRepository(session)
        failed = repository.claim_workflow(
            "submission-retry",
            str(uuid4()),
            started_at=NOW,
            lease_expires_at=NOW + LEASE,
        )
        repository.mark_failed(
            failed.workflow_run_id,
            "context_unavailable",
            NOW,
            execution_token=failed.execution_token,
            retryable=True,
            next_retry_at=retry_at,
        )

    executor = RecordingFeedbackExecutor()
    worker = FeedbackRecoveryWorker(
        session_factory,
        executor,
        now=lambda: retry_at,
        lease_duration=LEASE,
    )

    assert asyncio.run(worker.run_once()) is True
    assert len(executor.calls) == 1
    assert executor.calls[0][1] == "submission-retry"
    with session_factory() as session:
        stored = session.get(WorkflowRun, failed.workflow_run_id)
        assert stored is not None
        assert stored.current_stage is WorkflowStage.PENDING
        assert stored.execution_attempt_count == 2
        assert stored.next_retry_at is None

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_feedback_worker_terminally_fails_an_expired_third_attempt(
    tmp_path: Path,
) -> None:
    engine = create_db_engine(f"sqlite:///{(tmp_path / 'feedback-exhausted.db').as_posix()}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    observed_at = NOW
    with session_factory() as session:
        repository = SqlAlchemyFeedbackWorkflowRepository(session)
        claim = repository.claim_workflow(
            "submission-exhausted",
            str(uuid4()),
            started_at=observed_at,
            lease_expires_at=observed_at + LEASE,
        )
        for _ in range(2):
            repository.mark_failed(
                claim.workflow_run_id,
                "context_unavailable",
                observed_at,
                execution_token=claim.execution_token,
                retryable=True,
                next_retry_at=observed_at,
            )
            observed_at += timedelta(seconds=1)
            claim = repository.claim_workflow(
                claim.submission_id,
                str(uuid4()),
                started_at=observed_at,
                lease_expires_at=observed_at + LEASE,
            )
        assert claim.execution_attempt_count == 3

    executor = RecordingFeedbackExecutor()
    worker = FeedbackRecoveryWorker(
        session_factory,
        executor,
        now=lambda: observed_at + LEASE,
        lease_duration=LEASE,
    )

    assert asyncio.run(worker.run_once()) is True
    assert executor.calls == []
    with session_factory() as session:
        stored = session.get(WorkflowRun, claim.workflow_run_id)
        assert stored is not None
        assert stored.current_stage is WorkflowStage.FAILED
        assert stored.failure_category == "retry_attempts_exhausted"
        assert stored.execution_token is None

    Base.metadata.drop_all(engine)
    engine.dispose()


class RecordingOwnership:
    def __init__(self) -> None:
        self.heartbeats = 0
        self.releases = 0

    def heartbeat(self) -> bool:
        self.heartbeats += 1
        return True

    def release(self) -> bool:
        self.releases += 1
        return True


class SerialPass:
    def __init__(
        self,
        name: str,
        calls: list[str],
        active: list[int],
        *,
        processed: bool,
    ) -> None:
        self._name = name
        self._calls = calls
        self._active = active
        self._processed = processed

    async def run_once(self) -> bool:
        self._active[0] += 1
        assert self._active[0] == 1
        self._calls.append(self._name)
        await asyncio.sleep(0)
        self._active[0] -= 1
        return self._processed


class FailingPass:
    async def run_once(self) -> bool:
        raise RuntimeError("PRIVATE ANSWER learner@example.test")


def test_database_worker_runs_all_job_families_serially() -> None:
    calls: list[str] = []
    active = [0]
    ownership = RecordingOwnership()
    worker = DatabaseWorker(
        SerialPass("feedback", calls, active, processed=False),
        SerialPass("baseline", calls, active, processed=True),
        SerialPass("continuation", calls, active, processed=False),
        ownership,
        terminal_reconciliation=SerialPass(
            "terminal_reconciliation",
            calls,
            active,
            processed=False,
        ),
    )

    assert asyncio.run(worker.run_once()) is True
    assert calls == [
        "feedback",
        "terminal_reconciliation",
        "baseline",
        "continuation",
    ]
    assert ownership.heartbeats == 1


def test_one_worker_queue_failure_is_sanitized_and_does_not_block_others(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[str] = []
    active = [0]
    worker = DatabaseWorker(
        FailingPass(),
        SerialPass("baseline", calls, active, processed=True),
        SerialPass("continuation", calls, active, processed=False),
        RecordingOwnership(),
    )

    with caplog.at_level(logging.WARNING):
        assert asyncio.run(worker.run_once()) is True

    assert calls == ["baseline", "continuation"]
    assert "database_worker_pass_failed" in caplog.text
    assert "PRIVATE ANSWER" not in caplog.text
    assert "learner@example.test" not in caplog.text


def test_idle_database_worker_keeps_heartbeating_and_releases() -> None:
    async def exercise() -> RecordingOwnership:
        calls: list[str] = []
        active = [0]
        ownership = RecordingOwnership()
        idle = SerialPass("idle", calls, active, processed=False)
        worker = DatabaseWorker(
            idle,
            idle,
            idle,
            ownership,
            poll_interval_seconds=0.005,
            heartbeat_interval_seconds=0.01,
        )
        stop = asyncio.Event()

        async def stop_later() -> None:
            await asyncio.sleep(0.035)
            stop.set()

        await asyncio.gather(worker.run_forever(stop), stop_later())
        return ownership

    ownership = asyncio.run(exercise())
    assert ownership.heartbeats >= 3
    assert ownership.releases == 1


def test_worker_adapter_loading_fails_closed_when_not_configured() -> None:
    with pytest.raises(
        WorkerConfigurationError,
        match="worker adapter factory is not configured",
    ):
        load_worker_adapters("", Settings())


def test_database_worker_provides_durable_feedback_auditing_by_default(
    tmp_path: Path,
) -> None:
    engine = create_db_engine(f"sqlite:///{(tmp_path / 'worker-audit.db').as_posix()}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    adapters = WorkerAdapters(
        feedback_pipeline_factory=lambda _: None,  # type: ignore[arg-type,return-value]
        baseline_context_provider=object(),  # type: ignore[arg-type]
        baseline_generator=object(),  # type: ignore[arg-type]
        baseline_judge=object(),  # type: ignore[arg-type]
        progress_adapter=object(),  # type: ignore[arg-type]
        next_task_recommender=object(),  # type: ignore[arg-type]
    )

    worker = build_database_worker(
        adapters,
        configured_settings=Settings(),
        engine=engine,
        session_factory=session_factory,
        now=lambda: NOW,
    )
    feedback_pass = worker._passes[0][1]  # noqa: SLF001
    audit_events = feedback_pass._audit_events  # type: ignore[attr-defined]  # noqa: SLF001
    assert audit_events is not None
    workflow_id = str(uuid4())
    audit_events.workflow_failed(
        workflow_id,
        workflow_id,
        "retry_attempts_exhausted",
    )

    with session_factory() as session:
        event = session.scalar(select(AuditEvent))
        assert event is not None
        assert event.action is AuditAction.WORKFLOW_FAILED
        assert event.outcome is AuditOutcome.FAILURE
        assert event.failure_category == "retry_attempts_exhausted"

    Base.metadata.drop_all(engine)
    engine.dispose()
