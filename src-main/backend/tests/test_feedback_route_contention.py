"""A SQLite writer wait must not prevent the API loop from releasing that writer."""

import asyncio
import sqlite3
import threading
from types import SimpleNamespace

import pytest
from fastapi import Request, Response

from app.api.routes import activity_continuation, feedback
from app.models import WorkflowStage
from app.models.user import UserRole
from app.schemas.feedback_api import (
    AuthenticatedActor,
    FeedbackWorkflowResponse,
    FeedbackWorkflowStatus,
)
from app.services.feedback.contracts import WorkflowClaim


@pytest.mark.parametrize("route", ["feedback_read", "activity_action"])
def test_database_wait_leaves_api_loop_available_to_release_writer(tmp_path, monkeypatch, route):
    path = tmp_path / "contention.sqlite"
    connection = sqlite3.connect(path, timeout=4, check_same_thread=False)
    connection.execute("CREATE TABLE probe (value INTEGER)")
    connection.execute("INSERT INTO probe VALUES (0)")
    connection.commit()
    locked, release = threading.Event(), threading.Event()
    released_by_loop = []
    calls = []

    def hold_writer():
        with sqlite3.connect(path, timeout=4) as holder:
            holder.execute("UPDATE probe SET value=1")
            locked.set()
            released_by_loop.append(release.wait(2))
            holder.rollback()

    holder = threading.Thread(target=hold_writer)
    holder.start()
    assert locked.wait(2)

    async def exercise():
        loop = asyncio.get_running_loop()
        loop_thread = threading.get_ident()

        def database_work():
            calls.append(("database", threading.get_ident()))
            # This callback cannot run while synchronous SQLite is blocking the API loop.
            loop.call_soon_threadsafe(release.set)
            connection.execute("UPDATE probe SET value=2")
            connection.rollback()

        class Security:
            async def enforce(self, *args, **kwargs):
                calls.append(("security", threading.get_ident()))

        request = Request(
            {"type": "http", "method": "GET", "path": "/test", "headers": [], "query_string": b""}
        )
        response = Response()
        if route == "activity_action":

            class Service:
                def __init__(self, session):
                    assert session is connection

                def act(self, actor, workflow_id, payload):
                    database_work()
                    return {"result": "saved"}

            monkeypatch.setattr(activity_continuation, "ActivityService", Service)
            result = await activity_continuation.action(
                "workflow-1",
                object(),
                request,
                response,
                SimpleNamespace(id=1, role=UserRole.STUDENT),
                connection,
                Security(),
            )
            assert result == {"result": "saved"}
        else:
            claim = WorkflowClaim(
                workflow_run_id="00000000-0000-4000-8000-000000000101",
                submission_id="submission-1",
                stage=WorkflowStage.JUDGING,
                should_start=False,
            )

            class Policy:
                async def can_access_submission(self, *args):
                    calls.append(("access", threading.get_ident()))
                    return True

            class Application:
                def get(self, submission_id):
                    database_work()
                    return claim

                async def response(self, actual):
                    assert actual is claim
                    calls.append(("response", threading.get_ident()))
                    return FeedbackWorkflowResponse(
                        workflow_run_id=claim.workflow_run_id,
                        submission_id=claim.submission_id,
                        status=FeedbackWorkflowStatus.PROCESSING,
                        processing_stage=claim.stage,
                    )

            result = await feedback.get_feedback(
                "submission-1",
                request,
                response,
                AuthenticatedActor(actor_reference="1", role="student"),
                Policy(),
                Application(),
                None,
                None,
                Security(),
            )
            assert result.status is FeedbackWorkflowStatus.PROCESSING
            assert response.headers["Retry-After"] == "2"
        assert calls[0] == ("security", loop_thread)
        assert released_by_loop == [True], (
            "Synchronous route work blocked the API loop until SQLite's holder timed out"
        )
        assert all(identity != loop_thread for name, identity in calls if name != "security")

    try:
        asyncio.run(exercise())
    finally:
        release.set()
        holder.join(5)
        connection.close()


@pytest.mark.parametrize("route", ["feedback_read", "activity_action"])
def test_security_rejection_never_starts_request_session_work(monkeypatch, route):
    from app.api.feedback_dependencies import FeedbackApiException

    async def unexpected_work(*args):
        raise AssertionError("Session work ran before security approval")

    class Security:
        async def enforce(self, *args, **kwargs):
            raise FeedbackApiException(403, "csrf_rejected", "Rejected")

    monkeypatch.setattr(feedback, "run_session_work", unexpected_work)
    monkeypatch.setattr(activity_continuation, "run_session_work", unexpected_work)
    request = Request(
        {"type": "http", "method": "POST", "path": "/test", "headers": [], "query_string": b""}
    )

    async def exercise():
        with pytest.raises(FeedbackApiException) as caught:
            if route == "feedback_read":
                await feedback.get_feedback(
                    "submission-1",
                    request,
                    Response(),
                    AuthenticatedActor(actor_reference="1", role="student"),
                    None,
                    None,
                    None,
                    None,
                    Security(),
                )
            else:
                await activity_continuation.action(
                    "workflow-1",
                    object(),
                    request,
                    Response(),
                    SimpleNamespace(id=1, role=UserRole.STUDENT),
                    None,
                    Security(),
                )
        assert caught.value.status_code == 403

    asyncio.run(exercise())


def test_cancelled_request_waits_for_session_work_before_dependency_cleanup(monkeypatch):
    release = threading.Event()
    state = {"closed": False, "finished": False}

    class Security:
        async def enforce(self, *args, **kwargs):
            pass

    async def exercise():
        entered = asyncio.Event()
        loop = asyncio.get_running_loop()

        class Service:
            def __init__(self, session):
                assert session is state

            def act(self, actor, workflow_id, payload):
                loop.call_soon_threadsafe(entered.set)
                assert release.wait(3), "Test did not release request work"
                assert not state["closed"], "Request cleanup raced an active session user"
                state["finished"] = True

        monkeypatch.setattr(activity_continuation, "ActivityService", Service)
        request = Request(
            {"type": "http", "method": "POST", "path": "/test", "headers": [], "query_string": b""}
        )

        async def request_owner():
            try:
                return await activity_continuation.action(
                    "workflow-1",
                    object(),
                    request,
                    Response(),
                    SimpleNamespace(id=1, role=UserRole.STUDENT),
                    state,
                    Security(),
                )
            finally:
                state["closed"] = True

        task = asyncio.create_task(request_owner())
        try:
            await asyncio.wait_for(entered.wait(), 3)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done() and not state["closed"]
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert state == {"closed": True, "finished": True}

    asyncio.run(exercise())
