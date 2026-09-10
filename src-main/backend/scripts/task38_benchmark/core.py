"""Bounded scheduling, measurements and evidence-aware reporting."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit


class StopRun(Exception):
    """A bounded, safe-to-persist category rather than an exception message."""


@dataclass(frozen=True)
class Config:
    users: tuple[int, ...] = (50,)
    warmup_rounds: int = 1
    measurement_rounds: int = 1
    request_timeout: float = 15
    worker_timeout: float = 90
    human_timeout: float = 0
    phase_timeout: float = 600
    poll_seconds: float = 2
    max_requests: int = 1000
    max_cost_aud: str = "1"
    loop_cost_ceiling_aud: str = "0.10"
    target: str = ""
    origin: str = ""
    provider: str = ""
    model: str = ""
    synthetic_environment_record: str = ""
    provider_budget_record: str = ""
    csrf_cookie: str = "ql_csrf"
    csrf_header: str = "X-CSRF-Token"
    fake: bool = True
    versions: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)

    def validate(self):
        if not self.users or len(set(self.users)) != len(self.users):
            raise ValueError("Supply distinct scenario sizes")
        if any(type(n) is not int or not (1 if self.fake else 5) <= n <= 100 for n in self.users):
            raise ValueError("Real scenarios require 5–100 virtual users")
        if self.fake and (max(self.users) > 2 or self.measurement_rounds > 2):
            raise ValueError("Fake smoke runs are limited to two users and two measured rounds")
        if not 0 <= self.warmup_rounds <= 100 or not 1 <= self.measurement_rounds <= 100:
            raise ValueError("Invalid round count")
        for value in (
            self.request_timeout,
            self.worker_timeout,
            self.phase_timeout,
            self.poll_seconds,
        ):
            if not math.isfinite(value) or not 0 < value <= 3600:
                raise ValueError("Timeouts and poll intervals must be finite and bounded")
        if not math.isfinite(self.human_timeout) or not 0 <= self.human_timeout <= 3600:
            raise ValueError("Invalid human observation deadline")
        if type(self.max_requests) is not int or not 1 <= self.max_requests <= 1_000_000:
            raise ValueError("A bounded request budget is required")
        for value in (self.max_cost_aud, self.loop_cost_ceiling_aud):
            amount = Decimal(value)
            if not amount.is_finite() or amount <= 0:
                raise ValueError(
                    "Positive finite cost budget and per-loop exposure ceiling required"
                )
        if not self.fake:
            for url in (self.target, self.origin):
                parsed = urlsplit(url)
                if (
                    parsed.scheme not in {"http", "https"}
                    or not parsed.hostname
                    or parsed.username
                    or parsed.password
                    or parsed.query
                    or parsed.fragment
                ):
                    raise ValueError("Explicit credential-free target and origin are required")
                if parsed.scheme != "https" and parsed.hostname not in {
                    "127.0.0.1",
                    "localhost",
                    "::1",
                }:
                    raise ValueError("Remote targets require HTTPS")
            if not all(
                (
                    self.provider,
                    self.model,
                    self.synthetic_environment_record,
                    self.provider_budget_record,
                    self.versions,
                    self.runtime,
                )
            ):
                raise ValueError(
                    "Target/provider approval, budget enforcement and version records required"
                )


class Budget:
    """Atomic within one asyncio event loop; reserve before dispatch, never refund."""

    def __init__(self, config: Config):
        self.config = config
        self.requests = 0
        self.reserved_aud = Decimal(0)
        self.stopped = False
        self.actor_ids = set()

    def reserve_loop(self):
        ceiling = Decimal(self.config.loop_cost_ceiling_aud)
        if self.stopped or self.reserved_aud + ceiling > Decimal(self.config.max_cost_aud):
            raise StopRun("cost_budget")
        self.reserved_aud += ceiling

    def request(self):
        if self.stopped:
            raise StopRun("cancelled")
        if self.requests >= self.config.max_requests:
            raise StopRun("request_budget")
        self.requests += 1


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def p95(values):
    """Nearest-rank percentile, including elapsed failed/timed-out operations."""
    return sorted(values)[math.ceil(0.95 * len(values)) - 1] if values else None


def summarise(manifest, loops, samples):
    scenarios = []
    for users in manifest["config"]["users"]:
        selected = [r for r in loops if r["users"] == users and r["phase"] == "measurement"]
        measured = [s for s in samples if s["users"] == users and s["phase"] == "measurement"]
        metrics = {}
        for name, threshold in (
            ("ordinary", 2),
            ("progress", 3),
            ("feedback", 10),
            ("assessed_feedback", None),
        ):
            group = [s for s in measured if s["category"] == name]
            percentile = p95([s["seconds"] for s in group])
            metrics[name] = {
                "count": len(group),
                "p95_seconds": percentile,
                "threshold_seconds": threshold,
                "errors": sum(not s["ok"] for s in group),
                "censored": sum(s.get("censored", False) for s in group),
                "within_threshold_observed": percentile <= threshold
                if percentile is not None
                and threshold is not None
                and all(s["ok"] and not s.get("censored") for s in group)
                else None,
            }
        http = [s for s in measured if s["kind"] == "http"]
        errors = sum(not s["ok"] for s in http)
        loop_errors = sum(r["status"] not in {"complete", "awaiting_human"} for r in selected)
        scenarios.append(
            {
                "users": users,
                "report_mode": "50-user" if users == 50 else "scaling",
                "metrics": metrics,
                "loop_count": len(selected),
                "complete_loops": sum(r["status"] == "complete" for r in selected),
                "learning_loops": sum(r.get("learning_complete", False) for r in selected),
                "loop_outcomes": dict(Counter(r["status"] for r in selected)),
                "http_attempts": len(http),
                "http_errors": errors,
                "http_error_rate": errors / len(http) if http else None,
                "http_errors_within_threshold": errors / len(http) < 0.01 if http else None,
                "loop_error_rate": loop_errors / len(selected) if selected else None,
                "error_threshold_exclusive": 0.01,
            }
        )
    lookup = {r["users"]: r for r in scenarios}
    base = lookup.get(5, {}).get("metrics", {}).get("ordinary", {}).get("p95_seconds")
    scale = {
        "baseline_users": 5,
        "maximum_growth": 0.25,
        "status": "observed" if base and 100 in lookup else "pending_5_and_100",
        "comparisons": [],
    }
    if base:
        for r in scenarios:
            value = r["metrics"]["ordinary"]["p95_seconds"]
            scale["comparisons"].append(
                {
                    "users": r["users"],
                    "growth": value / base - 1 if value is not None else None,
                    "within_threshold_observed": value <= base * 1.25
                    if value is not None
                    else None,
                }
            )
    return {
        "schema": "task38.report.v1",
        "manifest": manifest,
        "scenarios": scenarios,
        "scaling": scale,
        "loops": loops,
        "samples": samples,
        "evidence_class": "SYNTHETIC DRY RUN"
        if manifest["config"]["fake"]
        else "synthetic environment observation",
        "production_compliance": "not_established",
        "external_provider_execution": "pending_usage_reconciliation",
        "assessment_evaluation_target": "pending separate approved target; human wait is separate",
        "cost": {
            "status": "unknown_missing_usage",
            "external_aud_per_complete_loop": None,
            "threshold_aud": "0.10",
        },
        "definitions": {
            "ordinary": "Dashboard/task/draft reads only; auth, simulation, mutations and polling separate",
            "progress": "Authenticated progress API response, excluding browser render",
            "feedback": "Formative next-activity submission dispatch through terminal receipt, including queue/worker wait; provider use must be confirmed by usage",
            "assessed_feedback": "Two locally generated assessed feedback operations; retained separately from external feedback evidence",
            "p95": "Nearest rank over all started operations including errors; deadlines are right-censored lower bounds",
            "complete_loop": "Supported prediction/simulation, unaided transfer, assessed feedback, revision, model/suggestion, choice, formative next-activity feedback and human-confirmed result",
            "learning_loop": "Same journey before human confirmation; not the formal complete-loop cost denominator",
            "cost": "All measured-loop external spend including failed/incomplete loops divided by complete measured loops; warm-up separate",
            "load": "Closed-loop VUs; one session per fresh synthetic learner-loop; no think time; rounds separated by phase barriers",
        },
    }


async def campaign(config, roster, adapter_factory, run_id, clock=time.perf_counter):
    config.validate()
    required = sum(config.users) * (config.warmup_rounds + config.measurement_rounds)
    if (
        len(roster) < required
        or len({r["student_email"].strip().casefold() for r in roster[:required]}) != required
    ):
        raise ValueError(
            "Supply one distinct synthetic learner for every warm-up and measured loop"
        )
    budget, loops, samples = Budget(config), [], []
    manifest = {
        "schema": "task38.manifest.v1",
        "run_id": run_id,
        "config": asdict(config),
        "roster_sha256": digest(roster),
        "planned_loops": required,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "periods": [],
    }
    index = 0
    cancelled = False
    for users in config.users:
        for phase, rounds in (
            ("warmup", config.warmup_rounds),
            ("measurement", config.measurement_rounds),
        ):
            phase_start = clock()
            active = peak = 0

            async def worker(worker_index):
                nonlocal index, active, peak
                for round_index in range(rounds):
                    row, index = roster[index], index + 1
                    key = f"{run_id}:{users}:{phase}:{worker_index}:{round_index}"
                    result = {
                        "loop_id": key,
                        "users": users,
                        "phase": phase,
                        "status": "not_started",
                        "learning_complete": False,
                        "workflow_ids": [],
                        "submission_ids": [],
                    }
                    loops.append(result)
                    start = clock()
                    adapter = None
                    try:
                        if clock() - phase_start >= config.phase_timeout:
                            raise StopRun("phase_deadline")
                        budget.reserve_loop()
                        adapter = adapter_factory(config, budget, samples, result, clock)
                        active += 1
                        peak = max(peak, active)
                        async with asyncio.timeout(
                            max(0.001, config.phase_timeout - (clock() - phase_start))
                        ):
                            await adapter.run(row)
                    except StopRun as error:
                        result["status"] = str(error)
                    except TimeoutError:
                        result["status"] = "phase_deadline"
                    except asyncio.CancelledError:
                        result["status"] = "cancelled"
                        raise
                    except Exception:
                        result["status"] = "adapter_error"
                    finally:
                        result["seconds"] = clock() - start
                        if adapter is not None:
                            active -= 1
                            await adapter.close()

            tasks = [asyncio.create_task(worker(n)) for n in range(users)]
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                budget.stopped = True
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                cancelled = True
            manifest["periods"].append(
                {
                    "users": users,
                    "phase": phase,
                    "rounds": rounds,
                    "wall_seconds": clock() - phase_start,
                    "peak_active_loops": peak,
                }
            )
            if cancelled:
                break
        if cancelled:
            break
    manifest.update(
        requests=budget.requests,
        reserved_cost_ceiling_aud=str(budget.reserved_aud),
        cancelled=cancelled,
        unstarted_loops=required - len(loops),
    )
    return summarise(manifest, loops, samples)
