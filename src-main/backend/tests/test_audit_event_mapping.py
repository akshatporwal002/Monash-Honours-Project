from datetime import UTC, datetime
from uuid import uuid4

from app.models.audit import AuditAction, AuditOutcome
from app.schemas.audit import AuditEventCommand
from app.services.audit_events import FeedbackAuditEvents, StudentAuditTracker

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
ACTOR = f"v1_{'c' * 64}"


class RecordingSink:
    def __init__(self) -> None:
        self.commands: list[AuditEventCommand] = []

    def record(self, command: AuditEventCommand) -> None:
        self.commands.append(command)


def test_feedback_audit_mapping_covers_every_required_student_action() -> None:
    sink = RecordingSink()
    events = FeedbackAuditEvents(sink, now=lambda: NOW)  # type: ignore[arg-type]
    workflow_id = str(uuid4())
    feedback_id = str(uuid4())
    report_id = str(uuid4())
    correlation_id = str(uuid4())

    events.generation_started(workflow_id, correlation_id)
    events.generation_completed(
        workflow_id,
        correlation_id,
        attempt=1,
        succeeded=True,
    )
    events.judged(workflow_id, correlation_id, attempt=1, succeeded=True)
    events.regenerated(workflow_id, correlation_id)
    events.generation_completed(
        workflow_id,
        correlation_id,
        attempt=2,
        succeeded=False,
    )
    events.judged(
        workflow_id,
        correlation_id,
        attempt=2,
        succeeded=False,
    )
    events.fallback_used(workflow_id, correlation_id)
    events.feedback_viewed(ACTOR, feedback_id, correlation_id)
    events.feedback_reported(ACTOR, report_id, correlation_id)
    events.workflow_completed(workflow_id, correlation_id)
    events.workflow_failed(workflow_id, correlation_id, "provider_unavailable")

    assert {command.action for command in sink.commands} == {
        AuditAction.FEEDBACK_GENERATION_STARTED,
        AuditAction.FEEDBACK_GENERATION_COMPLETED,
        AuditAction.FEEDBACK_JUDGED,
        AuditAction.FEEDBACK_REGENERATED,
        AuditAction.FEEDBACK_FALLBACK_USED,
        AuditAction.FEEDBACK_VIEWED,
        AuditAction.FEEDBACK_REPORTED,
        AuditAction.WORKFLOW_COMPLETED,
        AuditAction.WORKFLOW_FAILED,
    }
    failed = [command for command in sink.commands if command.outcome is AuditOutcome.FAILURE]
    assert {command.failure_category for command in failed} == {
        "provider_unavailable",
        "judge_unavailable",
    }
    assert all(
        command.resource_id in {workflow_id, feedback_id, report_id} for command in sink.commands
    )


def test_student_audit_tracker_is_best_effort_when_pseudonymization_fails() -> None:
    class BrokenPseudonymizer:
        def pseudonymize(self, namespace: str, reference: str) -> str:
            del namespace, reference
            raise RuntimeError("PRIVATE_STUDENT_REFERENCE")

    tracker = StudentAuditTracker(
        FeedbackAuditEvents(RecordingSink()),  # type: ignore[arg-type]
        BrokenPseudonymizer(),
    )

    tracker.record_feedback_view(
        actor_reference="private-student",
        feedback_id=str(uuid4()),
        correlation_id=str(uuid4()),
    )
    tracker.record_feedback_report(
        actor_reference="private-student",
        report_id=str(uuid4()),
        correlation_id=str(uuid4()),
    )
