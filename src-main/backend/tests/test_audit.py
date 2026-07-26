from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import create_db_engine, create_session_factory
from app.models.audit import AuditAction, AuditAppendOnlyError, AuditEvent, AuditOutcome
from app.schemas.audit import AuditEventCommand
from app.services.audit import (
    AuditConflictError,
    AuditPersistenceError,
    AuditRecorder,
    BestEffortAuditSink,
)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
ACTOR = f"v1_{'a' * 64}"


def command(**updates: object) -> AuditEventCommand:
    values: dict[str, object] = {
        "actor_reference": ACTOR,
        "action": AuditAction.FEEDBACK_VIEWED,
        "outcome": AuditOutcome.SUCCESS,
        "correlation_id": str(uuid4()),
        "resource_type": "feedback",
        "resource_id": str(uuid4()),
        "deduplication_key": "feedback-viewed:v1_actor:feedback-1",
        "occurred_at": NOW,
    }
    values.update(updates)
    return AuditEventCommand.model_validate(values)


def test_audit_recorder_stores_and_exactly_replays(db_session: Session) -> None:
    recorder = AuditRecorder(db_session)
    original = command()

    first = recorder.record(original)
    replay = recorder.record(original)

    assert first.created is True
    assert replay.created is False
    assert replay.id == first.id
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == 1


def test_audit_recorder_rejects_conflicting_deduplication(db_session: Session) -> None:
    recorder = AuditRecorder(db_session)
    original = command()
    recorder.record(original)

    with pytest.raises(AuditConflictError):
        recorder.record(
            original.model_copy(
                update={"resource_id": str(uuid4())},
            )
        )


def test_failed_audit_requires_sanitized_failure_category() -> None:
    with pytest.raises(ValueError):
        command(outcome=AuditOutcome.FAILURE)

    failed = command(
        outcome=AuditOutcome.FAILURE,
        failure_category="provider_timeout",
    )
    assert failed.failure_category == "provider_timeout"


def test_audit_timestamp_is_normalized_to_utc() -> None:
    local_time = datetime(
        2026,
        7,
        25,
        22,
        0,
        tzinfo=timezone(timedelta(hours=10)),
    )

    event = command(occurred_at=local_time)

    assert event.occurred_at == NOW
    assert event.occurred_at.tzinfo is UTC


def test_audit_schema_rejects_direct_actor_and_non_uuid_resource() -> None:
    with pytest.raises(ValueError):
        command(actor_reference="direct-student-id")
    with pytest.raises(ValueError):
        command(resource_id="submission-private")


def test_audit_rows_are_append_only(db_session: Session) -> None:
    receipt = AuditRecorder(db_session).record(command())
    record = db_session.get(AuditEvent, receipt.id)
    assert record is not None
    record.resource_type = "changed"

    with pytest.raises(AuditAppendOnlyError):
        db_session.commit()

    db_session.rollback()


def test_best_effort_sink_swallows_controlled_failure_without_content() -> None:
    failures: list[tuple[str, str, str]] = []

    class BrokenRecorder:
        def record(self, _: AuditEventCommand) -> None:
            raise AuditPersistenceError("private provider output")

    sink = BestEffortAuditSink(
        lambda: BrokenRecorder(),  # type: ignore[arg-type]
        lambda correlation, action, category: failures.append((correlation, action, category)),
    )
    event = command()

    assert sink.record(event) is None
    assert failures == [
        (
            event.correlation_id,
            AuditAction.FEEDBACK_VIEWED.value,
            "AuditPersistenceError",
        )
    ]
    assert "private provider output" not in repr(failures)


def test_best_effort_sink_swallows_unexpected_recorder_and_failure_hook_errors() -> None:
    class BrokenRecorder:
        def record(self, _: AuditEventCommand) -> None:
            raise RuntimeError("PRIVATE_PROVIDER_OUTPUT")

    def broken_failure_hook(*_: str) -> None:
        raise RuntimeError("PRIVATE_FAILURE_HOOK")

    sink = BestEffortAuditSink(
        lambda: BrokenRecorder(),  # type: ignore[arg-type]
        broken_failure_hook,
    )

    assert sink.record(command()) is None


def test_concurrent_exact_replay_creates_one_audit_event(tmp_path: Path) -> None:
    engine = create_db_engine(f"sqlite:///{(tmp_path / 'audit.db').as_posix()}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    event = command()
    barrier = Barrier(2)

    def record() -> str:
        with session_factory() as session:
            barrier.wait()
            return AuditRecorder(session).record(event).id

    with ThreadPoolExecutor(max_workers=2) as executor:
        identifiers = list(executor.map(lambda _: record(), range(2)))

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 1
    assert identifiers[0] == identifiers[1]
    engine.dispose()
