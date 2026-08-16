"""Deterministic Boolean pass rules over approved criterion-version outcomes."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from app.domain.assessment import AssessmentResult, CriterionDecision

MAX_RULE_DEPTH = 16
MAX_RULE_NODES = 64


class PassRuleValidationError(ValueError):
    """A stored pass rule or its criterion outcomes are unsafe to evaluate."""


@dataclass(frozen=True)
class CriterionRuleOutcome:
    """One versioned criterion decision supplied by the evaluator layer."""

    criterion_version_id: str
    decision: CriterionDecision


@dataclass(frozen=True)
class PassRuleEvaluationRequest:
    """The complete, version-bound input for one Boolean pass-rule evaluation."""

    expression: dict[str, Any]
    approved_criterion_version_ids: frozenset[str]
    mandatory_criterion_version_ids: frozenset[str]
    criterion_outcomes: tuple[CriterionRuleOutcome, ...]


@dataclass(frozen=True)
class PassRuleEvaluation:
    """A binary result plus stable evidence categories for review and feedback."""

    result: AssessmentResult
    reason_code: str
    met_criterion_version_ids: tuple[str, ...]
    not_met_criterion_version_ids: tuple[str, ...]
    missing_criterion_version_ids: tuple[str, ...]
    conflicting_criterion_version_ids: tuple[str, ...]
    not_evaluable_criterion_version_ids: tuple[str, ...]


class PassRuleEngine:
    """Evaluate only the frozen Boolean rule and exact criterion decisions."""

    def evaluate(self, request: PassRuleEvaluationRequest) -> PassRuleEvaluation:
        expression = _parse_expression(request.expression)
        leaves = _criterion_ids(expression)
        _validate_criterion_scope(request, leaves)
        decisions = _group_decisions(request.criterion_outcomes, leaves)
        summary = _summarise_decisions(leaves, decisions)
        rule_met = _evaluate_expression(expression, decisions)
        mandatory_met = all(
            decisions.get(criterion_id) == {CriterionDecision.MET}
            for criterion_id in request.mandatory_criterion_version_ids
        )
        result = (
            AssessmentResult.PASS if rule_met and mandatory_met else AssessmentResult.INCOMPLETE
        )

        return PassRuleEvaluation(
            result=result,
            reason_code=_reason_code(result, summary),
            met_criterion_version_ids=summary.met,
            not_met_criterion_version_ids=summary.not_met,
            missing_criterion_version_ids=summary.missing,
            conflicting_criterion_version_ids=summary.conflicting,
            not_evaluable_criterion_version_ids=summary.not_evaluable,
        )


def referenced_criterion_version_ids(expression: object) -> frozenset[str]:
    """Return the exact criterion-version leaves after bounded rule validation."""

    return _criterion_ids(_parse_expression(expression))


@dataclass(frozen=True)
class _DecisionSummary:
    met: tuple[str, ...]
    not_met: tuple[str, ...]
    missing: tuple[str, ...]
    conflicting: tuple[str, ...]
    not_evaluable: tuple[str, ...]


def _parse_expression(
    value: object, *, depth: int = 1, counter: list[int] | None = None
) -> dict[str, Any]:
    if depth > MAX_RULE_DEPTH:
        raise PassRuleValidationError("pass rule exceeds the maximum nesting depth")
    if not isinstance(value, dict):
        raise PassRuleValidationError("pass rule clauses must be objects")

    node_counter = counter if counter is not None else [0]
    node_counter[0] += 1
    if node_counter[0] > MAX_RULE_NODES:
        raise PassRuleValidationError("pass rule exceeds the maximum node count")

    if "criterion_version_id" in value:
        if set(value) != {"criterion_version_id"}:
            raise PassRuleValidationError("criterion clauses cannot contain unknown fields")
        criterion_id = value["criterion_version_id"]
        if not isinstance(criterion_id, str) or not criterion_id.strip():
            raise PassRuleValidationError("criterion clauses require a criterion_version_id")
        return {"criterion_version_id": criterion_id}

    if set(value) != {"operator", "clauses"}:
        raise PassRuleValidationError("pass rule Boolean operators cannot contain unknown fields")
    operator = value["operator"]
    clauses = value["clauses"]
    if operator not in {"ALL_OF", "ANY_OF", "NOT"}:
        raise PassRuleValidationError("pass rule has an unknown Boolean operator")
    if not isinstance(clauses, list) or not clauses:
        raise PassRuleValidationError("Boolean operators require one or more clauses")
    if operator == "NOT" and len(clauses) != 1:
        raise PassRuleValidationError("NOT requires exactly one clause")
    return {
        "operator": operator,
        "clauses": [
            _parse_expression(clause, depth=depth + 1, counter=node_counter) for clause in clauses
        ],
    }


def _criterion_ids(expression: dict[str, Any]) -> frozenset[str]:
    if "criterion_version_id" in expression:
        return frozenset((expression["criterion_version_id"],))
    return frozenset(
        criterion_id for clause in expression["clauses"] for criterion_id in _criterion_ids(clause)
    )


def _validate_criterion_scope(
    request: PassRuleEvaluationRequest,
    leaves: frozenset[str],
) -> None:
    if not request.approved_criterion_version_ids:
        raise PassRuleValidationError("pass rule requires approved criterion versions")
    if not leaves.issubset(request.approved_criterion_version_ids):
        raise PassRuleValidationError("pass rule references an unapproved criterion version")
    if not request.mandatory_criterion_version_ids.issubset(leaves):
        raise PassRuleValidationError("mandatory criteria must be present in the pass rule")
    if not request.mandatory_criterion_version_ids.issubset(request.approved_criterion_version_ids):
        raise PassRuleValidationError("mandatory criteria must be approved")


def _group_decisions(
    outcomes: tuple[CriterionRuleOutcome, ...],
    leaves: frozenset[str],
) -> dict[str, set[CriterionDecision]]:
    decisions: defaultdict[str, set[CriterionDecision]] = defaultdict(set)
    for outcome in outcomes:
        if not isinstance(outcome.decision, CriterionDecision):
            raise PassRuleValidationError("criterion outcomes require typed decisions")
        if not isinstance(outcome.criterion_version_id, str) or not outcome.criterion_version_id:
            raise PassRuleValidationError("criterion outcomes require a criterion version ID")
        if outcome.criterion_version_id not in leaves:
            raise PassRuleValidationError("criterion outcome is not part of the approved pass rule")
        decisions[outcome.criterion_version_id].add(outcome.decision)
    return dict(decisions)


def _summarise_decisions(
    leaves: frozenset[str],
    decisions: dict[str, set[CriterionDecision]],
) -> _DecisionSummary:
    ordered = tuple(sorted(leaves))
    return _DecisionSummary(
        met=tuple(
            criterion_id
            for criterion_id in ordered
            if CriterionDecision.MET in decisions.get(criterion_id, set())
        ),
        not_met=tuple(
            criterion_id
            for criterion_id in ordered
            if CriterionDecision.NOT_MET in decisions.get(criterion_id, set())
        ),
        missing=tuple(criterion_id for criterion_id in ordered if criterion_id not in decisions),
        conflicting=tuple(
            criterion_id for criterion_id in ordered if len(decisions.get(criterion_id, set())) > 1
        ),
        not_evaluable=tuple(
            criterion_id
            for criterion_id in ordered
            if CriterionDecision.NOT_EVALUABLE in decisions.get(criterion_id, set())
        ),
    )


def _evaluate_expression(
    expression: dict[str, Any], decisions: dict[str, set[CriterionDecision]]
) -> bool:
    if "criterion_version_id" in expression:
        return decisions.get(expression["criterion_version_id"]) == {CriterionDecision.MET}
    clauses = [_evaluate_expression(clause, decisions) for clause in expression["clauses"]]
    match expression["operator"]:
        case "ALL_OF":
            return all(clauses)
        case "ANY_OF":
            return any(clauses)
        case "NOT":
            return not clauses[0]
    raise AssertionError("parsed pass-rule operator was not recognised")


def _reason_code(result: AssessmentResult, summary: _DecisionSummary) -> str:
    if result is AssessmentResult.PASS:
        return "TARGET_EVIDENCE_MET"
    if summary.conflicting:
        return "CONFLICTING_CRITERION_EVIDENCE"
    if summary.missing:
        return "REQUIRED_CRITERION_EVIDENCE_MISSING"
    if summary.not_evaluable:
        return "CRITERION_NOT_EVALUABLE"
    if summary.not_met:
        return "CRITERION_EVIDENCE_NOT_MET"
    return "PASS_RULE_NOT_MET"
