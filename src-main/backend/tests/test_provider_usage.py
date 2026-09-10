"""Synthetic monetary limits only; no provider or budget approval evidence."""

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.db.session import create_db_engine
from app.models.provider_usage import ProviderBudget, ProviderUsage
from app.services.feedback.contracts import StructuredLlmRequest
from app.services.llm import ResponsesStructuredLlmClient, StructuredModelError
from app.services.provider_usage import (
    MeteringPolicy,
    ProviderBudgetError,
    ProviderUsageMeter,
    configured_meter,
)


def policy(**changes):
    return replace(
        MeteringPolicy(
            "synthetic-budget",
            "AUD",
            "fixture-budget-v1",
            Decimal("0.02"),
            "fixture-prices-v1",
            Decimal("1"),
            Decimal("0"),
            10_000,
            100,
        ),
        **changes,
    )


@pytest.fixture
def meter(tmp_path):
    engine = create_db_engine(f"sqlite:///{(tmp_path / 'usage.db').as_posix()}")
    ProviderBudget.__table__.create(engine)
    ProviderUsage.__table__.create(engine)
    yield ProviderUsageMeter(engine, policy())
    engine.dispose()


def snapshot(meter, key):
    with meter._sessions() as session:
        row = session.get(ProviderUsage, key)
        budget = session.get(ProviderBudget, meter.policy.budget_id)
        return row, budget


def request(key="logical-call"):
    return StructuredLlmRequest(
        "Synthetic", "Synthetic", {"type": "object"}, "synthetic", "v1", metering_key=key
    )


def reply(*, usage=True, malformed=False, status=200):
    body = {
        "id": "synthetic-response",
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": "malformed" if malformed else '{"answer":"ok"}'}
                ],
            }
        ],
    }
    if usage:
        body["usage"] = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
    return httpx.Response(status, json=body)


def client(meter, transport, **kwargs):
    return ResponsesStructuredLlmClient(
        api_key="synthetic",
        model="synthetic-model",
        meter=meter,
        transport=httpx.MockTransport(transport),
        **kwargs,
    )


def test_simultaneous_independent_workers_cannot_overspend(meter):
    url = meter._sessions.kw["bind"].url

    def worker(index):
        engine = create_db_engine(str(url))
        other = ProviderUsageMeter(engine, policy())
        try:
            other.reserve(str(index), {}, {"test": "concurrent"})
            other.dispatch(str(index))
            return True
        except ProviderBudgetError:
            return False
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=8) as workers:
        admitted = list(workers.map(worker, range(12)))
    assert sum(admitted) == 2
    with meter._sessions() as session:
        assert session.scalar(select(func.count()).select_from(ProviderUsage)) == 2
        assert session.get(ProviderBudget, policy().budget_id).exposure_micros == 20_000


def test_duplicate_reservation_and_dispatch_are_idempotent(meter):
    with ThreadPoolExecutor(max_workers=6) as workers:
        list(workers.map(lambda _: meter.reserve("same", {}, {}), range(6)))
    meter.dispatch("same")
    with pytest.raises(ProviderBudgetError, match="claimed"):
        meter.dispatch("same")
    with pytest.raises(ProviderBudgetError, match="conflicts"):
        meter.reserve("same", {"different": True}, {})
    assert snapshot(meter, "same")[1].exposure_micros == 10_000


def test_recovery_releases_only_undispatched_reservations(meter):
    meter.reserve("orphan", {}, {})
    meter.release_undispatched("orphan")
    meter.release_undispatched("orphan")
    assert snapshot(meter, "orphan")[1].exposure_micros == 0
    with pytest.raises(ProviderBudgetError):
        meter.dispatch("orphan")
    meter.reserve("crashed", {}, {})
    meter.dispatch("crashed")
    restarted = ProviderUsageMeter(meter._sessions.kw["bind"], policy())
    with pytest.raises(ProviderBudgetError, match="billing"):
        restarted.release_undispatched("crashed")
    assert snapshot(restarted, "crashed")[1].exposure_micros == 10_000


def test_receipt_reconciliation_is_atomic_idempotent_and_currency_bound(meter):
    meter.reserve("bill", {}, {})
    meter.dispatch("bill")
    meter.observe("bill", input_tokens=100, output_tokens=20)
    row, budget = snapshot(meter, "bill")
    assert row.actual_micros is None and row.estimated_micros == 100
    assert budget.exposure_micros == 10_000
    with pytest.raises(ProviderBudgetError):
        meter.reconcile(
            "bill",
            actual=Decimal("0.003"),
            currency="USD",
            receipt_id="invoice-line",
            actor="synthetic-operator",
        )
    with ThreadPoolExecutor(max_workers=6) as workers:
        list(
            workers.map(
                lambda _: meter.reconcile(
                    "bill",
                    actual=Decimal("0.003"),
                    currency="AUD",
                    receipt_id="invoice-line",
                    actor="synthetic-operator",
                ),
                range(6),
            )
        )
    row, budget = snapshot(meter, "bill")
    assert row.actual_micros == budget.exposure_micros == 3000
    with pytest.raises(ProviderBudgetError, match="Conflicting"):
        meter.reconcile(
            "bill",
            actual=Decimal("0"),
            currency="AUD",
            receipt_id="invoice-line",
            actor="synthetic-operator",
        )
    meter.reserve("other", {}, {})
    meter.dispatch("other")
    with pytest.raises(IntegrityError):
        meter.reconcile(
            "other",
            actual=Decimal("0"),
            currency="AUD",
            receipt_id="invoice-line",
            actor="synthetic-operator",
        )
    assert snapshot(meter, "other")[1].exposure_micros == 13_000


def test_late_usage_after_reconciliation_and_over_budget_actual_are_retained(meter):
    meter.reserve("late", {}, {})
    meter.dispatch("late")
    meter.reconcile(
        "late",
        actual=Decimal("0.03"),
        currency="AUD",
        receipt_id="late-bill",
        actor="synthetic-operator",
    )
    meter.observe("late", input_tokens=123, output_tokens=5)
    row, budget = snapshot(meter, "late")
    assert row.state == "RECONCILED" and row.input_tokens == 123
    assert budget.exposure_micros == 30_000
    with pytest.raises(ProviderBudgetError, match="exhausted"):
        meter.reserve("new", {}, {})


def test_policy_change_does_not_reset_existing_budget(meter):
    meter.reserve("first", {}, {})
    changed = ProviderUsageMeter(meter._sessions.kw["bind"], policy(limit=Decimal("100")))
    with pytest.raises(ProviderBudgetError, match="changed policy"):
        changed.reserve("second", {}, {})
    assert snapshot(meter, "first")[1].exposure_micros == 10_000


def test_success_preserves_actual_missingness_and_provenance(meter):
    calls = []

    def transport(req):
        calls.append(req)
        assert json.loads(req.content)["max_output_tokens"] == 100
        row, budget = snapshot(meter, "logical-call:1")
        assert row.state == "DISPATCHED" and budget.exposure_micros == 10_000
        return reply()

    response = asyncio.run(client(meter, transport).generate_structured(request()))
    assert response.token_usage.input_tokens == 100
    row, _ = snapshot(meter, "logical-call:1")
    assert row.actual_micros is None and row.estimated_micros == 100
    assert row.provider_response_id == "synthetic-response"
    assert row.provenance["pricing_version"] == "fixture-prices-v1"
    assert row.provenance["prompt_version"] == "v1"
    assert row.provenance["model"] == "synthetic-model"
    with pytest.raises(StructuredModelError):
        asyncio.run(client(meter, transport).generate_structured(request()))
    assert len(calls) == 1


@pytest.mark.parametrize("failure", ["malformed", "usage", "http", "read", "write", "body"])
def test_failures_preserve_usage_or_unknown_exposure_without_replay(meter, failure):
    calls = []

    def transport(req):
        calls.append(req)
        if failure == "read":
            raise httpx.ReadTimeout("private")
        if failure == "write":
            raise httpx.WriteError("private")
        if failure == "body":
            return httpx.Response(200, json=[])
        return reply(
            usage=failure != "usage",
            malformed=failure == "malformed",
            status=503 if failure == "http" else 200,
        )

    with pytest.raises(StructuredModelError, match="configured model"):
        asyncio.run(
            client(meter, transport, max_infrastructure_attempts=3).generate_structured(request())
        )
    assert len(calls) == 1
    row, budget = snapshot(meter, "logical-call:1")
    assert row.actual_micros is None and budget.exposure_micros == 10_000
    assert row.input_tokens == (100 if failure in {"malformed", "http"} else None)


def test_connect_retries_each_reserve_before_dispatch_and_release_only_not_sent(meter):
    calls = []

    def transport(req):
        calls.append(req)
        row, budget = snapshot(meter, f"logical-call:{len(calls)}")
        assert row.state == "DISPATCHED" and budget.exposure_micros == 10_000
        if len(calls) < 3:
            raise httpx.ConnectError("synthetic")
        return reply()

    asyncio.run(
        client(meter, transport, max_infrastructure_attempts=3).generate_structured(request())
    )
    assert len(calls) == 3
    assert snapshot(meter, "logical-call:1")[0].state == "NOT_SENT"
    meter.observe("logical-call:1")  # Late timeout cleanup cannot revive a released attempt.
    assert snapshot(meter, "logical-call:3")[1].exposure_micros == 10_000


def test_budget_denial_prevents_network_and_input_bound_is_enforced(meter):
    calls = []
    adapter = client(meter, lambda req: calls.append(req) or reply())
    asyncio.run(adapter.generate_structured(request("one")))
    asyncio.run(adapter.generate_structured(request("two")))
    with pytest.raises(StructuredModelError):
        asyncio.run(adapter.generate_structured(request("three")))
    with pytest.raises(StructuredModelError):
        asyncio.run(adapter.generate_structured(replace(request("huge"), user_prompt="x" * 10_000)))
    assert len(calls) == 2


@pytest.mark.parametrize("cancel", [False, True])
def test_timeout_and_cancellation_keep_durable_exposure(meter, cancel):
    started = asyncio.Event()

    async def slow(req):
        started.set()
        await asyncio.sleep(10)

    async def run():
        pending = asyncio.create_task(
            client(meter, slow, timeout_seconds=0.2).generate_structured(request())
        )
        if cancel:
            await started.wait()
            pending.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else StructuredModelError):
            await pending

    asyncio.run(run())
    row, budget = snapshot(meter, "logical-call:1")
    assert row.state == "UNKNOWN" and budget.exposure_micros == 10_000


def test_external_transport_requires_meter_and_config_requires_matching_approval(db_session):
    with pytest.raises(ProviderBudgetError):
        ResponsesStructuredLlmClient(api_key="synthetic", model="synthetic")
    configured = Settings(_env_file=None)
    with pytest.raises(ProviderBudgetError, match="budget"):
        configured_meter(db_session, provider="p", model="m", configured=configured)
    configured.llm_budget_limit = Decimal("1")
    with pytest.raises(ProviderBudgetError, match="prices"):
        configured_meter(db_session, provider="p", model="m", configured=configured)
    configured.llm_input_cost_per_million = Decimal("0")
    configured.llm_output_cost_per_million = Decimal("0")
    with pytest.raises(ProviderBudgetError, match="Pricing"):
        configured_meter(db_session, provider="p", model="m", configured=configured)


def test_migration_preserves_existing_rows_and_refuses_lossy_downgrade(tmp_path):
    path = (
        Path(__file__).resolve().parents[1] / "migrations/versions/20260911_0047_provider_usage.py"
    )
    spec = importlib.util.spec_from_file_location("usage_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "20260910_0046"
    engine = create_db_engine(f"sqlite:///{(tmp_path / 'migration.db').as_posix()}")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE existing_history (id TEXT)")
            connection.exec_driver_sql("INSERT INTO existing_history VALUES ('preserved')")
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            assert (
                connection.exec_driver_sql("SELECT id FROM existing_history").scalar()
                == "preserved"
            )
        migrated_meter = ProviderUsageMeter(engine, policy())
        migrated_meter.reserve("migration-proof", {}, {})
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                with pytest.raises(RuntimeError, match="history"):
                    migration.downgrade()
    finally:
        engine.dispose()


def _interrupted_process(url, dispatched):
    engine = create_db_engine(url)
    worker = ProviderUsageMeter(engine, policy())
    worker.reserve("interrupted", {}, {})
    if dispatched:
        worker.dispatch("interrupted")
    os._exit(0)  # Simulate termination without session/engine cleanup.


@pytest.mark.parametrize("dispatched", [False, True])
def test_process_interruption_preserves_reservation_boundary(meter, dispatched):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from test_provider_usage import _interrupted_process; "
            "_interrupted_process(sys.argv[1], sys.argv[2] == 'True')",
            str(meter._sessions.kw["bind"].url),
            str(dispatched),
        ],
        capture_output=True,
        text=True,
        timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert result.returncode == 0, result.stderr
    row, budget = snapshot(meter, "interrupted")
    assert budget.exposure_micros == 10_000
    assert row.state == ("DISPATCHED" if dispatched else "RESERVED")
    if dispatched:
        with pytest.raises(ProviderBudgetError):
            meter.release_undispatched("interrupted")
        with pytest.raises(ProviderBudgetError):
            meter.dispatch("interrupted")
    else:
        meter.release_undispatched("interrupted")
        assert snapshot(meter, "interrupted")[1].exposure_micros == 0


def test_observation_uses_frozen_pricing_and_retains_excess_exposure(meter):
    meter.reserve("excess", {}, {})
    meter.dispatch("excess")
    recovered = ProviderUsageMeter(meter._sessions.kw["bind"], policy(input_rate=Decimal("0")))
    recovered.observe("excess", input_tokens=30_000, output_tokens=20)
    row, budget = snapshot(meter, "excess")
    assert row.reserved_micros == 10_000 and row.estimated_micros == 30_000
    assert row.exposure_micros == budget.exposure_micros == 30_000
    meter.reconcile(
        "excess",
        actual=Decimal("0.004"),
        currency="AUD",
        receipt_id="fixture-excess-bill",
        actor="synthetic-operator",
    )
    assert snapshot(meter, "excess")[1].exposure_micros == 4000


def test_release_racing_dispatch_cannot_erase_dispatched_exposure(meter):
    meter.reserve("race", {}, {})

    def run(operation):
        try:
            operation("race")
            return True
        except ProviderBudgetError:
            return False

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(run, [meter.dispatch, meter.release_undispatched]))
    assert sum(outcomes) == 1
    row, budget = snapshot(meter, "race")
    assert budget.exposure_micros == (10_000 if row.state == "DISPATCHED" else 0)


def test_operator_cli_reconciliation_and_listing_preserve_evidence(meter, monkeypatch, capsys):
    from scripts import provider_usage as cli

    monkeypatch.setattr(cli, "engine", meter._sessions.kw["bind"])
    meter.reserve("cli", {}, {})
    meter.dispatch("cli")
    monkeypatch.setattr(
        "sys.argv",
        [
            "provider_usage",
            "reconcile",
            "--usage-id",
            "cli",
            "--actual",
            "0.004",
            "--currency",
            "AUD",
            "--receipt-id",
            "fixture-cli-bill",
            "--actor",
            "synthetic-operator",
        ],
    )
    cli.main()
    capsys.readouterr()
    monkeypatch.setattr("sys.argv", ["provider_usage", "list", "--budget-id", "synthetic-budget"])
    cli.main()
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["actual_micros"] == 4000
    assert rows[0]["reconciliation_actor"] == "synthetic-operator"
    assert rows[0]["input_tokens"] is None


def test_partial_usage_keeps_available_counts_and_response_identity(meter):
    def transport(req):
        return httpx.Response(
            200, json={"id": "partial-response", "usage": {"input_tokens": 123}, "output": []}
        )

    with pytest.raises(StructuredModelError):
        asyncio.run(client(meter, transport).generate_structured(request()))
    row, budget = snapshot(meter, "logical-call:1")
    assert row.input_tokens == 123 and row.output_tokens is None
    assert row.estimated_micros is None and row.actual_micros is None
    assert row.provider_response_id == "partial-response" and budget.exposure_micros == 10_000


def test_timeout_during_reservation_never_dispatches(meter, monkeypatch):
    import time

    reserve = meter.reserve

    def delayed(*args):
        time.sleep(0.08)
        return reserve(*args)

    monkeypatch.setattr(meter, "reserve", delayed)
    calls = []
    with pytest.raises(StructuredModelError):
        asyncio.run(
            client(
                meter, lambda req: calls.append(req) or reply(), timeout_seconds=0.02
            ).generate_structured(request())
        )
    assert calls == []
    row, budget = snapshot(meter, "logical-call:1")
    assert row.state == "RESERVED" and budget.exposure_micros == 10_000
    meter.release_undispatched("logical-call:1")
