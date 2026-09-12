"""Unpaid launcher boundaries; transport fixtures do not establish capacity."""

import asyncio
import sqlite3
import subprocess
import sys
from contextlib import closing
from dataclasses import replace

import pytest

from scripts.task38_benchmark.core import Budget, Config, StopRun, campaign
from scripts.task38_benchmark.fake import factory, roster
from scripts.task38_benchmark.local import BACKEND, local_environment, run_local


def test_stopped_fixture_export_recovers_hot_journal_without_losing_committed_data(tmp_path):
    from scripts.task38_benchmark.local import _snapshot_stopped_fixture

    database = tmp_path / "owned-synthetic.sqlite"
    snapshot = tmp_path / "snapshot.sqlite"
    tables = (
        "submission_attempts",
        "assessment_attempts",
        "assessment_decisions",
        "workflow_runs",
        "learner_model_snapshots",
        "provider_usage",
    )
    with closing(sqlite3.connect(database)) as db:
        for table in tables:
            db.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, payload BLOB)")
            db.executemany(
                f"INSERT INTO {table} VALUES (?, ?)",
                [(index, b"committed" * 512) for index in range(32)],
            )
        db.commit()
    crashed = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import os, sqlite3, sys
db = sqlite3.connect(sys.argv[1])
db.execute('PRAGMA cache_size=5')
db.execute('PRAGMA synchronous=FULL')
db.execute('BEGIN IMMEDIATE')
db.execute("UPDATE workflow_runs SET payload = zeroblob(8192)")
db.execute("INSERT INTO workflow_runs VALUES (1000, zeroblob(8192))")
os._exit(23)
""",
            str(database),
        ],
        timeout=10,
        check=False,
    )
    assert crashed.returncode == 23
    assert database.with_name(database.name + "-journal").stat().st_size > 512
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            db.execute("SELECT count(*) FROM workflow_runs").fetchone()

    assert _snapshot_stopped_fixture(database, snapshot) == dict.fromkeys(tables, 32)
    for path in (database, snapshot):
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            assert db.execute("PRAGMA quick_check").fetchone() == ("ok",)
            assert db.execute("SELECT id, payload FROM workflow_runs ORDER BY id").fetchall() == [
                (index, b"committed" * 512) for index in range(32)
            ]


def test_stopped_fixture_export_does_not_create_missing_source(tmp_path):
    from scripts.task38_benchmark.local import _snapshot_stopped_fixture

    missing = tmp_path / "missing.sqlite"
    with pytest.raises(sqlite3.OperationalError):
        _snapshot_stopped_fixture(missing, tmp_path / "snapshot.sqlite")
    assert not missing.exists()


def local_config(**changes):
    return replace(
        Config(
            fake=False,
            local_only=True,
            users=(5,),
            warmup_rounds=0,
            target="http://127.0.0.1:12345/api/v1",
            origin="http://127.0.0.1:12345",
            provider="local",
            model="local-template",
            max_cost_aud=None,
            loop_cost_ceiling_aud=None,
            synthetic_environment_record="synthetic-test-only",
            versions={"fixture": "synthetic"},
            runtime={"external_provider_disabled": True},
        ),
        **changes,
    )


def test_local_mode_has_request_bounds_without_inventing_money_or_approval():
    config = local_config(max_requests=300)
    result = asyncio.run(campaign(config, roster(5), factory, "fixture-local-mode"))
    assert result["evidence_class"] == "SYNTHETIC LOCAL CAPACITY"
    assert result["external_provider_execution"] == "disabled_local_campaign"
    assert result["manifest"]["reserved_cost_ceiling_aud"] is None
    assert result["manifest"]["config"]["provider_budget_record"] == ""
    assert result["scenarios"][0]["learning_loops"] == 5
    assert result["cost"]["external_aud_per_complete_loop"] is None
    budget = Budget(local_config(max_requests=1))
    budget.request()
    with pytest.raises(StopRun, match="request_budget"):
        budget.request()


@pytest.mark.parametrize(
    "changes",
    [
        {"target": "https://example.invalid/api/v1"},
        {"provider": "openai"},
        {"runtime": {}},
        {"max_cost_aud": "1"},
        {"fake": True},
    ],
)
def test_local_mode_rejects_external_or_monetary_configuration(changes):
    with pytest.raises(ValueError):
        local_config(**changes).validate()


def test_launcher_overrides_inherited_provider_credentials_and_imports(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "synthetic-do-not-inherit")
    monkeypatch.setenv("PYTHONPATH", "synthetic-wrong-checkout")
    environment = local_environment(tmp_path, "http://127.0.0.1:12345")
    assert environment["LLM_API_KEY"] == ""
    assert environment["LLM_API_BASE_URL"] == "https://127.0.0.1:1"
    assert environment["LLM_PROVIDER"] == "local"
    assert str(BACKEND) in environment["PYTHONPATH"]
    assert "synthetic-wrong-checkout" not in environment["PYTHONPATH"]
    assert environment["CSRF_ENABLED"] == environment["RATE_LIMIT_ENABLED"] == "true"
    assert environment["RESEARCH_ENABLED"] == "false"


def test_launcher_refuses_existing_directory_before_processes(tmp_path):
    sentinel = tmp_path / "keep"
    sentinel.write_text("preserved")
    with pytest.raises(FileExistsError):
        run_local(tmp_path)
    assert sentinel.read_text() == "preserved"


def test_each_generated_learner_identity_satisfies_mounted_login_contract():
    from app.schemas.authentication import LoginRequest
    from scripts.task38_benchmark.prepare import new_learner_identity

    identities = [new_learner_identity() for _ in range(5)]
    assert len({email for email, _ in identities}) == 5
    for email, password in identities:
        assert LoginRequest(email=email, password=password).email == email
