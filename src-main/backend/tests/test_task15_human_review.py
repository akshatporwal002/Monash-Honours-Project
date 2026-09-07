"""Task 15 human fallback with immutable v1 responses and a read-only port double."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from support.assessment import assign_assessor
from test_assessment_evaluation_api import _ready_attempt

from app.domain.assessment import (
    AssessmentAttemptState,
    AssessmentResult,
    CriterionDecision,
    ResultState,
)
from app.models.assessment import (
    AssessmentDecision,
    AssessmentEvaluationJob,
    AssessmentEvaluationJobState,
    CriterionEvaluation,
    CriterionVersion,
)
from app.models.human_assessment import HumanAssessmentAction, HumanCriterionDecision
from app.models.user import RoleAssignment
from app.schemas.assessment import EvidenceReference
from app.schemas.episode import FrozenResponseRead, ResponseContent
from app.services.assessment.access import RoleAssignmentService, ScopedRoleAccessDeniedError
from app.services.assessment.human_review import (
    HumanAssessmentRequest,
    HumanAssessmentService,
    HumanCriterionInput,
)
from app.services.assessment.review import (
    AssessmentReviewConflictError,
    AssessmentReviewValidationError,
)
from app.services.episode_contract import FrozenResponseStale


class FrozenV1Reader:
    def __init__(self, response):
        self.response = response
        self.stale = False

    def read(self, *, assessment):
        if self.stale:
            raise FrozenResponseStale("Injected stale reference")
        response = self.response
        return FrozenResponseRead(
            reference=EvidenceReference(
                assessment=assessment,
                evidence_id=response.id,
                evidence_type="learner_response",
                schema_version=response.response_schema_version,
                record_version=1,
                content_digest=response.content_digest,
                source_record_id=response.id,
                source_record_version=1,
                occurred_at=response.submitted_at.replace(tzinfo=UTC),
            ),
            assessment_work_start_id=response.assessment_work_start_id,
            task_form_version_id=response.task_form_version_id,
            content=ResponseContent(
                answer=response.answer, code=response.code, circuit=response.circuit
            ),
            episode=None,
            declared_conditions=response.declared_conditions,
        )


def context(session):
    attempt, response, definition, rule, owner = _ready_attempt(session)
    assign_assessor(session, owner, attempt.course_id, owner)
    reader = FrozenV1Reader(response)
    service = HumanAssessmentService(
        session, assignments=RoleAssignmentService(session), reader=reader
    )
    criterion = session.scalar(
        select(CriterionVersion).where(
            CriterionVersion.assessment_definition_version_id == definition.id
        )
    )
    return attempt, response, criterion, owner, service, reader


def request_for(
    service, actor, attempt, response, criterion, decision=CriterionDecision.MET, key="human-1"
):
    detail = service.detail(actor, assessment_attempt_id=attempt.id)
    return HumanAssessmentRequest(
        idempotency_key=key,
        expected_token=detail["expected_token"],
        reason="I inspected the complete frozen response against its approved rule.",
        criteria=(
            HumanCriterionInput(
                criterion.id,
                decision,
                "The response links the observed evidence to its claim.",
                (response.id,),
            ),
        ),
    )


def test_missing_criterion_rows_are_visible_and_human_confirmation_is_atomic(db_session):
    attempt, response, criterion, actor, service, _ = context(db_session)
    rows = service.queue(actor, course_id=attempt.course_id)
    assert len(rows) == 1
    assert rows[0]["assessment_attempt_id"] == attempt.id
    assert rows[0]["criteria"][0]["decision"] is None
    assert rows[0]["criteria"][0]["approved_anchors"] == criterion.approved_anchors
    assert db_session.scalar(select(AssessmentDecision)) is None
    assert db_session.scalar(select(CriterionEvaluation)) is None
    request = request_for(service, actor, attempt, response, criterion)
    receipt = service.finalise(actor, assessment_attempt_id=attempt.id, request=request)
    assert receipt["result"] is AssessmentResult.PASS
    assert receipt["result_state"] == "CONFIRMED"
    row = db_session.scalar(select(HumanCriterionDecision))
    assert row.evaluator_reference == f"human:{actor.id}:{receipt['action_id']}"
    assert row.evidence_references[0]["assessment"]["response_version_id"] == response.id
    assert db_session.scalar(select(CriterionEvaluation)) is None
    assert service.queue(actor, course_id=attempt.course_id) == ()
    replay = service.finalise(actor, assessment_attempt_id=attempt.id, request=request)
    assert replay["action_id"] == receipt["action_id"] and replay["replayed"]
    with pytest.raises(AssessmentReviewConflictError, match="different content"):
        service.finalise(
            actor,
            assessment_attempt_id=attempt.id,
            request=replace(request, reason="Changed reason"),
        )


@pytest.mark.parametrize("decision", [CriterionDecision.NOT_MET, CriterionDecision.NOT_EVALUABLE])
def test_valid_missing_or_unmet_evidence_applies_frozen_pass_rule(db_session, decision):
    attempt, response, criterion, actor, service, _ = context(db_session)
    receipt = service.finalise(
        actor,
        assessment_attempt_id=attempt.id,
        request=request_for(service, actor, attempt, response, criterion, decision),
    )
    assert receipt["result"] is AssessmentResult.INCOMPLETE
    assert receipt["result_state"] == "CONFIRMED"


def test_correcting_criterion_preserves_earlier_human_history(db_session):
    attempt, response, criterion, actor, service, _ = context(db_session)
    service.finalise(
        actor,
        assessment_attempt_id=attempt.id,
        request=request_for(
            service, actor, attempt, response, criterion, CriterionDecision.NOT_MET
        ),
    )
    first = db_session.scalar(select(HumanCriterionDecision))
    service.finalise(
        actor,
        assessment_attempt_id=attempt.id,
        request=request_for(service, actor, attempt, response, criterion, key="correction-2"),
    )
    assert db_session.get(HumanCriterionDecision, first.id).decision is CriterionDecision.NOT_MET
    decision = db_session.scalar(select(AssessmentDecision))
    assert decision.result_state is ResultState.OVERRIDDEN
    assert decision.prior_result is AssessmentResult.INCOMPLETE
    assert len(service.detail(actor, assessment_attempt_id=attempt.id)["history"]) == 2
    with pytest.raises(Exception, match="append-only"):
        db_session.execute(text("UPDATE human_criterion_decisions SET reason='rewritten'"))
    db_session.rollback()


def test_stale_evidence_and_technical_fault_do_not_become_incomplete(db_session):
    attempt, response, criterion, actor, service, reader = context(db_session)
    request = request_for(service, actor, attempt, response, criterion)
    reader.stale = True
    assert not service.detail(actor, assessment_attempt_id=attempt.id)["can_finalise"]
    with pytest.raises(AssessmentReviewConflictError):
        service.finalise(actor, assessment_attempt_id=attempt.id, request=request)
    reader.stale = False
    attempt.state = AssessmentAttemptState.FAULTED
    attempt.fault_reason = "Accepted work was lost by a system fault"
    db_session.commit()
    with pytest.raises(AssessmentReviewConflictError):
        service.finalise(
            actor,
            assessment_attempt_id=attempt.id,
            request=request_for(
                service, actor, attempt, response, criterion, CriterionDecision.NOT_MET
            ),
        )
    assert db_session.scalar(select(AssessmentDecision)) is None


def test_active_worker_lease_rejects_human_action(db_session):
    attempt, response, criterion, actor, service, _ = context(db_session)
    db_session.add(
        AssessmentEvaluationJob(
            assessment_attempt_id=attempt.id,
            response_version_id=response.id,
            evaluation_idempotency_key=f"assessment-evaluation:{attempt.id}",
            correlation_id=attempt.id,
            state=AssessmentEvaluationJobState.RUNNING,
            processing_attempts=1,
            execution_token="00000000-0000-4000-8000-000000000123",
            lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
    )
    db_session.commit()
    with pytest.raises(AssessmentReviewConflictError, match="worker"):
        service.finalise(
            actor,
            assessment_attempt_id=attempt.id,
            request=request_for(service, actor, attempt, response, criterion),
        )
    assert db_session.scalar(select(HumanAssessmentAction)) is None


def test_revoke_blocks_queue_detail_action_and_replay(db_session):
    attempt, response, criterion, actor, service, _ = context(db_session)
    request = request_for(service, actor, attempt, response, criterion)
    service.finalise(actor, assessment_attempt_id=attempt.id, request=request)
    assignment = db_session.scalar(select(RoleAssignment))
    assignment.revoked_at = datetime.now(UTC)
    assignment.revoked_by_user_id = actor.id
    assignment.revocation_reason = "Teaching assignment ended"
    db_session.commit()
    for call in (
        lambda: service.queue(actor, course_id=attempt.course_id),
        lambda: service.detail(actor, assessment_attempt_id=attempt.id),
        lambda: service.finalise(actor, assessment_attempt_id=attempt.id, request=request),
    ):
        with pytest.raises(ScopedRoleAccessDeniedError):
            call()


def test_changed_revision_conflicts_and_missing_criterion_rejects(db_session):
    attempt, response, criterion, actor, service, _ = context(db_session)
    request = request_for(service, actor, attempt, response, criterion)
    with pytest.raises(AssessmentReviewValidationError):
        service.finalise(
            actor, assessment_attempt_id=attempt.id, request=replace(request, criteria=())
        )
    service.finalise(actor, assessment_attempt_id=attempt.id, request=request)
    with pytest.raises(AssessmentReviewConflictError, match="changed"):
        service.finalise(
            actor,
            assessment_attempt_id=attempt.id,
            request=replace(request, idempotency_key="second-assessor"),
        )


@pytest.mark.parametrize("stage", ["replaced", "expires_during_evaluation"])
def test_worker_cannot_persist_with_replaced_or_expired_lease(db_session, stage):
    from test_assessment_evaluation_jobs import (
        StaticCriterionPort,
        _ready_attempt,
        _service_factory,
    )

    from app.services.assessment.evaluation import AssessmentEvaluationConflictError
    from app.services.assessment.jobs import SqlAlchemyAssessmentEvaluationJobRepository

    attempt, response, _ = _ready_attempt(db_session)
    now = datetime.now(UTC)
    repo = SqlAlchemyAssessmentEvaluationJobRepository(db_session)
    repo.ensure_pending(attempt)
    claim = repo.claim_for_response(
        response.id,
        now=now,
        lease_expires_at=now + timedelta(seconds=10),
        execution_token="00000000-0000-4000-8000-000000000911",
    )
    if stage == "replaced":
        repo.claim_next(
            now=now + timedelta(seconds=11),
            lease_expires_at=now + timedelta(seconds=30),
            execution_token="00000000-0000-4000-8000-000000000912",
        )
        times = iter([now + timedelta(seconds=12)])
    else:
        times = iter([now, now + timedelta(seconds=11)])

    def clock():
        return next(times)

    service = _service_factory(StaticCriterionPort())(db_session, attempt.id)
    with pytest.raises(AssessmentEvaluationConflictError, match="worker lease"):
        service.evaluate(
            assessment_attempt_id=attempt.id,
            evaluation_idempotency_key=claim.evaluation_idempotency_key,
            claim_execution_token=claim.execution_token,
            claim_processing_attempts=claim.processing_attempts,
            evaluation_clock=clock,
        )
    assert db_session.scalar(select(AssessmentDecision)) is None
    assert db_session.scalar(select(CriterionEvaluation)) is None
