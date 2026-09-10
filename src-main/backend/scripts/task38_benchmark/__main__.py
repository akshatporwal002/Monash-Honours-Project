"""python -m scripts.task38_benchmark --help (run from src-main/backend)."""

import argparse
import asyncio
import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from .adapter import LearningLoop, probe_settings
from .core import Budget, Config, campaign, digest
from .fake import factory, roster
from .usage import cost_report, extract_snapshot


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def provenance():
    root = Path(__file__).resolve().parents[4]

    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

    return {
        "commit": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "dirty": bool(git("status", "--porcelain")),
        "harness_sha256": digest(
            {
                p.name: p.read_text(encoding="utf-8")
                for p in sorted(Path(__file__).parent.glob("*.py"))
            }
        ),
    }


def read_config(args):
    if not args.ack_synthetic_target or not args.ack_provider_budget:
        raise ValueError(
            "Real mode requires explicit synthetic-target and provider-budget acknowledgements"
        )
    data = load(args.config)
    if (
        not {
            "users",
            "max_requests",
            "max_cost_aud",
            "loop_cost_ceiling_aud",
            "target",
            "origin",
            "provider",
            "model",
        }
        <= data.keys()
    ):
        raise ValueError("Scenario, target, provider and request/cost budgets must be explicit")
    data["fake"] = False
    data["users"] = tuple(data["users"])
    config = Config(**data)
    config.validate()
    # Only known, non-secret runtime values may enter a persisted manifest.
    allowed = {
        "provider_timeout_seconds",
        "max_infrastructure_attempts",
        "worker_adapter_factory",
        "worker_poll_seconds",
        "worker_heartbeat_seconds",
        "worker_stale_seconds",
        "database_engine",
        "database_isolation",
        "api_workers",
        "worker_processes",
        "rate_limit_enabled",
        "research_enabled",
        "production_adapters_ready",
        "provider_budget_enforcement",
        "deployment_revision",
        "host_specification",
        "llm_input_cost_per_million",
        "llm_output_cost_per_million",
    }
    if set(config.runtime) - allowed:
        raise ValueError("Runtime manifest contains unsupported fields; omit secrets")
    required_versions = {"source", "prompt", "rule", "model", "deployment", "fixture"}
    if not required_versions <= config.versions.keys():
        raise ValueError("Record source/prompt/rule/model/deployment/fixture versions")
    if not all(config.versions[key] for key in required_versions):
        raise ValueError("Version provenance must be filled before a real run")
    return config


async def settings_command(config, credentials):
    if config.max_requests < 32:
        raise ValueError(
            "Settings probe requires a budget of at least 32 requests, including restoration"
        )
    from dataclasses import replace

    budget = Budget(replace(config, max_requests=config.max_requests - 2))
    samples = []
    adapters = []
    receipt = {"schema": "task38.settings.v1", "config": asdict(config), "status": "started"}
    try:
        for role in ("admin", "learner"):
            result = {"loop_id": "settings-" + role, "phase": "preflight", "users": 1}
            adapter = LearningLoop(config, budget, samples, result, __import__("time").perf_counter)
            adapters.append(adapter)
            await adapter.request("POST", "auth/login", credentials[role])
        receipt["checks"] = await probe_settings(*adapters, credentials["desired"])
        receipt["status"] = "completed"
    except asyncio.CancelledError:
        receipt["status"] = "cancelled"
        receipt["operator_action"] = "Verify restored settings before another run."
    except Exception as error:
        from .core import StopRun

        receipt["status"] = str(error) if isinstance(error, StopRun) else "settings_probe_error"
        receipt["operator_action"] = "Check and restore original settings before any load run."
    finally:
        for adapter in adapters:
            await adapter.close()
        if adapters:
            receipt["original_settings"] = adapters[0].result.get("settings_original")
    receipt.update(samples=samples, requests=budget.requests)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fake = commands.add_parser("fake", help="Tiny deterministic transport smoke; no network")
    fake.add_argument("--output", required=True)
    fake.add_argument("--run-id", default=None)
    for name in ("run", "settings"):
        command = commands.add_parser(name)
        command.add_argument("--config", required=True)
        command.add_argument("--output", required=True)
        command.add_argument("--ack-synthetic-target", action="store_true")
        command.add_argument("--ack-provider-budget", action="store_true")
        command.add_argument("--roster" if name == "run" else "--credentials", required=True)
    extract = commands.add_parser(
        "extract-usage", help="Read a separately prepared synthetic SQLite snapshot"
    )
    extract.add_argument("--report", required=True)
    extract.add_argument("--snapshot", required=True)
    extract.add_argument("--ack-synthetic-snapshot", action="store_true")
    extract.add_argument("--output", required=True)
    report = commands.add_parser(
        "report", help="Attach operator-reconciled usage and billing receipts"
    )
    report.add_argument("--report", required=True)
    report.add_argument("--usage", required=True)
    report.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        parser.error("Output must be a new file")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        if args.command == "fake":
            config = Config(users=(2,), max_requests=300, max_cost_aud="1")
            result = asyncio.run(campaign(config, roster(4), factory, args.run_id or str(uuid4())))
            result["manifest"]["source"] = provenance()
        elif args.command == "run":
            config = read_config(args)
            source = provenance()
            result = asyncio.run(campaign(config, load(args.roster), LearningLoop, str(uuid4())))
            result["manifest"]["source"] = source
        elif args.command == "settings":
            result = asyncio.run(settings_command(read_config(args), load(args.credentials)))
        elif args.command == "extract-usage":
            if not args.ack_synthetic_snapshot:
                raise ValueError("Explicit synthetic snapshot acknowledgement required")
            result = extract_snapshot(load(args.report), args.snapshot)
        else:
            result = load(args.report)
            result["cost"] = cost_report(result, load(args.usage))
        save(output, result)
    except (ValueError, KeyError, TypeError) as error:
        # Do not echo malformed credentials, response payloads or config values.
        parser.error("Invalid inputs: " + type(error).__name__)
    print(f"Saved {output.resolve()}")
    if args.command in {"fake", "run"}:
        return int(
            result["manifest"]["cancelled"]
            or any(r["status"] not in {"complete", "awaiting_human"} for r in result["loops"])
        )
    if args.command == "settings":
        return int(result["status"] != "completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
