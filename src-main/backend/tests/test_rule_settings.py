"""Invalid stored rules must never manufacture criterion evidence."""

import pytest

from app.domain.assessment import BloomProcess, CriterionDecision
from app.services.assessment.evaluators import (
    CriterionEvaluationRequest,
    EvaluatorFailure,
    RuleCriterionEvaluator,
)


@pytest.mark.parametrize("anchors", ({}, {"met": ["valid explanation"]}))
def test_empty_or_unsupported_rules_cannot_accept_arbitrary_response(anchors: dict) -> None:
    with pytest.raises(EvaluatorFailure):
        RuleCriterionEvaluator().evaluate(
            CriterionEvaluationRequest("bananas", BloomProcess.UNDERSTAND, anchors, ())
        )


@pytest.mark.parametrize(
    "anchors",
    (
        {},
        [],
        {"met": ["phase"]},
        {"all_of": "phase"},
        {"all_of": [""]},
        {"all_of": [1]},
        {"all_of": [], "any_of": []},
        {"all_of": ["Phase"], "none_of": ["phase"]},
        {"any_of": ["phase shift"], "none_of": ["phase"]},
    ),
)
def test_invalid_recall_settings_fail_before_issuing_a_decision(anchors: object) -> None:
    with pytest.raises(EvaluatorFailure):
        RuleCriterionEvaluator().evaluate(
            CriterionEvaluationRequest("phase", BloomProcess.REMEMBER, anchors, ())
        )


@pytest.mark.parametrize(
    "process", [item for item in BloomProcess if item is not BloomProcess.REMEMBER]
)
def test_reasoning_targets_require_human_assessment(process: BloomProcess) -> None:
    with pytest.raises(EvaluatorFailure, match="human assessment"):
        RuleCriterionEvaluator().evaluate(
            CriterionEvaluationRequest("phase", process, {"all_of": ["phase"]}, ())
        )


@pytest.mark.parametrize(
    "response, expected",
    (
        ("PHASE shift", CriterionDecision.MET),
        ("bananas", CriterionDecision.NOT_MET),
        ("phase shift is classical", CriterionDecision.NOT_MET),
        ("", CriterionDecision.NOT_EVALUABLE),
    ),
)
def test_valid_recall_settings_apply_required_alternative_and_excluded_phrases(
    response: str,
    expected: CriterionDecision,
) -> None:
    outcome = RuleCriterionEvaluator().evaluate(
        CriterionEvaluationRequest(
            response,
            BloomProcess.REMEMBER,
            {"all_of": ["phase"], "any_of": ["shift", "change"], "none_of": ["classical"]},
            (),
        )
    )
    assert outcome.decision is expected
    assert outcome.evaluator_reference == "rules.anchor.v2"
