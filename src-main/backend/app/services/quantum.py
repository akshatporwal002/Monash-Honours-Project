"""Small, safe Qiskit Aer boundary used by introductory circuit tasks."""

from __future__ import annotations

from dataclasses import dataclass


class QuantumSimulationError(ValueError):
    """A user-safe circuit validation or execution failure."""


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


def simulate_circuit(
    *,
    qubits: int,
    operations: list[CircuitOperation],
    shots: int = 1024,
) -> CircuitResult:
    """Validate and execute a bounded gate circuit with Qiskit Aer.

    The MVP intentionally accepts a small allow-list instead of executing arbitrary
    Python supplied by a browser. This covers the introductory H, X, and controlled-X
    activities while keeping the simulation boundary understandable and safe.
    """

    if not 1 <= qubits <= 5:
        raise QuantumSimulationError("Circuits must contain between 1 and 5 qubits.")
    if not 1 <= shots <= 4096:
        raise QuantumSimulationError("Shot count must be between 1 and 4096.")
    if not operations:
        raise QuantumSimulationError("Add at least one gate before running the circuit.")

    try:
        from qiskit import QuantumCircuit, transpile
        from qiskit_aer import AerSimulator
    except ImportError as error:  # pragma: no cover - deployment configuration guard
        raise QuantumSimulationError("Quantum simulation is not configured.") from error

    circuit = QuantumCircuit(qubits, qubits)
    for operation in operations:
        gate = operation.gate.casefold()
        targets = operation.targets
        if gate in {"h", "x"}:
            if len(targets) != 1:
                raise QuantumSimulationError(f"{gate.upper()} requires one target qubit.")
            _validate_target(targets[0], qubits)
            getattr(circuit, gate)(targets[0])
        elif gate == "cx":
            if len(targets) != 2 or targets[0] == targets[1]:
                raise QuantumSimulationError("CX requires distinct control and target qubits.")
            _validate_target(targets[0], qubits)
            _validate_target(targets[1], qubits)
            circuit.cx(targets[0], targets[1])
        else:
            raise QuantumSimulationError(f"Gate '{operation.gate}' is not supported.")

    circuit.measure(range(qubits), range(qubits))
    try:
        backend = AerSimulator()
        compiled = transpile(circuit, backend, optimization_level=0)
        raw_counts = backend.run(compiled, shots=shots, seed_simulator=42).result().get_counts()
    except Exception as error:
        raise QuantumSimulationError("The circuit could not be simulated.") from error

    counts = {str(state).replace(" ", ""): int(count) for state, count in raw_counts.items()}
    probabilities = {state: round(count / shots, 6) for state, count in sorted(counts.items())}
    return CircuitResult(
        counts=dict(sorted(counts.items())),
        probabilities=probabilities,
        circuit_text=str(circuit),
    )


def _validate_target(target: int, qubits: int) -> None:
    if not 0 <= target < qubits:
        raise QuantumSimulationError(f"Qubit {target} is outside this circuit.")
