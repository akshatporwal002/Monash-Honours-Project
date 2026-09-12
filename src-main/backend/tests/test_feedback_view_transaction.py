"""Real released-feedback GETs batch independent, replay-safe view telemetry."""

import asyncio
import copy
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import event, select
from test_task16_feedback_release import collected, setup_human
from test_task16_feedback_workflow import run_pipeline

from app.api import audit_dependencies, learning_event_dependencies
from app.api.security_dependencies import get_request_security_guard
from app.core.config import settings
from app.core.session import create_session_token
from app.db.session import create_session_factory, get_db
from app.main import create_app
from app.models.audit import AuditAction, AuditEvent
from app.models.enums import LearningEventType
from app.models.lms import Enrollment, EnrollmentStatus
from app.models.persistence import LearningEvent, WorkflowRun
from app.models.user import User, UserRole
from app.schemas.feedback import FeedbackPipelineStatus
from app.services.audit import BestEffortAuditSink, IndependentAuditRecorder
from app.services.audit_events import FeedbackAuditEvents, StudentAuditTracker
from app.services.feedback.application import FeedbackWorkflowApplication
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository
from app.services.learning_events import (
    BestEffortLearningEventSink,
    HmacSha256Pseudonymizer,
    LearningEventRecorder,
    TrustedLearningEventHooks,
)

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")
SECRET = "synthetic-feedback-view-transaction-secret-20260912"


def view_records(factory):
    with factory() as session:
        return {
            "learning": copy.deepcopy(
                [
                    dict(row)
                    for row in session.execute(
                        select(LearningEvent.__table__)
                        .where(LearningEvent.event_type == LearningEventType.FEEDBACK_VIEW)
                        .order_by(LearningEvent.id)
                    ).mappings()
                ]
            ),
            "audit": copy.deepcopy(
                [
                    dict(row)
                    for row in session.execute(
                        select(AuditEvent.__table__)
                        .where(AuditEvent.action == AuditAction.FEEDBACK_VIEWED)
                        .order_by(AuditEvent.id)
                    ).mappings()
                ]
            ),
        }


@pytest.fixture
def feedback_view_harness(db_session, monkeypatch, request):
    engine = db_session.get_bind()
    request_factory = create_session_factory(engine)
    telemetry_factory = create_session_factory(engine)
    monkeypatch.setattr(settings, "learning_event_pseudonym_secret", SecretStr(SECRET))
    monkeypatch.setattr(learning_event_dependencies, "SessionLocal", telemetry_factory)
    monkeypatch.setattr(audit_dependencies, "SessionLocal", telemetry_factory)
    audit_dependencies.get_feedback_audit_events.cache_clear()
    audit_dependencies.get_student_audit_tracker.cache_clear()
    get_request_security_guard.cache_clear()

    _, _, attempt, submission_id = setup_human(db_session)
    student_id, course_id, task_id = attempt.student_id, attempt.course_id, attempt.task_id
    result = None
    if getattr(request, "param", "released") != "processing":
        result, _ = run_pipeline(db_session, collected(db_session, attempt))
        assert result.status is FeedbackPipelineStatus.VALIDATED
    else:
        # Submission queues a durable workflow without a live execution lease.
        # Read-time observation correctly reports that as interrupted/failed.
        # Claim it through the real application to represent current processing;
        # deliberately leave execution unstarted so no terminal content exists.
        claim = FeedbackWorkflowApplication(SqlAlchemyFeedbackWorkflowRepository(db_session)).start(
            submission_id
        )
        assert claim.should_start and claim.terminal_result is None
    db_session.rollback()
    app = create_app()

    def request_session():
        with request_factory() as session:
            yield session

    app.dependency_overrides[get_db] = request_session
    cookie = settings.session_cookie_name + "=" + create_session_token(student_id)
    try:
        yield SimpleNamespace(
            app=app,
            engine=engine,
            factory=request_factory,
            path=f"/api/v1/submissions/{submission_id}/feedback",
            cookie=cookie,
            student_id=student_id,
            course_id=course_id,
            task_id=task_id,
            result=result,
        )
    finally:
        app.dependency_overrides.clear()
        audit_dependencies.get_feedback_audit_events.cache_clear()
        audit_dependencies.get_student_audit_tracker.cache_clear()
        get_request_security_guard.cache_clear()


def test_fresh_feedback_get_records_both_view_events_in_one_commit(feedback_view_harness):
    harness = feedback_view_harness
    assert view_records(harness.factory) == {"learning": [], "audit": []}
    correlation = str(uuid4())
    commits = []

    def committed(connection):
        commits.append(connection)

    event.listen(harness.engine, "commit", committed)
    try:
        with TestClient(harness.app) as client:
            response = client.get(
                harness.path,
                headers={"Cookie": harness.cookie, "X-Correlation-ID": correlation},
            )
    finally:
        event.remove(harness.engine, "commit", committed)

    assert response.status_code == 200
    assert response.json()["status"] == "validated"
    records = view_records(harness.factory)
    assert len(records["learning"]) == len(records["audit"]) == 1
    learning, audit = records["learning"][0], records["audit"][0]
    pseudonymizer = HmacSha256Pseudonymizer(SECRET)
    assert learning["pseudonymous_user_id"] == pseudonymizer.pseudonymize(
        "learning-actor", str(harness.student_id)
    )
    assert audit["actor_reference"] == pseudonymizer.pseudonymize(
        "audit-actor", str(harness.student_id)
    )
    assert learning["workflow_reference"] == harness.result.workflow_run_id
    assert learning["course_id"] == harness.course_id
    assert learning["task_id"] == harness.task_id
    assert learning["metadata"] == {"feedback_status": "validated"}
    assert audit["resource_id"] == harness.result.feedback_id
    assert learning["correlation_id"] == audit["correlation_id"] == correlation
    assert len(commits) == 1, "A fresh feedback view must persist both events in one transaction"


def test_concurrent_feedback_views_and_replays_keep_one_stable_pair(feedback_view_harness):
    harness = feedback_view_harness

    async def concurrent_reads():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=harness.app), base_url="http://testserver"
        ) as client:
            return await asyncio.gather(
                *(
                    client.get(
                        harness.path,
                        headers={"Cookie": harness.cookie, "X-Correlation-ID": str(uuid4())},
                    )
                    for _ in range(4)
                )
            )

    responses = asyncio.run(concurrent_reads())
    assert [response.status_code for response in responses] == [200] * 4
    assert all(response.json()["status"] == "validated" for response in responses)
    first = view_records(harness.factory)
    assert len(first["learning"]) == len(first["audit"]) == 1
    with TestClient(harness.app) as client:
        for _ in range(2):
            response = client.get(
                harness.path,
                headers={"Cookie": harness.cookie, "X-Correlation-ID": str(uuid4())},
            )
            assert response.status_code == 200
    assert view_records(harness.factory) == first


def test_feedback_view_does_not_commit_or_rollback_pending_request_work(feedback_view_harness):
    harness = feedback_view_harness
    with harness.factory() as primary:
        pending = User(
            email=f"pending-feedback-view-{uuid4().hex}@example.com",
            full_name="Unrelated uncommitted synthetic work",
            password_hash="unused-synthetic-only",
            role=UserRole.STUDENT,
        )
        primary.add(pending)

        def request_session():
            yield primary

        harness.app.dependency_overrides[get_db] = request_session
        with TestClient(harness.app) as client:
            response = client.get(harness.path, headers={"Cookie": harness.cookie})
        assert response.status_code == 200
        assert pending in primary.new
        assert pending.id is None
        with harness.factory() as independent:
            assert independent.scalar(select(User.id).where(User.email == pending.email)) is None
        records = view_records(harness.factory)
        assert len(records["learning"]) == len(records["audit"]) == 1


@pytest.mark.parametrize("feedback_view_harness", ["processing"], indirect=True)
def test_processing_feedback_has_no_view_telemetry(feedback_view_harness):
    harness = feedback_view_harness
    with TestClient(harness.app) as client:
        response = client.get(harness.path, headers={"Cookie": harness.cookie})
    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    assert response.json()["feedback"] is None
    assert view_records(harness.factory) == {"learning": [], "audit": []}


def test_denied_feedback_has_no_view_telemetry(feedback_view_harness):
    harness = feedback_view_harness
    with TestClient(harness.app) as client:
        assert client.get(harness.path).status_code == 401
        with harness.factory() as session:
            enrollment = session.scalar(
                select(Enrollment).where(
                    Enrollment.student_id == harness.student_id,
                    Enrollment.course_id == harness.course_id,
                )
            )
            enrollment.status = EnrollmentStatus.WITHDRAWN
            session.commit()
        response = client.get(harness.path, headers={"Cookie": harness.cookie})
    assert response.status_code == 404
    assert view_records(harness.factory) == {"learning": [], "audit": []}


@pytest.fixture
def view_recorder_inputs(db_session):
    """Only the telemetry FK is needed for direct recorder contract cases."""
    workflow_id = str(uuid4())
    db_session.add(WorkflowRun(id=workflow_id, submission_id=f"synthetic-{workflow_id}"))
    db_session.commit()
    return create_session_factory(db_session.get_bind()), {
        "actor_reference": "synthetic-private-viewer",
        "course_id": "synthetic-course",
        "task_id": "synthetic-task",
        "workflow_run_id": workflow_id,
        "correlation_id": str(uuid4()),
        "feedback_status": "validated",
        "feedback_id": str(uuid4()),
    }


@pytest.mark.parametrize("invalid_field", ["course_id", "task_id", "feedback_id"])
def test_invalid_view_event_does_not_discard_its_valid_partner(view_recorder_inputs, invalid_field):
    # Function-local import keeps the earlier route regression collectible before
    # this candidate recorder exists. Run these cases after adding its source.
    from app.services.feedback_view_events import IndependentFeedbackViewEvents

    factory, values = view_recorder_inputs
    invalid = {**values, invalid_field: "not-a-uuid" if invalid_field == "feedback_id" else " "}
    IndependentFeedbackViewEvents(factory, HmacSha256Pseudonymizer(SECRET)).record(**invalid)
    records = view_records(factory)
    valid_kind = "learning" if invalid_field == "feedback_id" else "audit"
    invalid_kind = "audit" if valid_kind == "learning" else "learning"
    assert len(records[valid_kind]) == 1
    assert records[invalid_kind] == []
    if valid_kind == "learning":
        assert records["learning"][0]["workflow_reference"] == values["workflow_run_id"]
    else:
        assert records["audit"][0]["resource_id"] == values["feedback_id"]


def test_normal_view_replay_does_not_report_a_persistence_outage(view_recorder_inputs, caplog):
    from app.services.feedback_view_events import IndependentFeedbackViewEvents

    factory, values = view_recorder_inputs
    recorder = IndependentFeedbackViewEvents(factory, HmacSha256Pseudonymizer(SECRET))
    recorder.record(**values)
    original = view_records(factory)
    caplog.clear()
    recorder.record(**{**values, "correlation_id": str(uuid4())})
    assert view_records(factory) == original
    assert not caplog.records


def test_failed_preflight_connection_does_not_poison_partner_lookup(view_recorder_inputs):
    from sqlalchemy.exc import DBAPIError

    from app.services.feedback_view_events import IndependentFeedbackViewEvents

    factory, values = view_recorder_inputs
    with factory() as session:
        engine = session.get_bind()
    failed = []

    def disconnect_first_lookup(connection, cursor, statement, parameters, context, many):
        if not failed and "FROM learning_events" in statement:
            failed.append(True)
            connection.invalidate()
            raise DBAPIError(statement, parameters, RuntimeError("Synthetic disconnect"), True)

    event.listen(engine, "before_cursor_execute", disconnect_first_lookup)
    try:
        IndependentFeedbackViewEvents(factory, HmacSha256Pseudonymizer(SECRET)).record(**values)
    finally:
        event.remove(engine, "before_cursor_execute", disconnect_first_lookup)
    assert failed == [True]
    records = view_records(factory)
    assert records["learning"] == []
    assert len(records["audit"]) == 1


@pytest.mark.parametrize("failing_table", ["learning_events", "audit_events"])
def test_disconnected_view_insert_recovers_each_record_independently(
    view_recorder_inputs, failing_table
):
    from sqlalchemy.exc import DBAPIError

    from app.services.feedback_view_events import IndependentFeedbackViewEvents

    factory, values = view_recorder_inputs
    with factory() as session:
        engine = session.get_bind()
    failed = []

    def disconnect_first_insert(connection, cursor, statement, parameters, context, many):
        if not failed and statement.startswith(f"INSERT INTO {failing_table}"):
            failed.append(True)
            connection.invalidate()
            raise DBAPIError(
                statement,
                parameters,
                RuntimeError("Synthetic disconnect"),
                connection_invalidated=True,
            )

    event.listen(engine, "before_cursor_execute", disconnect_first_insert)
    try:
        IndependentFeedbackViewEvents(factory, HmacSha256Pseudonymizer(SECRET)).record(**values)
    finally:
        event.remove(engine, "before_cursor_execute", disconnect_first_insert)
    assert failed == [True]
    records = view_records(factory)
    assert len(records["audit"]) == 1
    assert len(records["learning"]) == 1


def test_persistent_view_disconnect_has_only_one_fallback_attempt_per_record(view_recorder_inputs):
    from sqlalchemy.exc import DBAPIError

    from app.services.feedback_view_events import IndependentFeedbackViewEvents

    factory, values = view_recorder_inputs
    with factory() as session:
        engine = session.get_bind()
    attempts = []

    def disconnect_insert(connection, cursor, statement, parameters, context, many):
        if statement.startswith(("INSERT INTO learning_events", "INSERT INTO audit_events")):
            attempts.append(statement.split()[2])
            connection.invalidate()
            raise DBAPIError(
                statement,
                parameters,
                RuntimeError("Synthetic disconnect"),
                connection_invalidated=True,
            )

    event.listen(engine, "before_cursor_execute", disconnect_insert)
    try:
        IndependentFeedbackViewEvents(factory, HmacSha256Pseudonymizer(SECRET)).record(**values)
    finally:
        event.remove(engine, "before_cursor_execute", disconnect_insert)
    assert attempts == ["learning_events", "learning_events", "audit_events"]
    assert view_records(factory) == {"learning": [], "audit": []}


@pytest.mark.parametrize("conflicting_kind", ["learning", "audit"])
def test_conflicting_view_replay_preserves_original_and_records_other_event(
    view_recorder_inputs, conflicting_kind
):
    from app.services.feedback_view_events import IndependentFeedbackViewEvents

    factory, values = view_recorder_inputs
    pseudonymizer = HmacSha256Pseudonymizer(SECRET)
    if conflicting_kind == "learning":
        hooks = TrustedLearningEventHooks(
            BestEffortLearningEventSink(LearningEventRecorder(factory, pseudonymizer))
        )
        hooks.record_feedback_view(
            **{
                key: value
                for key, value in values.items()
                if key not in {"course_id", "feedback_id"}
            },
            course_id="a-different-original-course",
        )
    else:
        events = FeedbackAuditEvents(BestEffortAuditSink(lambda: IndependentAuditRecorder(factory)))
        StudentAuditTracker(events, pseudonymizer).record_feedback_view(
            actor_reference=values["actor_reference"],
            feedback_id=values["feedback_id"],
            correlation_id=str(uuid4()),
        )
    original = view_records(factory)
    assert len(original[conflicting_kind]) == 1

    IndependentFeedbackViewEvents(factory, pseudonymizer).record(**values)

    after = view_records(factory)
    assert after[conflicting_kind] == original[conflicting_kind]
    assert len(after["learning"]) == len(after["audit"]) == 1


@pytest.mark.parametrize("failing_kind", ["learning", "audit"])
def test_failed_view_insert_rolls_back_its_savepoint_and_keeps_partner(
    view_recorder_inputs, failing_kind
):
    from app.services.feedback_view_events import IndependentFeedbackViewEvents

    factory, values = view_recorder_inputs
    model = LearningEvent if failing_kind == "learning" else AuditEvent
    failed_inserts = []

    def fail_after_insert(_mapper, _connection, row):
        failed_inserts.append(row.id)
        raise RuntimeError("Synthetic telemetry fault after INSERT")

    event.listen(model, "after_insert", fail_after_insert)
    try:
        IndependentFeedbackViewEvents(factory, HmacSha256Pseudonymizer(SECRET)).record(**values)
    finally:
        event.remove(model, "after_insert", fail_after_insert)

    assert len(failed_inserts) == 1
    rows = view_records(factory)
    partner = "audit" if failing_kind == "learning" else "learning"
    assert rows[failing_kind] == []
    assert len(rows[partner]) == 1
    # The failed side can be recovered without rewriting the surviving event.
    IndependentFeedbackViewEvents(factory, HmacSha256Pseudonymizer(SECRET)).record(**values)
    recovered = view_records(factory)
    assert recovered[partner] == rows[partner]
    assert len(recovered["learning"]) == len(recovered["audit"]) == 1


def test_failed_outer_view_commit_rolls_back_both_released_savepoints(view_recorder_inputs):
    from app.services.feedback_view_events import IndependentFeedbackViewEvents

    factory, values = view_recorder_inputs
    with factory() as session:
        engine = session.get_bind()
    inserted = []
    released = []
    commit_failures = []

    def inserted_row(_mapper, _connection, row):
        inserted.append(type(row))

    def released_savepoint(_connection, name, _context):
        released.append(name)

    def fail_outer_commit(session):
        if not session.in_nested_transaction():
            commit_failures.append(True)
            raise RuntimeError("Synthetic telemetry fault before outer COMMIT")

    event.listen(LearningEvent, "after_insert", inserted_row)
    event.listen(AuditEvent, "after_insert", inserted_row)
    event.listen(engine, "release_savepoint", released_savepoint)
    event.listen(factory, "before_commit", fail_outer_commit)
    try:
        IndependentFeedbackViewEvents(factory, HmacSha256Pseudonymizer(SECRET)).record(**values)
    finally:
        event.remove(factory, "before_commit", fail_outer_commit)
        event.remove(engine, "release_savepoint", released_savepoint)
        event.remove(AuditEvent, "after_insert", inserted_row)
        event.remove(LearningEvent, "after_insert", inserted_row)

    assert commit_failures == [True]
    assert set(inserted) == {LearningEvent, AuditEvent}
    assert len(released) == 2
    # SQLite SAVEPOINT without a real outer BEGIN would make its release durable.
    # An independent read must prove both rows disappeared after outer rollback.
    assert view_records(factory) == {"learning": [], "audit": []}
    IndependentFeedbackViewEvents(factory, HmacSha256Pseudonymizer(SECRET)).record(**values)
    recovered = view_records(factory)
    assert len(recovered["learning"]) == len(recovered["audit"]) == 1
