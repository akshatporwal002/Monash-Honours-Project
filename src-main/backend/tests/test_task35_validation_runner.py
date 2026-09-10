"""Deterministic import, adjudication and release-boundary checks with synthetic reviewers."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.task35_validation.prepare import FIXTURES, build_cases
from scripts.task35_validation.runner import digest, run, thresholds, validate_links
from scripts.task35_validation.schema import DIMENSIONS, Bundle

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def example():
    draft = json.loads((ROOT / FIXTURES / "draft-bundle.json").read_text())
    # Four cases of one criterion, with deliberately different error directions.
    cases = [draft["cases"][i] for i in (0, 1, 2, 3)]
    draft["cases"] = cases
    md = digest(draft["manifest"])
    draft["reviewers"] = [
        {
            "reviewer_id": rid,
            "name": f"Synthetic {rid}",
            "expertise_reference": "synthetic",
            "training_reference": "synthetic",
            "appointment_reference": "synthetic",
        }
        for rid in ("r1", "r2", "r3")
    ]
    for i, case in enumerate(cases):
        human_result = "PASS" if i < 2 else "INCOMPLETE"
        system_result = "PASS" if i in (0, 2, 3) else "INCOMPLETE"
        criterion = next(iter(case["criteria"]))
        gold = {
            "criteria": {criterion: "MET" if human_result == "PASS" else "NOT_MET"},
            "result": human_result,
        }
        for channel in ("task", "feedback", "evaluation", "judge", "assessment"):
            output = {
                "case_id": case["case_id"],
                "channel": channel,
                "manifest_digest": md,
                "case_digest": digest(case),
                "state": "RECORDED",
                "text": "Clearly synthetic recorded output for metric arithmetic.",
                "reason": "",
                "judge_decision": None,
                "criteria": None,
                "result": None,
            }
            if channel == "judge":
                output["judge_decision"] = "REJECTED" if i in (0, 2) else "APPROVED"
                values = {"flawed": i < 2}
            elif channel == "assessment":
                output["result"] = system_result
                output["criteria"] = {criterion: "MET" if system_result == "PASS" else "NOT_MET"}
                values = gold
            else:
                values = {"factual_correct": i != 1, "hallucination": i == 1}
                if channel == "feedback":
                    values |= {
                        "feedback_ratings": {d: i + 2 for d in DIMENSIONS},
                        "incomplete_response": i >= 2,
                        "next_action_and_revision": i == 2,
                    }
            draft["outputs"].append(output)
            for rid in ("r1", "r2"):
                draft["ratings"].append(
                    {
                        "rating_id": f"{i}-{channel}-{rid}",
                        "case_id": case["case_id"],
                        "channel": channel,
                        "reviewer_id": rid,
                        "rated_at": "2026-09-10T00:00:00Z",
                        "manifest_digest": md,
                        "case_digest": digest(case),
                        "output_digest": None if channel == "assessment" else digest(output),
                        "state": "RATED",
                        "rationale": "Synthetic arithmetic only.",
                        "independent": True,
                        "values": copy.deepcopy(values),
                    }
                )
    return draft


def report(data):
    bundle = Bundle.model_validate(data)
    return run(bundle, bundle.manifest, ROOT)


def test_known_counts_do_not_pool_quality_with_assessment(example):
    result = report(example)
    metrics = result["metrics"]
    assert metrics["task.factual_accuracy"]["estimate"] == 0.75
    assert metrics["feedback.hallucination"]["estimate"] == 0.25
    assert metrics["feedback.accuracy"]["estimate"] == 3.5
    assert metrics["feedback.next_action"]["estimate"] == 0.5
    assert metrics["judge.flawed_rejection"]["estimate"] == 0.5
    assert metrics["judge.false_rejection"]["estimate"] == 0.5
    assert metrics["assessment.false_pass"]["numerator"] == 2
    assert metrics["assessment.false_pass"]["denominator"] == 2
    assert metrics["assessment.false_incomplete"]["numerator"] == 1
    assert metrics["assessment.false_incomplete"]["denominator"] == 2
    assert metrics["assessment.Q-PRED-v1.agreement"]["estimate"] == 0.25
    assert result["included_pairs"] == 20
    assert result["exclusions"] == {}
    assert result["ai_assessment_release"] == "PENDING"
    assert result["content_feedback_judge_status"] == "UNVERIFIED"
    assert not result["operational_ai_suggestions_enabled"]
    assert "assessment.false_pass" not in result["target_comparisons"]
    assert result["strata"]["task_type"]["short_answer"]["assessment.false_pass"]["estimate"] == 1
    assert all(v["estimate"] == 1 for v in result["human_baseline"].values())


def test_missing_and_invalid_outputs_account_for_every_pair(example):
    example["outputs"] = [o for o in example["outputs"] if o["channel"] != "assessment"]
    result = report(example)
    assert result["exclusions"] == {"assessment.missing_output": 4}
    assert result["metrics"]["assessment.false_pass"]["estimate"] is None
    # Blinded trained-human agreement does not require system output.
    assert len(result["human_baseline"]) == 2
    assert result["included_pairs"] + sum(result["exclusions"].values()) == 20


@pytest.mark.parametrize("state", ["MISSING", "INVALID", "ABSTAINED"])
def test_explicit_nonrecorded_output_states(example, state):
    output = next(o for o in example["outputs"] if o["channel"] == "assessment")
    output.update(state=state, reason="Synthetic noncompletion", criteria=None, result=None)
    result = report(example)
    assert result["exclusions"] == {f"assessment.output_{state.lower()}": 1}


@pytest.mark.parametrize("state", ["ABSTAINED", "INVALID"])
def test_abstained_ratings_never_become_negative_labels(example, state):
    rating = next(r for r in example["ratings"] if r["channel"] == "assessment")
    rating.update(state=state, values=None)
    result = report(example)
    assert result["exclusions"] == {"assessment.rating_abstained_or_invalid": 1}
    assert result["metrics"]["assessment.false_incomplete"]["denominator"] == 1


def disagree(example):
    rating = next(r for r in example["ratings"] if r["rating_id"] == "0-assessment-r2")
    rating["values"] = {"criteria": {"Q-PRED-v1": "NOT_MET"}, "result": "INCOMPLETE"}
    return rating


def test_independent_disagreement_and_third_party_adjudication(example):
    rating = disagree(example)
    before = report(example)
    assert before["exclusions"] == {"assessment.unresolved_disagreement": 1}
    assert before["human_baseline"]["short_answer.Q-PRED-v1.r1:r2"]["estimate"] == 0.75
    example["adjudications"].append(
        {
            "case_id": rating["case_id"],
            "channel": "assessment",
            "reviewer_id": "r3",
            "rating_ids": ["0-assessment-r1", "0-assessment-r2"],
            "rationale": "Synthetic adjudication reason",
            "decided_at": "2026-09-10T01:00:00Z",
            "values": copy.deepcopy(rating["values"]),
        }
    )
    after = report(example)
    assert after["exclusions"] == {}
    assert after["metrics"]["assessment.false_pass"]["numerator"] == 3
    assert after["human_baseline"] == before["human_baseline"]
    example["adjudications"][0]["reviewer_id"] = "r1"
    with pytest.raises(ValueError, match="third reviewer"):
        report(example)


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda x: x["outputs"].append(x["outputs"][0]), "duplicate output"),
        (lambda x: x["ratings"].append(x["ratings"][0]), "duplicate rating"),
        (lambda x: x["ratings"][0].update(reviewer_id="unknown"), "unknown reviewer"),
        (lambda x: x["ratings"][0].update(case_digest="0" * 64), "stale case"),
        (lambda x: x["ratings"][0].update(manifest_digest="0" * 64), "stale manifest"),
        (
            lambda x: x["outputs"][0].update(text="Changed after review"),
            "stale or missing rated output",
        ),
        (lambda x: x["outputs"][0].update(case_id="missing"), "unknown case"),
        (
            lambda x: x["reviewers"][1].update(name=x["reviewers"][0]["name"]),
            "multiple independent",
        ),
    ],
)
def test_invalid_links_are_rejected(example, mutation, match):
    mutation(example)
    with pytest.raises(ValueError, match=match):
        report(example)


@pytest.mark.parametrize("value", [0, 6, True, "4", float("nan")])
def test_feedback_scores_reject_invalid_and_coerced_values(example, value):
    rating = next(r for r in example["ratings"] if r["channel"] == "feedback")
    rating["values"]["feedback_ratings"]["accuracy"] = value
    with pytest.raises(ValidationError):
        Bundle.model_validate(example)


def test_missing_fields_unknown_fields_and_impossible_ratings(example):
    example["ratings"][0]["values"]["hallucination"] = True
    with pytest.raises(ValidationError, match="factually correct"):
        Bundle.model_validate(example)
    example["ratings"][0]["values"].pop("hallucination")
    with pytest.raises(ValidationError, match="requires exactly"):
        Bundle.model_validate(example)
    example["enable_ai"] = True
    with pytest.raises(ValidationError, match="Extra inputs"):
        Bundle.model_validate(example)


def test_current_manifest_and_disk_changes_fail_closed(example, tmp_path):
    bundle = Bundle.model_validate(example)
    current = bundle.manifest.model_copy(deep=True)
    current.components["model"] = "changed-model"
    result = run(bundle, current, ROOT)
    assert "recorded/current manifest mismatch" in result["blockers"]
    current.files.pop(next(iter(current.files)))
    assert run(bundle, current, ROOT)["content_feedback_judge_status"] == "UNVERIFIED"
    # Simulate changed controlling content by a copied repository subset, not production writes.
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/01-implementation-requirements.md").write_text(
        (ROOT / "docs/01-implementation-requirements.md").read_text()
    )
    stale = run(bundle, bundle.manifest, tmp_path)
    assert any(x.startswith("stale artifact:") for x in stale["blockers"])
    assert not stale["operational_ai_suggestions_enabled"]


def test_thresholds_come_from_requirements_and_missing_text_errors(tmp_path):
    assert thresholds(ROOT) == {
        "minimum_cases": 100,
        "factual_accuracy": 0.8,
        "hallucination": 0.05,
        "feedback_rating": 4,
        "next_action": 0.8,
        "flawed_rejection": 0.8,
        "false_rejection": 0.2,
    }
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/01-implementation-requirements.md").write_text("No thresholds")
    with pytest.raises(ValueError, match="threshold not found"):
        thresholds(tmp_path)


def test_draft_golden_package_has_108_cases_and_no_human_evidence():
    bundle = Bundle.model_validate_json((ROOT / FIXTURES / "draft-bundle.json").read_text())
    scenarios = json.loads((ROOT / FIXTURES / "scenarios.json").read_text())
    assert bundle.cases == build_cases(scenarios)
    assert len(bundle.cases) == 108
    assert len({c.family for c in bundle.cases}) == 12
    assert len({c.task_type for c in bundle.cases}) == 6
    assert len({c.access_form for c in bundle.cases}) == 3
    assert len({c.variant for c in bundle.cases}) == 9
    assert sum(c.draft_judge_flawed for c in bundle.cases) == 36
    assert all(c.draft_feedback_candidate and c.draft_judge_rationale for c in bundle.cases)
    assert all(c.reviewer_decision is None and c.reviewer_provenance is None for c in bundle.cases)
    assert (
        not bundle.ratings and not bundle.reviewers and not bundle.approvals and not bundle.outputs
    )
    validate_links(bundle)
    result = run(bundle, bundle.manifest, ROOT)
    assert result["exclusions"] == {
        f"{ch}.missing_output": 108
        for ch in ("task", "feedback", "evaluation", "judge", "assessment")
    }
    assert not any("stale" in b for b in result["blockers"])
    assert result["approved_cases"] == 0
    assert result["content_feedback_judge_status"] == "UNVERIFIED"


@pytest.mark.parametrize(
    "component", ["model", "prompt", "source", "rule", "retrieval", "task", "curriculum", "bloom"]
)
def test_every_version_dimension_invalidates_evidence(example, component):
    bundle = Bundle.model_validate(example)
    current = bundle.manifest.model_copy(deep=True)
    current.components[component] = "new-revision"
    result = run(bundle, current, ROOT)
    assert "recorded/current manifest mismatch" in result["blockers"]
    assert result["content_feedback_judge_status"] == "UNVERIFIED"
    assert result["ai_assessment_release"] == "PENDING"


def test_baseline_does_not_pool_different_reviewer_pairs(example):
    for rating in example["ratings"]:
        if rating["rating_id"] == "0-assessment-r2":
            rating["reviewer_id"] = "r3"
    baseline = report(example)["human_baseline"]
    assert baseline["short_answer.Q-PRED-v1.r1:r2"]["denominator"] == 3
    assert baseline["short_answer.Q-PRED-v1.r1:r3"]["denominator"] == 1


def test_not_evaluable_criterion_remains_a_distinct_label(example):
    for rating in example["ratings"]:
        if rating["rating_id"] in {"2-assessment-r1", "2-assessment-r2"}:
            rating["values"]["criteria"]["Q-PRED-v1"] = "NOT_EVALUABLE"
    metric = report(example)["metrics"]["assessment.Q-PRED-v1.agreement"]
    assert metric["confusion"]["NOT_EVALUABLE"]["MET"] == 1


def test_cli_rejects_malformed_import_with_pending_report(tmp_path, monkeypatch):
    from scripts.task35_validation.runner import main

    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"operational_ai_suggestions_enabled": true}')
    destination = tmp_path / "report.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "runner",
            "--bundle",
            str(invalid),
            "--current-manifest",
            str(ROOT / FIXTURES / "manifest.json"),
            "--report",
            str(destination),
        ],
    )
    assert main() == 2
    result = json.loads(destination.read_text())
    assert "import_error" in result
    assert result["content_feedback_judge_status"] == "UNVERIFIED"
    assert result["ai_assessment_release"] == "PENDING"
    assert result["operational_ai_suggestions_enabled"] is False


def test_feedback_review_cannot_be_used_as_an_assessment_baseline(example):
    rating = next(r for r in example["ratings"] if r["channel"] == "assessment")
    rating["output_digest"] = "0" * 64
    with pytest.raises(ValidationError, match="blinded"):
        Bundle.model_validate(example)


def test_schema_export_matches_import_contract():
    actual = json.loads((ROOT / FIXTURES / "review-import.schema.json").read_text())
    assert actual == Bundle.model_json_schema()


def test_adjudication_does_not_inflate_independent_feedback_average(example):
    rating = next(r for r in example["ratings"] if r["rating_id"] == "0-feedback-r2")
    rating["values"]["feedback_ratings"]["accuracy"] = 4
    example["adjudications"].append(
        {
            "case_id": rating["case_id"],
            "channel": "feedback",
            "reviewer_id": "r3",
            "rating_ids": ["0-feedback-r1", "0-feedback-r2"],
            "rationale": "Synthetic resolution",
            "decided_at": "2026-09-10T01:00:00Z",
            "values": copy.deepcopy(rating["values"]),
        }
    )
    # Original scores average to 3 on this output, then 3,4,5 on the other outputs.
    assert report(example)["metrics"]["feedback.accuracy"]["estimate"] == 3.75


def test_blinded_packet_does_not_reveal_variant_or_expected_labels():
    packet = (ROOT / "docs/learnlens/task-35-reviewer-packet.md").read_text()
    assert "draft_expected" not in packet
    assert "draft_judge_flawed" not in packet
    assert "T35-h-zero-incorrect" not in packet
    assert packet.count("Reviewer decision: ______") == 108
    assert "## T35-001\n" in packet
    assert packet.index("## T35-001\n") > packet.index("## T35-")
