"""A local continuation handoff needs one commit for its target and acknowledgement."""

import asyncio
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import event, func, select, update
from test_terminal_integration_outbox import NOW, _continuation, _result, _save

from app.db.session import create_session_factory
from app.models.continuation import ContinuationJob
from app.models.enums import TerminalIntegrationState
from app.models.terminal_integration import TerminalIntegrationOutbox
from app.services.terminal_integrations.worker import TerminalIntegrationWorker


def seed_worker(session):
    result = _result()
    _save(session, result, _continuation(str(uuid4())))
    return TerminalIntegrationWorker(session, now=lambda: NOW + timedelta(seconds=2))


def test_continuation_target_and_acknowledgement_share_one_commit(db_session):
    worker = seed_worker(db_session)
    factory = create_session_factory(db_session.get_bind())
    committed = []

    def observe(session):
        with factory() as reader:
            committed.append(
                (
                    reader.scalar(select(func.count()).select_from(ContinuationJob)),
                    reader.scalar(select(TerminalIntegrationOutbox.state)),
                )
            )

    event.listen(db_session, "after_commit", observe)
    try:
        result = asyncio.run(worker.run_once())
    finally:
        event.remove(db_session, "after_commit", observe)
    assert result.processed and not result.stale_claim and not result.retryable
    assert committed == [
        (0, TerminalIntegrationState.RUNNING),
        (1, TerminalIntegrationState.COMPLETED),
    ]


def test_failed_acknowledgement_rolls_back_uncommitted_continuation(db_session, monkeypatch):
    worker = seed_worker(db_session)

    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic interruption before acknowledgement")

    with monkeypatch.context() as patch:
        patch.setattr(worker._repository, "complete", fail)
        result = asyncio.run(worker.run_once())
    assert result.processed and result.retryable
    factory = create_session_factory(db_session.get_bind())
    with factory() as reader:
        assert reader.scalar(select(func.count()).select_from(ContinuationJob)) == 0
    # Recovery still consumes the durable pending outbox after its claim expires.
    recovered = asyncio.run(
        TerminalIntegrationWorker(db_session, now=lambda: NOW + timedelta(minutes=6)).run_once()
    )
    assert recovered.processed and not recovered.retryable and not recovered.stale_claim
    assert db_session.scalar(select(func.count()).select_from(ContinuationJob)) == 1


def test_replaced_outbox_claim_cannot_commit_a_new_continuation(db_session, monkeypatch):
    worker = seed_worker(db_session)
    original = worker._apply
    factory = create_session_factory(db_session.get_bind())
    replacement_token = str(uuid4())

    def replace_before_apply(claim):
        with factory() as writer:
            writer.execute(
                update(TerminalIntegrationOutbox)
                .where(TerminalIntegrationOutbox.id == claim.outbox_id)
                .values(execution_token=replacement_token)
            )
            writer.commit()
        original(claim)

    monkeypatch.setattr(worker, "_apply", replace_before_apply)
    result = asyncio.run(worker.run_once())
    assert result.processed and result.stale_claim
    with factory() as reader:
        assert reader.scalar(select(func.count()).select_from(ContinuationJob)) == 0
        assert reader.scalar(select(TerminalIntegrationOutbox.execution_token)) == replacement_token


def test_failure_after_target_flush_does_not_commit_target_with_retry_state(
    db_session, monkeypatch
):
    worker = seed_worker(db_session)
    original = worker._apply

    def interrupt_after_apply(claim):
        original(claim)
        raise RuntimeError("Synthetic interruption after local target flush")

    monkeypatch.setattr(worker, "_apply", interrupt_after_apply)
    result = asyncio.run(worker.run_once())
    assert result.processed and result.retryable
    factory = create_session_factory(db_session.get_bind())
    with factory() as reader:
        assert reader.scalar(select(func.count()).select_from(ContinuationJob)) == 0
        assert (
            reader.scalar(select(TerminalIntegrationOutbox.state))
            == TerminalIntegrationState.RETRY_SCHEDULED
        )


def test_failed_handoff_commit_leaves_only_the_recoverable_claim(db_session):
    worker = seed_worker(db_session)
    commits = 0

    def interrupt_commit(session):
        nonlocal commits
        commits += 1
        if commits == 2:
            raise RuntimeError("Synthetic failed handoff commit")

    event.listen(db_session, "before_commit", interrupt_commit)
    try:
        result = asyncio.run(worker.run_once())
    finally:
        event.remove(db_session, "before_commit", interrupt_commit)
    assert result.processed and result.retryable
    factory = create_session_factory(db_session.get_bind())
    with factory() as reader:
        assert reader.scalar(select(func.count()).select_from(ContinuationJob)) == 0
    recovered = asyncio.run(
        TerminalIntegrationWorker(db_session, now=lambda: NOW + timedelta(minutes=6)).run_once()
    )
    assert recovered.processed and not recovered.retryable and not recovered.stale_claim
    assert db_session.scalar(select(func.count()).select_from(ContinuationJob)) == 1
