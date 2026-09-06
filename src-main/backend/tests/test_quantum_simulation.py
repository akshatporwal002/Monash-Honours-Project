from __future__ import annotations

import subprocess

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


def test_exact_probabilities_are_not_one_shot_frequencies() -> None:
    result = simulate_circuit(qubits=1, operations=[CircuitOperation("h", (0,))], shots=1)
    assert result.probabilities == pytest.approx({"0": 0.5, "1": 0.5})
    assert len(result.counts) == 1
    assert list(result.sampled_frequencies.values()) == [1.0]
    assert result.probability_method == "exact_statevector"


def test_saved_settings_expose_bit_order_and_reproduce_counts() -> None:
    arguments = {"qubits": 2, "operations": [CircuitOperation("x", (0,))], "shots": 32, "seed": 91}
    first = simulate_circuit(**arguments)
    replay = simulate_circuit(**arguments)
    assert first.counts == replay.counts == {"01": 32}
    assert first.probabilities["01"] == pytest.approx(1)
    assert first.qubit_order == [0, 1]
    assert first.measurement_mapping == [[0, 0], [1, 1]]
    assert first.seed == 91
    assert first.shots == 32
    assert first.engine_versions == replay.engine_versions
    assert set(first.engine_versions) == {"qiskit", "qiskit_aer"}


def test_equal_measurement_probabilities_do_not_erase_relative_phase() -> None:
    plus = simulate_circuit(qubits=1, operations=[CircuitOperation("h", (0,))])
    minus = simulate_circuit(
        qubits=1, operations=[CircuitOperation("x", (0,)), CircuitOperation("h", (0,))]
    )
    assert plus.probabilities == pytest.approx(minus.probabilities)
    assert plus.statevector[1][0] > 0
    assert minus.statevector[1][0] < 0
    assert sum(
        a[0] * b[0] + a[1] * b[1] for a, b in zip(plus.statevector, minus.statevector, strict=True)
    ) == pytest.approx(0)


@pytest.mark.parametrize("argument", [True, 1.5])
def test_core_boundary_rejects_coerced_qubit_numbers(argument) -> None:
    with pytest.raises(QuantumSimulationError):
        simulate_circuit(qubits=argument, operations=[CircuitOperation("h", (0,))])


def test_operation_limit_applies_outside_the_http_schema() -> None:
    with pytest.raises(QuantumSimulationError, match="at most 30 operations"):
        simulate_circuit(qubits=1, operations=[CircuitOperation("h", (0,))] * 31)


def test_timeout_terminates_and_reaps_the_simulation_child(monkeypatch) -> None:
    original = subprocess.Popen
    children = []

    def tracked_popen(*args, **kwargs):
        process = original(*args, **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", tracked_popen)
    with pytest.raises(QuantumSimulationError) as caught:
        simulate_circuit(qubits=1, operations=[CircuitOperation("h", (0,))], timeout_seconds=0.05)
    assert caught.value.code == "simulation_timeout"
    assert len(children) == 1
    assert children[0].poll() is not None
    assert (
        sum(
            simulate_circuit(
                qubits=1, operations=[CircuitOperation("h", (0,))], shots=8
            ).counts.values()
        )
        == 8
    )
