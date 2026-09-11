"""Hand-calculated cost denominators and metadata-only extraction from tiny synthetic tables."""

import copy
import json
import sqlite3

import pytest

from scripts.task38_benchmark.usage import cost_report, extract_snapshot


def example():
    report = {
        "manifest": {"run_id": "run", "config": {"fake": False}},
        "scenarios": [{"users": 50}],
        "evidence_class": "synthetic environment observation",
        "loops": [
            {
                "loop_id": "a",
                "users": 50,
                "phase": "measurement",
                "status": "complete",
                "submission_ids": ["response-a"],
            },
            {
                "loop_id": "b",
                "users": 50,
                "phase": "measurement",
                "status": "feedback_failed",
                "submission_ids": ["response-b"],
            },
            {
                "loop_id": "c",
                "users": 50,
                "phase": "warmup",
                "status": "complete",
                "submission_ids": [],
            },
        ],
    }
    ledger = {
        "run_id": "run",
        "records": [],
        "coverage": {
            "complete": True,
            "covered_loop_ids": ["a", "b", "c"],
            "reconciliation_record": "synthetic-billing-test-v1",
        },
        "pricing": {
            "provider/model": {
                "source": "synthetic-price-fixture",
                "date": "2026-09-10",
                "currency": "USD",
                "schedule_version": "fixture-v1",
                "input_per_million": "1",
                "output_per_million": "2",
            }
        },
        "fx": {
            "source": "synthetic-fx-fixture",
            "date": "2026-09-10",
            "currency": "USD",
            "aud_per_unit": "1.5",
        },
    }
    for loop, cost in (("a", "0.03"), ("b", "0.02"), ("c", "0.01")):
        ledger["records"].append(
            {
                "id": "receipt-" + loop,
                "loop_id": loop,
                "provider": "provider",
                "model": "model",
                "usage_complete": True,
                "input_tokens": 100,
                "output_tokens": 20,
                "prompt_version": "synthetic-v1",
                "agent": "feedback",
                "feature": "feedback_generation",
                "billing_receipt": "synthetic-receipt-" + loop,
                "billed_cost": cost,
                "billing_currency": "USD",
            }
        )
    return report, ledger


def test_cost_includes_failed_attempts_excludes_warmup_and_uses_aud():
    report, ledger = example()
    cost = cost_report(report, ledger)
    assert cost["status"] == "reconciled"
    assert cost["scenarios"][0]["external_aud_per_complete_loop"] == "0.075"
    assert cost["scenarios"][0]["complete_loop_denominator"] == 1
    assert cost["warmup_recorded_external_aud_subtotal"] == "0.015"
    assert (
        cost["by_agent_feature_provider_model"]["feedback/feedback_generation/provider/model"][
            "input_tokens"
        ]
        == 300
    )


@pytest.mark.parametrize(
    "change",
    [
        "local",
        "missing_usage",
        "missing_price",
        "missing_fx",
        "missing_bill",
        "missing_coverage",
        "fake",
    ],
)
def test_missing_data_or_templates_never_become_zero_actual_provider_cost(change):
    report, ledger = example()
    if change == "local":
        ledger["records"][0]["provider"] = "local"
    elif change == "missing_usage":
        ledger["records"][0]["usage_complete"] = False
    elif change == "missing_price":
        ledger["pricing"] = {}
    elif change == "missing_fx":
        ledger["fx"] = {}
    elif change == "missing_bill":
        del ledger["records"][0]["billed_cost"]
    elif change == "missing_coverage":
        ledger["coverage"]["covered_loop_ids"].pop()
    else:
        report["manifest"]["config"]["fake"] = True
    result = cost_report(report, ledger)
    assert result["status"] == "unknown_or_incomplete"
    assert result["scenarios"][0]["external_aud_per_complete_loop"] is None


def test_no_complete_human_loop_has_no_cost_denominator():
    report, ledger = example()
    report["loops"][0]["status"] = "awaiting_human"
    result = cost_report(report, ledger)
    assert result["scenarios"][0]["external_aud_per_complete_loop"] is None


@pytest.mark.parametrize(
    "change", ["duplicate", "wrong_run", "negative", "nan", "bad_fx", "float_tokens"]
)
def test_invalid_cost_receipts_rejected(change):
    report, ledger = example()
    if change == "duplicate":
        ledger["records"].append(copy.deepcopy(ledger["records"][0]))
    elif change == "wrong_run":
        ledger["run_id"] = "another"
    elif change == "negative":
        ledger["records"][0]["billed_cost"] = "-1"
    elif change == "nan":
        ledger["records"][0]["billed_cost"] = "NaN"
    elif change == "bad_fx":
        ledger["fx"]["aud_per_unit"] = "0"
    else:
        ledger["records"][0]["input_tokens"] = 1.5
    with pytest.raises(ValueError):
        cost_report(report, ledger)


def test_snapshot_extracts_only_requested_metadata_and_keeps_unknown_currency(tmp_path):
    path = tmp_path / "synthetic.sqlite"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE feedback_records (id TEXT, workflow_run_id TEXT, submission_id TEXT,
                provider TEXT, model TEXT, prompt_version TEXT, source_references TEXT,
                input_tokens INTEGER, output_tokens INTEGER, usage_complete INTEGER,
                estimated_cost NUMERIC, created_at TEXT, feedback_content TEXT);
            CREATE TABLE judge_evaluations (id TEXT, feedback_id TEXT, provider TEXT, model TEXT,
                prompt_version TEXT, quality_policy_version TEXT, input_tokens INTEGER,
                output_tokens INTEGER, usage_complete INTEGER, estimated_cost NUMERIC, created_at TEXT);
        """)
        for response in ("response-a", "unrelated"):
            db.execute(
                "INSERT INTO feedback_records VALUES (?, 'workflow', ?, 'provider', 'model', 'prompt', '[]', 100, 20, 1, 0.01, 'date', 'PRIVATE ANSWER')",
                (response, response),
            )
        db.execute(
            "INSERT INTO judge_evaluations VALUES ('judge', 'response-a', 'provider', 'model', 'prompt', 'rule', 10, 10, 1, 0.02, 'date')"
        )
    before = path.read_bytes()
    report, _ = example()
    ledger = extract_snapshot(report, path)
    assert len(ledger["records"]) == 2
    assert {r["feature"] for r in ledger["records"]} == {"feedback_generation", "feedback_judge"}
    assert "PRIVATE ANSWER" not in json.dumps(ledger)
    assert "unrelated" not in json.dumps(ledger)
    assert ledger["coverage"]["complete"] is False
    assert ledger["pricing"] == {}
    assert path.read_bytes() == before


def test_missing_snapshot_is_not_created(tmp_path):
    report, _ = example()
    path = tmp_path / "missing.sqlite"
    with pytest.raises(FileNotFoundError):
        extract_snapshot(report, path)
    assert not path.exists()


def test_durable_snapshot_keeps_failed_attempts_actuals_and_partial_usage(tmp_path):
    path = tmp_path / "durable.sqlite"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE feedback_records (id TEXT, workflow_run_id TEXT, submission_id TEXT,
                provider TEXT, model TEXT, prompt_version TEXT, source_references TEXT,
                input_tokens INTEGER, output_tokens INTEGER, usage_complete INTEGER,
                estimated_cost NUMERIC, created_at TEXT);
            CREATE TABLE judge_evaluations (id TEXT, feedback_id TEXT, provider TEXT, model TEXT,
                prompt_version TEXT, quality_policy_version TEXT, input_tokens INTEGER,
                output_tokens INTEGER, usage_complete INTEGER, estimated_cost NUMERIC, created_at TEXT);
            CREATE TABLE provider_usage (id TEXT, state TEXT, reserved_micros INTEGER,
                exposure_micros INTEGER, estimated_micros INTEGER, actual_micros INTEGER,
                input_tokens INTEGER, output_tokens INTEGER, provider_response_id TEXT,
                receipt_id TEXT, provenance TEXT, created_at TEXT);
            INSERT INTO feedback_records VALUES ('legacy','workflow','response-a','provider','model',
                'prompt','[]',100,20,1,0.01,'date');
        """)
        provenance = {
            "context": {"submission_id": "response-a", "private": "DO-NOT-EXPORT"},
            "provider": "provider",
            "model": "model",
            "prompt_version": "prompt",
            "currency": "USD",
            "pricing_version": "fixture-v1",
            "budget_policy_version": "fixture-budget",
        }
        for key, state, actual, output, response in (
            ("success", "RECONCILED", 30_000, 20, "response-a"),
            ("crashed", "DISPATCHED", None, None, "response-a"),
            ("unrelated", "UNKNOWN", None, None, "unrelated"),
        ):
            scoped = copy.deepcopy(provenance)
            scoped["context"]["submission_id"] = response
            db.execute(
                "INSERT INTO provider_usage VALUES (?,?,100000,100000,?,?,100,?,'response-id',?,?, 'date')",
                (
                    key,
                    state,
                    10_000 if output else None,
                    actual,
                    output,
                    "fixture-bill" if actual is not None else None,
                    json.dumps(scoped),
                ),
            )
    report, _ = example()
    ledger = extract_snapshot(report, path)
    assert ledger["durable_metering_available"] is True
    assert len(ledger["records"]) == 2
    assert len(ledger["legacy_generation_metadata"]) == 1
    records = {row["id"]: row for row in ledger["records"]}
    assert records["provider-usage:success"]["billed_cost"] == "0.03"
    assert records["provider-usage:success"]["recorded_estimated_cost"] == "0.01"
    assert records["provider-usage:crashed"]["billed_cost"] is None
    assert records["provider-usage:crashed"]["output_tokens"] is None
    assert "DO-NOT-EXPORT" not in json.dumps(ledger) and "unrelated" not in json.dumps(ledger)
    assert ledger["coverage"]["complete"] is False


def test_missing_tokens_do_not_erase_known_billed_subtotal():
    report, ledger = example()
    ledger["records"][0].update(usage_complete=False, output_tokens=None)
    costs = cost_report(report, ledger)
    assert costs["status"] == "unknown_or_incomplete"
    assert costs["scenarios"][0]["recorded_external_aud_subtotal"] == "0.075"
    assert costs["scenarios"][0]["external_aud_per_complete_loop"] is None


def test_duplicate_billing_receipts_and_changed_pricing_are_not_counted_twice():
    report, ledger = example()
    ledger["records"][1]["billing_receipt"] = ledger["records"][0]["billing_receipt"]
    with pytest.raises(ValueError, match="billing receipt"):
        cost_report(report, ledger)
    report, ledger = example()
    ledger["records"][0]["pricing_version"] = "different-version"
    assert cost_report(report, ledger)["status"] == "unknown_or_incomplete"


def test_not_sent_rows_require_no_fabricated_invoice_and_local_mode_stays_unknown():
    report, ledger = example()
    ledger["records"].append({"id": "not-sent", "loop_id": "a", "metering_state": "NOT_SENT"})
    costs = cost_report(report, ledger)
    assert costs["undispatched_receipts_excluded_from_billed_spend"] == ["not-sent"]
    report["manifest"]["config"]["local_only"] = True
    assert cost_report(report, ledger)["scenarios"][0]["external_aud_per_complete_loop"] is None
