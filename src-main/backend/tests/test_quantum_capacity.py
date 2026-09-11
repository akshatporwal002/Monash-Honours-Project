"""Deterministic compute reuse must not share mutable results or bypass execution limits."""

import json
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from importlib.metadata import version
from types import SimpleNamespace

import pytest

from app.services import quantum


@pytest.fixture(autouse=True)
def isolated_result_cache(monkeypatch):
    monkeypatch.setattr(quantum, "_RESULT_CACHE", OrderedDict())
    monkeypatch.setattr(quantum, "_IN_FLIGHT", {})


def output(payload):
    return quantum.CircuitResult(
        counts={"0": payload["shots"]},
        probabilities={"0": 1.0},
        circuit_text="Synthetic isolated executor",
        statevector=[[1.0, 0.0]],
        sampled_frequencies={"0": 1.0},
        engine_versions={"qiskit": version("qiskit"), "qiskit_aer": version("qiskit-aer")},
        shots=payload["shots"],
        seed=payload["seed"],
    )


def test_identical_concurrent_circuits_share_one_execution_and_detach_results(monkeypatch):
    calls = []
    gate = threading.Barrier(12)

    def execute(*args, **kwargs):
        payload = json.loads(kwargs["input"])
        calls.append(payload)
        time.sleep(0.03)
        return SimpleNamespace(returncode=0, stdout=json.dumps(asdict(output(payload))))

    monkeypatch.setattr(quantum.subprocess, "run", execute)

    def run(_):
        gate.wait()
        return quantum.simulate_circuit(
            qubits=1, operations=[quantum.CircuitOperation("x", (0,))], shots=7, seed=813
        )

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(run, range(12)))
    assert len(calls) == 1
    results[0].counts["0"] = 0
    results[0].statevector[0][0] = 9
    assert all(item.counts == {"0": 7} for item in results[1:])
    replay = quantum.simulate_circuit(
        qubits=1, operations=[quantum.CircuitOperation("x", (0,))], shots=7, seed=813
    )
    assert replay.counts == {"0": 7} and replay.statevector == [[1.0, 0.0]]


@pytest.mark.parametrize("changed", ["qubits", "order", "shots", "seed", "policy", "engine"])
def test_every_numerical_input_and_execution_identity_invalidates_reuse(monkeypatch, changed):
    calls = []

    def execute(*args, **kwargs):
        payload = json.loads(kwargs["input"])
        calls.append(payload)
        return SimpleNamespace(returncode=0, stdout=json.dumps(asdict(output(payload))))

    monkeypatch.setattr(quantum.subprocess, "run", execute)
    inputs = dict(
        qubits=1,
        operations=[quantum.CircuitOperation("h", (0,)), quantum.CircuitOperation("x", (0,))],
        shots=8,
        seed=42,
    )
    quantum.simulate_circuit(**inputs)
    quantum.simulate_circuit(**inputs)
    assert len(calls) == 1
    if changed == "order":
        inputs["operations"] = list(reversed(inputs["operations"]))
    elif changed in {"qubits", "shots", "seed"}:
        inputs[changed] += 1
    elif changed == "policy":
        monkeypatch.setattr(quantum, "SIMULATION_POLICY_VERSION", "synthetic-new-policy")
    else:
        monkeypatch.setattr(quantum, "version", lambda package: "synthetic-new-engine")
    quantum.simulate_circuit(**inputs)
    assert len(calls) == 2


def test_result_cache_is_bounded_and_evicts_least_recently_used(monkeypatch):
    calls = []

    def execute(*args, **kwargs):
        payload = json.loads(kwargs["input"])
        calls.append(payload["seed"])
        return SimpleNamespace(returncode=0, stdout=json.dumps(asdict(output(payload))))

    monkeypatch.setattr(quantum.subprocess, "run", execute)
    monkeypatch.setattr(quantum, "_RESULT_CACHE_SIZE", 2)
    for seed in (1, 2, 1, 3, 2):
        quantum.simulate_circuit(
            qubits=1, operations=[quantum.CircuitOperation("h", (0,))], seed=seed
        )
    assert calls == [1, 2, 3, 2]
    assert len(quantum._RESULT_CACHE) == 2


def test_waiting_caller_keeps_own_deadline_without_cancelling_shared_execution(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    calls = []

    def execute(*args, **kwargs):
        payload = json.loads(kwargs["input"])
        calls.append(payload)
        entered.set()
        assert release.wait(3)
        return SimpleNamespace(returncode=0, stdout=json.dumps(asdict(output(payload))))

    monkeypatch.setattr(quantum.subprocess, "run", execute)
    inputs = dict(qubits=1, operations=[quantum.CircuitOperation("h", (0,))], seed=29)
    with ThreadPoolExecutor(max_workers=1) as pool:
        owner = pool.submit(quantum.simulate_circuit, **inputs)
        try:
            assert entered.wait(3)
            with pytest.raises(quantum.QuantumSimulationError) as caught:
                quantum.simulate_circuit(**inputs, timeout_seconds=0.03)
            assert caught.value.code == "simulation_busy"
            assert not owner.done()
        finally:
            release.set()
        assert owner.result().seed == 29
    assert quantum.simulate_circuit(**inputs).seed == 29
    assert len(calls) == 1


@pytest.mark.parametrize("failure", ["timeout", "start", "exit", "payload"])
def test_failed_execution_is_not_cached_and_releases_single_flight(monkeypatch, failure):
    calls = []

    def execute(*args, **kwargs):
        payload = json.loads(kwargs["input"])
        calls.append(payload)
        if len(calls) == 1:
            if failure == "timeout":
                raise quantum.subprocess.TimeoutExpired("synthetic-runner", kwargs["timeout"])
            if failure == "start":
                raise OSError("Synthetic launch failure")
            return SimpleNamespace(returncode=1 if failure == "exit" else 0, stdout="invalid")
        return SimpleNamespace(returncode=0, stdout=json.dumps(asdict(output(payload))))

    monkeypatch.setattr(quantum.subprocess, "run", execute)
    inputs = dict(qubits=1, operations=[quantum.CircuitOperation("h", (0,))], seed=19)
    with pytest.raises(quantum.QuantumSimulationError) as caught:
        quantum.simulate_circuit(**inputs)
    assert (
        caught.value.code
        == {
            "timeout": "simulation_timeout",
            "start": "simulation_unavailable",
            "exit": "simulation_failed",
            "payload": "simulation_failed",
        }[failure]
    )
    assert not quantum._IN_FLIGHT and not quantum._RESULT_CACHE
    assert quantum.simulate_circuit(**inputs).seed == 19
    assert len(calls) == 2


def test_failed_owner_wakes_existing_waiter_for_a_new_execution(monkeypatch):
    entered, release, waiting = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def execute(*args, **kwargs):
        payload = json.loads(kwargs["input"])
        calls.append(payload)
        if len(calls) == 1:
            entered.set()
            assert release.wait(3)
            raise quantum.subprocess.TimeoutExpired("synthetic-runner", kwargs["timeout"])
        return SimpleNamespace(returncode=0, stdout=json.dumps(asdict(output(payload))))

    monkeypatch.setattr(quantum.subprocess, "run", execute)
    inputs = dict(qubits=1, operations=[quantum.CircuitOperation("h", (0,))], seed=61)
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(quantum.simulate_circuit, **inputs)
        try:
            assert entered.wait(3)
            pending = next(iter(quantum._IN_FLIGHT.values()))
            original_wait = pending.wait

            def observe_wait(timeout=None):
                waiting.set()
                return original_wait(timeout)

            monkeypatch.setattr(pending, "wait", observe_wait)
            follower = pool.submit(quantum.simulate_circuit, **inputs)
            assert waiting.wait(3)
        finally:
            release.set()
        with pytest.raises(quantum.QuantumSimulationError) as caught:
            owner.result(timeout=3)
        assert caught.value.code == "simulation_timeout"
        assert follower.result(timeout=3).seed == 61
    assert len(calls) == 2 and not quantum._IN_FLIGHT


def test_different_circuits_keep_two_process_capacity(monkeypatch):
    active, peak = 0, 0
    lock = threading.Lock()

    def execute(*args, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            time.sleep(0.03)
            payload = json.loads(kwargs["input"])
            return SimpleNamespace(returncode=0, stdout=json.dumps(asdict(output(payload))))
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(quantum.subprocess, "run", execute)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(
            pool.map(
                lambda seed: quantum.simulate_circuit(
                    qubits=1, operations=[quantum.CircuitOperation("x", (0,))], seed=seed
                ),
                range(6),
            )
        )
    assert peak == 2 and {result.seed for result in results} == set(range(6))
