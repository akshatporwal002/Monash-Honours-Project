import asyncio
from collections.abc import Iterable
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.schemas.continuation import ContinuationAvailability
from app.services.continuation import (
    ContinuationClaim,
    ContinuationFailureCategory,
    ContinuationQueryService,
    ContinuationRecord,
    ContinuationState,
    ContinuationWorker,
    NextTaskRequest,
    ProgressUpdate,
    TerminalContinuationService,
    TerminalFeedbackNotice,
)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


def notice() -> TerminalFeedbackNotice:
    return TerminalFeedbackNotice(
        workflow_run_id=str(uuid4()),
        pseudonymous_actor_reference=f"v1_{'a' * 64}",
        course_reference="course-quantum-1",
        completed_task_reference="task-bell-state",
        correlation_id=str(uuid4()),
    )


class MemoryRepository:
    def __init__(self) -> None:
        self.records: dict[str, ContinuationRecord] = {}
        self.tokens: dict[str, str] = {}
        self.leases: dict[str, datetime] = {}
        self.ensure_calls = 0
        self.progress_checkpoints = 0
        self.complete_calls = 0
        self.fail_calls = 0
        self.reject_completion = False
        self.exhaustion_calls = 0

    def ensure_pending(self, item: TerminalFeedbackNotice) -> ContinuationRecord:
        self.ensure_calls += 1
        existing = self.records.get(item.workflow_run_id)
        if existing is not None:
            immutable = (
                existing.pseudonymous_actor_reference,
                existing.course_reference,
                existing.completed_task_reference,
                existing.correlation_id,
            )
            replay = (
                item.pseudonymous_actor_reference,
                item.course_reference,
                item.completed_task_reference,
                item.correlation_id,
            )
            if immutable != replay:
                raise RuntimeError("continuation conflict")
            return existing
        record = ContinuationRecord(
            workflow_run_id=item.workflow_run_id,
            pseudonymous_actor_reference=item.pseudonymous_actor_reference,
            course_reference=item.course_reference,
            completed_task_reference=item.completed_task_reference,
            correlation_id=item.correlation_id,
            state=ContinuationState.PENDING,
        )
        self.records[item.workflow_run_id] = record
        return record

    def claim_next(
        self,
        *,
        now: datetime,
        lease_expires_at: datetime,
        execution_token: str,
        maximum_attempts: int,
    ) -> ContinuationClaim | None:
        for workflow_run_id, record in self.records.items():
            due = record.next_retry_at is None or record.next_retry_at <= now
            expired = (
                record.state is ContinuationState.RUNNING and self.leases[workflow_run_id] <= now
            )
            available = record.state is ContinuationState.PENDING or (
                record.state is ContinuationState.RETRY_SCHEDULED and due
            )
            if not (available or expired):
                continue
            if record.processing_attempts >= maximum_attempts:
                continue
            attempts = record.processing_attempts + 1
            running = replace(
                record,
                state=ContinuationState.RUNNING,
                processing_attempts=attempts,
                retryable=False,
                next_retry_at=None,
                failure_category=None,
            )
            self.records[workflow_run_id] = running
            self.tokens[workflow_run_id] = execution_token
            self.leases[workflow_run_id] = lease_expires_at
            return ContinuationClaim(
                workflow_run_id=workflow_run_id,
                execution_token=execution_token,
                pseudonymous_actor_reference=record.pseudonymous_actor_reference,
                course_reference=record.course_reference,
                completed_task_reference=record.completed_task_reference,
                correlation_id=record.correlation_id,
                progress_recorded=record.progress_recorded,
                processing_attempts=attempts,
                lease_expires_at=lease_expires_at,
            )
        return None

    def mark_progress_recorded(self, claim: ContinuationClaim) -> bool:
        if self.tokens.get(claim.workflow_run_id) != claim.execution_token:
            return False
        self.progress_checkpoints += 1
        self.records[claim.workflow_run_id] = replace(
            self.records[claim.workflow_run_id],
            progress_recorded=True,
        )
        return True

    def finalize_next_exhausted(
        self,
        *,
        observed_at: datetime,
        maximum_attempts: int,
    ) -> str | None:
        self.exhaustion_calls += 1
        for workflow_run_id, record in self.records.items():
            if (
                record.state is not ContinuationState.RUNNING
                or record.processing_attempts < maximum_attempts
                or self.leases[workflow_run_id] > observed_at
            ):
                continue
            self.records[workflow_run_id] = replace(
                record,
                state=ContinuationState.FAILED,
                retryable=False,
                next_retry_at=None,
                failure_category=ContinuationFailureCategory.PERSISTENCE_UNAVAILABLE,
            )
            self.tokens.pop(workflow_run_id, None)
            self.leases.pop(workflow_run_id, None)
            return workflow_run_id
        return None

    def complete(
        self,
        claim: ContinuationClaim,
        next_task_reference: str,
        *,
        completed_at: datetime,
    ) -> bool:
        del completed_at
        self.complete_calls += 1
        if (
            self.reject_completion
            or self.tokens.get(claim.workflow_run_id) != claim.execution_token
        ):
            return False
        self.records[claim.workflow_run_id] = replace(
            self.records[claim.workflow_run_id],
            state=ContinuationState.COMPLETED,
            next_task_reference=next_task_reference,
            retryable=False,
            failure_category=None,
        )
        return True

    def fail(
        self,
        claim: ContinuationClaim,
        category: ContinuationFailureCategory,
        *,
        failed_at: datetime,
        retryable: bool,
        next_retry_at: datetime | None,
    ) -> bool:
        del failed_at
        self.fail_calls += 1
        if self.tokens.get(claim.workflow_run_id) != claim.execution_token:
            return False
        self.records[claim.workflow_run_id] = replace(
            self.records[claim.workflow_run_id],
            state=(ContinuationState.RETRY_SCHEDULED if retryable else ContinuationState.FAILED),
            retryable=retryable,
            next_retry_at=next_retry_at,
            failure_category=category,
        )
        return True

    def get(self, workflow_run_id: str) -> ContinuationRecord | None:
        return self.records.get(workflow_run_id)


class ProgressAdapter:
    def __init__(self) -> None:
        self.calls: list[ProgressUpdate] = []
        self.recorded_keys: set[str] = set()

    async def record_terminal_feedback(self, update: ProgressUpdate) -> None:
        self.calls.append(update)
        self.recorded_keys.add(update.idempotency_key)


class Recommender:
    def __init__(self, outcomes: Iterable[str | Exception]) -> None:
        self.outcomes = iter(outcomes)
        self.requests: list[NextTaskRequest] = []

    async def recommend_next_task(self, request: NextTaskRequest) -> str:
        self.requests.append(request)
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class ExplodingRepository(MemoryRepository):
    def ensure_pending(self, item: TerminalFeedbackNotice) -> ContinuationRecord:
        del item
        raise RuntimeError("PRIVATE ANSWER student@example.test provider output")


def test_schedule_and_progress_are_idempotent_by_workflow_id() -> None:
    repository = MemoryRepository()
    progress = ProgressAdapter()
    recommender = Recommender(["next-task:2"])
    item = notice()
    service = TerminalContinuationService(repository)

    first = service.after_terminal_feedback(item)
    replay = service.after_terminal_feedback(item)
    worker = ContinuationWorker(repository, progress, recommender, now=lambda: NOW)
    completed = asyncio.run(worker.run_once())
    no_more_work = asyncio.run(worker.run_once())

    assert first.accepted is True
    assert replay.accepted is True
    assert len(repository.records) == 1
    assert completed.state is ContinuationState.COMPLETED
    assert no_more_work.processed is False
    assert repository.progress_checkpoints == 1
    assert progress.recorded_keys == {item.workflow_run_id}
    assert progress.calls[0].idempotency_key == item.workflow_run_id


def test_retry_resumes_after_progress_checkpoint_without_duplicate_progress() -> None:
    repository = MemoryRepository()
    progress = ProgressAdapter()
    private_exception = RuntimeError(
        "provider failed with raw answer: |psi> and learner@example.test"
    )
    recommender = Recommender([private_exception, "opaque-next_task.v3"])
    item = notice()
    TerminalContinuationService(repository).after_terminal_feedback(item)
    clock = [NOW]
    worker = ContinuationWorker(
        repository,
        progress,
        recommender,
        now=lambda: clock[0],
        retry_backoff=timedelta(seconds=5),
    )

    failed = asyncio.run(worker.run_once())
    clock[0] += timedelta(seconds=5)
    completed = asyncio.run(worker.run_once())

    assert failed.state is ContinuationState.RETRY_SCHEDULED
    assert failed.retryable is True
    assert failed.failure_category is ContinuationFailureCategory.RECOMMENDER_UNAVAILABLE
    assert completed.state is ContinuationState.COMPLETED
    assert len(progress.calls) == 1
    assert len(recommender.requests) == 2
    record = repository.records[item.workflow_run_id]
    assert record.processing_attempts == 2
    assert record.next_task_reference == "opaque-next_task.v3"
    assert "raw answer" not in repr(record)
    assert "learner@example.test" not in repr(record)


def test_opaque_next_task_handoff_is_returned_without_recommendation_logic() -> None:
    repository = MemoryRepository()
    progress = ProgressAdapter()
    opaque_reference = "team-owned:quantum-path_4.next"
    recommender = Recommender([opaque_reference])
    item = notice()
    TerminalContinuationService(repository).after_terminal_feedback(item)

    asyncio.run(
        ContinuationWorker(
            repository,
            progress,
            recommender,
            now=lambda: NOW,
        ).run_once()
    )
    response = ContinuationQueryService(repository).get(item.workflow_run_id)

    assert response.status is ContinuationAvailability.READY
    assert response.next_task_reference == opaque_reference
    assert recommender.requests == [
        NextTaskRequest(
            workflow_run_id=item.workflow_run_id,
            pseudonymous_actor_reference=item.pseudonymous_actor_reference,
            course_reference=item.course_reference,
            completed_task_reference=item.completed_task_reference,
            correlation_id=item.correlation_id,
        )
    ]


def test_continuation_failure_cannot_withhold_already_released_feedback() -> None:
    released_feedback = {"feedback_id": str(uuid4()), "summary": "Durable feedback"}
    item = notice()

    receipt = TerminalContinuationService(ExplodingRepository()).after_terminal_feedback(item)

    assert receipt.accepted is False
    assert receipt.failure_category is ContinuationFailureCategory.PERSISTENCE_UNAVAILABLE
    assert released_feedback["summary"] == "Durable feedback"
    assert "PRIVATE ANSWER" not in repr(receipt)
    assert "student@example.test" not in repr(receipt)


def test_missing_adapter_fails_closed_with_only_a_sanitized_category() -> None:
    repository = MemoryRepository()
    item = notice()
    TerminalContinuationService(repository).after_terminal_feedback(item)

    outcome = asyncio.run(
        ContinuationWorker(
            repository,
            progress_adapter=None,
            recommender=Recommender(["never-used"]),
            now=lambda: NOW,
        ).run_once()
    )
    response = ContinuationQueryService(repository).get(item.workflow_run_id)

    assert outcome.state is ContinuationState.FAILED
    assert outcome.retryable is False
    assert outcome.failure_category is ContinuationFailureCategory.PROGRESS_ADAPTER_NOT_CONFIGURED
    assert response.status is ContinuationAvailability.UNAVAILABLE
    assert response.next_task_reference is None
    assert "not_configured" not in response.model_dump_json()


def test_missing_recommender_does_not_block_the_progress_checkpoint() -> None:
    repository = MemoryRepository()
    progress = ProgressAdapter()
    item = notice()
    TerminalContinuationService(repository).after_terminal_feedback(item)

    outcome = asyncio.run(
        ContinuationWorker(
            repository,
            progress_adapter=progress,
            recommender=None,
            now=lambda: NOW,
        ).run_once()
    )

    assert outcome.failure_category is ContinuationFailureCategory.RECOMMENDER_NOT_CONFIGURED
    assert repository.records[item.workflow_run_id].progress_recorded is True
    assert progress.recorded_keys == {item.workflow_run_id}


def test_privacy_minimal_adapter_requests_and_invalid_handoff_rejection() -> None:
    repository = MemoryRepository()
    progress = ProgressAdapter()
    recommender = Recommender(["student@example.test"])
    item = notice()
    TerminalContinuationService(repository).after_terminal_feedback(item)

    outcome = asyncio.run(
        ContinuationWorker(
            repository,
            progress,
            recommender,
            now=lambda: NOW,
            maximum_attempts=1,
        ).run_once()
    )

    assert outcome.failure_category is ContinuationFailureCategory.INVALID_RECOMMENDATION
    request_text = repr(asdict(recommender.requests[0]))
    progress_text = repr(asdict(progress.calls[0]))
    for forbidden in (
        "submitted_answer",
        "submission_id",
        "feedback_content",
        "email",
        "student_id",
        "provider_output",
    ):
        assert forbidden not in request_text
        assert forbidden not in progress_text
    stored = repository.records[item.workflow_run_id]
    assert stored.next_task_reference is None
    assert stored.failure_category is ContinuationFailureCategory.INVALID_RECOMMENDATION


def test_malformed_notice_does_not_echo_sensitive_values() -> None:
    private_value = "PRIVATE ANSWER student@example.test"
    malformed = TerminalFeedbackNotice(
        workflow_run_id=private_value,
        pseudonymous_actor_reference=private_value,
        course_reference=private_value,
        completed_task_reference=private_value,
        correlation_id=private_value,
    )

    receipt = TerminalContinuationService(MemoryRepository()).after_terminal_feedback(malformed)

    assert receipt.accepted is False
    assert receipt.failure_category is ContinuationFailureCategory.INVALID_NOTICE
    assert private_value not in repr(receipt)


def test_stale_worker_cannot_persist_the_next_task_reference() -> None:
    repository = MemoryRepository()
    repository.reject_completion = True
    item = notice()
    TerminalContinuationService(repository).after_terminal_feedback(item)

    outcome = asyncio.run(
        ContinuationWorker(
            repository,
            ProgressAdapter(),
            Recommender(["next-task"]),
            now=lambda: NOW,
        ).run_once()
    )

    assert outcome.stale_claim is True
    assert repository.records[item.workflow_run_id].next_task_reference is None


def test_expired_third_attempt_is_finalized_before_new_work_is_claimed() -> None:
    repository = MemoryRepository()
    progress = ProgressAdapter()
    item = notice()
    TerminalContinuationService(repository).after_terminal_feedback(item)
    clock = [NOW]
    worker = ContinuationWorker(
        repository,
        progress,
        Recommender(
            [
                RuntimeError("first transient provider failure"),
                RuntimeError("second transient provider failure"),
            ]
        ),
        now=lambda: clock[0],
        lease_duration=timedelta(seconds=10),
        retry_backoff=timedelta(0),
    )

    assert asyncio.run(worker.run_once()).state is ContinuationState.RETRY_SCHEDULED
    assert asyncio.run(worker.run_once()).state is ContinuationState.RETRY_SCHEDULED
    crashed_claim = repository.claim_next(
        now=clock[0],
        lease_expires_at=clock[0] + timedelta(seconds=10),
        execution_token=str(uuid4()),
        maximum_attempts=3,
    )
    assert crashed_claim is not None
    assert crashed_claim.processing_attempts == 3

    clock[0] += timedelta(seconds=10)
    outcome = asyncio.run(worker.run_once())

    assert outcome.processed is True
    assert outcome.workflow_run_id == item.workflow_run_id
    assert outcome.state is ContinuationState.FAILED
    assert outcome.retryable is False
    assert outcome.failure_category is ContinuationFailureCategory.PERSISTENCE_UNAVAILABLE
    assert repository.records[item.workflow_run_id].state is ContinuationState.FAILED
    assert (
        repository.records[item.workflow_run_id].failure_category
        is ContinuationFailureCategory.PERSISTENCE_UNAVAILABLE
    )
    assert item.workflow_run_id not in repository.tokens
    assert repository.exhaustion_calls == 3
