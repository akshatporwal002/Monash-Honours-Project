"""Synthetic runtime controls: authorization, fresh policy, transport and durable work."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import func, select
from test_lms_core_api import lms_context as _lms_context
from test_lms_core_api import login
from test_typed_practice_feedback import practice

from app.core.config import Settings, settings
from app.db.session import create_session_factory
from app.models import PlatformAuditEvent, WorkflowRun, WorkflowStage
from app.models.lms import SystemSetting
from app.models.persistence import FeedbackRecord
from app.schemas.lms import SettingsUpdate
from app.services.feedback.application import InProcessFeedbackExecutor
from app.services.feedback.contracts import StructuredLlmRequest
from app.services.feedback.errors import ContextCollectionError
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository
from app.services.feedback.worker import FeedbackRecoveryWorker
from app.services.llm import ResponsesStructuredLlmClient, StructuredModelError
from app.services.lms import LmsService, LmsServiceError
from app.services.rag.contracts import TaskGenerationRequest
from app.services.runtime_policy import RuntimePolicyUnavailable, read_runtime_policy
from app.worker import build_database_worker, build_offline_worker_adapters


def set_policy(session, timeout=10, attempts=3):
    for key, value in {
        "provider_timeout_seconds": timeout,
        "max_infrastructure_attempts": attempts,
    }.items():
        row = session.scalar(select(SystemSetting).where(SystemSetting.key == key))
        if row is None:
            session.add(
                SystemSetting(key=key, value=value, description="Synthetic runtime control")
            )
        else:
            row.value = value
    session.commit()


def request():
    return StructuredLlmRequest(
        system_prompt="Synthetic",
        user_prompt="Synthetic",
        response_schema={"type": "object"},
        schema_name="synthetic",
        prompt_version="synthetic-v1",
    )


def response(output):
    return httpx.Response(
        200,
        json={
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(output)}],
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        },
    )


@pytest.fixture
def runtime_api(tmp_path):
    yield from _lms_context.__wrapped__(tmp_path)


def test_only_admin_can_persist_bounded_runtime_controls(runtime_api):
    client, session = runtime_api
    url = "/api/v1/admin/settings"
    assert client.get(url).status_code == 401
    for role in ("student", "educator", "admin"):
        login(client, role)
        headers = {
            settings.csrf_header_name: client.cookies.get(settings.csrf_cookie_name),
            "Origin": settings.frontend_origin,
        }
        updated = client.put(
            url,
            json={"provider_timeout_seconds": 7, "max_infrastructure_attempts": 2},
            headers=headers,
        )
        assert updated.status_code == (200 if role == "admin" else 403)
        if role == "admin":
            assert updated.json()["provider_timeout_seconds"] == 7
            assert client.get(url).json()["max_infrastructure_attempts"] == 2
            assert (
                client.put(
                    url, json={"max_infrastructure_attempts": 4}, headers=headers
                ).status_code
                == 422
            )
            assert client.get(url).json()["max_infrastructure_attempts"] == 2
        client.post("/api/v1/auth/logout", headers=headers)
    events = session.scalars(
        select(PlatformAuditEvent).where(PlatformAuditEvent.action == "setting.updated")
    ).all()
    assert len(events) == 2
    rows = session.scalars(
        select(SystemSetting).where(
            SystemSetting.key.in_(["provider_timeout_seconds", "max_infrastructure_attempts"])
        )
    ).all()
    assert len(rows) == 2 and all(row.updated_by is not None for row in rows)


@pytest.mark.parametrize(
    "key,value",
    [("provider_timeout_seconds", v) for v in (0, 61, True, None, "5", 1.5)]
    + [("max_infrastructure_attempts", v) for v in (0, 4, False, None, "2", 2.0)],
)
def test_runtime_controls_reject_coercion_nulls_and_out_of_bounds(key, value):
    with pytest.raises(ValidationError):
        SettingsUpdate(**{key: value})


def test_runtime_policy_uses_defaults_and_fresh_scalar_values(db_session):
    configured = Settings(
        _env_file=None, provider_timeout_seconds=19, max_infrastructure_attempts=2
    )
    assert read_runtime_policy(db_session, configured).provider_timeout_seconds == 19
    set_policy(db_session, 8, 3)
    cached = db_session.scalar(
        select(SystemSetting).where(SystemSetting.key == "provider_timeout_seconds")
    )
    with create_session_factory(db_session.get_bind())() as separate:
        set_policy(separate, 4, 1)
    assert cached.value == 8
    db_session.commit()
    assert read_runtime_policy(db_session, configured).provider_timeout_seconds == 4
    assert read_runtime_policy(db_session, configured).max_infrastructure_attempts == 1


@pytest.mark.parametrize("value", [None, True, "5", 61])
def test_corrupt_persisted_policy_stops_dispatch(db_session, value):
    from app.services.feedback.runtime import _configured_model_client
    from app.services.task_generation_runtime import configured_task_generation_client

    set_policy(db_session, value, 3)
    for build in (_configured_model_client, configured_task_generation_client):
        with pytest.raises(RuntimePolicyUnavailable):
            build(db_session)
    with pytest.raises(LmsServiceError) as failure:
        LmsService(db_session).read_settings()
    assert failure.value.status_code == 503


def test_runtime_contract_has_bounded_nonnullable_optional_updates():
    from scripts.export_openapi import openapi_document

    schemas = openapi_document()["components"]["schemas"]
    for name, maximum in (("provider_timeout_seconds", 60), ("max_infrastructure_attempts", 3)):
        for schema in ("SettingsUpdate", "SettingsRead"):
            field = schemas[schema]["properties"][name]
            assert field["type"] == "integer"
            assert (field["minimum"], field["maximum"]) == (1, maximum)
        assert name not in schemas["SettingsUpdate"].get("required", [])
        assert name in schemas["SettingsRead"]["required"]


@pytest.mark.parametrize("attempts", [1, 2, 3])
def test_connection_retries_are_bounded_before_dispatch(attempts):
    calls = []

    def failing(req):
        calls.append(req)
        raise httpx.ConnectError("private synthetic transport message")

    client = ResponsesStructuredLlmClient(
        api_key="synthetic-key",
        model="synthetic",
        timeout_seconds=2,
        max_infrastructure_attempts=attempts,
        transport=httpx.MockTransport(failing),
    )
    with pytest.raises(StructuredModelError, match="configured model"):
        asyncio.run(client.generate_structured(request()))
    assert len(calls) == attempts
    assert all(call.extensions["timeout"]["connect"] == 2 for call in calls)


@pytest.mark.parametrize("failure", ["read", "write", "http", "malformed"])
def test_ambiguous_or_completed_requests_are_never_replayed(failure):
    calls = []

    def failing(req):
        calls.append(req)
        if failure == "read":
            raise httpx.ReadTimeout("synthetic")
        if failure == "write":
            raise httpx.WriteError("synthetic")
        if failure == "http":
            return httpx.Response(503)
        return httpx.Response(200, json={"output": []})

    client = ResponsesStructuredLlmClient(
        api_key="synthetic-key",
        model="synthetic",
        max_infrastructure_attempts=3,
        transport=httpx.MockTransport(failing),
    )
    with pytest.raises(StructuredModelError):
        asyncio.run(client.generate_structured(request()))
    assert len(calls) == 1


def test_wall_timeout_bounds_even_a_transport_ignoring_httpx_timeouts():
    calls = []

    async def slow(req):
        calls.append(req)
        await asyncio.sleep(1)
        return response({"unused": True})

    client = ResponsesStructuredLlmClient(
        api_key="synthetic-key",
        model="synthetic",
        timeout_seconds=0.02,
        max_infrastructure_attempts=3,
        transport=httpx.MockTransport(slow),
    )
    with pytest.raises(StructuredModelError):
        asyncio.run(client.generate_structured(request()))
    assert len(calls) == 1


def test_task_generation_uses_current_timeout_and_non_nested_connect_retry(db_session, monkeypatch):
    import app.services.task_generation_runtime as runtime

    monkeypatch.setattr(settings, "llm_api_key", SecretStr("synthetic-recording-only"))
    monkeypatch.setattr(settings, "llm_model", "synthetic-recording-model")
    calls = []

    def transport(req):
        calls.append(req)
        if len(calls) == 1:
            raise httpx.ConnectError("pre-dispatch synthetic failure")
        return response({"tasks": [{"title": "Synthetic"}]})

    monkeypatch.setattr(
        runtime,
        "ResponsesStructuredLlmClient",
        lambda **kwargs: ResponsesStructuredLlmClient(
            **kwargs, transport=httpx.MockTransport(transport)
        ),
    )
    set_policy(db_session, 9, 2)
    generator = runtime.configured_task_generation_client(db_session)
    result = asyncio.run(
        generator.generate_structured(TaskGenerationRequest(prompt_version="synthetic", payload={}))
    )
    assert result.tasks[0]["title"] == "Synthetic"
    assert len(calls) == 2 and all(call.extensions["timeout"]["read"] == 9 for call in calls)


def test_feedback_transport_does_not_multiply_worker_retry_ceiling(db_session, monkeypatch):
    import app.services.feedback.runtime as runtime

    monkeypatch.setattr(settings, "llm_api_key", SecretStr("synthetic-recording-only"))
    monkeypatch.setattr(settings, "llm_model", "synthetic-recording-model")
    calls = []

    def fail(req):
        calls.append(req)
        raise httpx.ConnectError("synthetic")

    monkeypatch.setattr(
        runtime,
        "ResponsesStructuredLlmClient",
        lambda **kwargs: ResponsesStructuredLlmClient(
            **kwargs, transport=httpx.MockTransport(fail)
        ),
    )
    set_policy(db_session, 6, 3)
    with pytest.raises(StructuredModelError):
        asyncio.run(runtime._configured_model_client(db_session).generate_structured(request()))
    assert len(calls) == 1 and calls[0].extensions["timeout"]["read"] == 6


def test_running_recovery_worker_reloads_limits_without_duplicate_logical_work(db_session):
    now = [datetime(2026, 9, 10, tzinfo=UTC)]
    factory = create_session_factory(db_session.get_bind())
    executions = []

    class FailingPipeline:
        def attach_progress_recorder(self, repository):
            pass

        def attach_audit_events(self, audit):
            pass

        async def run(self, submission, workflow, **kwargs):
            executions.append((submission, workflow))
            raise ContextCollectionError()

    worker = FeedbackRecoveryWorker(
        factory,
        InProcessFeedbackExecutor(factory, lambda repo: FailingPipeline(), now=lambda: now[0]),
        now=lambda: now[0],
    )
    set_policy(db_session, 8, 3)
    repository = SqlAlchemyFeedbackWorkflowRepository(db_session)
    claim = repository.claim_workflow(
        "synthetic-runtime-work", str(uuid4()), started_at=now[0], lease_expires_at=now[0]
    )
    assert asyncio.run(worker.run_once())
    assert executions == [(claim.submission_id, claim.workflow_run_id)]
    set_policy(db_session, 4, 2)
    now[0] += timedelta(seconds=6)
    assert asyncio.run(worker.run_once())
    db_session.expire_all()
    row = db_session.get(WorkflowRun, claim.workflow_run_id)
    assert row.failure_category == "retry_attempts_exhausted" and row.next_retry_at is None
    assert row.execution_attempt_count == 2 and len(executions) == 1
    set_policy(db_session, 4, 3)
    assert (
        asyncio.run(worker.run_once()) is False
    )  # Increasing limits cannot resurrect terminal work.
    assert db_session.scalar(select(func.count()).select_from(WorkflowRun)) == 1


@pytest.mark.parametrize("initial_attempts,changed_attempts", [(1, 3), (3, 1)])
def test_inprocess_failure_retains_policy_while_admin_changes_limits(
    db_session, initial_attempts, changed_attempts
):
    now = datetime(2026, 9, 10, tzinfo=UTC)
    factory = create_session_factory(db_session.get_bind())
    set_policy(db_session, 9, initial_attempts)
    claim = SqlAlchemyFeedbackWorkflowRepository(db_session).claim_workflow(
        "policy-snapshot-failure",
        str(uuid4()),
        started_at=now,
        lease_expires_at=now + timedelta(seconds=30),
    )

    class ChangingPipeline:
        def attach_progress_recorder(self, repository):
            self.policy = repository.runtime_policy

        async def run(self, *args, **kwargs):
            assert self.policy.max_infrastructure_attempts == initial_attempts
            with factory() as administrator_session:
                set_policy(administrator_session, 4, changed_attempts)
            raise ContextCollectionError()

    executor = InProcessFeedbackExecutor(factory, lambda repo: ChangingPipeline(), now=lambda: now)
    asyncio.run(executor.execute(claim.workflow_run_id, claim.submission_id, claim.execution_token))
    db_session.expire_all()
    failed = db_session.get(WorkflowRun, claim.workflow_run_id)
    assert failed.current_stage is WorkflowStage.FAILED
    assert failed.execution_attempt_count == 1
    assert (failed.next_retry_at is not None) is (initial_attempts > 1)
    assert read_runtime_policy(db_session).max_infrastructure_attempts == changed_attempts


def test_lower_limit_preserves_an_active_execution_lease(db_session):
    now = [datetime(2026, 9, 10, tzinfo=UTC)]
    calls = []

    class Executor:
        async def execute(self, *args):
            calls.append(args)

    worker = FeedbackRecoveryWorker(
        create_session_factory(db_session.get_bind()), Executor(), now=lambda: now[0]
    )
    claim = SqlAlchemyFeedbackWorkflowRepository(db_session).claim_workflow(
        "synthetic-active-work",
        str(uuid4()),
        started_at=now[0],
        lease_expires_at=now[0] + timedelta(seconds=30),
    )
    set_policy(db_session, 2, 1)
    assert asyncio.run(worker.run_once()) is False
    db_session.expire_all()
    assert (
        db_session.get(WorkflowRun, claim.workflow_run_id).execution_token == claim.execution_token
    )
    now[0] += timedelta(seconds=31)
    assert asyncio.run(worker.run_once()) is True
    db_session.expire_all()
    assert (
        db_session.get(WorkflowRun, claim.workflow_run_id).failure_category
        == "retry_attempts_exhausted"
    )
    assert calls == []


@pytest.mark.parametrize("judge_accepts", [True, False])
def test_persistent_worker_uses_updated_policy_in_actual_provider_requests(
    db_session, monkeypatch, judge_accepts
):
    import app.services.feedback.runtime as runtime

    lms, student, task, payload = practice(db_session)
    monkeypatch.setattr(settings, "llm_api_key", SecretStr("synthetic-recording-only"))
    monkeypatch.setattr(settings, "research_enabled", False)
    calls = []

    def transport(req):
        body = json.loads(req.content)
        context = json.loads(body["input"][1]["content"][0]["text"])
        calls.append(req.extensions["timeout"]["read"])
        if body["text"]["format"]["name"] == "quality_judge_output":
            return response(
                {
                    "decision": "pass" if judge_accepts else "fail",
                    "correctness_score": 90,
                    "relevance_score": 90,
                    "grounding_score": 90,
                    "actionability_score": 90,
                    "safety_score": 100,
                    "reason": "Synthetic checked feedback",
                    "unsupported_claims": [],
                    "regeneration_instructions": [],
                }
            )
        return response(
            {
                "response_classification": "not_evaluated",
                "summary": "Synthetic feedback",
                "identified_error": None,
                "explanation": "Compare your reasoning with the cited source.",
                "improvement_actions": ["Explain the evidence."],
                "recommended_next_step": "Reflect on your explanation.",
                "source_references": [r["source_id"] for r in context.get("retrieved_context", [])],
                "simulation_references": [],
            }
        )

    monkeypatch.setattr(
        runtime,
        "ResponsesStructuredLlmClient",
        lambda **kwargs: ResponsesStructuredLlmClient(
            **kwargs, transport=httpx.MockTransport(transport)
        ),
    )
    configured = Settings(_env_file=None, research_enabled=False)
    worker = build_database_worker(
        build_offline_worker_adapters(configured),
        configured_settings=configured,
        engine=db_session.get_bind(),
        session_factory=create_session_factory(db_session.get_bind()),
        now=lambda: datetime.now(UTC) + timedelta(minutes=5),
    )
    identities = []
    for index, timeout in enumerate((11, 4)):
        set_policy(db_session, timeout, (3, 1)[index])
        current = payload.model_copy(update={"idempotency_key": f"runtime-response-{index}"})
        submitted = lms.submit(student, task.id, current)
        identities.append(submitted.id)
        assert asyncio.run(worker.run_once())
        db_session.expire_all()
        stored = db_session.scalar(
            select(WorkflowRun).where(WorkflowRun.submission_id == submitted.id)
        )
        assert stored.current_stage == WorkflowStage.COMPLETED, stored.failure_category
        assert stored.regeneration_count == (0 if judge_accepts else 1)
    assert calls == [11] * (2 if judge_accepts else 4) + [4] * (2 if judge_accepts else 4)
    assert len(set(identities)) == 2
    assert db_session.scalar(select(func.count()).select_from(FeedbackRecord)) == (
        2 if judge_accepts else 6
    )


def test_every_configurable_persistent_pass_reloads_policy(db_session, monkeypatch):
    import app.worker as module

    recorded = []
    for name in (
        "AssessmentEvaluationRecoveryWorker",
        "_GovernedResearchPass",
        "_ContinuationDatabasePass",
        "_TerminalIntegrationDatabasePass",
        "MaterialRecoveryWorker",
    ):
        original = getattr(module, name)

        def observe(*args, _name=name, _original=original, **kwargs):
            configured = kwargs.get("configured_settings") or (
                args[2] if _name == "_GovernedResearchPass" else None
            )
            attempts = (
                configured.max_infrastructure_attempts if configured else kwargs["maximum_attempts"]
            )
            timeout = (
                configured.provider_timeout_seconds
                if configured
                else kwargs.get("provider_timeout_seconds")
            )
            recorded.append((_name, attempts, timeout))
            return _original(*args, **kwargs)

        monkeypatch.setattr(module, name, observe)
    configured = Settings(_env_file=None, research_enabled=False)
    worker = build_database_worker(
        build_offline_worker_adapters(configured),
        configured_settings=configured,
        engine=db_session.get_bind(),
        session_factory=create_session_factory(db_session.get_bind()),
    )
    for timeout, attempts in ((8, 1), (5, 2)):
        set_policy(db_session, timeout, attempts)
        asyncio.run(worker.run_once())
        observed = recorded[-5:]
        assert len(observed) == 5
        assert all(item[1] == attempts for item in observed)
        assert all(item[2] in (None, timeout) for item in observed)
