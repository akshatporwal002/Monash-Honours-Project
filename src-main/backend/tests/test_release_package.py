"""Focused release CLI contracts; Docker execution remains an external check."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "ready",
    [
        {"status": "not_ready", "checks": {"worker": "not_ready"}},
        {"status": "ready", "checks": {}},
        {"status": "ready", "checks": []},
        [],
        None,
    ],
)
def test_smoke_rejects_incomplete_readiness_even_after_liveness_passes(monkeypatch, ready):
    smoke = load("smoke_check")
    responses = iter(
        [
            (b"<title>QuantumLearn</title>", "text/html"),
            (b'{"status":"ok"}', "application/json"),
            (json.dumps(ready).encode(), "application/json"),
        ]
    )
    monkeypatch.setattr(smoke, "fetch", lambda *args: next(responses))
    with pytest.raises(smoke.SmokeCheckError, match="required readiness"):
        smoke.check("http://localhost:8080", 1)


def test_smoke_accepts_all_checks_and_rejects_a_stale_worker(monkeypatch):
    smoke = load("smoke_check")
    checks = dict.fromkeys(smoke.REQUIRED_CHECKS, "ready")

    def fetch(base, path, timeout):
        if path == "/":
            return b"<title>QuantumLearn</title>", "text/html"
        data = (
            {"status": "ok"}
            if path.endswith("health")
            else {
                "status": "ready",
                "checks": checks,
            }
        )
        return json.dumps(data).encode(), "application/json"

    monkeypatch.setattr(smoke, "fetch", fetch)
    smoke.check("http://localhost:8080", 1)
    checks["worker"] = "not_ready"
    with pytest.raises(smoke.SmokeCheckError):
        smoke.check("http://localhost:8080", 1)


def test_docker_runtime_includes_standalone_backup_cli(tmp_path):
    backend = ROOT / "backend"
    assert "COPY scripts ./scripts" in (backend / "Dockerfile").read_text()
    shutil.copytree(
        backend / "scripts", tmp_path / "scripts", ignore=shutil.ignore_patterns("__pycache__")
    )
    environment = {**os.environ, "PYTHONPATH": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, "-m", "scripts.learning_backup", "--help"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "create" in result.stdout and "restore" in result.stdout


def test_backup_refuses_live_writers_before_running_a_container(tmp_path, monkeypatch):
    operations = load("release_operations")
    env_file = tmp_path / "deployment.env"
    env_file.touch()
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "backend\nworker\n")

    monkeypatch.setattr(operations, "run", run)
    with pytest.raises(ValueError, match="Stop backend and worker"):
        operations.backup(env_file, True, tmp_path)
    assert len(commands) == 1
    assert str(ROOT / "deploy" / "compose.hosted.yaml") in commands[0]


def test_backup_uses_compose_volume_flag_and_disables_startup_mutations(tmp_path, monkeypatch):
    operations = load("release_operations")
    env_file = tmp_path / "deployment.env"
    env_file.touch()
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "")

    monkeypatch.setattr(operations, "run", run)
    operations.backup(env_file, False, tmp_path)
    command = commands[-1]
    assert "--volume" in command and "--mount" not in command
    assert f"{tmp_path.resolve()}:/backups" in command
    assert "MIGRATE_ON_START=false" in command and "BOOTSTRAP_DEMO=false" in command
    assert "settings.database_url" in command[-1] and "settings.rag_upload_dir" in command[-1]
    compile(command[-1], "container-backup-command", "exec")


@pytest.mark.parametrize("existing,head", [(True, "head"), (False, "wrong"), (False, "head")])
def test_rollback_requires_fresh_volume_and_matching_image(tmp_path, monkeypatch, existing, head):
    operations = load("release_operations")
    (tmp_path / "manifest.json").write_text(json.dumps({"database": {"migration_head": "head"}}))
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        output = "candidate\n" if existing else ""
        if "volume" not in command:
            output = head
        return subprocess.CompletedProcess(command, 0, output)

    monkeypatch.setattr(operations, "run", run)
    if existing or head != "head":
        with pytest.raises(ValueError, match="already exists|does not match"):
            operations.restore(tmp_path, "quantumlearn-backend:retained", "candidate")
        assert len(commands) == (1 if existing else 2)
    else:
        operations.restore(tmp_path, "quantumlearn-backend:retained", "candidate")
        command = commands[-1]
        assert "scripts.learning_backup" in command and "restore" in command
        assert "type=volume,src=candidate,dst=/data" in command
        assert "--read-only" in command and "none" in command
        assert "up" not in command and "upgrade" not in command
