"""API background work keeps its own sessions off the foreground event loop."""

import asyncio
import sqlite3
import threading
from datetime import UTC, datetime, timedelta

import anyio
import pytest
from fastapi import FastAPI, Request
from sqlalchemy import event

from app.api.background_execution import ThreadedBackgroundExecutor, get_background_limiter
from app.db.session import create_session_factory
from app.models import WorkflowRun, WorkflowStage
from app.services.feedback.application import InProcessFeedbackExecutor
from app.services.feedback.errors import ContextCollectionError
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository


def test_background_feedback_writer_wait_is_responsive_and_preserves_retry_state(db_session):
    engine = db_session.get_bind()
    factory = create_session_factory(engine)
    now = datetime.now(UTC)
    claim = SqlAlchemyFeedbackWorkflowRepository(db_session).claim_workflow(
        "synthetic-submission",
        "synthetic-workflow",
        started_at=now,
        lease_expires_at=now + timedelta(minutes=5),
    )
    ready, entered, progress = (threading.Event() for _ in range(3))
    observed, errors, session_threads = [], [], []

    def hold_writer():
        try:
            with sqlite3.connect(engine.url.database, timeout=5) as connection:
                connection.execute("BEGIN IMMEDIATE")
                ready.set()
                if not entered.wait(5):
                    raise AssertionError("Feedback never reached its SQLite write")
                observed.append(progress.wait(1))
                connection.rollback()
        except Exception as error:
            errors.append(type(error).__name__)
            ready.set()

    class Pipeline:
        def __init__(self, repository):
            self.repository = repository
            session_threads.append(threading.get_ident())

        def attach_progress_recorder(self, recorder):
            assert recorder is self.repository

        async def run(self, submission_id, workflow_run_id, *, execution_token, correlation_id):
            self.repository.record_stage(
                workflow_run_id, WorkflowStage.CONTEXT_COLLECTION, execution_token=execution_token
            )
            raise ContextCollectionError()

    async def exercise():
        loop = asyncio.get_running_loop()
        request = Request({"type": "http", "app": FastAPI()})
        limiter = await get_background_limiter(request)
        assert await get_background_limiter(request) is limiter
        assert limiter is not anyio.to_thread.current_default_thread_limiter()

        def write_started(conn, cursor, statement, parameters, context, many):
            if not entered.is_set() and statement.lstrip().upper().startswith("UPDATE"):
                entered.set()
                loop.call_soon_threadsafe(progress.set)

        executor = InProcessFeedbackExecutor(factory, Pipeline, now=lambda: now)
        event.listen(engine, "before_cursor_execute", write_started)
        try:
            await ThreadedBackgroundExecutor(executor, limiter).execute(
                claim.workflow_run_id, claim.submission_id, claim.execution_token
            )
        finally:
            event.remove(engine, "before_cursor_execute", write_started)

    holder = threading.Thread(target=hold_writer, daemon=True)
    holder.start()
    try:
        assert ready.wait(5) and not errors
        asyncio.run(exercise())
    finally:
        entered.set()
        progress.set()
        holder.join(timeout=5)
    assert not holder.is_alive() and not errors
    assert observed == [True], "Background SQLite write blocked the foreground API event loop"
    assert session_threads and all(
        identity != threading.get_ident() for identity in session_threads
    )
    db_session.expire_all()
    workflow = db_session.get(WorkflowRun, claim.workflow_run_id)
    assert workflow.current_stage is WorkflowStage.FAILED
    assert workflow.failure_category == "context_unavailable"
    assert workflow.execution_attempt_count == 1
    assert workflow.next_retry_at is not None


def test_background_limit_leaves_foreground_thread_capacity_and_closes_job_loops():
    gate = threading.Event()
    four_running = threading.Event()
    guard = threading.Lock()
    active = maximum = 0
    loops = []

    class Executor:
        async def execute(self, identity):
            nonlocal active, maximum
            with guard:
                active += 1
                maximum = max(maximum, active)
                loops.append(asyncio.get_running_loop())
                if active == 4:
                    four_running.set()
            try:
                assert gate.wait(5), "Synthetic background jobs were not released"
            finally:
                with guard:
                    active -= 1

    async def exercise():
        foreground = anyio.to_thread.current_default_thread_limiter()
        foreground.total_tokens = 1
        request = Request({"type": "http", "app": FastAPI()})
        executor = ThreadedBackgroundExecutor(Executor(), await get_background_limiter(request))
        jobs = [asyncio.create_task(executor.execute(index)) for index in range(6)]
        try:
            assert await anyio.to_thread.run_sync(four_running.wait, 3)
            # All four background slots are occupied, but a foreground dependency runs.
            assert await anyio.to_thread.run_sync(lambda: "foreground") == "foreground"
        finally:
            gate.set()
            await asyncio.gather(*jobs)

    asyncio.run(exercise())
    assert active == 0 and maximum == 4
    assert len(loops) == 6 and all(loop.is_closed() for loop in loops)


def test_raw_task_cancellation_waits_for_active_executor_cleanup():
    entered, release, cleaned = (threading.Event() for _ in range(3))

    class Executor:
        async def execute(self):
            entered.set()
            try:
                assert release.wait(5), "Synthetic executor was not released"
            finally:
                cleaned.set()

    async def exercise():
        executor = ThreadedBackgroundExecutor(Executor(), anyio.CapacityLimiter(1))
        task = asyncio.create_task(executor.execute())
        try:
            assert await anyio.to_thread.run_sync(entered.wait, 3)
            task.cancel()
            await asyncio.sleep(0.03)
            assert not task.done(), "Cancellation abandoned the active session-owning executor"
            assert not cleaned.is_set()
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert cleaned.is_set()

    asyncio.run(exercise())
