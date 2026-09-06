"""Private subprocess entrypoint. It accepts only the validated circuit schema."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from importlib.metadata import version

from app.services.quantum import CircuitOperation, CircuitResult, validate_circuit


def run(payload: dict) -> CircuitResult:
    operations = [
        CircuitOperation(item["gate"], tuple(item["targets"])) for item in payload["operations"]
    ]
    qubits, shots, seed = payload["qubits"], payload["shots"], payload["seed"]
    validate_circuit(qubits=qubits, operations=operations, shots=shots, seed=seed)
    from qiskit import QuantumCircuit, transpile
    from qiskit.quantum_info import Statevector
    from qiskit_aer import AerSimulator

    circuit = QuantumCircuit(qubits, qubits)
    for operation in operations:
        getattr(circuit, operation.gate.casefold())(*operation.targets)
    state = Statevector.from_instruction(circuit)
    probabilities = {
        format(index, f"0{qubits}b"): float(probability)
        for index, probability in enumerate(state.probabilities())
    }
    amplitudes = [[float(value.real), float(value.imag)] for value in state.data]
    circuit.measure(range(qubits), range(qubits))
    backend = AerSimulator(method="statevector", max_parallel_threads=1)
    compiled = transpile(circuit, backend, optimization_level=0, seed_transpiler=seed)
    counts = {
        str(state).replace(" ", ""): int(count)
        for state, count in backend.run(compiled, shots=shots, seed_simulator=seed)
        .result()
        .get_counts()
        .items()
    }
    return CircuitResult(
        counts=dict(sorted(counts.items())),
        probabilities=probabilities,
        circuit_text=str(circuit),
        sampled_frequencies={state: count / shots for state, count in sorted(counts.items())},
        statevector=amplitudes,
        engine_versions={"qiskit": version("qiskit"), "qiskit_aer": version("qiskit-aer")},
        qubit_order=list(range(qubits)),
        measurement_mapping=[[index, index] for index in range(qubits)],
        seed=seed,
        shots=shots,
    )


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read(100_000))
        result = run(payload)
        sys.stdout.write(json.dumps(asdict(result), ensure_ascii=True, allow_nan=False))
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
