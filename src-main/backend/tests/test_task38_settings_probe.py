import asyncio
import json

import httpx
import pytest

from scripts.task38_benchmark.__main__ import settings_command
from scripts.task38_benchmark.adapter import LearningLoop, probe_settings
from scripts.task38_benchmark.core import Budget, Config, StopRun
from scripts.task38_benchmark.fake import FakeTransport

DESIRED = {
    "llm_provider": "configured",
    "llm_model": "model",
    "provider_timeout_seconds": 15,
    "max_infrastructure_attempts": 2,
}


@pytest.mark.parametrize(
    "changed",
    [{"provider_timeout_seconds": 61}, {"max_infrastructure_attempts": True}, {"budget_aud": 1}],
)
def test_probe_rejects_invalid_or_unsupported_settings_before_network(changed):
    class NoNetwork:
        async def request(self, *args, **kwargs):
            pytest.fail("Invalid probe configuration must not reach the target")

    with pytest.raises(StopRun):
        asyncio.run(probe_settings(NoNetwork(), NoNetwork(), {**DESIRED, **changed}))


@pytest.mark.parametrize("failure", ["save", "bounds", "budget"])
def test_probe_restores_all_settings_after_runtime_failure(failure):
    class Target(FakeTransport):
        def handle(self, request):
            if request.method == "PUT" and request.url.path.endswith("/admin/settings"):
                body = json.loads(request.content)
                if body == {"provider_timeout_seconds": 15} and failure == "save":
                    super().handle(request)  # Simulate a mutation before its response is lost.
                    return httpx.Response(503, json={})
                if body == {"provider_timeout_seconds": 0} and failure == "bounds":
                    return httpx.Response(200, json=self.settings)
            return super().handle(request)

    async def exercise():
        config = Config(users=(1,), max_requests=14 if failure == "budget" else 40)
        budget = Budget(config)
        target, learner_target = Target(), FakeTransport()
        original = dict(target.settings)
        learner_target.settings = target.settings
        result = {"loop_id": "settings", "phase": "preflight", "users": 1}
        admin = LearningLoop(config, budget, [], result, lambda: 0, target.session())
        learner = LearningLoop(config, budget, [], result, lambda: 0, learner_target.session())
        try:
            await admin.request("POST", "auth/login", {"email": "admin", "password": "synthetic"})
            await learner.request(
                "POST", "auth/login", {"email": "student", "password": "synthetic"}
            )
            with pytest.raises(StopRun):
                await probe_settings(admin, learner, DESIRED)
            assert target.settings == original
            assert target.calls[-2][0] == "PUT" and target.calls[-2][2] == original
            assert target.calls[-1][0] == "GET"
        finally:
            await admin.close()
            await learner.close()

    asyncio.run(exercise())


def test_settings_command_reserves_sufficient_requests_before_login():
    with pytest.raises(ValueError, match="at least 32"):
        asyncio.run(settings_command(Config(max_requests=31), {}))


@pytest.mark.parametrize("original", [{"llm_model": ""}, {"max_infrastructure_attempts": 0}])
def test_probe_refuses_unrestorable_original_values_before_mutation(original):
    class ReadOnlyTarget:
        result = {}

        async def request(self, method, path):
            assert method == "GET" and path == "admin/settings"
            return {**DESIRED, **original}

    with pytest.raises(StopRun, match="original_values_not_restorable"):
        asyncio.run(probe_settings(ReadOnlyTarget(), ReadOnlyTarget(), DESIRED))
