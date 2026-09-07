"""Task 15: bounded circuit checks must not infer reasoning from a distribution."""

import pytest

from app.domain.assessment import BloomProcess, CriterionDecision
from app.services.assessment.circuit_rules import (
    evaluate_circuit_structure,
    validate_circuit_settings,
)

SETTINGS = {
    "kind": "circuit_v1",
    "stage": "supported",
    "qubits": 1,
    "operations": [{"gate": "h", "targets": [0]}],
}


def test_exact_structure_and_difference():
    settings = validate_circuit_settings(SETTINGS, BloomProcess.APPLY)
    decision, reason = evaluate_circuit_structure(
        settings, {"qubits": 1, "operations": [{"gate": "h", "targets": [0]}]}
    )
    assert decision is CriterionDecision.MET
    assert "no claim" in reason
    assert evaluate_circuit_structure(settings, {"qubits": 1, "operations": []})[0] is (
        CriterionDecision.NOT_MET
    )


@pytest.mark.parametrize(
    "circuit", [None, {}, {"qubits": 1, "operations": [{"gate": "z", "targets": [0]}]}]
)
def test_unsupported_structure_requires_inspection(circuit):
    settings = validate_circuit_settings(SETTINGS, BloomProcess.APPLY)
    assert evaluate_circuit_structure(settings, circuit)[0] is CriterionDecision.NOT_EVALUABLE


@pytest.mark.parametrize(
    "bloom", [BloomProcess.UNDERSTAND, BloomProcess.ANALYSE, BloomProcess.CREATE]
)
def test_conceptual_claims_require_human(bloom):
    with pytest.raises(ValueError, match="reasoning needs human"):
        validate_circuit_settings(SETTINGS, bloom)


@pytest.mark.parametrize(
    "extra",
    [
        {"probabilities": {"0": 0.5}},
        {"explanation": "correct"},
        {"qubits": True},
        {"operations": [{"gate": "h", "targets": [1]}]},
    ],
)
def test_unapproved_or_invalid_checks_fail_closed(extra):
    with pytest.raises(ValueError):
        validate_circuit_settings({**SETTINGS, **extra}, BloomProcess.APPLY)


def test_execution_metadata_is_validated_but_not_graded():
    settings = validate_circuit_settings(SETTINGS, BloomProcess.APPLY)
    for shots, seed in [(1, 0), (4096, 4294967295)]:
        decision, _ = evaluate_circuit_structure(
            settings,
            {"qubits": 1, "operations": SETTINGS["operations"], "shots": shots, "seed": seed},
        )
        assert decision is CriterionDecision.MET
    assert (
        evaluate_circuit_structure(
            settings, {"qubits": 1, "operations": SETTINGS["operations"], "shots": True}
        )[0]
        is CriterionDecision.NOT_EVALUABLE
    )
