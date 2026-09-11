"""Actual process interruption and recovery against a disposable migrated database."""

import os
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

import pytest
from alembic import command
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from support.person4 import migration_config
from support.task_review import approve_fixture_task, bootstrap_reviewed_demo

from app.api.feedback_dependencies import get_feedback_application, get_feedback_executor
from app.core.config import settings
from app.db.session import create_db_engine, create_session_factory, get_db_session
from app.main import create_app
from app.models import (
    FeedbackRecord,
    LearningMaterial,
    LearningTask,
    MaterialChunk,
    ResearchEvaluation,
    WorkflowRun,
    WorkflowStage,
)
from app.models.enums import TerminalIntegrationType
from app.models.terminal_integration import TerminalIntegrationOutbox
from app.services.feedback.application import FeedbackWorkflowApplication
from app.services.feedback.errors import LostWorkflowLeaseError
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository
from app.services.lms import DEMO_PASSWORD
from app.services.rag.source_history import record_approval, resolve_passages

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")

BACKEND = Path(__file__).resolve().parents[1]


class DeferredExecutor:
    """Model a lost API background execution after its durable acceptance commit."""

    async def execute(self, *args, **kwargs):
        pass


def wait_until(predicate, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    pytest.fail("Timed out waiting for durable worker evidence")


def test_accepted_submission_recovers_after_worker_kill_without_second_post(tmp_path, monkeypatch):
    database_url = f"sqlite:///{(tmp_path / 'recovery.db').as_posix()}"
    command.upgrade(migration_config(database_url), "head")
    engine = create_db_engine(database_url)
    factory = create_session_factory(engine)
    with factory() as session:
        bootstrap_reviewed_demo(session)
        task_id = session.scalar(select(LearningTask.id).order_by(LearningTask.position))
        task = session.get(LearningTask, task_id)
        material = LearningMaterial(
            course_id=task.course_id,
            original_filename="task7.txt",
            mime_type="text/plain",
            content_hash="task7-synthetic",
        )
        session.add(material)
        session.flush()
        from support.material_scanning import record_synthetic_scan

        record_synthetic_scan(session, material)
        chunk = MaterialChunk(
            material_id=material.id,
            chunk_index=0,
            chunk_text="A qubit can be in a superposition of zero and one.",
        )
        session.add(chunk)
        session.flush()
        task.source_references = [chunk.id]
        session.commit()
        _, _, revision = resolve_passages(session, task.course_id, task.source_references)[0]
        record_approval(
            session,
            course_id=task.course_id,
            material_id=material.id,
            revision_id=revision.id,
            actor_id="test-fixture-educator",
            state="APPROVED",
            reason="Reviewed worker test source",
        )
        session.commit()
        approve_fixture_task(session, task)

    monkeypatch.setattr(settings, "llm_api_key", None)
    monkeypatch.setattr(settings, "research_enabled", False)
    app = create_app()

    def database():
        with factory() as session:
            yield session

    def application(session: Session = Depends(get_db_session)):
        # Only shorten initial API expiry; worker claims keep the supported 30-second lease.
        return FeedbackWorkflowApplication(
            SqlAlchemyFeedbackWorkflowRepository(session), lease_duration=timedelta(milliseconds=1)
        )

    app.dependency_overrides[get_db_session] = database
    app.dependency_overrides[get_feedback_application] = application
    app.dependency_overrides[get_feedback_executor] = DeferredExecutor
    env = dict(os.environ)
    env.update(
        APP_ENV="test",
        DATABASE_URL=database_url,
        RESEARCH_ENABLED="false",
        LLM_API_KEY="",
        LLM_PROVIDER="local",
        WORKER_ADAPTER_FACTORY="app.worker:build_offline_worker_adapters",
        WORKER_STALE_SECONDS="30",
        WORKER_HEARTBEAT_SECONDS="0.2",
        WORKER_POLL_SECONDS="0.1",
        FEEDBACK_JOB_LEASE_SECONDS="30",
        PYTHONPATH=os.pathsep.join([str(BACKEND), str(BACKEND / "tests")]),
    )
    children = []
    marker = tmp_path / "claimed"
    log_path = tmp_path / "worker.log"
    try:
        with TestClient(app) as client, log_path.open("w") as log:
            login = client.post(
                "/api/v1/auth/login",
                json={
                    "email": "student@quantumlearn.demo",
                    "password": DEMO_PASSWORD,
                },
            )
            assert login.status_code == 200
            headers = {
                settings.csrf_header_name: client.cookies.get(settings.csrf_cookie_name),
                "Origin": settings.frontend_origin,
            }
            accepted = client.post(
                f"/api/v1/students/me/tasks/{task_id}/submissions",
                json={"answer": "b"},
                headers=headers,
            )
            assert accepted.status_code == 201, accepted.text
            submission_id = accepted.json()["id"]
            first = subprocess.Popen(
                [sys.executable, "-m", "support.task7_worker_process", str(marker)],
                cwd=BACKEND,
                env=env,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            children.append(first)
            wait_until(marker.exists)
            with factory() as session:
                old = session.scalar(
                    select(WorkflowRun).where(WorkflowRun.submission_id == submission_id)
                )
                workflow_id, stale_token = old.id, old.execution_token
                assert old.execution_attempt_count == 2
            # A second actual process cannot steal the fresh singleton slot.
            duplicate = subprocess.run(
                [sys.executable, "-c", "from app.worker import main; raise SystemExit(main())"],
                cwd=BACKEND,
                env=env,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                timeout=20,
            )
            assert duplicate.returncode == 2
            first.kill()
            first.wait(timeout=10)
            # Let real ownership and job leases expire; never rewrite stored timestamps.
            time.sleep(31)
            replacement = subprocess.Popen(
                [sys.executable, "-c", "from app.worker import main; raise SystemExit(main())"],
                cwd=BACKEND,
                env=env,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            children.append(replacement)

            def completed():
                with factory() as session:
                    row = session.get(WorkflowRun, workflow_id)
                    return row.current_stage == WorkflowStage.COMPLETED

            wait_until(completed)
            response = client.get(f"/api/v1/submissions/{submission_id}/feedback")
            assert response.status_code == 200
            assert response.json()["status"] in {"validated", "fallback"}
            with factory() as session:
                repository = SqlAlchemyFeedbackWorkflowRepository(session)
                with pytest.raises(LostWorkflowLeaseError):
                    repository.record_stage(
                        workflow_id, WorkflowStage.GENERATING, execution_token=stale_token
                    )
                replay = FeedbackWorkflowApplication(repository).start(submission_id)
                assert not replay.should_start
                assert replay.workflow_run_id == workflow_id
                assert session.scalar(select(func.count()).select_from(FeedbackRecord)) == 1
                assert session.scalar(select(func.count()).select_from(WorkflowRun)) == 1
                assert session.scalar(select(func.count()).select_from(ResearchEvaluation)) == 0
                assert (
                    session.scalar(
                        select(func.count())
                        .select_from(TerminalIntegrationOutbox)
                        .where(
                            TerminalIntegrationOutbox.integration_type
                            == TerminalIntegrationType.RESEARCH_PAIR
                        )
                    )
                    == 0
                )
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)
        engine.dispose()
