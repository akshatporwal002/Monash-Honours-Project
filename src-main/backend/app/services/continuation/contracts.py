from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.models.enums import ContinuationFailureCategory, ContinuationState


@dataclass(frozen=True, slots=True)
class TerminalFeedbackNotice:
    """Privacy-minimal notification produced only after feedback is durable."""

    workflow_run_id: str
    pseudonymous_actor_reference: str
    course_reference: str
    completed_task_reference: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ContinuationRecord:
    workflow_run_id: str
    pseudonymous_actor_reference: str
    course_reference: str
    completed_task_reference: str
    correlation_id: str
    state: ContinuationState
    progress_recorded: bool = False
    processing_attempts: int = 0
    next_task_reference: str | None = None
    failure_category: ContinuationFailureCategory | None = None
    retryable: bool = False
    next_retry_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ContinuationClaim:
    workflow_run_id: str
    execution_token: str
    pseudonymous_actor_reference: str
    course_reference: str
    completed_task_reference: str
    correlation_id: str
    progress_recorded: bool
    processing_attempts: int
    lease_expires_at: datetime


@dataclass(frozen=True, slots=True)
class ProgressUpdate:
    workflow_run_id: str
    pseudonymous_actor_reference: str
    course_reference: str
    completed_task_reference: str
    idempotency_key: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class NextTaskRequest:
    workflow_run_id: str
    pseudonymous_actor_reference: str
    course_reference: str
    completed_task_reference: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ContinuationScheduleReceipt:
    workflow_run_id: str
    accepted: bool
    state: ContinuationState | None
    failure_category: ContinuationFailureCategory | None = None


@dataclass(frozen=True, slots=True)
class ContinuationWorkerOutcome:
    processed: bool
    workflow_run_id: str | None = None
    state: ContinuationState | None = None
    retryable: bool = False
    stale_claim: bool = False
    failure_category: ContinuationFailureCategory | None = None


class ProgressPersistenceAdapter(Protocol):
    async def record_terminal_feedback(self, update: ProgressUpdate) -> None:
        """Record progress idempotently using ``update.idempotency_key``."""


class NextTaskRecommender(Protocol):
    async def recommend_next_task(self, request: NextTaskRequest) -> str: ...


class ContinuationRepository(Protocol):
    def ensure_pending(self, notice: TerminalFeedbackNotice) -> ContinuationRecord:
        """Create once by workflow ID, or return the exact existing record."""

    def claim_next(
        self,
        *,
        now: datetime,
        lease_expires_at: datetime,
        execution_token: str,
        maximum_attempts: int,
    ) -> ContinuationClaim | None:
        """Atomically claim pending, retryable, or expired work."""

    def finalize_next_exhausted(
        self,
        *,
        observed_at: datetime,
        maximum_attempts: int,
    ) -> str | None:
        """Finalize one expired claim whose bounded attempts are exhausted."""

    def mark_progress_recorded(self, claim: ContinuationClaim) -> bool:
        """Persist the progress checkpoint, fenced by claim execution token."""

    def complete(
        self,
        claim: ContinuationClaim,
        next_task_reference: str,
        *,
        completed_at: datetime,
    ) -> bool:
        """Persist the opaque handoff, fenced by claim execution token."""

    def fail(
        self,
        claim: ContinuationClaim,
        category: ContinuationFailureCategory,
        *,
        failed_at: datetime,
        retryable: bool,
        next_retry_at: datetime | None,
    ) -> bool:
        """Persist only a sanitized category, fenced by claim execution token."""

    def get(self, workflow_run_id: str) -> ContinuationRecord | None: ...
