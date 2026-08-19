"""Tests for deterministic binary pass-rule evaluation."""

from __future__ import annotations

import inspect

import pytest

from app.domain.assessment import AssessmentReasonCode, AssessmentResult, CriterionDecision
from app.services.assessment.pass_rules import (
    MAX_RULE_DEPTH,
    MAX_RULE_NODES,
    CriterionRuleOutcome,
    PassRuleEngine,
    PassRuleEvaluationRequest,
    PassRuleValidationError,
)


def _request(
    *outcomes: CriterionRuleOutcome,
    expression: dict[str, object] | None = None,
) -> PassRuleEvaluationRequest:
    return PassRuleEvaluationRequest(
        expression=expression
        or {
            "operator": "ALL_OF",
            "clauses": [
                {"criterion_version_id": "criterion-1"},
                {"criterion_version_id": "criterion-2"},
            ],
        },
        approved_criterion_version_ids=frozenset({"criterion-1", "criterion-2", "criterion-3"}),
        mandatory_criterion_version_ids=frozenset({"criterion-1", "criterion-2"}),
        criterion_outcomes=outcomes,
    )


def _outcome(criterion_version_id: str, decision: CriterionDecision) -> CriterionRuleOutcome:
    return CriterionRuleOutcome(criterion_version_id, decision)


def test_all_mandatory_criteria_met_returns_pass() -> None:
    result = PassRuleEngine().evaluate(
        _request(
            _outcome("criterion-1", CriterionDecision.MET),
            _outcome("criterion-2", CriterionDecision.MET),
        )
    )

    assert result.result is AssessmentResult.PASS
    assert result.reason_code is AssessmentReasonCode.TARGET_EVIDENCE_MET
    assert result.met_criterion_version_ids == ("criterion-1", "criterion-2")


def test_missing_mandatory_criterion_returns_incomplete() -> None:
    result = PassRuleEngine().evaluate(_request(_outcome("criterion-1", CriterionDecision.MET)))

    assert result.result is AssessmentResult.INCOMPLETE
    assert result.reason_code is AssessmentReasonCode.MISSING_REQUIRED_EVIDENCE
    assert result.missing_criterion_version_ids == ("criterion-2",)


def test_same_versions_return_same_result_and_criterion_order() -> None:
    first = PassRuleEngine().evaluate(
        _request(
            _outcome("criterion-2", CriterionDecision.MET),
            _outcome("criterion-1", CriterionDecision.MET),
        )
    )
    second = PassRuleEngine().evaluate(
        _request(
            _outcome("criterion-1", CriterionDecision.MET),
            _outcome("criterion-2", CriterionDecision.MET),
        )
    )

    assert first == second
    assert first.met_criterion_version_ids == ("criterion-1", "criterion-2")


def test_nested_all_of_any_of_and_not_rule_is_evaluated() -> None:
    expression: dict[str, object] = {
        "operator": "ALL_OF",
        "clauses": [
            {"criterion_version_id": "criterion-1"},
            {
                "operator": "ANY_OF",
                "clauses": [
                    {"criterion_version_id": "criterion-2"},
                    {"criterion_version_id": "criterion-3"},
                ],
            },
            {
                "operator": "NOT",
                "clauses": [{"criterion_version_id": "criterion-3"}],
            },
        ],
    }

    result = PassRuleEngine().evaluate(
        _request(
            _outcome("criterion-1", CriterionDecision.MET),
            _outcome("criterion-2", CriterionDecision.MET),
            _outcome("criterion-3", CriterionDecision.NOT_MET),
            expression=expression,
        )
    )

    assert result.result is AssessmentResult.PASS


@pytest.mark.parametrize(
    "forbidden_field",
    (
        "score",
        "weight",
        "threshold",
        "research_condition",
        "confidence",
        "time_taken",
        "hints_used",
        "points",
        "access_support",
        "model_estimate",
        "progress",
    ),
)
def test_rule_rejects_numeric_and_forbidden_inputs(forbidden_field: str) -> None:
    expression: dict[str, object] = {
        "operator": "ALL_OF",
        "clauses": [{"criterion_version_id": "criterion-1", forbidden_field: 1}],
    }

    with pytest.raises(PassRuleValidationError, match="unknown fields"):
        PassRuleEngine().evaluate(_request(expression=expression))


def test_unknown_unbounded_or_cyclic_rule_is_rejected() -> None:
    unknown = {"operator": "SCORE_AT_LEAST", "clauses": [{"criterion_version_id": "criterion-1"}]}
    with pytest.raises(PassRuleValidationError, match="unknown Boolean operator"):
        PassRuleEngine().evaluate(_request(expression=unknown))

    deep: dict[str, object] = {"criterion_version_id": "criterion-1"}
    for _ in range(MAX_RULE_DEPTH):
        deep = {"operator": "NOT", "clauses": [deep]}
    with pytest.raises(PassRuleValidationError, match="maximum nesting depth"):
        PassRuleEngine().evaluate(_request(expression=deep))

    wide = {
        "operator": "ANY_OF",
        "clauses": [{"criterion_version_id": "criterion-1"}] * MAX_RULE_NODES,
    }
    with pytest.raises(PassRuleValidationError, match="maximum node count"):
        PassRuleEngine().evaluate(_request(expression=wide))

    cyclic: dict[str, object] = {"operator": "NOT", "clauses": []}
    cyclic["clauses"] = [cyclic]
    with pytest.raises(PassRuleValidationError, match="maximum nesting depth"):
        PassRuleEngine().evaluate(_request(expression=cyclic))


def test_research_condition_confidence_hint_time_and_access_do_not_change_result() -> None:
    request = _request(
        _outcome("criterion-1", CriterionDecision.MET),
        _outcome("criterion-2", CriterionDecision.MET),
    )
    parameter_names = set(inspect.signature(PassRuleEvaluationRequest).parameters)
    forbidden = {
        "research_condition",
        "confidence",
        "hint_use",
        "time_taken",
        "access_support",
    }

    assert forbidden.isdisjoint(parameter_names)
    assert PassRuleEngine().evaluate(request).result is AssessmentResult.PASS


def test_not_met_not_evaluable_and_conflicting_criteria_are_listed() -> None:
    result = PassRuleEngine().evaluate(
        _request(
            _outcome("criterion-1", CriterionDecision.NOT_MET),
            _outcome("criterion-1", CriterionDecision.NOT_EVALUABLE),
            _outcome("criterion-2", CriterionDecision.NOT_EVALUABLE),
        )
    )

    assert result.result is AssessmentResult.INCOMPLETE
    assert result.reason_code is AssessmentReasonCode.UNRESOLVED_EVIDENCE_CONFLICT
    assert result.not_met_criterion_version_ids == ("criterion-1",)
    assert result.conflicting_criterion_version_ids == ("criterion-1",)
    assert result.not_evaluable_criterion_version_ids == ("criterion-1", "criterion-2")


@pytest.mark.parametrize(
    "decision, expected_reason",
    (
        (CriterionDecision.NOT_MET, AssessmentReasonCode.CRITERIA_NOT_MET),
        (CriterionDecision.NOT_EVALUABLE, AssessmentReasonCode.MISSING_REQUIRED_EVIDENCE),
    ),
)
def test_unmet_criterion_reasons_use_stable_public_codes(
    decision: CriterionDecision,
    expected_reason: AssessmentReasonCode,
) -> None:
    result = PassRuleEngine().evaluate(
        _request(
            _outcome("criterion-1", decision),
            _outcome("criterion-2", decision),
        )
    )

    assert result.result is AssessmentResult.INCOMPLETE
    assert result.reason_code is expected_reason


def test_unapproved_criterion_or_missing_mandatory_rule_leaf_is_rejected() -> None:
    with pytest.raises(PassRuleValidationError, match="unapproved criterion"):
        PassRuleEngine().evaluate(
            _request(
                expression={
                    "operator": "ALL_OF",
                    "clauses": [{"criterion_version_id": "criterion-unknown"}],
                }
            )
        )

    with pytest.raises(PassRuleValidationError, match="mandatory criteria"):
        PassRuleEngine().evaluate(_request(expression={"criterion_version_id": "criterion-1"}))
