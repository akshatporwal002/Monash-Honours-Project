from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.db.session import create_db_engine, create_session_factory
from app.models import LearningEvent, LearningEventType, WorkflowRun
from app.schemas.learning_events import validate_learning_event_metadata
from app.services.learning_events import (
    BestEffortFeedbackViewTracker,
    BestEffortLearningEventSink,
    HmacSha256Pseudonymizer,
    InvalidPseudonymizationSecretError,
    LearningEventCommand,
    LearningEventConflictError,
    LearningEventRecorder,
    TrustedLearningEventHooks,
)

SECRET = "event-test-secret-that-is-at-least-32-bytes"
FIXED_TIME = datetime(2026, 7, 25, 12, 30, tzinfo=timezone.utc)


@pytest.fixture
def event_session_factory(
    tmp_path: Path,
) -> sessionmaker[Session]:
    database_path = tmp_path / "learning-events.db"
    engine = create_db_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def recorder(factory: sessionmaker[Session]) -> LearningEventRecorder:
    return LearningEventRecorder(
        factory,
        HmacSha256Pseudonymizer(SECRET),
        now=lambda: FIXED_TIME,
    )


def command(
    event_type: LearningEventType,
    metadata: dict[str, object],
    *,
    event_id: str | None = None,
    actor: str = "student-private",
    course_id: str = "course-1",
    task_id: str = "task-1",
    workflow_reference: str | None = None,
) -> LearningEventCommand:
    return LearningEventCommand(
        actor_reference=actor,
        course_id=course_id,
        task_id=task_id,
        event_type=event_type,
        client_event_id=event_id or str(uuid4()),
        correlation_id=str(uuid4()),
        metadata=metadata,
        workflow_reference=workflow_reference,
    )


def seed_workflow(
    factory: sessionmaker[Session],
    workflow_run_id: str,
) -> None:
    with factory() as session:
        session.add(
            WorkflowRun(
                id=workflow_run_id,
                submission_id=f"submission-{workflow_run_id}",
            )
        )
        session.commit()


def test_hmac_pseudonyms_are_deterministic_versioned_and_namespace_separated() -> None:
    pseudonymizer = HmacSha256Pseudonymizer(SECRET)

    first = pseudonymizer.pseudonymize("learning-actor", "student-private")
    repeated = pseudonymizer.pseudonymize("learning-actor", "student-private")
    other_namespace = pseudonymizer.pseudonymize("research-actor", "student-private")

    assert first == repeated
    assert first.startswith("v1_")
    assert first != other_namespace
    assert "student-private" not in first

    with pytest.raises(InvalidPseudonymizationSecretError):
        HmacSha256Pseudonymizer("too-short")


def test_production_configuration_requires_a_32_byte_pseudonym_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            learning_event_pseudonym_secret="too-short",
        )

    configured = Settings(
        _env_file=None,
        app_env="production",
        learning_event_pseudonym_secret="x" * 32,
        session_secret_key="y" * 32,
    )
    assert configured.learning_event_pseudonym_secret is not None


def test_recorder_accepts_all_five_typed_event_shapes(
    event_session_factory: sessionmaker[Session],
) -> None:
    strict_recorder = recorder(event_session_factory)
    workflow_run_id = str(uuid4())
    seed_workflow(event_session_factory, workflow_run_id)
    commands = (
        command(LearningEventType.TASK_VIEW, {"source": "task-page"}),
        command(LearningEventType.DRAFT_SAVE, {"duration_ms": 1500}),
        command(
            LearningEventType.SUBMISSION,
            {"attempt_number": 1, "score": 87.5},
        ),
        command(
            LearningEventType.FEEDBACK_VIEW,
            {"feedback_status": "validated"},
            workflow_reference=workflow_run_id,
        ),
        command(
            LearningEventType.COMPLETION,
            {"completion_status": "completed", "score": 90.0},
        ),
    )

    receipts = [strict_recorder.record(item).receipt for item in commands]

    assert len({receipt.learning_event_id for receipt in receipts}) == 5
    with event_session_factory() as session:
        events = session.scalars(select(LearningEvent).order_by(LearningEvent.event_type)).all()
    assert len(events) == 5
    assert {event.event_type for event in events} == set(LearningEventType)
    assert all(event.pseudonymous_user_id.startswith("v1_") for event in events)
    assert all("student-private" not in event.pseudonymous_user_id for event in events)
    feedback_view = next(
        event for event in events if event.event_type is LearningEventType.FEEDBACK_VIEW
    )
    assert feedback_view.workflow_reference == workflow_run_id


def test_exact_replay_returns_original_receipt_and_conflicting_reuse_is_rejected(
    event_session_factory: sessionmaker[Session],
) -> None:
    strict_recorder = recorder(event_session_factory)
    event_id = str(uuid4())
    original = command(
        LearningEventType.DRAFT_SAVE,
        {"duration_ms": 100},
        event_id=event_id,
    )

    first = strict_recorder.record(original)
    replay = strict_recorder.record(original)

    assert first.created is True
    assert replay.created is False
    assert replay.receipt == first.receipt

    conflicting = command(
        LearningEventType.DRAFT_SAVE,
        {"duration_ms": 200},
        event_id=event_id,
    )
    with pytest.raises(LearningEventConflictError):
        strict_recorder.record(conflicting)

    with event_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(LearningEvent)) == 1


def test_concurrent_replay_creates_exactly_one_event(
    event_session_factory: sessionmaker[Session],
) -> None:
    strict_recorder = recorder(event_session_factory)
    shared = command(
        LearningEventType.TASK_VIEW,
        {"source": "task-page"},
    )
    barrier = Barrier(6)

    def record_once() -> tuple[str, bool]:
        barrier.wait()
        result = strict_recorder.record(shared)
        return result.receipt.learning_event_id, result.created

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: record_once(), range(6)))

    assert len({event_id for event_id, _ in results}) == 1
    assert sum(created for _, created in results) == 1
    with event_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(LearningEvent)) == 1


@pytest.mark.parametrize(
    ("event_type", "metadata"),
    [
        (LearningEventType.TASK_VIEW, {"source": {"answer": "private"}}),
        (LearningEventType.DRAFT_SAVE, {"duration_ms": [1, 2]}),
        (LearningEventType.SUBMISSION, {"attempt_number": 0}),
        (LearningEventType.FEEDBACK_VIEW, {"feedback_status": "accepted"}),
        (LearningEventType.COMPLETION, {"completion_status": "unknown"}),
        (LearningEventType.TASK_VIEW, {"source": "x" * 101}),
        (LearningEventType.TASK_VIEW, {"prompt": "private"}),
    ],
)
def test_private_nested_mismatched_and_oversized_metadata_is_rejected(
    event_type: LearningEventType,
    metadata: dict[str, object],
) -> None:
    with pytest.raises((ValueError, ValidationError)):
        validate_learning_event_metadata(event_type, metadata)


def test_recorder_transaction_is_independent_of_primary_student_transaction(
    event_session_factory: sessionmaker[Session],
) -> None:
    strict_recorder = recorder(event_session_factory)
    with event_session_factory() as primary_session:
        primary_session.add(WorkflowRun(submission_id="uncommitted-submission"))
        strict_recorder.record(command(LearningEventType.TASK_VIEW, {"source": "task-page"}))
        primary_session.rollback()

    with event_session_factory() as verification_session:
        assert verification_session.scalar(select(func.count()).select_from(WorkflowRun)) == 0
        assert verification_session.scalar(select(func.count()).select_from(LearningEvent)) == 1


def test_best_effort_sink_never_raises_or_logs_private_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    private_marker = "PRIVATE-ANSWER-MARKER"

    class FailingRecorder:
        def record(self, _: LearningEventCommand) -> None:
            raise RuntimeError(private_marker)

    sink = BestEffortLearningEventSink(FailingRecorder())  # type: ignore[arg-type]
    result = sink.record(
        command(
            LearningEventType.TASK_VIEW,
            {"source": "task-page"},
            actor=private_marker,
        )
    )

    assert result is None
    assert private_marker not in caplog.text
    assert caplog.records[0].failure_category == "analytics_persistence_unavailable"


def test_trusted_hooks_deduplicate_feedback_view_per_actor(
    event_session_factory: sessionmaker[Session],
) -> None:
    hooks = TrustedLearningEventHooks(recorder(event_session_factory))
    workflow_run_id = str(uuid4())
    seed_workflow(event_session_factory, workflow_run_id)
    arguments = {
        "actor_reference": "student-1",
        "course_id": "course-1",
        "task_id": "task-1",
        "workflow_run_id": workflow_run_id,
        "correlation_id": str(uuid4()),
        "feedback_status": "validated",
    }

    first = hooks.record_feedback_view(**arguments)
    second = hooks.record_feedback_view(**arguments)
    hooks.record_feedback_view(**{**arguments, "actor_reference": "student-2"})

    assert first == second
    with event_session_factory() as session:
        stored = list(session.scalars(select(LearningEvent)))
        assert len(stored) == 2
        assert {event.workflow_reference for event in stored} == {workflow_run_id}


def test_workflow_reference_is_required_only_for_trusted_feedback_views(
    event_session_factory: sessionmaker[Session],
) -> None:
    strict_recorder = recorder(event_session_factory)

    with pytest.raises(ValueError, match="require a workflow reference"):
        strict_recorder.record(
            command(
                LearningEventType.FEEDBACK_VIEW,
                {"feedback_status": "validated"},
            )
        )
    with pytest.raises(ValueError, match="only valid for feedback-view"):
        strict_recorder.record(
            command(
                LearningEventType.TASK_VIEW,
                {"source": "task-page"},
                workflow_reference=str(uuid4()),
            )
        )


def test_trusted_submission_and_completion_hooks_use_typed_metadata(
    event_session_factory: sessionmaker[Session],
) -> None:
    hooks = TrustedLearningEventHooks(recorder(event_session_factory))

    hooks.record_submission(
        actor_reference="student-1",
        course_id="course-1",
        task_id="task-1",
        source_event_id=str(uuid4()),
        correlation_id=str(uuid4()),
        attempt_number=2,
        score=75.0,
    )
    hooks.record_completion(
        actor_reference="student-1",
        course_id="course-1",
        task_id="task-1",
        source_event_id=str(uuid4()),
        correlation_id=str(uuid4()),
        completion_status="passed",
        score=75.0,
    )

    with event_session_factory() as session:
        stored = {
            event.event_type: event.metadata_payload
            for event in session.scalars(select(LearningEvent))
        }
    assert stored == {
        LearningEventType.SUBMISSION: {"attempt_number": 2, "score": 75.0},
        LearningEventType.COMPLETION: {
            "completion_status": "passed",
            "score": 75.0,
        },
    }


def test_feedback_view_tracker_is_best_effort_and_omits_private_failures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    private_marker = "PRIVATE-FEEDBACK-MARKER"

    class FailingHooks:
        def record_feedback_view(self, **_: object) -> None:
            raise RuntimeError(private_marker)

    tracker = BestEffortFeedbackViewTracker(FailingHooks())  # type: ignore[arg-type]
    tracker.record_terminal_view(
        actor_reference=private_marker,
        course_id="course-private",
        task_id="task-private",
        workflow_run_id=str(uuid4()),
        correlation_id=str(uuid4()),
        feedback_status="validated",
    )

    assert private_marker not in caplog.text
    assert caplog.records[0].failure_category == "analytics_persistence_unavailable"
