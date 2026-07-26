from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from app.services.audit_events import FeedbackAuditEvents
from app.services.feedback.application import FeedbackBackgroundExecutor
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository


def _utc_now() -> datetime:
    return datetime.now(UTC)


class FeedbackRecoveryWorker:
    """Find and execute feedback work that no API background task still owns."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        executor: FeedbackBackgroundExecutor,
        *,
        now: Callable[[], datetime] = _utc_now,
        lease_duration: timedelta = timedelta(minutes=5),
        audit_events: FeedbackAuditEvents | None = None,
    ) -> None:
        if lease_duration <= timedelta(0):
            raise ValueError("lease_duration must be positive")
        self._session_factory = session_factory
        self._executor = executor
        self._now = now
        self._lease_duration = lease_duration
        self._audit_events = audit_events

    async def run_once(self) -> bool:
        observed_at = self._now()
        with self._session_factory() as session:
            repository = SqlAlchemyFeedbackWorkflowRepository(session)
            exhausted_workflow_id = repository.finalize_next_exhausted(observed_at=observed_at)
            claim = (
                None
                if exhausted_workflow_id is not None
                else repository.claim_next_recoverable(
                    started_at=observed_at,
                    lease_expires_at=observed_at + self._lease_duration,
                )
            )
        if exhausted_workflow_id is not None:
            if self._audit_events is not None:
                try:
                    self._audit_events.workflow_failed(
                        exhausted_workflow_id,
                        exhausted_workflow_id,
                        "retry_attempts_exhausted",
                    )
                except Exception:
                    pass
            return True
        if claim is None or claim.execution_token is None:
            return False
        await self._executor.execute(
            claim.workflow_run_id,
            claim.submission_id,
            claim.execution_token,
            claim.workflow_run_id,
        )
        return True
