from __future__ import annotations

import pytest

from app.services.quantum import (
    CircuitOperation,
    QuantumSimulationError,
    simulate_circuit,
)

pytest.importorskip("qiskit")
pytest.importorskip("qiskit_aer")


def test_hadamard_circuit_runs_through_qiskit_aer() -> None:
    result = simulate_circuit(
        qubits=1,
        operations=[CircuitOperation(gate="h", targets=(0,))],
        shots=1024,
    )

    assert result.engine == "Qiskit AerSimulator"
    assert set(result.counts) == {"0", "1"}
    assert sum(result.counts.values()) == 1024
    assert sum(result.probabilities.values()) == pytest.approx(1)
    assert "H" in result.circuit_text
    assert "M" in result.circuit_text


@pytest.mark.parametrize(
    ("qubits", "operations", "message"),
    [
        (0, [CircuitOperation(gate="h", targets=(0,))], "between 1 and 5"),
        (2, [], "at least one gate"),
        (2, [CircuitOperation(gate="cx", targets=(0, 0))], "distinct"),
        (1, [CircuitOperation(gate="z", targets=(0,))], "not supported"),
    ],
)
def test_invalid_circuit_returns_a_controlled_error(
    qubits: int,
    operations: list[CircuitOperation],
    message: str,
) -> None:
    with pytest.raises(QuantumSimulationError, match=message):
        simulate_circuit(qubits=qubits, operations=operations)
