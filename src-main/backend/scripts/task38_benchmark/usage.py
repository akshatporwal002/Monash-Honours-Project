"""Metadata-only snapshot extraction and explicitly reconciled provider billing."""

import hashlib
import json
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

LOCAL = {"local", "offline", "local-deterministic", "local-template", "template"}


def extract_snapshot(report, snapshot):
    """Read ONLY benchmark response metadata from an operator-provided synthetic snapshot."""
    snapshot = Path(snapshot).resolve(strict=True)
    with snapshot.open("rb") as source:
        snapshot_digest = hashlib.file_digest(source, "sha256").hexdigest()
    rows = []
    with sqlite3.connect(snapshot.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        for loop in report["loops"]:
            # Submission IDs also recover a workflow when the initial feedback poll failed.
            for submission in loop["submission_ids"]:
                records = db.execute(
                    """
                    SELECT f.id, f.workflow_run_id, f.provider, f.model, f.prompt_version,
                           f.source_references, f.input_tokens, f.output_tokens,
                           f.usage_complete, f.estimated_cost, f.created_at
                    FROM feedback_records f WHERE f.submission_id = ?
                    ORDER BY f.id
                """,
                    (submission,),
                ).fetchall()
                for record in records:
                    item = dict(record)
                    item["source_references"] = json.loads(item["source_references"])
                    item.update(
                        loop_id=loop["loop_id"], feature="feedback_generation", agent="feedback"
                    )
                    item["recorded_estimated_cost"] = str(item.pop("estimated_cost"))
                    item["usage_complete"] = bool(item["usage_complete"])
                    rows.append(item)
                    judges = db.execute(
                        """
                        SELECT id, provider, model, prompt_version, quality_policy_version,
                               input_tokens, output_tokens, usage_complete, estimated_cost, created_at
                        FROM judge_evaluations WHERE feedback_id = ? ORDER BY id
                    """,
                        (record["id"],),
                    ).fetchall()
                    for judge in judges:
                        item = dict(judge)
                        item.update(
                            loop_id=loop["loop_id"],
                            workflow_run_id=record["workflow_run_id"],
                            feature="feedback_judge",
                            agent="quality_judge",
                            source_references=json.loads(record["source_references"]),
                        )
                        item["recorded_estimated_cost"] = str(item.pop("estimated_cost"))
                        item["usage_complete"] = bool(item["usage_complete"])
                        rows.append(item)
    return {
        "schema": "task38.usage.v1",
        "run_id": report["manifest"]["run_id"],
        "snapshot_sha256": snapshot_digest,
        "evidence_class": report["evidence_class"],
        "records": rows,
        "coverage": {"complete": False, "covered_loop_ids": [], "reconciliation_record": None},
        "pricing": {},
        "fx": {},
        "limitations": [
            "Database estimates have no currency/provenance field.",
            "Unpersisted attempts, retries and other agents require provider billing reconciliation.",
            "Learner API does not expose usage. Local records are not zero-cost external evidence.",
        ],
    }


def amount(value):
    number = Decimal(str(value))
    if not number.is_finite() or number < 0:
        raise ValueError("Usage amounts must be finite and nonnegative")
    return number


def cost_report(report, ledger):
    if ledger["run_id"] != report["manifest"]["run_id"]:
        raise ValueError("Usage belongs to another run")
    loops = {r["loop_id"]: r for r in report["loops"]}
    ids, totals, grouped, missing, local_records = set(), {}, {}, [], []
    for row in ledger["records"]:
        identity = row["id"]
        if identity in ids or row["loop_id"] not in loops:
            raise ValueError("Duplicate usage receipt or unknown loop")
        ids.add(identity)
        if (row.get("provider") or "").casefold() in LOCAL:
            local_records.append(identity)
            continue
        if not row.get("usage_complete"):
            missing.append(identity)
            continue
        if not row.get("provider") or not row.get("model"):
            missing.append(identity)
            continue
        for token in ("input_tokens", "output_tokens"):
            if type(row.get(token)) is not int or row[token] < 0:
                raise ValueError("Actual token counts must be nonnegative integers")
        price = ledger.get("pricing", {}).get(row["provider"] + "/" + row["model"], {})
        fx = ledger.get("fx", {})
        if not all(price.get(k) for k in ("source", "date", "currency", "schedule_version")):
            missing.append(identity)
            continue
        date.fromisoformat(price["date"])
        if (
            not all(fx.get(k) for k in ("source", "date", "currency", "aud_per_unit"))
            or fx["currency"] != price["currency"]
        ):
            missing.append(identity)
            continue
        date.fromisoformat(fx["date"])
        if (
            not all(row.get(k) for k in ("prompt_version", "feature", "agent", "billing_receipt"))
            or row.get("billed_cost") is None
            or row.get("billing_currency") != price["currency"]
        ):
            missing.append(identity)
            continue
        # The paid/billable amount comes from a provider receipt, not token estimates.
        billed = amount(row["billed_cost"])
        rate = amount(fx["aud_per_unit"])
        if rate == 0:
            raise ValueError("Currency conversion must be positive")
        aud = billed * rate
        totals[row["loop_id"]] = totals.get(row["loop_id"], Decimal(0)) + aud
        key = "/".join((row["agent"], row["feature"], row["provider"], row["model"]))
        group = grouped.setdefault(key, {"input_tokens": 0, "output_tokens": 0, "aud": Decimal(0)})
        group["input_tokens"] += row["input_tokens"]
        group["output_tokens"] += row["output_tokens"]
        group["aud"] += aud
    coverage = ledger.get("coverage", {})
    complete = (
        coverage.get("complete") is True
        and bool(coverage.get("reconciliation_record"))
        and set(coverage.get("covered_loop_ids", [])) == set(loops)
        and not missing
        and bool(totals)
        and not report["manifest"]["config"]["fake"]
        and all(
            r["loop_id"] in totals
            for r in loops.values()
            if r["status"] in {"complete", "awaiting_human"}
        )
        and ledger.get("evidence_class") != "SYNTHETIC DRY RUN"
    )
    scenarios = []
    for scenario in report["scenarios"]:
        selected = [
            r
            for r in loops.values()
            if r["users"] == scenario["users"] and r["phase"] == "measurement"
        ]
        spend = sum((totals.get(r["loop_id"], Decimal(0)) for r in selected), Decimal(0))
        denominator = sum(r["status"] == "complete" for r in selected)
        average = spend / denominator if complete and denominator else None
        scenarios.append(
            {
                "users": scenario["users"],
                "recorded_external_aud_subtotal": str(spend) if totals else None,
                "complete_loop_denominator": denominator,
                "external_aud_per_complete_loop": str(average) if average is not None else None,
                "within_threshold_observed": average <= Decimal("0.10")
                if average is not None
                else None,
            }
        )
    return {
        "status": "reconciled" if complete else "unknown_or_incomplete",
        "provider_model_observation": {
            "declared": {
                key: report["manifest"]["config"].get(key) for key in ("provider", "model")
            },
            "recorded_external": sorted(
                {
                    str(row.get("provider")) + "/" + str(row.get("model"))
                    for row in ledger["records"]
                    if row.get("provider") and row["provider"].casefold() not in LOCAL
                }
            ),
            "note": "Compare recorded versions with declared runtime and approved aliases before accepting a configuration-change claim.",
        },
        "threshold_aud": "0.10",
        "scenarios": scenarios,
        "missing_receipts": missing,
        "local_template_receipts_excluded_from_external_evidence": local_records,
        "by_agent_feature_provider_model": {
            key: {**v, "aud": str(v["aud"])} for key, v in grouped.items()
        },
        "warmup_recorded_external_aud_subtotal": str(
            sum(
                (
                    totals.get(r["loop_id"], Decimal(0))
                    for r in loops.values()
                    if r["phase"] == "warmup"
                ),
                Decimal(0),
            )
        )
        if totals
        else None,
        "ledger": ledger,
        "limitation": "Reconciliation is an external attestation; harness does not verify invoices or approve compliance.",
    }
