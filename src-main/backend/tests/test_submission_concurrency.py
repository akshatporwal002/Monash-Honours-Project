"""Mounted submission scheduling under real SQLite writer contention."""

import asyncio
import sqlite3
import threading
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select

from app.api.dependencies.roles import require_student
from app.api.routes import lms
from app.db.session import create_db_engine, create_session_factory
from app.models.lms import AttemptStatus
from app.models.user import User, UserRole
from app.schemas.lms import AttemptRead, SubmissionCreate
from app.services.lms import LmsService
from app.services.task_review import TaskReviewError


def test_submission_writer_wait_keeps_event_loop_and_async_background_tasks_running(tmp_path):
    """Only dispatch is under test; retain the real service's SQLite lock operation."""
    database = tmp_path / "submission-contention.sqlite"
    engine = create_db_engine("sqlite:///" + database.as_posix())
    factory = create_session_factory(engine)
    writer_ready = threading.Event()
    submission_entered = threading.Event()
    loop_progress = threading.Event()
    progressed_before_release = []
    holder_errors = []
    background_calls = []
    student = User(id=1, email="synthetic@example.com", role=UserRole.STUDENT)
    attempt = AttemptRead(
        id="synthetic-attempt",
        task_id="synthetic-task",
        attempt_number=1,
        status=AttemptStatus.SUBMITTED,
        answer="Synthetic response",
        code=None,
        circuit=None,
        feedback="Submission recorded",
        feedback_reference=None,
        points_awarded=0,
        submitted_at=datetime.now(UTC),
    )

    def hold_writer():
        try:
            with sqlite3.connect(database, timeout=5) as connection:
                connection.execute("BEGIN IMMEDIATE")
                writer_ready.set()
                if not submission_entered.wait(5):
                    raise AssertionError("The mounted submission did not reach its writer lock")
                # The old async route blocks its own loop until this timeout releases
                # the writer. A correctly dispatched sync route lets the callback run.
                progressed_before_release.append(loop_progress.wait(1))
                connection.rollback()
        except Exception as error:
            holder_errors.append(type(error).__name__)
            writer_ready.set()

    class FeedbackApplication:
        def start(self, submission_id, *, correlation_id):
            assert submission_id == attempt.id
            return SimpleNamespace(
                should_start=True,
                workflow_run_id="synthetic-workflow",
                execution_token="synthetic-token",
            )

    class AssessmentApplication:
        def start(self, submission_id):
            assert submission_id == attempt.id
            return "synthetic-assessment-claim"

    class BackgroundExecutor:
        def __init__(self, kind):
            self.kind = kind

        async def execute(self, *args):
            await asyncio.sleep(0)
            background_calls.append((self.kind, args))

    async def exercise():
        loop = asyncio.get_running_loop()

        class ContendedSubmission:
            def submit(self, actor, task_id, payload):
                assert actor.id == student.id and task_id == attempt.task_id
                assert payload.answer == attempt.answer
                with factory() as session:
                    submission_entered.set()
                    loop.call_soon_threadsafe(loop_progress.set)
                    LmsService(session)._acquire_submission_sequence_lock(actor.id)
                    session.commit()
                return attempt

        app = FastAPI()
        app.include_router(lms.router, prefix="/api/v1")
        app.dependency_overrides.update(
            {
                require_student: lambda: student,
                lms.get_lms_service: lambda: ContendedSubmission(),
                lms.get_feedback_application: lambda: FeedbackApplication(),
                lms.get_feedback_executor: lambda: BackgroundExecutor("feedback"),
                lms.get_assessment_evaluation_application: lambda: AssessmentApplication(),
                lms.get_assessment_evaluation_executor: lambda: BackgroundExecutor("assessment"),
            }
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post(
                f"/api/v1/students/me/tasks/{attempt.task_id}/submissions",
                json={"answer": attempt.answer},
            )

    holder = threading.Thread(target=hold_writer, daemon=True)
    holder.start()
    try:
        assert writer_ready.wait(5), "Synthetic writer did not start"
        assert not holder_errors
        response = asyncio.run(exercise())
    finally:
        submission_entered.set()
        loop_progress.set()
        holder.join(timeout=5)
        engine.dispose()
    assert not holder.is_alive() and not holder_errors
    assert response.status_code == 201, response.text
    assert response.json()["id"] == attempt.id
    assert progressed_before_release == [True], "SQLite writer wait blocked the API event loop"
    assert [kind for kind, _ in background_calls] == ["feedback", "assessment"]
    assert background_calls[0][1][:3] == (
        "synthetic-workflow",
        attempt.id,
        "synthetic-token",
    )
    assert background_calls[1][1] == ("synthetic-assessment-claim",)


@pytest.mark.usefixtures("synthetic_material_scanning")
def test_submission_read_phases_recheck_mutation_and_preserve_atomic_rollback(
    db_session, monkeypatch
):
    from support.curriculum import setup_curriculum

    from app.models import Recommendation, SubmissionAttempt, WorkflowRun
    from app.models.learning_evidence import LearningEvidence

    _, _, student, _, tasks, _, _ = setup_curriculum(db_session)
    service = LmsService(db_session)
    task = tasks[0]
    service._validate_submission_availability(student, task)
    task.description = "Changed after the approved read phase"
    db_session.flush()
    with pytest.raises(TaskReviewError):
        service._validate_submission_availability(student, task)
    db_session.rollback()

    first = service.submit(
        student, task.id, SubmissionCreate(answer="b", idempotency_key="original")
    )
    models = (SubmissionAttempt, WorkflowRun, Recommendation, LearningEvidence)

    def counts():
        return tuple(db_session.scalar(select(func.count()).select_from(model)) for model in models)

    before = counts()
    persist = service._persist_recommendations

    def fail_after_projection(*args):
        persist(*args)
        raise RuntimeError("synthetic failure after read-only projection")

    monkeypatch.setattr(service, "_persist_recommendations", fail_after_projection)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        service.submit(student, task.id, SubmissionCreate(answer="b", idempotency_key="rollback"))
    db_session.rollback()
    assert counts() == before
    assert db_session.get(SubmissionAttempt, first.id).answer == first.answer


@pytest.mark.usefixtures("synthetic_material_scanning")
def test_submission_projection_validates_each_path_once(db_session, monkeypatch):
    from support.curriculum import setup_curriculum

    from app.services.curriculum import CurriculumService

    _, _, student, _, tasks, _, _ = setup_curriculum(db_session)
    service = LmsService(db_session)
    service.submit(student, tasks[0].id, SubmissionCreate(answer="b", idempotency_key="path-read"))
    bindings = CurriculumService._bindings
    checked = []

    def record_check(self, course_id, outcome_id, payload):
        checked.append((course_id, outcome_id))
        return bindings(self, course_id, outcome_id, payload)

    monkeypatch.setattr(CurriculumService, "_bindings", record_check)
    assert service._submission_recommendations(student)
    assert checked and len(checked) == len(set(checked))


@pytest.mark.parametrize("mutation", ["pending", "flushed", "bulk"])
@pytest.mark.usefixtures("synthetic_material_scanning")
def test_path_read_reuse_never_hides_changed_approval(db_session, mutation, monkeypatch):
    from sqlalchemy import update
    from support.curriculum import setup_curriculum

    from app.models.persistence import LearningTask
    from app.services.curriculum import CurriculumService
    from app.services.validation_reads import validation_read_scope

    _, _, _, _, tasks, _, _ = setup_curriculum(db_session)
    task = tasks[0]
    bindings = CurriculumService._bindings
    checks = []

    def record_check(self, *args):
        checks.append(True)
        return bindings(self, *args)

    monkeypatch.setattr(CurriculumService, "_bindings", record_check)

    class PathRead(CurriculumService):
        @validation_read_scope
        def exercise(self):
            path = self._latest(task.learning_outcome_id)
            self._current(path)
            self._current(path)
            if mutation == "bulk":
                self.session.execute(
                    update(LearningTask)
                    .where(LearningTask.id == task.id)
                    .values(title="Changed approval binding")
                )
            else:
                task.title = "Changed approval binding"
                if mutation == "flushed":
                    self.session.flush()
            if mutation == "pending":
                # With autoflush disabled, existing authoritative refreshes read
                # stored state. Pending edits must still bypass the cached check.
                self._current(path)
            else:
                with pytest.raises(TaskReviewError):
                    self._current(path)
            assert len(checks) == 2
            self.session.rollback()
            self._current(path)
            assert len(checks) == 3

    PathRead(db_session).exercise()
