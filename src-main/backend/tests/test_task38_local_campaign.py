"""Unpaid launcher boundaries; transport fixtures do not establish capacity."""

import asyncio
from dataclasses import replace

import pytest

from scripts.task38_benchmark.core import Budget, Config, StopRun, campaign
from scripts.task38_benchmark.fake import factory, roster
from scripts.task38_benchmark.local import BACKEND, local_environment, run_local


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
