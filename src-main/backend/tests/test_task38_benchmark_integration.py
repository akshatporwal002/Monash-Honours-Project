"""One synthetic learner over real loopback API and worker; no campaign approvals."""

import asyncio
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

import httpx

from scripts.task38_benchmark.adapter import LearningLoop
from scripts.task38_benchmark.core import Budget, Config
from scripts.task38_benchmark.usage import cost_report, extract_snapshot

BACKEND = Path(__file__).resolve().parents[1]


def test_preparer_refuses_existing_directory_without_changing_it(tmp_path):
    scratch = tmp_path / "existing"
    scratch.mkdir()
    sentinel = scratch / "keep.txt"
    sentinel.write_text("preserve existing contents", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.task38_benchmark.prepare",
            "--directory",
            str(scratch),
            "--learners",
            "1",
            "--ack-synthetic-only",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(BACKEND), "LLM_API_KEY": ""},
        capture_output=True,
        timeout=10,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert result.returncode != 0
    assert b"FileExistsError" in result.stderr
    assert list(scratch.iterdir()) == [sentinel]
    assert sentinel.read_text(encoding="utf-8") == "preserve existing contents"


def test_preparer_and_real_local_learning_loop(tmp_path):
    port = 4690
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))
    origin = f"http://127.0.0.1:{port}"
    scratch = tmp_path / "synthetic"
    environment = {
        **os.environ,
        "PYTHONPATH": str(BACKEND),
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
        "LEARNING_EVENT_PSEUDONYM_SECRET": "task38-local-synthetic-pseudonym-secret-32-bytes",
        "SESSION_SECRET_KEY": "task38-local-synthetic-session-secret-32-bytes",
    }
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (tmp_path / "prepare.log").open("w", encoding="utf-8") as log:
        prepared = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.task38_benchmark.prepare",
                "--directory",
                str(scratch),
                "--learners",
                "1",
                "--ack-synthetic-only",
            ],
            cwd=tmp_path,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=60,
            creationflags=flags,
        )
    assert prepared.returncode == 0, "Preparer failed; inspect isolated prepare.log"
    rows = json.loads((scratch / "roster.json").read_text(encoding="utf-8"))
    assert len(rows) == 1
    database = scratch / "task38-synthetic.sqlite"
    environment.update(
        DATABASE_URL="sqlite:///" + database.as_posix(), RAG_UPLOAD_DIR=str(scratch / "uploads")
    )
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT count(*) FROM submission_attempts").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM assessment_decisions").fetchone()[0] == 0
    processes, logs = [], []
    try:
        for role, command in (
            ("worker", ["-c", "from app.worker import main; raise SystemExit(main())"]),
            (
                "api",
                [
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--no-access-log",
                ],
            ),
        ):
            log = (tmp_path / (role + ".log")).open("w", encoding="utf-8")
            logs.append(log)
            processes.append(
                subprocess.Popen(
                    [sys.executable, *command],
                    cwd=scratch,
                    env=environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=flags,
                )
            )
        deadline = time.monotonic() + 30
        with httpx.Client(trust_env=False, timeout=1) as client:
            while time.monotonic() < deadline:
                assert all(p.poll() is None for p in processes), "Local API/worker exited"
                try:
                    ready = client.get(origin + "/api/v1/ready")
                    checks = ready.json().get("checks", {})
                    if (
                        ready.status_code == 200
                        and checks
                        and all(v == "ready" for v in checks.values())
                    ):
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
            else:
                raise AssertionError("Local API and worker did not become ready")
        # Direct adapter regression, deliberately outside the approval-gated campaign.
        config = Config(
            fake=False,
            users=(1,),
            warmup_rounds=0,
            target=origin + "/api/v1",
            origin=origin,
            provider="local",
            model="local-template",
            max_requests=200,
            worker_timeout=30,
        )
        result = {
            "loop_id": "task38-local-integration",
            "users": 1,
            "phase": "integration",
            "status": "not_started",
            "learning_complete": False,
            "workflow_ids": [],
            "submission_ids": [],
        }
        samples = []

        async def exercise():
            adapter = LearningLoop(config, Budget(config), samples, result, time.perf_counter)
            try:
                await adapter.run(rows[0])
            finally:
                await adapter.close()

        try:
            asyncio.run(exercise())
        finally:
            (tmp_path / "adapter-result.json").write_text(
                json.dumps(
                    {
                        "evidence_class": "local integration only; no load/cost/approval evidence",
                        "readiness": {"http_status": ready.status_code, "body": ready.json()},
                        "result": result,
                        "samples": samples,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        assert result["learning_complete"] is True
        assert result["status"] == "awaiting_human"
        assert result["formal_result"] is None
        assert len(result["submission_ids"]) == 3
        assert len(set(result["workflow_ids"])) == 3
        assert all(s["ok"] for s in samples)
        with sqlite3.connect(database) as db:
            assert db.execute("SELECT count(*) FROM assessment_decisions").fetchone()[0] == 0
            assert db.execute("SELECT count(*) FROM worker_heartbeats").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM learner_model_snapshots").fetchone()[0] >= 2
            assert db.execute("SELECT count(*) FROM assessment_attempts").fetchone()[0] == 2
            next_episode, next_form, next_work = db.execute(
                "SELECT episode, task_form_version_id, assessment_work_start_id "
                "FROM submission_attempts WHERE id = ?",
                (result["submission_ids"][2],),
            ).fetchone()
            assert (
                json.loads(next_episode)["supported"]["explanation"]
                == rows[0]["next_activity_answer"]
            )
            assert next_form is None and next_work is None
            providers = db.execute(
                "SELECT DISTINCT provider FROM feedback_records UNION SELECT DISTINCT provider FROM judge_evaluations"
            ).fetchall()
            assert providers and all(p[0] == "local" for p in providers)
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=15)
        for log in logs:
            log.close()
    # Back up only the isolated synthetic database after both owned processes stop.
    snapshot = tmp_path / "usage-snapshot.sqlite"
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as source:
        with sqlite3.connect(snapshot) as destination:
            source.backup(destination)
    report = {
        "manifest": {"run_id": result["loop_id"], "config": asdict(config)},
        "evidence_class": "LOCAL INTEGRATION ONLY",
        "loops": [result],
        "scenarios": [{"users": 1}],
    }
    ledger = extract_snapshot(report, snapshot)
    assert len(ledger["records"]) >= 6  # Generation and judge for each submission.
    assert all(row["provider"] == "local" for row in ledger["records"])
    assert {row["workflow_run_id"] for row in ledger["records"]} == set(result["workflow_ids"])
    costs = cost_report(report, ledger)
    assert costs["status"] == "unknown_or_incomplete"
    assert costs["provider_model_observation"]["recorded_external"] == []
    assert costs["scenarios"][0]["complete_loop_denominator"] == 0
    assert costs["scenarios"][0]["external_aud_per_complete_loop"] is None
    (tmp_path / "usage-result.json").write_text(json.dumps(costs, indent=2), encoding="utf-8")
