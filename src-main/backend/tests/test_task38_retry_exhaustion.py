"""Real queue transitions when the runtime attempt ceiling changes."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_assessment_evaluation_jobs import (
    NOW,
    StaticCriterionPort,
    _ready_attempt,
    _service_factory,
)
from test_continuation_repository import _notice, _released_workflow
from test_terminal_integration_outbox import _continuation, _result, _save

from app.db.session import create_session_factory
from app.models.assessment import AssessmentDecision, AssessmentEvaluationFailureCategory
from app.models.continuation import ContinuationJob
from app.models.enums import ContinuationFailureCategory, TerminalIntegrationFailureCategory
from app.models.terminal_integration import TerminalIntegrationOutbox
from app.services.assessment.jobs import (
    AssessmentEvaluationExecutor,
    AssessmentEvaluationRecoveryWorker,
    SqlAlchemyAssessmentEvaluationJobRepository,
)
from app.services.continuation.repository import SqlAlchemyContinuationRepository
from app.services.terminal_integrations.repository import SqlAlchemyTerminalIntegrationRepository


def queue(session, kind):
    if kind == "assessment":
        attempt, response, _ = _ready_attempt(session)
        repo = SqlAlchemyAssessmentEvaluationJobRepository(session)
        repo.ensure_pending(attempt)
        return (
            repo,
            lambda: repo.get(attempt.id),
            AssessmentEvaluationFailureCategory.PROVIDER_FAULT,
        )
    if kind == "continuation":
        workflow = _released_workflow(session)
        repo = SqlAlchemyContinuationRepository(session)
        repo.ensure_pending(_notice(workflow.id))
        return (
            repo,
            lambda: session.get(ContinuationJob, workflow.id),
            ContinuationFailureCategory.PERSISTENCE_UNAVAILABLE,
        )
    result = _result()
    _save(session, result, _continuation(str(uuid4())))
    repo = SqlAlchemyTerminalIntegrationRepository(session)
    return (
        repo,
        lambda: session.scalar(select(TerminalIntegrationOutbox)),
        TerminalIntegrationFailureCategory.INTEGRATION_UNAVAILABLE,
    )


def claim(repo, now=NOW, maximum=3):
    return repo.claim_next(
        now=now,
        lease_expires_at=now + timedelta(minutes=5),
        execution_token=str(uuid4()),
        maximum_attempts=maximum,
    )


@pytest.mark.parametrize("kind", ["assessment", "continuation", "outbox"])
def test_lowered_ceiling_finalizes_due_scheduled_retry_without_resurrection(db_session, kind):
    repo, get, category = queue(db_session, kind)
    first = claim(repo)
    assert first is not None
    schedule = (
        {"retry_backoff": timedelta(seconds=5)}
        if kind == "assessment"
        else {"next_retry_at": NOW + timedelta(seconds=5)}
    )
    assert repo.fail(first, category, failed_at=NOW, retryable=True, **schedule)
    assert get().state.value == "retry_scheduled"
    assert repo.finalize_next_exhausted(observed_at=NOW, maximum_attempts=1) is None
    observed = NOW + timedelta(seconds=6)
    assert repo.finalize_next_exhausted(observed_at=observed, maximum_attempts=1) is not None
    db_session.expire_all()
    terminal = get()
    assert terminal.state.value == ("review_required" if kind == "assessment" else "failed")
    assert terminal.processing_attempts == 1
    assert terminal.next_retry_at is None
    assert terminal.failure_category == category
    snapshot = (terminal.state, terminal.completed_at, terminal.failure_category)
    assert claim(repo, now=observed, maximum=3) is None
    assert repo.finalize_next_exhausted(observed_at=observed, maximum_attempts=3) is None
    assert (get().state, get().completed_at, get().failure_category) == snapshot
    assert db_session.scalar(select(AssessmentDecision)) is None


@pytest.mark.parametrize("kind", ["assessment", "continuation", "outbox"])
def test_lowered_ceiling_preserves_active_lease_then_finalizes_expiry(db_session, kind):
    repo, get, _ = queue(db_session, kind)
    first = claim(repo)
    assert first is not None
    assert (
        repo.finalize_next_exhausted(observed_at=NOW + timedelta(seconds=1), maximum_attempts=1)
        is None
    )
    assert get().state.value == "running"
    assert get().execution_token == first.execution_token
    assert (
        repo.finalize_next_exhausted(observed_at=NOW + timedelta(minutes=6), maximum_attempts=1)
        is not None
    )
    assert get().processing_attempts == 1
    assert claim(repo, now=NOW + timedelta(minutes=7), maximum=3) is None


def test_assessment_worker_at_one_attempt_finalizes_first_retryable_fault(db_session):
    attempt, response, _ = _ready_attempt(db_session)
    original = (response.id, response.answer, response.content_digest)
    repository = SqlAlchemyAssessmentEvaluationJobRepository(db_session)
    repository.ensure_pending(attempt)
    sessions = create_session_factory(db_session.bind)

    class FaultPort(StaticCriterionPort):
        def evaluate(self, **kwargs):
            raise TimeoutError("synthetic provider fault")

    worker = AssessmentEvaluationRecoveryWorker(
        sessions,
        AssessmentEvaluationExecutor(sessions, _service_factory(FaultPort()), now=lambda: NOW),
        maximum_attempts=1,
        now=lambda: NOW,
    )
    assert asyncio.run(worker.run_once()) is True
    db_session.expire_all()
    job = repository.get(attempt.id)
    assert job.state.value == "review_required"
    assert job.processing_attempts == 1
    assert job.next_retry_at is None
    assert job.failure_category == AssessmentEvaluationFailureCategory.PROVIDER_FAULT
    assert asyncio.run(worker.run_once()) is False
    assert db_session.scalar(select(AssessmentDecision)) is None
    assert (response.id, response.answer, response.content_digest) == original
