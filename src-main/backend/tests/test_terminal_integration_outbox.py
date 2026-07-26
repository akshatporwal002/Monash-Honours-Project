import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.models.continuation import ContinuationJob
from app.models.enums import (
    TerminalIntegrationFailureCategory,
    TerminalIntegrationState,
    TerminalIntegrationType,
)
from app.models.persistence import ResearchEvaluation, WorkflowRun
from app.models.terminal_integration import TerminalIntegrationOutbox
from app.schemas.feedback import (
    ContextProviderStatus,
    FeedbackContext,
    FeedbackPipelineResult,
    FeedbackPipelineStatus,
    RetrievalContext,
    SafeFallbackFeedback,
    SubmissionContext,
    TaskContext,
    TokenUsage,
)
from app.services.continuation.contracts import TerminalFeedbackNotice
from app.services.continuation.repository import SqlAlchemyContinuationRepository
from app.services.feedback.contracts import PipelinePersistenceRequest
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository
from app.services.terminal_integrations.contracts import (
    ContinuationIntegrationIntent,
    TerminalIntegrationIntent,
)
from app.services.terminal_integrations.planner import (
    DurableTerminalIntegrationPlanner,
)
from app.services.terminal_integrations.repository import (
    SqlAlchemyTerminalIntegrationRepository,
)
from app.services.terminal_integrations.worker import TerminalIntegrationWorker

NOW = datetime(2026, 7, 26, 10, 0, tzinfo=UTC)
PSEUDONYM = f"v1_{'a' * 64}"


def _result(*, workflow_id: str | None = None) -> FeedbackPipelineResult:
    return FeedbackPipelineResult(
        workflow_run_id=workflow_id or str(uuid4()),
        feedback_id=str(uuid4()),
        submission_id=f"submission-{uuid4()}",
        status=FeedbackPipelineStatus.FALLBACK,
        validated_feedback=None,
        safe_fallback=SafeFallbackFeedback(
            feedback_content={"summary": "Safe fallback"},
        ),
        judge_evaluations=[],
        regeneration_count=0,
        fallback_used=True,
        latency_ms=10,
        token_usage=TokenUsage(),
        estimated_cost=Decimal("0"),
        source_references=[],
    )


def _continuation(correlation_id: str) -> ContinuationIntegrationIntent:
    return ContinuationIntegrationIntent(
        correlation_id=correlation_id,
        pseudonymous_actor_reference=PSEUDONYM,
        course_reference="course-1",
        completed_task_reference="task-1",
    )


def _save(
    session: Session,
    result: FeedbackPipelineResult,
    *intents: TerminalIntegrationIntent,
) -> None:
    SqlAlchemyFeedbackWorkflowRepository(session).save_result(
        PipelinePersistenceRequest(
            result=result,
            attempts=(),
            started_at=NOW,
            completed_at=NOW + timedelta(seconds=1),
            course_id="course-1",
            task_id="task-1",
            terminal_integrations=intents,
        )
    )


def _context(
    result: FeedbackPipelineResult,
    *,
    source_label: str = "Source",
) -> FeedbackContext:
    return FeedbackContext(
        correlation_id=str(uuid4()),
        task=TaskContext(
            task_id="task-1",
            course_id="course-1",
            task_type="short_answer",
            prompt="private prompt",
            difficulty="introductory",
            expected_answer="private expected answer",
            learning_outcome_id="outcome-1",
            source_references=["source-1"],
        ),
        submission=SubmissionContext(
            submission_id=result.submission_id,
            task_id="task-1",
            course_id="course-1",
            student_id="private-student",
            attempt_number=1,
            submitted_answer="private answer",
            submitted_at=NOW,
        ),
        retrieval_status=ContextProviderStatus.COMPLETED,
        retrieval_request_ids=["request-1"],
        retrieval_context=[
            RetrievalContext(
                retrieval_request_id="request-1",
                task_id="task-1",
                course_id="course-1",
                source_id="source-1",
                document_id="private-document",
                chunk_id="private-chunk",
                chunk_text="private source chunk",
                relevance_score=0.9,
                source_label=source_label,
            )
        ],
    )


class Eligible:
    async def is_eligible(self, context: FeedbackContext) -> bool:
        del context
        return True


class HungEligibility:
    async def is_eligible(self, context: FeedbackContext) -> bool:
        del context
        await asyncio.Event().wait()
        return True


class Pseudonymizer:
    def __init__(self, value: str = PSEUDONYM) -> None:
        self._value = value

    def pseudonymize(self, namespace: str, reference: str) -> str:
        del namespace, reference
        return self._value


def test_terminal_save_atomically_creates_privacy_safe_outbox(
    db_session: Session,
) -> None:
    result = _result()
    correlation_id = str(uuid4())

    _save(db_session, result, _continuation(correlation_id))

    assert db_session.get(WorkflowRun, result.workflow_run_id) is not None
    outbox = db_session.scalar(select(TerminalIntegrationOutbox))
    assert outbox is not None
    assert outbox.workflow_run_id == result.workflow_run_id
    assert outbox.integration_type is TerminalIntegrationType.CONTINUATION
    assert outbox.state is TerminalIntegrationState.PENDING
    serialized = str(outbox.payload).lower()
    assert "private" not in serialized
    assert "answer" not in serialized
    assert "feedback" not in serialized
    assert "prompt" not in serialized


def test_invalid_optional_intent_never_rolls_back_terminal_feedback(
    db_session: Session,
) -> None:
    result = _result()
    invalid = ContinuationIntegrationIntent(
        correlation_id=str(uuid4()),
        pseudonymous_actor_reference="direct-student-id",
        course_reference="course-1",
        completed_task_reference="task-1",
    )

    _save(db_session, result, invalid)

    assert db_session.get(WorkflowRun, result.workflow_run_id) is not None
    assert db_session.scalar(select(func.count()).select_from(TerminalIntegrationOutbox)) == 0


def test_large_valid_label_is_normalized_and_research_outbox_commits(
    db_session: Session,
) -> None:
    result = _result()
    context = _context(result, source_label="x" * 50_000)
    planner = DurableTerminalIntegrationPlanner(
        Pseudonymizer(),
        research_eligibility=Eligible(),
    )

    intents = asyncio.run(planner.plan(context, result, ()))
    assert {intent.integration_type for intent in intents} == {
        TerminalIntegrationType.CONTINUATION,
        TerminalIntegrationType.RESEARCH_PAIR,
    }

    _save(db_session, result, *intents)
    assert db_session.get(WorkflowRun, result.workflow_run_id) is not None
    assert db_session.scalar(select(func.count()).select_from(TerminalIntegrationOutbox)) == 2
    research = db_session.scalar(
        select(TerminalIntegrationOutbox).where(
            TerminalIntegrationOutbox.integration_type == TerminalIntegrationType.RESEARCH_PAIR
        )
    )
    assert research is not None
    sources = research.payload["retrieved_sources"]
    assert isinstance(sources, list)
    assert len(sources[0]["label"]) == 255


def test_maximal_valid_research_context_fits_bounded_outbox(
    db_session: Session,
) -> None:
    result = _result()
    base = _context(result)
    source_references = [f"source-{index}-{'s' * 235}" for index in range(100)]
    request_ids = [f"request-{index}" for index in range(50)]
    retrieval = [
        RetrievalContext(
            retrieval_request_id=request_ids[index],
            task_id="task-1",
            course_id="course-1",
            source_id=source_references[index],
            document_id=f"document-{index}",
            chunk_id=f"chunk-{index}",
            chunk_text="private source chunk",
            relevance_score=0.9,
            source_label="label-" + ("l" * 49_994),
        )
        for index in range(50)
    ]
    context = FeedbackContext(
        correlation_id=base.correlation_id,
        task=base.task.model_copy(update={"source_references": source_references}),
        submission=base.submission,
        retrieval_status=ContextProviderStatus.COMPLETED,
        retrieval_request_ids=request_ids,
        retrieval_context=retrieval,
    )
    planner = DurableTerminalIntegrationPlanner(
        Pseudonymizer(),
        research_eligibility=Eligible(),
    )

    intents = asyncio.run(planner.plan(context, result, ()))
    assert {intent.integration_type for intent in intents} == {
        TerminalIntegrationType.CONTINUATION,
        TerminalIntegrationType.RESEARCH_PAIR,
    }
    _save(db_session, result, *intents)
    research = db_session.scalar(
        select(TerminalIntegrationOutbox).where(
            TerminalIntegrationOutbox.integration_type == TerminalIntegrationType.RESEARCH_PAIR
        )
    )
    assert research is not None
    encoded = json.dumps(
        research.payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    assert len(encoded) <= 131_072


def test_malformed_pseudonym_plans_nothing_and_feedback_commits(
    db_session: Session,
) -> None:
    result = _result()
    planner = DurableTerminalIntegrationPlanner(
        Pseudonymizer("private-student-id"),
        research_eligibility=Eligible(),
    )

    intents = asyncio.run(planner.plan(_context(result), result, ()))
    assert intents == ()

    _save(db_session, result, *intents)
    assert db_session.get(WorkflowRun, result.workflow_run_id) is not None
    assert db_session.scalar(select(func.count()).select_from(TerminalIntegrationOutbox)) == 0


def test_hung_eligibility_times_out_without_withholding_continuation() -> None:
    result = _result()
    planner = DurableTerminalIntegrationPlanner(
        Pseudonymizer(),
        research_eligibility=HungEligibility(),
        eligibility_timeout_seconds=0.01,
    )

    intents = asyncio.run(planner.plan(_context(result), result, ()))

    assert [intent.integration_type for intent in intents] == [TerminalIntegrationType.CONTINUATION]


def test_expired_claim_replays_idempotently_after_target_commit(
    db_session: Session,
) -> None:
    result = _result()
    correlation_id = str(uuid4())
    _save(db_session, result, _continuation(correlation_id))
    outbox_repository = SqlAlchemyTerminalIntegrationRepository(db_session)
    claim = outbox_repository.claim_next(
        now=NOW + timedelta(seconds=2),
        lease_expires_at=NOW + timedelta(seconds=3),
        execution_token=str(uuid4()),
        maximum_attempts=3,
    )
    assert claim is not None
    SqlAlchemyContinuationRepository(db_session).ensure_pending(
        TerminalFeedbackNotice(
            workflow_run_id=result.workflow_run_id,
            pseudonymous_actor_reference=PSEUDONYM,
            course_reference="course-1",
            completed_task_reference="task-1",
            correlation_id=correlation_id,
        )
    )
    db_session.execute(
        update(TerminalIntegrationOutbox)
        .where(TerminalIntegrationOutbox.id == claim.outbox_id)
        .values(lease_expires_at=NOW + timedelta(seconds=2))
    )
    db_session.commit()

    outcome = asyncio.run(
        TerminalIntegrationWorker(
            db_session,
            now=lambda: NOW + timedelta(seconds=4),
        ).run_once()
    )

    assert outcome.processed is True
    restored = db_session.get(TerminalIntegrationOutbox, claim.outbox_id)
    assert restored is not None
    assert restored.state is TerminalIntegrationState.COMPLETED
    assert restored.processing_attempts == 2
    assert db_session.scalar(select(func.count()).select_from(ContinuationJob)) == 1


def test_worker_reconciles_eligible_research_pair_only_after_terminal_commit(
    db_session: Session,
) -> None:
    result = _result()
    context = _context(result)
    planner = DurableTerminalIntegrationPlanner(
        Pseudonymizer(),
        research_eligibility=Eligible(),
        fallback_provider="provider",
        fallback_model="model",
    )
    intents = asyncio.run(planner.plan(context, result, ()))
    assert {intent.integration_type for intent in intents} == {
        TerminalIntegrationType.CONTINUATION,
        TerminalIntegrationType.RESEARCH_PAIR,
    }
    _save(db_session, result, *intents)

    worker = TerminalIntegrationWorker(
        db_session,
        now=lambda: NOW + timedelta(seconds=2),
    )
    asyncio.run(worker.run_once())
    asyncio.run(worker.run_once())

    assert db_session.scalar(select(func.count()).select_from(ResearchEvaluation)) == 2
    assert db_session.scalar(select(func.count()).select_from(ContinuationJob)) == 1
    assert set(db_session.scalars(select(TerminalIntegrationOutbox.state))) == {
        TerminalIntegrationState.COMPLETED
    }
    research_rows = list(db_session.scalars(select(ResearchEvaluation)))
    assert {row.correlation_id for row in research_rows} == {context.correlation_id}
    serialized_payloads = " ".join(
        str(payload) for payload in db_session.scalars(select(TerminalIntegrationOutbox.payload))
    ).lower()
    for sentinel in (
        "private answer",
        "private prompt",
        "private source chunk",
        "safe fallback",
        "private-student",
    ):
        assert sentinel not in serialized_payloads


def test_exact_terminal_replay_recovers_an_expired_outbox_claim(
    db_session: Session,
) -> None:
    result = _result()
    _save(db_session, result, _continuation(str(uuid4())))
    repository = SqlAlchemyTerminalIntegrationRepository(db_session)
    claim = repository.claim_next(
        now=NOW + timedelta(seconds=2),
        lease_expires_at=NOW + timedelta(seconds=3),
        execution_token=str(uuid4()),
        maximum_attempts=3,
    )
    assert claim is not None

    replay = SqlAlchemyFeedbackWorkflowRepository(db_session)
    existing = replay.get_by_submission(result.submission_id)
    assert existing is not None
    replay.recover_terminal_integrations(
        existing.workflow_run_id,
        observed_at=NOW + timedelta(seconds=4),
    )

    restored = db_session.get(TerminalIntegrationOutbox, claim.outbox_id)
    assert restored is not None
    assert restored.state is TerminalIntegrationState.RETRY_SCHEDULED
    assert restored.execution_token is None


def test_concurrent_outbox_claim_has_exactly_one_winner(
    db_session: Session,
) -> None:
    result = _result()
    _save(db_session, result, _continuation(str(uuid4())))
    sessions = sessionmaker(
        bind=db_session.get_bind(),
        autoflush=False,
        expire_on_commit=False,
    )

    def claim_once(_: int) -> bool:
        with sessions() as session:
            return (
                SqlAlchemyTerminalIntegrationRepository(session).claim_next(
                    now=NOW + timedelta(seconds=2),
                    lease_expires_at=NOW + timedelta(minutes=5),
                    execution_token=str(uuid4()),
                    maximum_attempts=3,
                )
                is not None
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        winners = list(executor.map(claim_once, range(2)))

    assert winners.count(True) == 1
    assert winners.count(False) == 1


def test_infrastructure_failures_stop_after_three_sanitized_attempts(
    db_session: Session,
    monkeypatch: object,
) -> None:
    result = _result()
    _save(db_session, result, _continuation(str(uuid4())))
    current = [NOW + timedelta(seconds=2)]
    worker = TerminalIntegrationWorker(db_session, now=lambda: current[0])

    def fail_apply(claim: object) -> None:
        del claim
        raise RuntimeError("PRIVATE PROVIDER EXCEPTION")

    monkeypatch.setattr(worker, "_apply", fail_apply)  # type: ignore[attr-defined]

    first = asyncio.run(worker.run_once())
    assert first.retryable is True
    current[0] += timedelta(seconds=3)
    second = asyncio.run(worker.run_once())
    assert second.retryable is True
    current[0] += timedelta(seconds=5)
    third = asyncio.run(worker.run_once())
    assert third.retryable is False

    stored = db_session.scalar(select(TerminalIntegrationOutbox))
    assert stored is not None
    assert stored.state is TerminalIntegrationState.FAILED
    assert stored.processing_attempts == 3
    assert stored.failure_category is TerminalIntegrationFailureCategory.INTEGRATION_UNAVAILABLE
    assert "PRIVATE PROVIDER EXCEPTION" not in str(stored.payload)
