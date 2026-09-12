"""Bounded unpaid loopback campaign against a new synthetic database only."""

import argparse
import asyncio
import json
import os
import platform
import secrets
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path
from uuid import uuid4

import httpx

from .__main__ import provenance
from .adapter import LearningLoop
from .core import Config, campaign
from .usage import LOCAL, cost_report, extract_snapshot

BACKEND = Path(__file__).resolve().parents[2]


def local_environment(directory, origin):
    """Explicit isolation overrides; never inherit a working provider credential."""
    return {
        **os.environ,
        "PYTHONPATH": os.pathsep.join((str(BACKEND), str(BACKEND / "tests"))),
        "DATABASE_URL": "sqlite:///" + (directory / "fixture/task38-synthetic.sqlite").as_posix(),
        "RAG_UPLOAD_DIR": str(directory / "fixture/uploads"),
        "LLM_API_KEY": "",
        "LLM_API_BASE_URL": "https://127.0.0.1:1",
        "LLM_PROVIDER": "local",
        "LLM_MODEL": "local-template",
        "RESEARCH_ENABLED": "false",
        "APP_ENV": "development",
        "API_PREFIX": "/api/v1",
        "FRONTEND_ORIGIN": origin,
        "CORS_ALLOWED_ORIGINS": origin,
        "SESSION_COOKIE_SECURE": "false",
        "CSRF_ENABLED": "true",
        "RATE_LIMIT_ENABLED": "true",
        "WORKER_ADAPTER_FACTORY": "app.worker:build_offline_worker_adapters",
        "WORKER_POLL_SECONDS": "0.1",
        "WORKER_HEARTBEAT_SECONDS": "1",
        "SESSION_SECRET_KEY": secrets.token_hex(32),
        "LEARNING_EVENT_PSEUDONYM_SECRET": secrets.token_hex(32),
    }


def stop_owned(processes, logs):
    failures = []
    for process in reversed(processes):
        try:
            if process.poll() is None:
                if os.name == "nt":
                    stopped = subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                        timeout=10,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    if stopped.returncode and process.poll() is None:
                        raise RuntimeError("Owned Windows process tree did not stop")
                else:
                    os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    process.kill()
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        except Exception as error:
            failures.append(type(error).__name__)
    for log in logs:
        log.close()
    if failures:
        raise RuntimeError("Owned local process cleanup failed")


def serve(role, port):
    """Synthetic scanner is scoped to this disposable fixture process only."""
    from support.material_scanning import synthetic_scanning_scope

    with synthetic_scanning_scope():
        if role == "api":
            import uvicorn

            uvicorn.run("app.main:app", host="127.0.0.1", port=int(port), access_log=False)
        else:
            from app.worker import main

            main()


def _ready(origin, processes):
    deadline = time.monotonic() + 60
    with httpx.Client(trust_env=False, timeout=2) as client:
        while time.monotonic() < deadline:
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("Owned local API or worker exited; inspect private logs")
            try:
                response = client.get(origin + "/api/v1/ready")
                body = response.json()
                checks = body.get("checks", {})
                if (
                    response.status_code == 200
                    and checks
                    and all(value == "ready" for value in checks.values())
                ):
                    return {"http_status": 200, "body": body}
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(0.1)
    raise RuntimeError("Local readiness deadline exceeded; inspect private logs")


def _drain(database):
    deadline = time.monotonic() + 60
    remaining = None
    while time.monotonic() < deadline:
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
            remaining = db.execute(
                "SELECT count(*) FROM workflow_runs WHERE current_stage NOT IN ('completed','failed') OR next_retry_at IS NOT NULL"
            ).fetchone()[0]
        if remaining == 0:
            break
        time.sleep(0.5)
    return {"remaining_feedback_workflows": remaining, "drained": remaining == 0}


def _snapshot_stopped_fixture(database, snapshot):
    """Export the launcher-owned fixture after all its processes have stopped."""
    # Forced process shutdown can leave a hot rollback journal. SQLite needs a
    # writable connection to recover it before backup; mode=rw requires the
    # existing owned fixture and never creates a missing source database.
    with closing(sqlite3.connect(database.as_uri() + "?mode=rw", uri=True)) as source_db:
        with closing(sqlite3.connect(snapshot)) as destination:
            source_db.backup(destination)
        counts = {
            table: source_db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in (
                "submission_attempts",
                "assessment_attempts",
                "assessment_decisions",
                "workflow_runs",
                "learner_model_snapshots",
                "provider_usage",
            )
        }
    return counts


def run_local(directory, *, users=50, warmup_rounds=1, measurement_rounds=1, port=0):
    if not 5 <= users <= 100 or not 0 <= warmup_rounds <= 2 or not 1 <= measurement_rounds <= 3:
        raise ValueError("Local campaigns allow 5–100 users, 0–2 warmup and 1–3 measured rounds")
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))
        port = probe.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    environment = local_environment(directory, origin)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    learners = users * (warmup_rounds + measurement_rounds)
    with (directory / "prepare.log").open("w", encoding="utf-8") as log:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.task38_benchmark.prepare",
                "--directory",
                str(directory / "fixture"),
                "--learners",
                str(learners),
                "--ack-synthetic-only",
            ],
            cwd=directory,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=max(90, learners * 3),
            check=True,
            creationflags=flags,
        )
    source = provenance()
    config = Config(
        fake=False,
        local_only=True,
        users=(users,),
        warmup_rounds=warmup_rounds,
        measurement_rounds=measurement_rounds,
        target=origin + "/api/v1",
        origin=origin,
        provider="local",
        model="local-template",
        max_requests=learners * 150,
        max_cost_aud=None,
        loop_cost_ceiling_aud=None,
        request_timeout=30,
        poll_seconds=1,
        synthetic_environment_record="owned-new-loopback-synthetic-database",
        versions={"profile": "task38-single-qubit-v1-synthetic-only", "source": source},
        runtime={
            "external_provider_disabled": True,
            "provider_endpoint": "unreachable-loopback",
            "database_engine": "sqlite",
            "api_workers": 1,
            "worker_processes": 1,
            "rate_limit_enabled": True,
            "csrf_enabled": True,
            "research_enabled": False,
            "material_scanner": "synthetic-test-only; no malware effectiveness evidence",
            "worker_poll_seconds": 0.1,
            "worker_heartbeat_seconds": 1,
            "host": {
                "os": platform.system(),
                "architecture": platform.machine(),
                "logical_cpus": os.cpu_count(),
                "python": platform.python_version(),
            },
        },
    )
    config.validate()
    roster = json.loads((directory / "fixture/roster.json").read_text(encoding="utf-8"))
    database = directory / "fixture/task38-synthetic.sqlite"
    processes, logs = [], []
    result = None
    try:
        for role in ("api", "worker"):
            arguments = [
                "-c",
                "import sys; from scripts.task38_benchmark.local import serve; serve(sys.argv[1], sys.argv[2])",
                role,
                str(port),
            ]
            log = (directory / f"{role}.log").open("w", encoding="utf-8")
            logs.append(log)
            processes.append(
                subprocess.Popen(
                    [sys.executable, *arguments],
                    cwd=directory,
                    env=environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=flags,
                    start_new_session=os.name != "nt",
                )
            )
        readiness = _ready(origin, processes)
        result = asyncio.run(campaign(config, roster, LearningLoop, str(uuid4())))
        result["manifest"]["source"] = source
        result["readiness"] = readiness
        # Preserve observations before drain/cleanup so failures remain reviewable.
        (directory / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        result["drain"] = _drain(database)
    finally:
        stop_owned(processes, logs)
    # Windows may retain closed connections in TIME_WAIT after all owned
    # processes exit. Verify the listener closed without requiring an immediate
    # bind that would confuse that kernel cleanup with a running server.
    deadline = time.monotonic() + 5
    while True:
        with socket.socket() as probe:
            probe.settimeout(0.2)
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                break
        if time.monotonic() >= deadline:
            raise RuntimeError("Local listener remains after owned process cleanup")
        time.sleep(0.1)
    result["cleanup"] = {"owned_processes_stopped": True, "listener_closed": True}
    snapshot = directory / "usage-snapshot.sqlite"
    counts = _snapshot_stopped_fixture(database, snapshot)
    ledger = extract_snapshot(result, snapshot)
    if counts["provider_usage"] or any(row["provider"] not in LOCAL for row in ledger["records"]):
        raise RuntimeError("Unexpected external usage in local campaign; inspect isolated ledger")
    result["database_counts"] = counts
    result["cost"] = cost_report(result, ledger)
    (directory / "usage.json").write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    (directory / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    parser.add_argument("--users", type=int, default=50)
    parser.add_argument("--warmup-rounds", type=int, default=1)
    parser.add_argument("--measurement-rounds", type=int, default=1)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--ack-synthetic-only", action="store_true")
    args = parser.parse_args()
    if not args.ack_synthetic_only:
        parser.error("Explicit synthetic-only acknowledgement required")
    result = run_local(
        args.directory,
        users=args.users,
        warmup_rounds=args.warmup_rounds,
        measurement_rounds=args.measurement_rounds,
        port=args.port,
    )
    print(
        json.dumps(
            {
                "evidence_class": result["evidence_class"],
                "scenarios": result["scenarios"],
                "cleanup": result["cleanup"],
                "report": str(Path(args.directory).resolve() / "report.json"),
            },
            indent=2,
        )
    )
    return int(
        any(loop["status"] not in {"complete", "awaiting_human"} for loop in result["loops"])
    )


if __name__ == "__main__":
    raise SystemExit(main())
