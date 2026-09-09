"""Reports retain their source, scoped ownership and every human action."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from support.assessment import assign_assessor
from support.assessment_review import seed_review_context

from app.models.assessment import AssessmentDecision
from app.models.enums import FeedbackReportCategory, FeedbackStatus
from app.models.escalation import EscalationCase, EscalationEvent
from app.models.persistence import FeedbackRecord, WorkflowRun
from app.models.user import User, UserRole
from app.schemas.escalation import (
    EscalationActionWrite,
    OutputReportWrite,
    QueueWrite,
    SamplingWrite,
)
from app.services.assessment.access import RoleAssignmentService, ScopedRoleAccessDeniedError
from app.services.escalation import EscalationService
from app.services.feedback.contracts import FeedbackReportWrite
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository
from app.services.lms import LmsServiceError


def setup(session, kind="ASSESSOR"):
    fixture = seed_review_context(session)
    actor = session.scalar(select(User).where(User.email == fixture["educator_email"]))
    student = session.scalar(select(User).where(User.email == fixture["student_email"]))
    if kind == "TECHNICAL":
        actor = User(
            email=f"technical-{uuid4().hex}@example.edu",
            full_name="Technical owner",
            password_hash="unused",
            role=UserRole.ADMINISTRATOR,
        )
        session.add(actor)
        session.commit()
    backup = User(
        email=f"backup-{uuid4().hex}@example.edu",
        full_name="Backup owner",
        password_hash="unused",
        role=actor.role,
    )
    session.add(backup)
    session.commit()
    if kind == "ASSESSOR":
        assign_assessor(session, backup, fixture["course_id"], actor)
    service = EscalationService(session)
    configuration = QueueWrite(
        expected_revision=0,
        primary_user_id=actor.id,
        backup_user_id=backup.id,
        acknowledgement_target="One staffed day under the fixture staffing schedule.",
        resolution_target="Two staffed days for normal priority.",
        reason="Synthetic course owners approved for this test.",
    )
    saved = service.configure(actor, fixture["course_id"], kind, configuration)
    assert service.configure(actor, fixture["course_id"], kind, configuration).id == saved.id
    workflow = session.scalar(
        select(WorkflowRun).where(WorkflowRun.submission_id == fixture["response_id"])
    )
    feedback = FeedbackRecord(
        id=str(uuid4()),
        submission_id=fixture["response_id"],
        workflow_run_id=workflow.id,
        status=FeedbackStatus.ACCEPTED,
        generation_attempt=1,
        provider="test",
        model="test",
        prompt_version="test.v1",
        feedback_content={"explanation": "Retained accepted output"},
    )
    session.add(feedback)
    session.commit()
    report = OutputReportWrite(
        source_kind="FEEDBACK",
        source_id=feedback.id,
        queue_kind=kind,
        reason="Please check the explanation.",
        idempotency_key="report",
    )
    return fixture, service, actor, backup, student, feedback, report


@pytest.mark.parametrize("kind", ["ASSESSOR", "TECHNICAL"])
def test_owned_report_moves_through_human_lifecycle_without_result_change(db_session, kind):
    fixture, service, actor, backup, student, _, report = setup(db_session, kind)
    decision = db_session.get(AssessmentDecision, fixture["decision_id"])
    original = (decision.result, decision.result_state)
    case = service.report(student, report)
    assert service.report(student, report).id == case.id
    assert len(service.queue(actor, fixture["course_id"], kind)) == 1
    now = datetime.now(UTC)
    for revision, status in enumerate(("ACKNOWLEDGED", "ACTIONED", "RESOLVED", "CLOSED")):
        command = EscalationActionWrite(
            expected_revision=revision,
            idempotency_key=f"action-{revision}",
            status=status,
            owner_user_id=backup.id,
            severity="NORMAL",
            acknowledgement_due_at=now + timedelta(hours=1),
            resolution_due_at=now + timedelta(hours=48),
            reason=f"PRIVATE: {status}",
            learner_notice=f"Your report is {status.lower()}.",
        )
        result = service.act(backup, case.id, command)
        assert result.revision == revision + 1
        assert service.act(backup, case.id, command).revision == revision + 1
    notices = service.learner_cases(student, fixture["task_id"])
    assert len(notices[0].notices) == 4
    assert "PRIVATE" not in notices[0].model_dump_json()
    assert (decision.result, decision.result_state) == original
    assert len(list(db_session.scalars(select(EscalationEvent)))) == 4
    for table in ("escalation_cases", "escalation_events", "escalation_queue_revisions"):
        with pytest.raises(IntegrityError, match="immutable"):
            db_session.execute(text(f"DELETE FROM {table}"))
        db_session.rollback()


def test_replay_scope_stale_actions_and_out_of_order_closure(db_session):
    fixture, service, actor, _, student, _, report = setup(db_session)
    case = service.report(student, report)
    with pytest.raises(LmsServiceError, match="different details"):
        service.report(student, report.model_copy(update={"reason": "Different report"}))
    db_session.rollback()
    with pytest.raises(LmsServiceError):
        service.report(actor, report)
    db_session.rollback()
    with pytest.raises(ScopedRoleAccessDeniedError):
        service.queue(student, fixture["course_id"], "ASSESSOR")
    now = datetime.now(UTC)
    command = EscalationActionWrite(
        expected_revision=0,
        idempotency_key="skip",
        status="CLOSED",
        owner_user_id=actor.id,
        severity="HIGH",
        acknowledgement_due_at=now,
        resolution_due_at=now,
        reason="Private reason",
        learner_notice="Public notice",
    )
    with pytest.raises(LmsServiceError, match="in order"):
        service.act(actor, case.id, command)
    db_session.rollback()
    service.act(actor, case.id, command.model_copy(update={"status": "ACKNOWLEDGED"}))
    with pytest.raises(LmsServiceError, match="report changed"):
        service.act(
            actor,
            case.id,
            command.model_copy(update={"idempotency_key": "stale", "status": "ACTIONED"}),
        )
    db_session.rollback()
    actor.is_active = False
    db_session.commit()
    with pytest.raises(LmsServiceError, match="access"):
        service.evidence(actor, case.id)


def test_existing_feedback_report_routes_and_accepted_output_can_be_sampled(db_session):
    fixture, service, actor, _, student, feedback, _ = setup(db_session)
    repository = SqlAlchemyFeedbackWorkflowRepository(db_session)
    command = FeedbackReportWrite(
        feedback_id=feedback.id,
        reporter_reference="pseudonymous-test-reference",
        category=FeedbackReportCategory.INCORRECT,
        note="Check this feedback.",
    )
    first = repository.save_report(command)
    assert repository.save_report(command).report_id == first.report_id
    assert len(service.learner_cases(student, fixture["task_id"])) == 1
    assert feedback.id in service.samples(actor, fixture["course_id"])
    sample = service.sample(
        actor,
        fixture["course_id"],
        SamplingWrite(feedback_id=feedback.id, reason="Routine human sampling."),
    )
    assert service.evidence(actor, sample.id)["feedback"] == feedback.feedback_content
    assert len(list(db_session.scalars(select(EscalationCase)))) == 2


def test_overdue_triage_and_unreleased_notices_preserve_private_history(db_session):
    from test_assessor_review_api import _request

    from app.domain.assessment import AssessorReviewAction, ResultState
    from app.services.assessment.review import AssessmentReviewService
    from app.services.escalation_sources import record_signal

    fixture, service, actor, _, student, _, _ = setup(db_session)
    case = record_signal(
        db_session,
        source_kind="ASSESSMENT",
        source_id=fixture["attempt_id"],
        trigger="CONFLICTING_EVIDENCE",
        reason="Human review required.",
    )
    db_session.commit()
    assert service.queue(actor, fixture["course_id"], "ASSESSOR")[0].attention == "NEEDS_TRIAGE"
    command = EscalationActionWrite(
        expected_revision=0,
        idempotency_key="triage",
        status="OPEN",
        severity="CRITICAL",
        owner_user_id=actor.id,
        acknowledgement_due_at=datetime(2020, 1, 1, tzinfo=UTC),
        resolution_due_at=datetime(2020, 1, 2, tzinfo=UTC),
        reason="PRIVATE checked evidence",
        learner_notice="Your result is PASS.",
    )
    assert service.act(actor, case.id, command).attention == "ACKNOWLEDGEMENT_OVERDUE"
    command = command.model_copy(
        update={"expected_revision": 1, "idempotency_key": "ack", "status": "ACKNOWLEDGED"}
    )
    assert service.act(actor, case.id, command).attention == "RESOLUTION_OVERDUE"
    assert "PASS" not in service.learner_cases(student, fixture["task_id"])[0].model_dump_json()
    assert db_session.scalar(select(EscalationEvent.learner_notice)) == "Your result is PASS."
    reviews = AssessmentReviewService(db_session, assignments=RoleAssignmentService(db_session))
    reviews.act(
        actor, decision_id=fixture["decision_id"], request=_request(AssessorReviewAction.CONFIRM)
    )
    assert (
        service.learner_cases(student, fixture["task_id"])[0].notices[0].learner_notice
        == "Your result is PASS."
    )
    reviews.act(
        actor,
        decision_id=fixture["decision_id"],
        request=_request(
            AssessorReviewAction.VOID, expected_state=ResultState.CONFIRMED, expected_revision=1
        ),
    )
    assert "PASS" not in service.learner_cases(student, fixture["task_id"])[0].model_dump_json()
    retained = service.queue(actor, fixture["course_id"], "ASSESSOR")[0]
    assert retained.notices[0].learner_notice == "Your result is PASS."
    assert retained.attention == "RESOLUTION_OVERDUE"
