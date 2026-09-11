"""Packet checks use synthetic data only; none of these fixtures approve an evaluator."""

import copy
from datetime import UTC, datetime, timedelta

import pytest
from test_evaluator_release_workflow import gate_evidence
from test_live_assessment_moderation import evidence
from test_task35_validation_runner import ROOT, example  # noqa: F401

from scripts.task35_validation import release_packet
from scripts.task35_validation.schema import Bundle


def test_actual_runner_rejects_draft_and_synthetic_packets(request):
    bundle = Bundle.model_validate(request.getfixturevalue("example"))
    approval = {**evidence(), "assessment_gate": gate_evidence(), "baseline_key": "test"}
    approval.pop("false_pass")
    approval.pop("false_incomplete")
    with pytest.raises(ValueError, match="not met"):
        release_packet.prepare_packet(
            bundle, bundle.manifest, ROOT, approval, "a" * 64, datetime.now(UTC) + timedelta(days=1)
        )


@pytest.fixture
def packet_inputs(request, monkeypatch):
    bundle = Bundle.model_validate(request.getfixturevalue("example"))
    gate = gate_evidence()
    gate.update(
        case_count=4,
        approved_minimum_case_count=4,
        baseline_statistic="agreement",
        baseline_value=1.0,
    )
    gate["experts"] = [r.model_dump(exclude={"reviewer_id"}) for r in bundle.reviewers[:2]]
    approval = {
        **evidence(),
        "assessment_gate": gate,
        "baseline_key": "sample",
        "max_false_pass": 0.1,
        "max_false_incomplete": 0.1,
    }
    approval.pop("false_pass")
    approval.pop("false_incomplete")
    report = {
        "content_feedback_judge_status": "TARGETS_MET",
        "exclusions": {},
        "approved_cases": 4,
        "human_baseline": {"sample": {"estimate": 1.0}},
        "manifest_digest": "a" * 64,
        "metrics": {
            f"assessment.{name}": {"estimate": 0.05, "denominator": 20, "numerator": 1}
            for name in ("false_pass", "false_incomplete")
        },
        "uncertainty": "Synthetic test interval description",
    }
    monkeypatch.setattr(release_packet, "run", lambda *_: report)
    return bundle, approval, report


def prepared(inputs):
    bundle, approval, _ = inputs
    return release_packet.prepare_packet(
        bundle, bundle.manifest, ROOT, approval, "a" * 64, datetime.now(UTC) + timedelta(days=1)
    )


def test_packet_uses_measured_rates_and_preserves_exact_record_digests(packet_inputs):
    packet = prepared(packet_inputs)
    assert packet["evidence"]["false_pass"] == 0.05
    assert packet["evidence"]["recorded_validation"]["bundle_digest"] == release_packet.digest(
        packet_inputs[0]
    )
    assert "record_kind" not in packet["evidence"]


@pytest.mark.parametrize("failure", ["exclusion", "zero", "error", "baseline", "sample", "expert"])
def test_packet_rejects_missing_failed_or_mismatched_assessment_records(packet_inputs, failure):
    _, approval, report = packet_inputs
    if failure == "exclusion":
        report["exclusions"]["assessment.unresolved_disagreement"] = 1
    elif failure == "zero":
        report["metrics"]["assessment.false_pass"]["denominator"] = 0
    elif failure == "error":
        report["metrics"]["assessment.false_incomplete"]["estimate"] = 0.2
    elif failure == "baseline":
        report["human_baseline"]["sample"]["estimate"] = None
    elif failure == "sample":
        report["approved_cases"] = 3
    else:
        approval["assessment_gate"]["experts"] = copy.deepcopy(
            approval["assessment_gate"]["experts"]
        )
        approval["assessment_gate"]["experts"][0]["training_reference"] = "Different training"
    with pytest.raises(ValueError):
        prepared(packet_inputs)
