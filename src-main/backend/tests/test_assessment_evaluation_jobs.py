"""Durable assessment-evaluation orchestration tests."""

from __future__ import annotations

import asyncio
import os
import sqlite3
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from support.assessment import build_assessment_attempt
from support.person4 import migration_config
from support.task_review import bind_reviewed_fixture_form

from app.db.session import create_db_engine, create_session_factory
from app.domain.assessment import AssessmentAttemptState, BloomProcess, CriterionDecision
from app.models.assessment import (
    AssessmentApprovalState,
    AssessmentDecision,
    AssessmentDefinitionVersion,
    AssessmentEvaluationFailureCategory,
    AssessmentEvaluationJob,
    AssessmentEvaluationJobState,
    BloomTargetVersion,
    CriterionEvaluation,
    CriterionEvaluatorType,
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
    AssessmentEvaluationJobError,
    AssessmentEvaluationRecoveryWorker,
    SqlAlchemyAssessmentEvaluationJobRepository,
)
from app.services.assessment.runtime import SqlAlchemyRuleCriterionEvaluationPort
from scripts.learning_backup import create_bundle, restore_bundle

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")

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
    review_event = bind_reviewed_fixture_form(session, form)
    form.approval_state = AssessmentApprovalState.APPROVED
    form.approved_at = datetime.now(UTC)
    form.approved_by_user_id = owner.id
    definition.approval_state = AssessmentApprovalState.APPROVED
    definition.approved_at = NOW
    definition.approved_by_user_id = owner.id
    session.add(
        TaskApproval(
            course_id=attempt.course_id,
            assessment_definition_version_id=definition.id,
            task_form_version_id=form.id,
            task_review_event_id=review_event.id,
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
    from app.models.escalation import EscalationCase

    case = db_session.scalar(select(EscalationCase))
    assert (case.trigger, case.source_id, case.queue_kind) == (
        "EVALUATION_FAILED",
        attempt.id,
        "TECHNICAL",
    )


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
    from app.models.escalation import EscalationCase

    case = db_session.scalar(select(EscalationCase))
    assert (case.queue_kind, case.trigger, case.source_id) == (
        "ASSESSOR",
        "HUMAN_EVALUATION_REQUIRED",
        attempt.id,
    )
    asyncio.run(executor.execute(claim))
    assert len(db_session.scalars(select(EscalationCase)).all()) == 1


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
    bloom = db_session.get(BloomTargetVersion, attempt.bloom_target_version_id)
    assert bloom is not None
    bloom.bloom_process = BloomProcess.REMEMBER
    criterion.approved_anchors = {"all_of": ["observation"]}
    criterion.critical_error_rules = {}
    db_session.commit()
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


@pytest.mark.parametrize(
    "evaluator_type, anchors, critical_errors",
    (
        (CriterionEvaluatorType.RULES, {}, {}),
        (CriterionEvaluatorType.RULES, {"met": ["observation"]}, {}),
        (CriterionEvaluatorType.RULES, {"all_of": ["observation"], "none_of": ["observation"]}, {}),
        (
            CriterionEvaluatorType.RULES,
            {"all_of": ["observation"]},
            {"errors": ["unsupported rule"]},
        ),
        (CriterionEvaluatorType.HUMAN, {}, {}),
    ),
)
def test_unsafe_or_human_rules_leave_attempt_for_review_without_result(
    db_session: Session,
    evaluator_type: CriterionEvaluatorType,
    anchors: dict,
    critical_errors: dict,
) -> None:
    attempt, _, criterion = _ready_attempt(db_session)
    bloom = db_session.get(BloomTargetVersion, attempt.bloom_target_version_id)
    assert bloom is not None
    bloom.bloom_process = BloomProcess.REMEMBER
    criterion.evaluator_type = evaluator_type
    criterion.approved_anchors = anchors
    criterion.critical_error_rules = critical_errors
    db_session.commit()
    service = AssessmentEvaluationService(
        db_session,
        criterion_port=SqlAlchemyRuleCriterionEvaluationPort(db_session),
        quality_port=UnavailableQualityReviewPort(),
        retain_pending_on_fault=True,
    )
    with pytest.raises(AssessmentEvaluationFaultError) as captured:
        service.evaluate(
            assessment_attempt_id=attempt.id, evaluation_idempotency_key=f"settings:{attempt.id}"
        )
    assert captured.value.retryable is False
    assert captured.value.failure_category == "provider_unavailable"
    assert attempt.state is AssessmentAttemptState.PENDING
    assert db_session.scalar(select(AssessmentDecision)) is None


@pytest.mark.parametrize("fault", ["timeout", "malformed"])
def test_provider_fault_retries_preserve_response_and_create_one_decision(db_session, fault):
    attempt, response, _ = _ready_attempt(db_session)
    factory = create_session_factory(db_session.bind)
    original = (response.id, response.answer, response.content_digest)
    repository = SqlAlchemyAssessmentEvaluationJobRepository(db_session)
    repository.ensure_pending(attempt)

    class FaultPort(StaticCriterionPort):
        def evaluate(self, **kwargs):
            if fault == "timeout":
                raise TimeoutError("private provider response must not be stored")
            return replace(super().evaluate(**kwargs), evidence=())

    claim = AssessmentEvaluationApplication(repository, now=lambda: NOW).start(response.id)
    assert claim is not None
    asyncio.run(
        AssessmentEvaluationExecutor(
            factory, _service_factory(FaultPort()), now=lambda: NOW
        ).execute(claim)
    )
    db_session.expire_all()
    job = repository.get(attempt.id)
    assert job.state is AssessmentEvaluationJobState.RETRY_SCHEDULED
    assert job.failure_category is AssessmentEvaluationFailureCategory.PROVIDER_FAULT
    assert db_session.scalar(select(AssessmentDecision)) is None
    assert db_session.scalar(select(CriterionEvaluation)) is None
    assert (response.id, response.answer, response.content_digest) == original
    assert AssessmentEvaluationApplication(repository, now=lambda: NOW).start(response.id) is None

    def clock():
        return NOW + timedelta(seconds=6)

    worker = AssessmentEvaluationRecoveryWorker(
        factory,
        AssessmentEvaluationExecutor(factory, _service_factory(StaticCriterionPort()), now=clock),
        now=clock,
    )
    assert asyncio.run(worker.run_once()) is True
    assert asyncio.run(worker.run_once()) is False
    assert len(db_session.scalars(select(AssessmentDecision)).all()) == 1
    assert len(db_session.scalars(select(CriterionEvaluation)).all()) == 1
    db_session.expire_all()
    assert repository.get(attempt.id).state is AssessmentEvaluationJobState.COMPLETED
    db_session.refresh(response)
    assert (response.id, response.answer, response.content_digest) == original


def test_writer_contention_preserves_pending_job_then_recovers(db_session):
    attempt, response, _ = _ready_attempt(db_session)
    repository = SqlAlchemyAssessmentEvaluationJobRepository(db_session)
    repository.ensure_pending(attempt)
    original = (response.answer, response.content_digest)
    # Hold a real SQLite writer lock; fail immediately rather than waiting 30 seconds.
    db_session.execute(text("PRAGMA busy_timeout=0"))
    with sqlite3.connect(db_session.bind.url.database, timeout=0) as blocker:
        blocker.execute("BEGIN IMMEDIATE")
        with pytest.raises(AssessmentEvaluationJobError, match="could not be claimed"):
            AssessmentEvaluationApplication(repository, now=lambda: NOW).start(response.id)
        blocker.rollback()
    db_session.expire_all()
    job = repository.get(attempt.id)
    assert job.state is AssessmentEvaluationJobState.PENDING
    assert job.processing_attempts == 0
    assert (response.answer, response.content_digest) == original
    worker = AssessmentEvaluationRecoveryWorker(
        lambda: db_session,
        AssessmentEvaluationExecutor(
            lambda: db_session, _service_factory(StaticCriterionPort()), now=lambda: NOW
        ),
        now=lambda: NOW,
    )
    assert asyncio.run(worker.run_once()) is True
    assert asyncio.run(worker.run_once()) is False
    assert len(db_session.scalars(select(AssessmentDecision)).all()) == 1


def test_killed_assessment_claim_recovers_and_restores_immutable_history(tmp_path):
    database = tmp_path / "accepted.db"
    url = f"sqlite:///{database.as_posix()}"
    command.upgrade(migration_config(url), "head")
    engine = create_db_engine(url)
    factory = create_session_factory(engine)
    with factory() as session:
        attempt, response, _ = _ready_attempt(session)
        SqlAlchemyAssessmentEvaluationJobRepository(session).ensure_pending(attempt)
        attempt_id, response_id = attempt.id, response.id
        original = (response.answer, response.content_digest)
    backend = Path(__file__).resolve().parents[1]
    env = dict(os.environ, DATABASE_URL=url, PYTHONPATH=str(backend))
    child = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-c",
            """
import threading
from datetime import datetime, timedelta
from app.db.session import SessionLocal
from app.services.assessment.jobs import AssessmentEvaluationApplication, SqlAlchemyAssessmentEvaluationJobRepository
with SessionLocal() as session:
    claim = AssessmentEvaluationApplication(SqlAlchemyAssessmentEvaluationJobRepository(session),
        now=lambda: datetime.fromisoformat(__import__('sys').argv[2]), lease_duration=timedelta(seconds=1)
    ).start(__import__('sys').argv[1])
    assert claim is not None
    print(claim.execution_token, flush=True)
threading.Event().wait()
""",
            response_id,
            NOW.isoformat(),
        ],
        cwd=backend,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        # A bounded reader confirms the claim committed before the process is killed.
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor() as pool:
            future = pool.submit(child.stdout.readline)
            try:
                token = future.result(timeout=20).strip()
                assert token
            finally:
                child.kill()
                child.wait(timeout=10)
        with factory() as session:
            job = session.get(AssessmentEvaluationJob, attempt_id)
            assert job.execution_token == token
            assert job.state is AssessmentEvaluationJobState.RUNNING

        def clock():
            return NOW + timedelta(seconds=2)

        executor = AssessmentEvaluationExecutor(
            factory, _service_factory(StaticCriterionPort()), now=clock
        )
        worker = AssessmentEvaluationRecoveryWorker(factory, executor, now=clock)
        assert asyncio.run(worker.run_once()) is True
        assert asyncio.run(worker.run_once()) is False
        with factory() as session:
            job = session.get(AssessmentEvaluationJob, attempt_id)
            assert job.state is AssessmentEvaluationJobState.COMPLETED
            assert job.processing_attempts == 2
            decisions = session.scalars(select(AssessmentDecision)).all()
            assert len(decisions) == 1
            decision_id = decisions[0].id
        uploads = tmp_path / "uploads"
        uploads.mkdir()
        bundle = create_bundle(database, uploads, tmp_path / "backups")
        restored = restore_bundle(bundle, tmp_path / "restored")
        restored_engine = create_db_engine(
            f"sqlite:///{(restored / 'database.sqlite3').as_posix()}"
        )
        try:
            with create_session_factory(restored_engine)() as session:
                job = session.get(AssessmentEvaluationJob, attempt_id)
                assert job.state is AssessmentEvaluationJobState.COMPLETED
                assert session.scalar(select(AssessmentDecision)).id == decision_id
                from app.models.lms import SubmissionAttempt

                saved = session.get(SubmissionAttempt, response_id)
                assert (saved.answer, saved.content_digest) == original
                assert session.execute(text("PRAGMA foreign_key_check")).all() == []
                from sqlalchemy.exc import DatabaseError

                with pytest.raises(DatabaseError, match="assessment records are append-only"):
                    session.execute(
                        text("DELETE FROM assessment_decisions WHERE id=:id"), {"id": decision_id}
                    )
                    session.commit()
                session.rollback()
        finally:
            restored_engine.dispose()
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)
        child.stdout.close()
        child.stderr.close()
        engine.dispose()


def test_contention_after_decision_commit_recovers_without_duplicate_history(
    db_session, monkeypatch
):
    attempt, response, _ = _ready_attempt(db_session)
    factory = create_session_factory(db_session.bind)
    repository = SqlAlchemyAssessmentEvaluationJobRepository(db_session)
    repository.ensure_pending(attempt)
    claim = AssessmentEvaluationApplication(
        repository, now=lambda: NOW, lease_duration=timedelta(seconds=1)
    ).start(response.id)
    complete = SqlAlchemyAssessmentEvaluationJobRepository.complete

    def blocked_complete(repository, claim, *, completed_at):
        repository._session.execute(text("PRAGMA busy_timeout=0"))
        with sqlite3.connect(db_session.bind.url.database, timeout=0) as blocker:
            blocker.execute("BEGIN IMMEDIATE")
            try:
                return complete(repository, claim, completed_at=completed_at)
            finally:
                blocker.rollback()

    with monkeypatch.context() as patch:
        patch.setattr(SqlAlchemyAssessmentEvaluationJobRepository, "complete", blocked_complete)
        asyncio.run(
            AssessmentEvaluationExecutor(
                factory, _service_factory(StaticCriterionPort()), now=lambda: NOW
            ).execute(claim)
        )
    db_session.expire_all()
    assert repository.get(attempt.id).state is AssessmentEvaluationJobState.RUNNING
    decision = db_session.scalar(select(AssessmentDecision))
    assert decision is not None
    decision_id = decision.id
    criterion_id = db_session.scalar(select(CriterionEvaluation)).id
    worker = AssessmentEvaluationRecoveryWorker(
        factory,
        AssessmentEvaluationExecutor(
            factory, _service_factory(StaticCriterionPort()), now=lambda: NOW + timedelta(seconds=2)
        ),
        now=lambda: NOW + timedelta(seconds=2),
    )
    assert asyncio.run(worker.run_once()) is True
    assert asyncio.run(worker.run_once()) is False
    db_session.expire_all()
    assert repository.get(attempt.id).state is AssessmentEvaluationJobState.COMPLETED
    assert [row.id for row in db_session.scalars(select(AssessmentDecision))] == [decision_id]
    assert [row.id for row in db_session.scalars(select(CriterionEvaluation))] == [criterion_id]
