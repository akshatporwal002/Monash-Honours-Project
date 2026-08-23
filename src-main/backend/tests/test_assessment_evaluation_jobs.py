"""Durable assessment-evaluation orchestration tests."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from support.assessment import build_assessment_attempt

from app.domain.assessment import AssessmentAttemptState, CriterionDecision
from app.models.assessment import (
    AssessmentApprovalState,
    AssessmentDecision,
    AssessmentDefinitionVersion,
    AssessmentEvaluationFailureCategory,
    AssessmentEvaluationJob,
    AssessmentEvaluationJobState,
    CriterionEvaluation,
    TaskApproval,
)
from app.schemas.assessment import EvidenceReference
from app.services.assessment.evaluation import (
    AssessmentEvaluationFaultError,
    AssessmentEvaluationService,
    CriterionEvaluationUnavailableError,
    UnavailableQualityReviewPort,
)
from app.services.assessment.evaluators import EvaluatorOutcome
from app.services.assessment.jobs import (
    AssessmentEvaluationApplication,
    AssessmentEvaluationExecutor,
    AssessmentEvaluationRecoveryWorker,
    SqlAlchemyAssessmentEvaluationJobRepository,
)
from app.services.assessment.runtime import SqlAlchemyRuleCriterionEvaluationPort

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


class StaticCriterionPort:
    def evaluate(self, *, assessment, response_text, bloom_process, criterion) -> EvaluatorOutcome:
        del response_text, bloom_process
        evidence = EvidenceReference(
            assessment=assessment,
            evidence_id=f"response:{assessment.response_version_id}",
            evidence_type="learner_response",
            schema_version="assessment.response.v1",
            record_version=1,
            content_digest=f"sha256:{'a' * 64}",
            source_record_id=assessment.response_version_id,
            source_record_version=1,
            occurred_at=NOW,
        )
        return EvaluatorOutcome(
            decision=CriterionDecision.MET,
            reason="The frozen response contains the approved evidence.",
            evidence=(evidence,),
            evaluator_type=criterion.evaluator_type,
            evaluator_reference="test.rules.v1",
        )


class UnavailableCriterionPort:
    def evaluate(self, **_: object) -> EvaluatorOutcome:
        raise CriterionEvaluationUnavailableError("human evaluation is required")


class AdvisoryCriterionPort(StaticCriterionPort):
    def evaluate(self, **kwargs: object) -> EvaluatorOutcome:
        return replace(super().evaluate(**kwargs), advisory=True)


def _ready_attempt(session: Session):
    attempt, response, criterion, _, owner = build_assessment_attempt(session)
    definition = session.get(AssessmentDefinitionVersion, attempt.assessment_definition_version_id)
    form = response.task_form_version
    assert definition is not None and form is not None
    definition.formal_result_eligible = True
    definition.result_eligibility_declared_at = NOW
    session.commit()
    definition.approval_state = AssessmentApprovalState.APPROVED
    definition.approved_at = NOW
    definition.approved_by_user_id = owner.id
    session.add(
        TaskApproval(
            course_id=attempt.course_id,
            assessment_definition_version_id=definition.id,
            task_form_version_id=form.id,
            actor_user_id=owner.id,
            approval_reason="The frozen task form is approved for orchestration tests.",
            approval_state=AssessmentApprovalState.APPROVED,
            approved_at=NOW,
            approved_by_user_id=owner.id,
        )
    )
    session.commit()
    return attempt, response, criterion


def _service_factory(criterion_port):
    def factory(session: Session, correlation_id: str) -> AssessmentEvaluationService:
        return AssessmentEvaluationService(
            session,
            criterion_port=criterion_port,
            quality_port=UnavailableQualityReviewPort(),
            correlation_id=correlation_id,
            retain_pending_on_fault=True,
        )

    return factory


def test_claims_are_lease_fenced_across_api_and_recovery_worker(db_session: Session) -> None:
    attempt, response, _ = _ready_attempt(db_session)
    repository = SqlAlchemyAssessmentEvaluationJobRepository(db_session)
    repository.ensure_pending(attempt)
    application = AssessmentEvaluationApplication(
        repository,
        now=lambda: NOW,
        uuid_factory=lambda: "00000000-0000-4000-8000-000000000031",
        lease_duration=timedelta(minutes=5),
    )

    api_claim = application.start(response.id)
    duplicate = application.start(response.id)

    assert api_claim is not None
    assert duplicate is None
    assert api_claim.processing_attempts == 1

    recovery_claim = repository.claim_next(
        now=NOW + timedelta(minutes=6),
        lease_expires_at=NOW + timedelta(minutes=11),
        execution_token="00000000-0000-4000-8000-000000000032",
        maximum_attempts=3,
    )
    assert recovery_claim is not None
    assert recovery_claim.processing_attempts == 2
    assert repository.complete(api_claim, completed_at=NOW + timedelta(minutes=7)) is False
    assert repository.complete(recovery_claim, completed_at=NOW + timedelta(minutes=7)) is True


def test_expired_final_claim_moves_to_human_review(db_session: Session) -> None:
    attempt, _, _ = _ready_attempt(db_session)
    repository = SqlAlchemyAssessmentEvaluationJobRepository(db_session)
    repository.ensure_pending(attempt)
    claim = None
    for sequence in range(3):
        observed = NOW + timedelta(minutes=sequence * 6)
        claim = repository.claim_next(
            now=observed,
            lease_expires_at=observed + timedelta(minutes=5),
            execution_token=f"00000000-0000-4000-8000-{40 + sequence:012d}",
            maximum_attempts=3,
        )
        assert claim is not None and claim.processing_attempts == sequence + 1
    assert claim is not None

    exhausted = repository.finalize_next_exhausted(
        observed_at=claim.lease_expires_at + timedelta(seconds=1),
        maximum_attempts=3,
    )

    job = repository.get(attempt.id)
    assert exhausted == attempt.id
    assert job is not None
    assert job.state is AssessmentEvaluationJobState.REVIEW_REQUIRED
    assert job.failure_category is AssessmentEvaluationFailureCategory.PERSISTENCE_UNAVAILABLE


def test_configured_executor_creates_one_provisional_decision(db_session: Session) -> None:
    attempt, _, _ = _ready_attempt(db_session)
    repository = SqlAlchemyAssessmentEvaluationJobRepository(db_session)
    repository.ensure_pending(attempt)
    claim = repository.claim_next(
        now=NOW,
        lease_expires_at=NOW + timedelta(minutes=5),
        execution_token="00000000-0000-4000-8000-000000000033",
        maximum_attempts=3,
    )
    assert claim is not None
    executor = AssessmentEvaluationExecutor(
        lambda: db_session,
        _service_factory(StaticCriterionPort()),
        now=lambda: NOW + timedelta(seconds=1),
    )

    asyncio.run(executor.execute(claim))
    asyncio.run(executor.execute(claim))

    decisions = db_session.scalars(select(AssessmentDecision)).all()
    job = db_session.get(AssessmentEvaluationJob, attempt.id)
    assert len(decisions) == 1
    assert job is not None and job.state is AssessmentEvaluationJobState.COMPLETED
    assert attempt.state is AssessmentAttemptState.EVALUATED


def test_recovery_worker_processes_a_pending_job_once(db_session: Session) -> None:
    attempt, _, _ = _ready_attempt(db_session)
    SqlAlchemyAssessmentEvaluationJobRepository(db_session).ensure_pending(attempt)
    executor = AssessmentEvaluationExecutor(
        lambda: db_session,
        _service_factory(StaticCriterionPort()),
        now=lambda: NOW + timedelta(seconds=1),
    )
    worker = AssessmentEvaluationRecoveryWorker(
        lambda: db_session,
        executor,
        now=lambda: NOW,
        uuid_factory=lambda: "00000000-0000-4000-8000-000000000035",
    )

    assert asyncio.run(worker.run_once()) is True
    assert asyncio.run(worker.run_once()) is False
    assert len(db_session.scalars(select(AssessmentDecision)).all()) == 1


def test_unavailable_adapter_leaves_response_under_review(db_session: Session) -> None:
    attempt, _, _ = _ready_attempt(db_session)
    repository = SqlAlchemyAssessmentEvaluationJobRepository(db_session)
    repository.ensure_pending(attempt)
    claim = repository.claim_next(
        now=NOW,
        lease_expires_at=NOW + timedelta(minutes=5),
        execution_token="00000000-0000-4000-8000-000000000034",
        maximum_attempts=3,
    )
    assert claim is not None
    executor = AssessmentEvaluationExecutor(
        lambda: db_session,
        _service_factory(UnavailableCriterionPort()),
        now=lambda: NOW + timedelta(seconds=1),
    )

    asyncio.run(executor.execute(claim))

    job = db_session.get(AssessmentEvaluationJob, attempt.id)
    assert job is not None
    assert job.state is AssessmentEvaluationJobState.REVIEW_REQUIRED
    assert job.failure_category is AssessmentEvaluationFailureCategory.PROVIDER_UNAVAILABLE
    assert attempt.state is AssessmentAttemptState.PENDING
    assert db_session.scalar(select(AssessmentDecision)) is None


def test_advisory_evaluator_cannot_create_a_provisional_result(db_session: Session) -> None:
    attempt, _, _ = _ready_attempt(db_session)
    service = _service_factory(AdvisoryCriterionPort())(db_session, attempt.id)

    with pytest.raises(AssessmentEvaluationFaultError) as captured:
        service.evaluate(
            assessment_attempt_id=attempt.id,
            evaluation_idempotency_key=f"assessment-evaluation:{attempt.id}",
        )

    assert captured.value.retryable is False
    assert captured.value.failure_category == "provider_unavailable"
    assert attempt.state is AssessmentAttemptState.PENDING
    assert db_session.scalar(select(AssessmentDecision)) is None


def test_production_rule_adapter_uses_only_the_frozen_response(db_session: Session) -> None:
    attempt, response, criterion = _ready_attempt(db_session)
    service = AssessmentEvaluationService(
        db_session,
        criterion_port=SqlAlchemyRuleCriterionEvaluationPort(db_session),
        quality_port=UnavailableQualityReviewPort(),
        retain_pending_on_fault=True,
    )

    result = service.evaluate(
        assessment_attempt_id=attempt.id,
        evaluation_idempotency_key=f"assessment-evaluation:{attempt.id}",
    )

    evaluation = db_session.scalar(select(AssessmentDecision))
    criterion_outcome = db_session.scalar(select(CriterionEvaluation))
    assert evaluation is not None and evaluation.id == result.decision_id
    assert criterion_outcome is not None
    reference = EvidenceReference.model_validate(criterion_outcome.evidence_references[0])
    assert reference.assessment.response_version_id == response.id
    assert reference.content_digest == response.content_digest
    assert reference.source_record_id == response.id
    assert criterion_outcome.criterion_version_id == criterion.id
