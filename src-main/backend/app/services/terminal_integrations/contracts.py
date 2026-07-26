from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, TypeAlias

from app.models.enums import (
    TerminalIntegrationFailureCategory,
    TerminalIntegrationType,
)


@dataclass(frozen=True, slots=True)
class RetrievedSourceIntent:
    source_id: str
    label: str
    relevance_score: float


@dataclass(frozen=True, slots=True)
class ContinuationIntegrationIntent:
    correlation_id: str
    pseudonymous_actor_reference: str
    course_reference: str
    completed_task_reference: str
    integration_type: TerminalIntegrationType = TerminalIntegrationType.CONTINUATION


@dataclass(frozen=True, slots=True)
class ResearchIntegrationIntent:
    correlation_id: str
    pseudonymous_user_id: str
    pseudonymous_submission_reference: str
    task_type: str
    fallback_provider: str
    fallback_model: str
    input_references: tuple[str, ...]
    retrieved_sources: tuple[RetrievedSourceIntent, ...]
    retrieval_request_count: int
    retrieval_hit_count: int
    simulation_reference: str | None
    simulation_status: str
    integration_type: TerminalIntegrationType = TerminalIntegrationType.RESEARCH_PAIR


TerminalIntegrationIntent: TypeAlias = ContinuationIntegrationIntent | ResearchIntegrationIntent


@dataclass(frozen=True, slots=True)
class TerminalIntegrationClaim:
    outbox_id: str
    workflow_run_id: str
    integration_type: TerminalIntegrationType
    correlation_id: str
    payload: dict[str, object]
    execution_token: str
    processing_attempts: int
    lease_expires_at: datetime


class TerminalIntegrationRepository(Protocol):
    def claim_next(
        self,
        *,
        now: datetime,
        lease_expires_at: datetime,
        execution_token: str,
        maximum_attempts: int,
    ) -> TerminalIntegrationClaim | None: ...

    def complete(
        self,
        claim: TerminalIntegrationClaim,
        *,
        completed_at: datetime,
    ) -> bool: ...

    def fail(
        self,
        claim: TerminalIntegrationClaim,
        category: TerminalIntegrationFailureCategory,
        *,
        failed_at: datetime,
        retryable: bool,
        next_retry_at: datetime | None,
    ) -> bool: ...

    def recover_expired(self, workflow_run_id: str, *, observed_at: datetime) -> int: ...

    def finalize_next_exhausted(
        self,
        *,
        observed_at: datetime,
        maximum_attempts: int,
    ) -> str | None: ...
