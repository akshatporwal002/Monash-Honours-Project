"""Unit checks only: no servers, provider traffic or load campaign."""

import asyncio
import copy
import json
from dataclasses import asdict, replace

import httpx
import pytest

from app.schemas.activity_continuation import ActivityAction
from app.schemas.episode import EpisodeHelpUseWrite
from app.schemas.lms import DraftWrite, EpisodeCheckpointWrite, SubmissionCreate
from app.schemas.student import SimulationRequest
from scripts.task38_benchmark.__main__ import main
from scripts.task38_benchmark.adapter import LearningLoop, probe_settings
from scripts.task38_benchmark.core import Budget, Config, StopRun, campaign, p95, summarise
from scripts.task38_benchmark.fake import FakeTransport, factory, roster


def run(config=None, build=factory):
    config = config or Config(users=(2,), max_requests=300)
    count = sum(config.users) * (config.warmup_rounds + config.measurement_rounds)
    return asyncio.run(campaign(config, roster(count), build, "test-run"))


def test_warmup_is_separate_unique_loops_and_fake_is_not_cost_evidence():
    report = run()
    assert len(report["loops"]) == 4
    assert len({r["loop_id"] for r in report["loops"]}) == 4
    assert report["scenarios"][0]["loop_count"] == 2
    assert report["scenarios"][0]["learning_loops"] == 2
    assert report["scenarios"][0]["complete_loops"] == 0
    assert report["scenarios"][0]["metrics"]["feedback"]["count"] == 2
    assert report["scenarios"][0]["metrics"]["assessed_feedback"]["count"] == 4
    assert report["scenarios"][0]["metrics"]["feedback"]["p95_seconds"] == pytest.approx(2.15)
    assert report["cost"]["external_aud_per_complete_loop"] is None
    assert report["evidence_class"] == "SYNTHETIC DRY RUN"
    encoded = json.dumps(report)
    assert "synthetic-fixture-only" not in encoded
    assert "@example.invalid" not in encoded
    assert "Equal amplitudes" not in encoded


def test_adapter_requests_match_existing_production_request_schemas_and_preserve_history():
    transports = []

    def build(c, b, samples, result, clock):
        fake = FakeTransport(result["loop_id"])
        transports.append(fake)
        return LearningLoop(c, b, samples, result, lambda: fake.now, fake.session(), fake.sleep)

    report = run(Config(users=(1,), warmup_rounds=0), build)
    calls = transports[0].calls
    for method, path, body in calls:
        if path.endswith("/episode/checkpoints"):
            EpisodeCheckpointWrite.model_validate(body)
        elif path.endswith("/episode/transfer") or (path.endswith("/draft") and method == "PUT"):
            DraftWrite.model_validate(body)
        elif path.endswith("/submissions") and method == "POST":
            SubmissionCreate.model_validate(body)
        elif path.endswith("/simulate"):
            SimulationRequest.model_validate(body)
        elif path.endswith("/actions"):
            ActivityAction.model_validate(body)
        elif path.endswith("/episode/help"):
            EpisodeHelpUseWrite.model_validate(body)
    transfer_index = next(i for i, (_, p, _) in enumerate(calls) if p.endswith("/episode/transfer"))
    assert not any(p.endswith("/episode/help") for _, p, _ in calls[transfer_index + 1 :])
    submissions = [b for m, p, b in calls if m == "POST" and p.endswith("/submissions")]
    assert len(submissions) == 3
    assert (
        submissions[2]["episode"]["supported"]["explanation"]
        == roster(1)[0]["next_activity_answer"]
    )
    assert submissions[2].get("assessment_work_start_id") is None
    assert not submissions[2].get("answer")
    assert submissions[2]["episode"].get("transfer") is None
    assert "revision" not in submissions[0]["episode"]["supported"]
    assert (
        submissions[1]["episode"]["supported"]["revision"]["previous_response_version_id"]
        == report["loops"][0]["submission_ids"][0]
    )
    assert not any("assessment/" in p for _, p, _ in calls)


@pytest.mark.parametrize(
    "changed",
    [
        {"task_type": "reflection"},
        {"assessment": {"task_form_version_id": "changed"}},
        {"episode_plan": {"prediction_required": True}},
    ],
)
def test_changed_next_activity_conditions_stop_before_draft_or_submission(changed):
    transports = []

    def build(c, b, samples, result, clock):
        class ChangedNextTask(FakeTransport):
            def handle(self, request):
                response = super().handle(request)
                if request.method == "GET" and request.url.path.endswith("/tasks/task38-next"):
                    return httpx.Response(200, json={**response.json(), **changed})
                return response

        fake = ChangedNextTask(result["loop_id"])
        transports.append(fake)
        return LearningLoop(c, b, samples, result, lambda: fake.now, fake.session(), fake.sleep)

    report = run(Config(users=(1,), warmup_rounds=0), build)
    assert report["loops"][0]["status"] == "next_activity_profile_mismatch"
    assert not any(
        method in {"POST", "PUT"} and "/task38-next/" in path
        for method, path, _ in transports[0].calls
    )


@pytest.mark.parametrize("status", ["failed", "fallback"])
def test_terminal_feedback_failures_are_retained(status):
    def build(c, b, samples, result, clock):
        fake = FakeTransport(result["loop_id"], feedback_status=status)
        return LearningLoop(c, b, samples, result, lambda: fake.now, fake.session(), fake.sleep)

    report = run(Config(users=(1,), warmup_rounds=0), build)
    assert report["loops"][0]["status"] == "feedback_" + status
    assert report["scenarios"][0]["metrics"]["assessed_feedback"]["errors"] == 1
    assert report["scenarios"][0]["loop_error_rate"] == 1
    assert report["scenarios"][0]["http_error_rate"] == 0


def test_worker_timeout_keeps_lower_bound_latency_and_workflow():
    def build(c, b, samples, result, clock):
        fake = FakeTransport(result["loop_id"], feedback_status="processing")
        return LearningLoop(c, b, samples, result, lambda: fake.now, fake.session(), fake.sleep)

    report = run(Config(users=(1,), warmup_rounds=0, worker_timeout=3), build)
    assert report["loops"][0]["status"] == "feedback_timeout"
    assert report["loops"][0]["workflow_ids"]
    metric = report["scenarios"][0]["metrics"]["assessed_feedback"]
    assert metric["censored"] == 1 and metric["p95_seconds"] >= 3


def test_human_timeout_is_separate_from_feedback_and_not_an_assessment_result():
    report = run(Config(users=(1,), warmup_rounds=0, human_timeout=1))
    assert report["loops"][0]["status"] == "human_timeout"
    assert report["loops"][0]["learning_complete"]
    assert report["scenarios"][0]["complete_loops"] == 0
    assert report["scenarios"][0]["metrics"]["feedback"]["errors"] == 0


def test_only_observed_human_confirmation_completes_formal_loop():
    def build(c, b, samples, result, clock):
        fake = FakeTransport(result["loop_id"], confirmed=True)
        return LearningLoop(c, b, samples, result, lambda: fake.now, fake.session(), fake.sleep)

    report = run(Config(users=(1,), warmup_rounds=0), build)
    assert report["scenarios"][0]["complete_loops"] == 1
    assert report["loops"][0]["formal_result"] == "PASS"
    assert report["production_compliance"] == "not_established"


@pytest.mark.parametrize(
    "config,expected",
    [
        (Config(users=(1,), warmup_rounds=0, max_requests=1), "request_budget"),
        (Config(users=(1,), warmup_rounds=0, max_cost_aud="0.01"), "cost_budget"),
    ],
)
def test_budget_is_enforced_before_dispatch(config, expected):
    report = run(config)
    assert report["loops"][0]["status"] == expected
    assert report["manifest"]["requests"] <= config.max_requests
    if expected == "cost_budget":
        assert report["manifest"]["requests"] == 0


@pytest.mark.parametrize(
    "change",
    [
        {"users": (4,), "fake": False},
        {"users": (101,)},
        {"max_requests": 0},
        {"worker_timeout": float("nan")},
        {"loop_cost_ceiling_aud": "Infinity"},
        {"max_cost_aud": "0"},
        {"fake": False, "users": (50,)},
        {"users": (1, 1)},
        {"measurement_rounds": 0},
    ],
)
def test_invalid_or_unapproved_config_is_rejected(change):
    with pytest.raises(ValueError):
        replace(Config(users=(1,)), **change).validate()


def test_duplicate_learners_rejected_before_io():
    rows = roster(2)
    rows[1] = copy.deepcopy(rows[0])
    with pytest.raises(ValueError):
        asyncio.run(campaign(Config(users=(2,), warmup_rounds=0), rows, factory, "duplicate"))


@pytest.mark.parametrize(
    "field", ["provider_timeout_seconds", "max_infrastructure_attempts", "budget_aud"]
)
def test_runtime_timeout_retry_budget_are_not_supported_by_existing_admin_contract(field):
    from app.schemas.lms import SettingsUpdate

    with pytest.raises(ValueError):
        SettingsUpdate.model_validate({field: 1})


def test_aliases_for_one_authenticated_actor_stop_before_second_work_start():
    def build(c, b, samples, result, clock):
        fake = FakeTransport("same-actor")
        return LearningLoop(c, b, samples, result, lambda: fake.now, fake.session(), fake.sleep)

    report = run(Config(users=(2,), warmup_rounds=0), build)
    assert sum(r["status"] == "fixture_actor_not_unique_student" for r in report["loops"]) == 1


def test_cancellation_returns_partial_report_and_closes_sessions():
    async def exercise():
        entered = asyncio.Event()
        closed = []

        class Waiting:
            def __init__(self, *args):
                pass

            async def run(self, row):
                entered.set()
                await asyncio.Event().wait()

            async def close(self):
                closed.append(True)

        task = asyncio.create_task(
            campaign(Config(users=(2,), warmup_rounds=0), roster(2), Waiting, "cancel")
        )
        await entered.wait()
        task.cancel()
        result = await task
        assert result["manifest"]["cancelled"]
        assert all(r["status"] == "cancelled" for r in result["loops"])
        assert len(closed) == 2

    asyncio.run(exercise())


def test_bounded_concurrency_and_phase_deadline_account_for_all_planned_loops():
    active = peak = 0

    class Counting:
        def __init__(self, c, b, samples, result, clock):
            self.result = result

        async def run(self, row):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.Event().wait()
            finally:
                active -= 1

        async def close(self):
            pass

    report = run(
        Config(users=(2,), warmup_rounds=0, measurement_rounds=2, phase_timeout=0.01), Counting
    )
    assert peak == 2
    assert len(report["loops"]) == 4
    assert {r["status"] for r in report["loops"]} == {"phase_deadline"}


def test_p95_50_user_and_scaling_report_from_hand_calculated_samples():
    assert p95(list(range(1, 101))) == 95
    assert p95([]) is None
    config = asdict(Config(users=(5, 50, 100), fake=False))
    samples = [
        {
            "users": n,
            "phase": "measurement",
            "category": "ordinary",
            "kind": "http",
            "seconds": value,
            "ok": True,
        }
        for n, value in ((5, 2), (50, 2.4), (100, 2.6))
    ]
    report = summarise({"config": config}, [], samples)
    assert report["scenarios"][1]["report_mode"] == "50-user"
    assert report["scaling"]["comparisons"][-1]["growth"] == pytest.approx(0.3)
    assert not report["scaling"]["comparisons"][-1]["within_threshold_observed"]


def test_settings_authority_and_restoration_with_supported_http_interfaces():
    async def exercise():
        config = Config(users=(1,))
        budget, samples = Budget(config), []
        shared = {"llm_provider": "old-provider", "llm_model": "old-model"}
        admin_fake, learner_fake = FakeTransport(), FakeTransport()
        admin_fake.settings = learner_fake.settings = shared
        result = {"loop_id": "settings", "phase": "preflight", "users": 1}
        admin = LearningLoop(config, budget, samples, result, lambda: 0, admin_fake.session())
        learner = LearningLoop(config, budget, samples, result, lambda: 0, learner_fake.session())
        try:
            await admin.request(
                "POST", "auth/login", {"email": "admin@example.invalid", "password": "fake"}
            )
            await learner.request(
                "POST", "auth/login", {"email": "student@example.invalid", "password": "fake"}
            )
            receipt = await probe_settings(
                admin, learner, {"llm_provider": "new-provider", "llm_model": "new-model"}
            )
            assert receipt["restored"]
            assert receipt["llm_model"]["unauthorized"] == "denied_403"
            assert receipt["budget"]["status"] == "missing_runtime_interface"
            assert shared == {"llm_provider": "old-provider", "llm_model": "old-model"}
        finally:
            await admin.close()
            await learner.close()

    asyncio.run(exercise())


def test_transport_timeout_is_sanitised_and_counted():
    def build(c, b, samples, result, clock):
        def timeout(request):
            raise httpx.ReadTimeout("private secret provider message")

        client = httpx.AsyncClient(
            base_url="https://task38.invalid/api/v1/", transport=httpx.MockTransport(timeout)
        )
        return LearningLoop(c, b, samples, result, clock, client)

    report = run(Config(users=(1,), warmup_rounds=0), build)
    assert report["loops"][0]["status"] == "request_timeout"
    assert report["scenarios"][0]["http_errors"] == 1
    assert "private secret" not in json.dumps(report)


def test_cli_refuses_real_without_acknowledgements_before_network(tmp_path):
    config = tmp_path / "config.json"
    config.write_text("{}")
    with pytest.raises(SystemExit) as error:
        main(
            [
                "run",
                "--config",
                str(config),
                "--roster",
                "missing.json",
                "--output",
                str(tmp_path / "output.json"),
            ]
        )
    assert error.value.code == 2


def test_settings_restores_when_unauthorized_actor_is_unexpectedly_allowed():
    async def exercise():
        c, result = Config(users=(1,)), {"loop_id": "test", "phase": "preflight", "users": 1}
        fake = FakeTransport()
        admin = LearningLoop(c, Budget(c), [], result, lambda: 0, fake.session())
        try:
            await admin.request("POST", "auth/login", {"email": "admin", "password": "fake"})
            with pytest.raises(StopRun, match="http_200"):
                await probe_settings(admin, admin, {"llm_provider": "new", "llm_model": "new"})
            assert fake.settings == {"llm_provider": "local", "llm_model": "template"}
        finally:
            await admin.close()

    asyncio.run(exercise())
