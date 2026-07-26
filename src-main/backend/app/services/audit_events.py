from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from app.models.audit import AuditAction, AuditOutcome
from app.schemas.audit import AuditEventCommand, AuditEventReceipt

SYSTEM_FEEDBACK_ACTOR = "system_feedback-worker"


class AuditEventSink(Protocol):
    def record(self, command: AuditEventCommand) -> AuditEventReceipt | None: ...


class AuditPseudonymizer(Protocol):
    def pseudonymize(self, namespace: str, reference: str) -> str: ...


class FeedbackAuditEvents:
    """Typed, content-free mapping from feedback lifecycle changes to audit rows."""

    def __init__(
        self,
        sink: AuditEventSink,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._sink = sink
        self._now = now

    def generation_started(
        self,
        workflow_id: str,
        correlation_id: str,
        *,
        execution_token: str | None = None,
    ) -> None:
        self._system_event(
            AuditAction.FEEDBACK_GENERATION_STARTED,
            workflow_id,
            correlation_id,
            f"claim-{execution_token or 'unfenced'}",
        )

    def generation_completed(
        self,
        workflow_id: str,
        correlation_id: str,
        *,
        attempt: int,
        succeeded: bool,
        failure_category: str = "provider_unavailable",
        execution_token: str | None = None,
    ) -> None:
        self._system_event(
            AuditAction.FEEDBACK_GENERATION_COMPLETED,
            workflow_id,
            correlation_id,
            f"attempt-{attempt}-{execution_token or 'unfenced'}",
            succeeded=succeeded,
            failure_category=failure_category,
        )

    def judged(
        self,
        workflow_id: str,
        correlation_id: str,
        *,
        attempt: int,
        succeeded: bool,
        failure_category: str = "judge_unavailable",
        execution_token: str | None = None,
    ) -> None:
        self._system_event(
            AuditAction.FEEDBACK_JUDGED,
            workflow_id,
            correlation_id,
            f"attempt-{attempt}-{execution_token or 'unfenced'}",
            succeeded=succeeded,
            failure_category=failure_category,
        )

    def regenerated(
        self,
        workflow_id: str,
        correlation_id: str,
        *,
        execution_token: str | None = None,
    ) -> None:
        self._system_event(
            AuditAction.FEEDBACK_REGENERATED,
            workflow_id,
            correlation_id,
            f"attempt-2-{execution_token or 'unfenced'}",
        )

    def fallback_used(self, workflow_id: str, correlation_id: str) -> None:
        self._system_event(
            AuditAction.FEEDBACK_FALLBACK_USED,
            workflow_id,
            correlation_id,
            "released",
        )

    def workflow_completed(self, workflow_id: str, correlation_id: str) -> None:
        self._system_event(
            AuditAction.WORKFLOW_COMPLETED,
            workflow_id,
            correlation_id,
            "terminal",
        )

    def workflow_failed(
        self,
        workflow_id: str,
        correlation_id: str,
        failure_category: str,
    ) -> None:
        self._system_event(
            AuditAction.WORKFLOW_FAILED,
            workflow_id,
            correlation_id,
            "terminal",
            succeeded=False,
            failure_category=failure_category,
        )

    def feedback_viewed(
        self,
        actor_pseudonym: str,
        feedback_id: str,
        correlation_id: str,
    ) -> None:
        self._actor_event(
            actor_pseudonym,
            AuditAction.FEEDBACK_VIEWED,
            "feedback",
            feedback_id,
            correlation_id,
            f"actor-{actor_pseudonym}",
        )

    def feedback_reported(
        self,
        actor_pseudonym: str,
        report_id: str,
        correlation_id: str,
    ) -> None:
        self._actor_event(
            actor_pseudonym,
            AuditAction.FEEDBACK_REPORTED,
            "feedback_report",
            report_id,
            correlation_id,
            f"report-{report_id}",
        )

    def _system_event(
        self,
        action: AuditAction,
        workflow_id: str,
        correlation_id: str,
        discriminator: str,
        *,
        succeeded: bool = True,
        failure_category: str | None = None,
    ) -> None:
        self._actor_event(
            SYSTEM_FEEDBACK_ACTOR,
            action,
            "feedback_workflow",
            workflow_id,
            correlation_id,
            discriminator,
            succeeded=succeeded,
            failure_category=failure_category,
        )

    def _actor_event(
        self,
        actor_reference: str,
        action: AuditAction,
        resource_type: str,
        resource_id: str,
        correlation_id: str,
        discriminator: str,
        *,
        succeeded: bool = True,
        failure_category: str | None = None,
    ) -> None:
        outcome = AuditOutcome.SUCCESS if succeeded else AuditOutcome.FAILURE
        self._sink.record(
            AuditEventCommand(
                actor_reference=actor_reference,
                action=action,
                outcome=outcome,
                correlation_id=correlation_id,
                resource_type=resource_type,
                resource_id=resource_id,
                failure_category=None if succeeded else failure_category,
                deduplication_key=(f"{action.value}:{resource_id}:{discriminator}:{outcome.value}"),
                occurred_at=self._now(),
            )
        )


class StudentAuditTracker:
    def __init__(
        self,
        events: FeedbackAuditEvents,
        pseudonymizer: AuditPseudonymizer,
    ) -> None:
        self._events = events
        self._pseudonymizer = pseudonymizer

    def record_feedback_view(
        self,
        *,
        actor_reference: str,
        feedback_id: str,
        correlation_id: str,
    ) -> None:
        try:
            self._events.feedback_viewed(
                self._pseudonymizer.pseudonymize("audit-actor", actor_reference),
                feedback_id,
                correlation_id,
            )
        except Exception:
            # Audit and pseudonymization failures cannot change the result of a
            # student-facing terminal feedback read.
            return

    def record_feedback_report(
        self,
        *,
        actor_reference: str,
        report_id: str,
        correlation_id: str,
    ) -> None:
        try:
            self._events.feedback_reported(
                self._pseudonymizer.pseudonymize("audit-actor", actor_reference),
                report_id,
                correlation_id,
            )
        except Exception:
            # Report persistence is authoritative; auditing remains best effort.
            return


class NullStudentAuditTracker:
    def record_feedback_view(self, **_: str) -> None:
        return

    def record_feedback_report(self, **_: str) -> None:
        return
