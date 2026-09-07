"""Durable simulation execution. Each operation owns a short database transaction."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from importlib.metadata import PackageNotFoundError, version
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import LearningTask, SubmissionAttempt, User
from app.models.simulation import CircuitVersion, SimulationOutcome, SimulationRun
from app.services.quantum import (
    SIMULATION_POLICY_VERSION,
    SIMULATION_TIMEOUT_SECONDS,
    CircuitOperation,
    QuantumSimulationError,
    simulate_circuit,
    validate_circuit,
)


class SimulationEvidenceError(ValueError):
    pass


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def engine_versions() -> dict[str, str]:
    result = {}
    for package in ("qiskit", "qiskit-aer"):
        try:
            result[package.replace("-", "_")] = version(package)
        except PackageNotFoundError:
            result[package.replace("-", "_")] = "unavailable"
    return result


class SimulationEvidenceService:
    def __init__(self, session: Session, *, now=None, executor=None) -> None:
        self._bind = session.get_bind()
        self._now = now or (lambda: datetime.now(UTC))
        self._executor = executor or simulate_circuit

    def prepare(
        self,
        *,
        owner_id: int,
        task_id: str | None,
        qubits: int,
        operations: list[CircuitOperation],
        shots: int = 1024,
        seed: int = 42,
        request_key: str | None = None,
        submission_id: str | None = None,
        prediction_checkpoint_id: str | None = None,
        episode_stage_start_id: str | None = None,
        episode_part_id: str | None = None,
    ) -> tuple[str, bool]:
        validate_circuit(qubits=qubits, operations=operations, shots=shots, seed=seed)
        request_key = request_key or str(uuid4())
        if not request_key.strip() or len(request_key) > 128:
            raise SimulationEvidenceError("Invalid simulation request key")
        circuit = {
            "qubits": qubits,
            "operations": [
                {"gate": operation.gate.casefold(), "targets": list(operation.targets)}
                for operation in operations
            ],
        }
        purpose = "feedback" if submission_id else "task" if task_id else "practice"
        with Session(self._bind) as session:
            user = session.get(User, owner_id)
            task = session.get(LearningTask, task_id) if task_id else None
            if user is None or not user.is_active or (task_id and task is None):
                raise SimulationEvidenceError("Simulation context is unavailable")
            course_id = task.course_id if task else None
            if submission_id:
                attempt = session.get(SubmissionAttempt, submission_id)
                if attempt is None or attempt.student_id != owner_id or attempt.task_id != task_id:
                    raise SimulationEvidenceError(
                        "Simulation submission does not match its context"
                    )
            if task_id:
                from app.services.episodes import EpisodeService

                if submission_id:
                    process = (attempt.episode or {}).get("supported", {})
                    prediction_checkpoint_id = process.get("prediction_checkpoint_id")
                EpisodeService(session).require_simulation_checkpoint(
                    owner_id=owner_id,
                    task_id=task_id,
                    checkpoint_id=prediction_checkpoint_id,
                    stage_start_id=episode_stage_start_id,
                    part_id=episode_part_id,
                    circuit=circuit,
                    shots=shots,
                    seed=seed,
                )
            circuit_id = _digest([owner_id, task_id, course_id, circuit])
            existing = session.scalar(
                select(SimulationRun).where(
                    SimulationRun.owner_id == owner_id,
                    SimulationRun.request_key == request_key,
                )
            )
            if existing:
                self._check_replay(
                    existing,
                    circuit_id,
                    shots,
                    seed,
                    submission_id,
                    prediction_checkpoint_id,
                    episode_stage_start_id,
                )
                return existing.id, False
            run_id = str(uuid4())
            archiving = False
            try:
                if session.get(CircuitVersion, circuit_id) is None:
                    archiving = True
                    session.add(
                        CircuitVersion(
                            id=circuit_id,
                            owner_id=owner_id,
                            task_id=task_id,
                            course_id=course_id,
                            circuit=circuit,
                            content_digest=_digest(circuit),
                        )
                    )
                    session.flush()
                    archiving = False
                now = self._now()
                session.add(
                    SimulationRun(
                        id=run_id,
                        owner_id=owner_id,
                        request_key=request_key,
                        circuit_version_id=circuit_id,
                        submission_id=submission_id,
                        purpose=purpose,
                        prediction_checkpoint_id=prediction_checkpoint_id,
                        episode_stage_start_id=episode_stage_start_id,
                        shots=shots,
                        seed=seed,
                        policy_version=SIMULATION_POLICY_VERSION,
                        engine_versions=engine_versions(),
                        created_at=now,
                        deadline_at=now + timedelta(seconds=SIMULATION_TIMEOUT_SECONDS + 5),
                    )
                )
                session.commit()
                return run_id, True
            except IntegrityError:
                session.rollback()
                existing = session.scalar(
                    select(SimulationRun).where(
                        SimulationRun.owner_id == owner_id,
                        SimulationRun.request_key == request_key,
                    )
                )
                if existing:
                    self._check_replay(
                        existing,
                        circuit_id,
                        shots,
                        seed,
                        submission_id,
                        prediction_checkpoint_id,
                        episode_stage_start_id,
                    )
                    return existing.id, False
                # Another request may have archived the same circuit in the meantime.
                if not archiving or session.get(CircuitVersion, circuit_id) is None:
                    raise
        return self.prepare(
            owner_id=owner_id,
            task_id=task_id,
            qubits=qubits,
            operations=operations,
            shots=shots,
            seed=seed,
            request_key=request_key,
            submission_id=submission_id,
            prediction_checkpoint_id=prediction_checkpoint_id,
            episode_stage_start_id=episode_stage_start_id,
            episode_part_id=episode_part_id,
        )

    @staticmethod
    def _check_replay(run, circuit_id, shots, seed, submission_id, checkpoint_id, stage_id) -> None:
        if (
            run.circuit_version_id,
            run.shots,
            run.seed,
            run.submission_id,
            run.prediction_checkpoint_id,
            run.episode_stage_start_id,
        ) != (
            circuit_id,
            shots,
            seed,
            submission_id,
            checkpoint_id,
            stage_id,
        ):
            raise SimulationEvidenceError(
                "The simulation request key was already used for different inputs"
            )

    def execute(self, **inputs) -> dict:
        run_id, created = self.prepare(**inputs)
        if not created:
            return self.read(run_id)
        try:
            result = self._executor(
                qubits=inputs["qubits"],
                operations=inputs["operations"],
                shots=inputs.get("shots", 1024),
                seed=inputs.get("seed", 42),
            )
        except QuantumSimulationError as error:
            state = "timed_out" if error.code == "simulation_timeout" else "failed"
            self.finish(run_id, status=state, error_code=error.code)
        except Exception:
            self.finish(run_id, status="failed", error_code="simulation_failed")
        else:
            self.finish(run_id, status="completed", result=asdict(result))
        return self.read(run_id)

    def finish(
        self, run_id: str, *, status: str, result: dict | None = None, error_code: str | None = None
    ) -> None:
        with Session(self._bind) as session:
            run = session.get(SimulationRun, run_id)
            if run is None:
                raise SimulationEvidenceError("Simulation run not found")
            if session.get(SimulationOutcome, run_id) is not None:
                return
            if _utc(run.deadline_at) <= self._now():
                status, result, error_code = "interrupted", None, "simulation_interrupted"
            session.add(
                SimulationOutcome(
                    id=run_id,
                    status=status,
                    result=result,
                    error_code=error_code,
                    created_at=self._now(),
                )
            )
            try:
                session.flush()
                from app.services.evidence.live import LiveEvidenceCapture

                LiveEvidenceCapture(session).simulation(run, session.get(SimulationOutcome, run_id))
                session.commit()
            except IntegrityError:
                session.rollback()
                if session.get(SimulationOutcome, run_id) is None:
                    raise

    def read(self, run_id: str) -> dict:
        with Session(self._bind) as session:
            run = session.get(SimulationRun, run_id)
            if run is None:
                raise SimulationEvidenceError("Simulation run not found")
            circuit = session.get(CircuitVersion, run.circuit_version_id)
            outcome = session.get(SimulationOutcome, run_id)
            if outcome is None and _utc(run.deadline_at) <= self._now():
                self.finish(run_id, status="interrupted", error_code="simulation_interrupted")
                outcome = session.get(SimulationOutcome, run_id)
            return {
                "run_id": run.id,
                "owner_id": run.owner_id,
                "task_id": circuit.task_id,
                "course_id": circuit.course_id,
                "circuit_version_id": circuit.id,
                "content_digest": circuit.content_digest,
                "circuit": circuit.circuit,
                "submission_id": run.submission_id,
                "purpose": run.purpose,
                "prediction_checkpoint_id": run.prediction_checkpoint_id,
                "episode_stage_start_id": run.episode_stage_start_id,
                "seed": run.seed,
                "shots": run.shots,
                "policy_version": run.policy_version,
                "engine_versions": run.engine_versions,
                "created_at": _utc(run.created_at),
                "deadline_at": _utc(run.deadline_at),
                "finished_at": _utc(outcome.created_at) if outcome else None,
                "status": outcome.status if outcome else "pending",
                "error_code": outcome.error_code if outcome else None,
                "result": outcome.result if outcome else None,
            }

    def recover_expired(self, limit: int = 100) -> int:
        with Session(self._bind) as session:
            ids = list(
                session.scalars(
                    select(SimulationRun.id)
                    .outerjoin(
                        SimulationOutcome,
                        SimulationOutcome.id == SimulationRun.id,
                    )
                    .where(SimulationOutcome.id.is_(None), SimulationRun.deadline_at <= self._now())
                    .order_by(SimulationRun.deadline_at, SimulationRun.id)
                    .limit(limit)
                )
            )
        for run_id in ids:
            self.finish(run_id, status="interrupted", error_code="simulation_interrupted")
        return len(ids)


class SimulationRecoveryWorker:
    def __init__(self, session_factory, *, now=None) -> None:
        self._factory = session_factory
        self._now = now

    async def run_once(self) -> bool:
        def recover() -> bool:
            with self._factory() as session:
                return SimulationEvidenceService(session, now=self._now).recover_expired() > 0

        return await asyncio.to_thread(recover)
