"""Validated, process-bounded Qiskit boundary for introductory circuit tasks."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

MAX_QUBITS = 5
MAX_SHOTS = 4096
MAX_OPERATIONS = 30
SIMULATION_TIMEOUT_SECONDS = 15.0
SIMULATION_POLICY_VERSION = "ideal-h-x-cx-v1"
_SLOTS = threading.BoundedSemaphore(2)
_RESULT_CACHE_SIZE = 128
_RESULT_CACHE = OrderedDict()
_IN_FLIGHT = {}
_CACHE_LOCK = threading.Lock()


class QuantumSimulationError(ValueError):
    """A safe validation or execution failure, never an assessment judgement."""

    def __init__(self, message: str, *, code: str = "invalid_circuit") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class CircuitOperation:
    gate: str
    targets: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CircuitResult:
    counts: dict[str, int]
    probabilities: dict[str, float]
    circuit_text: str
    engine: str = "Qiskit AerSimulator"
    sampled_frequencies: dict[str, float] = field(default_factory=dict)
    statevector: list[list[float]] = field(default_factory=list)
    engine_versions: dict[str, str] = field(default_factory=dict)
    qubit_order: list[int] = field(default_factory=list)
    measurement_mapping: list[list[int]] = field(default_factory=list)
    seed: int = 42
    shots: int = 1024
    probability_method: str = "exact_statevector"
    policy_version: str = SIMULATION_POLICY_VERSION


def simulation_capabilities() -> dict:
    return {
        "policy_version": SIMULATION_POLICY_VERSION,
        "gates": ["h", "x", "cx"],
        "max_qubits": MAX_QUBITS,
        "max_shots": MAX_SHOTS,
        "max_operations": MAX_OPERATIONS,
        "timeout_seconds": SIMULATION_TIMEOUT_SECONDS,
        "measurement_basis": "computational",
        "bitstring_order": "highest_qubit_leftmost",
        "measurement_mapping": "qubit_i_to_classical_bit_i",
        "probability_method": "exact_statevector",
        "statevector_available": True,
        "noise_model": "none",
    }


def validate_circuit(
    *,
    qubits: int,
    operations: list[CircuitOperation],
    shots: int = 1024,
    seed: int = 42,
    allow_empty: bool = False,
) -> None:
    if type(qubits) is not int or not 1 <= qubits <= MAX_QUBITS:
        raise QuantumSimulationError("Circuits must contain between 1 and 5 qubits.")
    if type(shots) is not int or not 1 <= shots <= MAX_SHOTS:
        raise QuantumSimulationError("Shot count must be between 1 and 4096.")
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise QuantumSimulationError("The simulation seed must be a valid unsigned 32-bit integer.")
    if not isinstance(operations, list) or (not operations and not allow_empty):
        raise QuantumSimulationError("Add at least one gate before running the circuit.")
    if len(operations) > MAX_OPERATIONS:
        raise QuantumSimulationError("Circuits may contain at most 30 operations.")
    for operation in operations:
        if not isinstance(operation, CircuitOperation) or not isinstance(operation.gate, str):
            raise QuantumSimulationError("The circuit operation is invalid.")
        gate, targets = operation.gate.casefold(), operation.targets
        if not isinstance(targets, (tuple, list)):
            raise QuantumSimulationError("The circuit targets are invalid.")
        if gate in {"h", "x"}:
            if len(targets) != 1:
                raise QuantumSimulationError(f"{gate.upper()} requires one target qubit.")
        elif gate == "cx":
            if len(targets) != 2 or targets[0] == targets[1]:
                raise QuantumSimulationError("CX requires distinct control and target qubits.")
        else:
            raise QuantumSimulationError("This circuit gate is not supported.")
        for target in targets:
            if type(target) is not int or not 0 <= target < qubits:
                raise QuantumSimulationError("A target qubit is outside this circuit.")


def simulate_circuit(
    *,
    qubits: int,
    operations: list[CircuitOperation],
    shots: int = 1024,
    seed: int = 42,
    timeout_seconds: float = SIMULATION_TIMEOUT_SECONDS,
) -> CircuitResult:
    """Reuse exact seeded arithmetic; each cache miss retains isolated execution."""
    validate_circuit(qubits=qubits, operations=operations, shots=shots, seed=seed)
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise QuantumSimulationError("The simulation timeout must be positive.")
    deadline = time.monotonic() + timeout_seconds
    payload = {
        "qubits": qubits,
        "operations": [asdict(operation) for operation in operations],
        "shots": shots,
        "seed": seed,
    }
    engines = {}
    for package in ("qiskit", "qiskit-aer"):
        try:
            engines[package.replace("-", "_")] = version(package)
        except PackageNotFoundError:
            engines[package.replace("-", "_")] = "unavailable"
    key = (
        qubits,
        tuple((operation.gate.casefold(), tuple(operation.targets)) for operation in operations),
        shots,
        seed,
        SIMULATION_POLICY_VERSION,
        tuple(engines.items()),
    )
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _simulation_busy()
        with _CACHE_LOCK:
            if key in _RESULT_CACHE:
                _RESULT_CACHE.move_to_end(key)
                return deepcopy(_RESULT_CACHE[key])
            pending = _IN_FLIGHT.get(key)
            owner = pending is None
            if owner:
                pending = threading.Event()
                _IN_FLIGHT[key] = pending
        if not owner:
            if not pending.wait(timeout=max(0, deadline - time.monotonic())):
                raise _simulation_busy()
            # A failed owner leaves no cache entry. Retry only within this caller's
            # original budget; an earlier failure never becomes a reusable result.
            continue
        try:
            result = _execute_circuit(payload, deadline)
            if (
                result.engine_versions == engines
                and result.policy_version == SIMULATION_POLICY_VERSION
            ):
                with _CACHE_LOCK:
                    _RESULT_CACHE[key] = deepcopy(result)
                    _RESULT_CACHE.move_to_end(key)
                    while len(_RESULT_CACHE) > _RESULT_CACHE_SIZE:
                        _RESULT_CACHE.popitem(last=False)
            return result
        finally:
            with _CACHE_LOCK:
                _IN_FLIGHT.pop(key, None)
                pending.set()


def _simulation_busy() -> QuantumSimulationError:
    return QuantumSimulationError(
        "Simulation capacity is busy. Try again shortly.", code="simulation_busy"
    )


def _execute_circuit(payload: dict, deadline: float) -> CircuitResult:
    """The two process slots and queue-plus-execution deadline also bound misses."""
    remaining = deadline - time.monotonic()
    if remaining <= 0 or not _SLOTS.acquire(timeout=remaining):
        raise QuantumSimulationError(
            "Simulation capacity is busy. Try again shortly.", code="simulation_busy"
        )
    try:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise QuantumSimulationError(
                "Simulation capacity is busy. Try again shortly.", code="simulation_busy"
            )
        try:
            process = subprocess.run(
                [sys.executable, "-m", "app.services.quantum_runner"],
                cwd=Path(__file__).resolve().parents[2],
                input=json.dumps(payload),
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=remaining,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired:
            raise QuantumSimulationError(
                "The circuit simulation exceeded its time limit.", code="simulation_timeout"
            ) from None
        except OSError:
            raise QuantumSimulationError(
                "Quantum simulation could not start.", code="simulation_unavailable"
            ) from None
        if process.returncode != 0:
            raise QuantumSimulationError(
                "The circuit could not be simulated.", code="simulation_failed"
            )
        try:
            payload = json.loads(process.stdout)
            return CircuitResult(**payload)
        except (TypeError, ValueError):
            raise QuantumSimulationError(
                "The simulation result could not be read.", code="simulation_failed"
            ) from None
    finally:
        _SLOTS.release()
