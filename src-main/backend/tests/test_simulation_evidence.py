import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from support.task_review import approve_fixture_task, bootstrap_reviewed_demo

from app.models import User, UserRole
from app.models.simulation import CircuitVersion, SimulationOutcome, SimulationRun
from app.services.quantum import CircuitOperation, QuantumSimulationError
from app.services.simulation_evidence import SimulationEvidenceError, SimulationEvidenceService


@pytest.fixture
def evidence(db_session):
    user = User(
        email="circuit@example.test",
        password_hash="unused",
        full_name="Circuit learner",
        role=UserRole.STUDENT,
    )
    db_session.add(user)
    db_session.commit()
    now = [datetime(2026, 9, 7, tzinfo=UTC)]
    service = SimulationEvidenceService(db_session, now=lambda: now[0])
    inputs = dict(
        owner_id=user.id,
        task_id=None,
        qubits=1,
        operations=[CircuitOperation("h", (0,))],
        shots=1,
        seed=42,
        request_key="run-one",
    )
    return service, inputs, now


def test_real_result_survives_new_session_and_replay(db_session, evidence):
    from dataclasses import asdict

    from app.services.quantum import simulate_circuit

    service, inputs, _ = evidence
    original = service.execute(**inputs)
    assert original["status"] == "completed"
    assert original["result"]["probabilities"] == pytest.approx({"0": 0.5, "1": 0.5})
    assert sum(original["result"]["counts"].values()) == 1
    assert original["result"]["engine_versions"] == original["engine_versions"]
    repeated = simulate_circuit(
        qubits=original["circuit"]["qubits"],
        operations=[
            CircuitOperation(op["gate"], tuple(op["targets"]))
            for op in original["circuit"]["operations"]
        ],
        shots=original["shots"],
        seed=original["seed"],
    )
    assert asdict(repeated) == original["result"]
    with Session(db_session.get_bind()) as restarted:
        service = SimulationEvidenceService(restarted)
        assert service.read(original["run_id"]) == original
        assert service.execute(**inputs) == original
    assert db_session.scalar(select(func.count()).select_from(SimulationRun)) == 1


def test_changed_input_cannot_reuse_request_key(evidence):
    service, inputs, _ = evidence
    service.prepare(**inputs)
    with pytest.raises(SimulationEvidenceError, match="different inputs"):
        service.prepare(**{**inputs, "seed": 7})


def test_circuit_version_reused_but_each_run_retained(db_session, evidence):
    service, inputs, _ = evidence
    first, _ = service.prepare(**inputs)
    second, _ = service.prepare(**{**inputs, "request_key": "run-two"})
    assert first != second
    assert db_session.scalar(select(func.count()).select_from(CircuitVersion)) == 1
    assert db_session.scalar(select(func.count()).select_from(SimulationRun)) == 2


def test_concurrent_duplicate_only_claims_one_execution(db_session, evidence):
    _, inputs, now = evidence
    barrier = Barrier(2)

    def claim():
        with Session(db_session.get_bind()) as session:
            service = SimulationEvidenceService(session, now=lambda: now[0])
            barrier.wait()
            return service.prepare(**inputs)

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: claim(), range(2)))
    assert outcomes[0][0] == outcomes[1][0]
    assert sorted(result[1] for result in outcomes) == [False, True]


@pytest.mark.parametrize(
    "code,state",
    [
        ("simulation_timeout", "timed_out"),
        ("simulation_busy", "failed"),
        ("simulation_unavailable", "failed"),
    ],
)
def test_failure_is_durable_and_never_invents_counts(evidence, code, state):
    service, inputs, _ = evidence

    def fail(**_):
        raise QuantumSimulationError("safe failure", code=code)

    service._executor = fail
    result = service.execute(**inputs)
    assert result["status"] == state
    assert result["error_code"] == code
    assert result["result"] is None
    assert service.execute(**inputs) == result


def test_unexpected_failure_is_sanitized(evidence):
    service, inputs, _ = evidence

    def fail(**_):
        raise RuntimeError("secret internal path")

    service._executor = fail
    result = service.execute(**inputs)
    assert result["error_code"] == "simulation_failed"
    assert "secret" not in str(result)


def test_interrupted_run_recovered_and_late_completion_cannot_replace_it(evidence):
    service, inputs, now = evidence
    run_id, _ = service.prepare(**inputs)
    assert service.read(run_id)["status"] == "pending"
    now[0] += timedelta(seconds=21)
    assert service.recover_expired() == 1
    assert service.recover_expired() == 0
    service.finish(run_id, status="completed", result={"counts": {"0": 1}})
    assert service.read(run_id)["status"] == "interrupted"
    assert service.read(run_id)["result"] is None


def test_expired_read_persists_interruption(db_session, evidence):
    service, inputs, now = evidence
    run_id, _ = service.prepare(**inputs)
    now[0] += timedelta(seconds=21)
    assert service.read(run_id)["status"] == "interrupted"
    assert db_session.get(SimulationOutcome, run_id).status == "interrupted"


@pytest.mark.parametrize("table", ["circuit_versions", "simulation_runs", "simulation_outcomes"])
def test_database_history_cannot_be_mutated(db_session, evidence, table):
    service, inputs, _ = evidence
    record = service.execute(**inputs)
    identity = record["circuit_version_id"] if table == "circuit_versions" else record["run_id"]
    for statement in (
        f"UPDATE {table} SET id = id WHERE id = :id",
        f"DELETE FROM {table} WHERE id = :id",
        f"INSERT OR REPLACE INTO {table} SELECT * FROM {table} WHERE id = :id",
    ):
        with pytest.raises(IntegrityError, match="append-only"):
            db_session.execute(text(statement), {"id": identity})
        db_session.rollback()


def test_request_key_unique_constraint_cannot_replace_history(db_session, evidence):
    service, inputs, _ = evidence
    run_id, _ = service.prepare(**inputs)
    with pytest.raises(IntegrityError, match="append-only"):
        db_session.execute(
            text("""INSERT OR REPLACE INTO simulation_runs
            SELECT 'different-id', owner_id, request_key, circuit_version_id, submission_id,
                purpose, shots, seed, policy_version, engine_versions, created_at, deadline_at
            FROM simulation_runs WHERE id = :id"""),
            {"id": run_id},
        )
    db_session.rollback()


def test_invalid_circuit_never_creates_execution_record(db_session, evidence):
    service, inputs, _ = evidence
    with pytest.raises(QuantumSimulationError):
        service.execute(**{**inputs, "operations": [CircuitOperation("z", (0,))]})
    assert db_session.scalar(select(func.count()).select_from(SimulationRun)) == 0


def test_other_learner_cannot_read_private_practice_evidence(db_session, evidence):
    from app.services.lms import LmsService, LmsServiceError

    service, inputs, _ = evidence
    run_id, _ = service.prepare(**inputs)
    other = User(
        email="other@example.test",
        password_hash="unused",
        full_name="Other learner",
        role=UserRole.STUDENT,
    )
    db_session.add(other)
    db_session.commit()
    with pytest.raises(LmsServiceError) as error:
        LmsService(db_session).read_simulation(other, run_id)
    assert error.value.status_code == 404


def test_worker_recovers_expired_requests(db_session, evidence):
    from app.services.simulation_evidence import SimulationRecoveryWorker

    service, inputs, now = evidence
    run_id, _ = service.prepare(**inputs)
    now[0] += timedelta(seconds=21)
    worker = SimulationRecoveryWorker(lambda: Session(db_session.get_bind()), now=lambda: now[0])
    assert asyncio.run(worker.run_once())
    assert not asyncio.run(worker.run_once())
    assert service.read(run_id)["status"] == "interrupted"


def test_feedback_reuses_persisted_submission_simulation_and_rejects_wrong_scope(db_session):
    from test_task_review import _source

    from app.models import LearningTask, TaskType
    from app.schemas.feedback import ContextProviderStatus
    from app.schemas.lms import SubmissionCreate
    from app.services.feedback.providers import SqlAlchemyTaskProvider
    from app.services.feedback.runtime import (
        LmsSubmissionProvider,
        SubmittedCircuitSimulationProvider,
    )
    from app.services.lms import LmsService
    from app.services.rag.source_history import record_approval

    bootstrap_reviewed_demo(db_session)
    student = db_session.scalar(select(User).where(User.role == UserRole.STUDENT))
    task = db_session.scalar(
        select(LearningTask).where(LearningTask.task_type == TaskType.QUANTUM_CIRCUIT)
    )
    task.prerequisite_task_ids = []
    material, revision = _source(db_session, task)
    record_approval(
        db_session,
        course_id=task.course_id,
        material_id=material.id,
        revision_id=revision.id,
        actor_id="fixture-educator",
        state="APPROVED",
        reason="Source checked for simulation feedback fixture",
    )
    db_session.commit()
    approve_fixture_task(db_session, task)
    attempt = LmsService(db_session).submit(
        student,
        task.id,
        SubmissionCreate(
            circuit={
                "qubits": 2,
                "seed": 123,
                "operations": [{"gate": "h", "targets": [0]}, {"gate": "cx", "targets": [0, 1]}],
            },
        ),
    )
    submission = asyncio.run(LmsSubmissionProvider(db_session).get_submission(attempt.id))
    context = asyncio.run(SqlAlchemyTaskProvider(db_session).get_task(task.id))
    provider = SubmittedCircuitSimulationProvider(db_session)
    first = asyncio.run(provider.get_simulation_context(context, submission))
    assert first.status == ContextProviderStatus.COMPLETED
    replay = asyncio.run(provider.get_simulation_context(context, submission))
    assert replay == first
    stored = SimulationEvidenceService(db_session).read(first.context.simulation_id)
    assert stored["submission_id"] == attempt.id
    assert stored["result"]["seed"] == stored["seed"] == 123
    assert stored["result"]["counts"] == first.context.measurement_counts
    assert stored["result"]["probabilities"] == first.context.probability_distribution
    wrong = submission.model_copy(update={"student_id": "99999"})
    assert (
        asyncio.run(provider.get_simulation_context(context, wrong)).status
        == ContextProviderStatus.FAILED
    )
    assert db_session.scalar(select(func.count()).select_from(SimulationRun)) == 1
