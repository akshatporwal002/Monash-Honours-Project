from copy import deepcopy

import pytest
from support.alignment import next_action_contract

from app.services.assessment.alignment_contract import validate_next_action_alignment


def test_complete_prospective_links_preserve_opaque_policy_without_learner_records():
    policy = next_action_contract("required", "optional")
    policy["review_policy"] = {"retain": ["opaque", {"version": 3}]}
    before = deepcopy(policy)
    validate_next_action_alignment(
        policy, {"required": ["learner_response"], "optional": ["learner_response"]}
    )
    assert policy == before


@pytest.mark.parametrize("policy", [{"anything": True}, [], {"alignment": []}])
def test_arbitrary_next_action_data_does_not_declare_alignment(policy):
    with pytest.raises(ValueError):
        validate_next_action_alignment(policy, {"criterion": ["learner_response"]})


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), 2),
        (("schema_version",), True),
        (("schema_version",), "1"),
        (("criterion_feedback",), []),
        (("criterion_feedback", 0, "criterion_key"), "other_version_criterion"),
        (("criterion_feedback", 0, "evidence_source_types"), ["other_evidence"]),
        (("criterion_feedback", 0, "evidence_source_types"), ["learner_response"] * 2),
        (("criterion_feedback", 0, "met"), " "),
        (("criterion_feedback", 0, "not_met"), None),
        (("criterion_feedback", 0, "not_evaluable"), True),
        (("criterion_feedback", 0, "met"), "x" * 4001),
        (("result_adaptation",), {}),
        (("result_adaptation", "PASS", "feedback"), []),
        (("result_adaptation", "PASS", "adaptation"), ""),
        (("result_adaptation", "INCOMPLETE", "feedback"), "\n"),
        (("result_adaptation", "INCOMPLETE", "adaptation"), {}),
    ],
)
def test_missing_invalid_or_mismatched_links_are_rejected(path, value):
    policy = next_action_contract("criterion")
    target = policy["alignment"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        validate_next_action_alignment(policy, {"criterion": ["learner_response"]})


def test_feedback_must_cover_optional_criteria_and_cannot_duplicate_keys():
    policy = next_action_contract("required")
    criteria = {"required": ["learner_response"], "optional": ["learner_response"]}
    with pytest.raises(ValueError, match="every current criterion exactly once"):
        validate_next_action_alignment(policy, criteria)
    policy["alignment"]["criterion_feedback"] *= 2
    with pytest.raises(ValueError, match="every current criterion exactly once"):
        validate_next_action_alignment(policy, {"required": ["learner_response"]})


def test_each_result_branch_is_required_and_unknown_results_are_rejected():
    for result in ("PASS", "INCOMPLETE"):
        policy = next_action_contract("criterion")
        del policy["alignment"]["result_adaptation"][result]
        with pytest.raises(ValueError):
            validate_next_action_alignment(policy, {"criterion": ["learner_response"]})
    policy = next_action_contract("criterion")
    policy["alignment"]["result_adaptation"]["FAIL"] = policy["alignment"]["result_adaptation"][
        "INCOMPLETE"
    ]
    with pytest.raises(ValueError):
        validate_next_action_alignment(policy, {"criterion": ["learner_response"]})
