from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import create_db_engine, create_session_factory
from app.models import (
    ContinuationFailureCategory,
    ContinuationJob,
    ContinuationState,
    WorkflowOutcome,
    WorkflowRun,
    WorkflowStage,
)
from app.services.continuation import (
    ContinuationConflictError,
    ContinuationPersistenceError,
    SqlAlchemyContinuationRepository,
    TerminalFeedbackNotice,
)

NOW = datetime(2026, 7, 26, 8, 0, tzinfo=UTC)
LEASE = timedelta(seconds=300)


def _released_workflow(
    session: Session,
    *,
    workflow_run_id: str | None = None,
) -> WorkflowRun:
    workflow = WorkflowRun(
        id=workflow_run_id or str(uuid4()),
        submission_id=f"submission-{uuid4()}",
        course_id="course-quantum",
        task_id="task-entanglement",
        current_stage=WorkflowStage.COMPLETED,
        final_outcome=WorkflowOutcome.FIRST_PASS,
        regeneration_count=0,
        execution_attempt_count=1,
        started_at=NOW - timedelta(seconds=2),
        completed_at=NOW - timedelta(seconds=1),
        latency_ms=1000,
    )
    session.add(workflow)
    session.commit()
    return workflow


def _notice(workflow_run_id: str) -> TerminalFeedbackNotice:
    return TerminalFeedbackNotice(
        workflow_run_id=workflow_run_id,
        pseudonymous_actor_reference=f"v1_{'a' * 64}",
        course_reference="course-quantum",
        completed_task_reference="task-entanglement",
        correlation_id=str(uuid4()),
    )


def _claim(
    repository: SqlAlchemyContinuationRepository,
    *,
    now: datetime = NOW,
    token: str | None = None,
):
    return repository.claim_next(
        now=now,
        lease_expires_at=now + LEASE,
        execution_token=token or str(uuid4()),
        maximum_attempts=3,
    )


def test_ensure_pending_supports_exact_replay_and_rejects_conflict(
    db_session: Session,
) -> None:
    workflow = _released_workflow(db_session)
    item = _notice(workflow.id)
    repository = SqlAlchemyContinuationRepository(db_session)

    created = repository.ensure_pending(item)
    replay = repository.ensure_pending(item)

    assert created == replay
    assert created.state is ContinuationState.PENDING
    assert db_session.scalar(select(func.count()).select_from(ContinuationJob)) == 1

    with pytest.raises(ContinuationConflictError, match="workflow ID was reused"):
        repository.ensure_pending(replace(item, completed_task_reference="task-different"))


def test_ensure_pending_requires_a_released_terminal_workflow(
    db_session: Session,
) -> None:
    workflow = WorkflowRun(
        submission_id=f"submission-{uuid4()}",
        current_stage=WorkflowStage.PENDING,
    )
    db_session.add(workflow)
    db_session.commit()

    with pytest.raises(
        ContinuationPersistenceError,
        match="released workflow is unavailable",
    ):
        SqlAlchemyContinuationRepository(db_session).ensure_pending(_notice(workflow.id))


def test_progress_checkpoint_is_required_before_opaque_completion(
    db_session: Session,
) -> None:
    workflow = _released_workflow(db_session)
    item = _notice(workflow.id)
    repository = SqlAlchemyContinuationRepository(db_session)
    repository.ensure_pending(item)
    claim = _claim(repository)

    assert claim is not None
    assert claim.processing_attempts == 1
    assert claim.lease_expires_at - NOW == LEASE
    assert (
        repository.complete(
            claim,
            "next-task:opaque.v1",
            completed_at=NOW + timedelta(seconds=1),
        )
        is False
    )
    assert repository.mark_progress_recorded(claim) is True
    assert (
        repository.complete(
            claim,
            "next-task:opaque.v1",
            completed_at=NOW + timedelta(seconds=1),
        )
        is True
    )

    record = repository.get(workflow.id)
    assert record is not None
    assert record.state is ContinuationState.COMPLETED
    assert record.progress_recorded is True
    assert record.next_task_reference == "next-task:opaque.v1"
    assert _claim(repository, now=NOW + LEASE + timedelta(seconds=1)) is None


def test_retry_checkpoint_survives_session_and_worker_restart(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'continuation-restart.db').as_posix()}"
    engine = create_db_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    retry_at = NOW + timedelta(seconds=5)

    with session_factory() as first_session:
        workflow = _released_workflow(first_session)
        item = _notice(workflow.id)
        first_repository = SqlAlchemyContinuationRepository(first_session)
        first_repository.ensure_pending(item)
        first_claim = _claim(first_repository)
        assert first_claim is not None
        assert first_repository.mark_progress_recorded(first_claim) is True
        assert (
            first_repository.fail(
                first_claim,
                ContinuationFailureCategory.RECOMMENDER_UNAVAILABLE,
                failed_at=NOW,
                retryable=True,
                next_retry_at=retry_at,
            )
            is True
        )

    with session_factory() as restarted_session:
        restarted_repository = SqlAlchemyContinuationRepository(restarted_session)
        assert (
            _claim(
                restarted_repository,
                now=retry_at - timedelta(microseconds=1),
            )
            is None
        )
        restarted_claim = _claim(restarted_repository, now=retry_at)
        assert restarted_claim is not None
        assert restarted_claim.processing_attempts == 2
        assert restarted_claim.progress_recorded is True
        assert (
            restarted_repository.complete(
                restarted_claim,
                "team-recommender:task-2",
                completed_at=retry_at + timedelta(seconds=1),
            )
            is True
        )
        restored = restarted_repository.get(workflow.id)
        assert restored is not None
        assert restored.state is ContinuationState.COMPLETED

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_expired_claim_is_recovered_and_stale_token_is_fenced(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'continuation-fencing.db').as_posix()}"
    engine = create_db_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as setup_session:
        workflow = _released_workflow(setup_session)
        setup_repository = SqlAlchemyContinuationRepository(setup_session)
        setup_repository.ensure_pending(_notice(workflow.id))

    with session_factory() as stale_session:
        stale_repository = SqlAlchemyContinuationRepository(stale_session)
        stale_claim = _claim(stale_repository, token=str(uuid4()))
        assert stale_claim is not None

        with session_factory() as winner_session:
            winner_repository = SqlAlchemyContinuationRepository(winner_session)
            winner_claim = _claim(
                winner_repository,
                now=NOW + LEASE,
                token=str(uuid4()),
            )
            assert winner_claim is not None
            assert winner_claim.processing_attempts == 2
            assert winner_claim.execution_token != stale_claim.execution_token

            assert stale_repository.mark_progress_recorded(stale_claim) is False
            assert (
                stale_repository.complete(
                    stale_claim,
                    "stale-next-task",
                    completed_at=NOW + LEASE,
                )
                is False
            )
            assert (
                stale_repository.fail(
                    stale_claim,
                    ContinuationFailureCategory.RECOMMENDER_UNAVAILABLE,
                    failed_at=NOW + LEASE,
                    retryable=False,
                    next_retry_at=None,
                )
                is False
            )

            assert winner_repository.mark_progress_recorded(winner_claim) is True
            assert (
                winner_repository.complete(
                    winner_claim,
                    "winner-next-task",
                    completed_at=NOW + LEASE + timedelta(seconds=1),
                )
                is True
            )

    with session_factory() as verification_session:
        stored = SqlAlchemyContinuationRepository(verification_session).get(workflow.id)
        assert stored is not None
        assert stored.processing_attempts == 2
        assert stored.next_task_reference == "winner-next-task"

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_third_attempt_is_terminal_and_cannot_be_reclaimed(
    db_session: Session,
) -> None:
    workflow = _released_workflow(db_session)
    repository = SqlAlchemyContinuationRepository(db_session)
    repository.ensure_pending(_notice(workflow.id))
    observed_at = NOW

    for expected_attempt in (1, 2):
        claim = _claim(repository, now=observed_at)
        assert claim is not None
        assert claim.processing_attempts == expected_attempt
        observed_at += timedelta(seconds=1)
        assert (
            repository.fail(
                claim,
                ContinuationFailureCategory.RECOMMENDER_UNAVAILABLE,
                failed_at=observed_at,
                retryable=True,
                next_retry_at=observed_at,
            )
            is True
        )

    final_claim = _claim(repository, now=observed_at)
    assert final_claim is not None
    assert final_claim.processing_attempts == 3
    with pytest.raises(
        ContinuationPersistenceError,
        match="retry schedule is invalid",
    ):
        repository.fail(
            final_claim,
            ContinuationFailureCategory.RECOMMENDER_UNAVAILABLE,
            failed_at=observed_at,
            retryable=True,
            next_retry_at=observed_at,
        )
    assert (
        repository.fail(
            final_claim,
            ContinuationFailureCategory.RECOMMENDER_UNAVAILABLE,
            failed_at=observed_at,
            retryable=False,
            next_retry_at=None,
        )
        is True
    )
    assert _claim(repository, now=observed_at + LEASE) is None
    stored = repository.get(workflow.id)
    assert stored is not None
    assert stored.state is ContinuationState.FAILED
    assert stored.failure_category is ContinuationFailureCategory.RECOMMENDER_UNAVAILABLE
    assert "exception" not in repr(stored).casefold()


def test_expired_third_attempt_crash_is_durably_finalized(
    db_session: Session,
) -> None:
    workflow = _released_workflow(db_session)
    repository = SqlAlchemyContinuationRepository(db_session)
    repository.ensure_pending(_notice(workflow.id))
    observed_at = NOW

    for _ in range(2):
        claim = _claim(repository, now=observed_at)
        assert claim is not None
        assert (
            repository.fail(
                claim,
                ContinuationFailureCategory.RECOMMENDER_UNAVAILABLE,
                failed_at=observed_at,
                retryable=True,
                next_retry_at=observed_at,
            )
            is True
        )

    crashed_claim = _claim(repository, now=observed_at)
    assert crashed_claim is not None
    assert crashed_claim.processing_attempts == 3
    assert (
        repository.finalize_next_exhausted(
            observed_at=crashed_claim.lease_expires_at - timedelta(microseconds=1),
            maximum_attempts=3,
        )
        is None
    )

    finalized = repository.finalize_next_exhausted(
        observed_at=crashed_claim.lease_expires_at,
        maximum_attempts=3,
    )

    assert finalized == workflow.id
    stored = repository.get(workflow.id)
    assert stored is not None
    assert stored.state is ContinuationState.FAILED
    assert stored.processing_attempts == 3
    assert stored.retryable is False
    assert stored.failure_category is ContinuationFailureCategory.PERSISTENCE_UNAVAILABLE
    job = db_session.get(ContinuationJob, workflow.id)
    assert job is not None
    assert job.execution_token is None
    assert job.lease_expires_at is None
    assert job.next_retry_at is None
    assert job.completed_at is not None
    assert (
        repository.finalize_next_exhausted(
            observed_at=crashed_claim.lease_expires_at + timedelta(seconds=1),
            maximum_attempts=3,
        )
        is None
    )
    assert (
        _claim(
            repository,
            now=crashed_claim.lease_expires_at + timedelta(seconds=1),
        )
        is None
    )


def test_exhaustion_finalizer_cannot_overwrite_a_concurrent_terminal_update(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'continuation-exhaustion-fence.db').as_posix()}"
    engine = create_db_engine(database_url)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as setup_session:
        workflow = _released_workflow(setup_session)
        setup_repository = SqlAlchemyContinuationRepository(setup_session)
        setup_repository.ensure_pending(_notice(workflow.id))
        observed_at = NOW
        for _ in range(2):
            claim = _claim(setup_repository, now=observed_at)
            assert claim is not None
            assert (
                setup_repository.fail(
                    claim,
                    ContinuationFailureCategory.RECOMMENDER_UNAVAILABLE,
                    failed_at=observed_at,
                    retryable=True,
                    next_retry_at=observed_at,
                )
                is True
            )
        final_claim = _claim(setup_repository, now=observed_at)
        assert final_claim is not None

    with session_factory() as snapshot_session:
        stale_job = snapshot_session.get(ContinuationJob, workflow.id)
        assert stale_job is not None
        snapshot_session.expunge(stale_job)
        snapshot_session.rollback()

    with session_factory() as winner_session:
        winner_repository = SqlAlchemyContinuationRepository(winner_session)
        assert (
            winner_repository.fail(
                final_claim,
                ContinuationFailureCategory.INVALID_RECOMMENDATION,
                failed_at=final_claim.lease_expires_at,
                retryable=False,
                next_retry_at=None,
            )
            is True
        )

    with session_factory() as stale_session:
        stale_repository = SqlAlchemyContinuationRepository(stale_session)
        assert (
            stale_repository._finalize_exhausted_job(  # noqa: SLF001
                stale_job,
                final_claim.lease_expires_at,
            )
            is False
        )

    with session_factory() as verification_session:
        stored = SqlAlchemyContinuationRepository(verification_session).get(workflow.id)
        assert stored is not None
        assert stored.state is ContinuationState.FAILED
        assert stored.failure_category is ContinuationFailureCategory.INVALID_RECOMMENDATION

    Base.metadata.drop_all(engine)
    engine.dispose()
