"""Real API acceptance, process loss and verified restore in one synthetic journey."""

import copy
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from support.learning_loop import seed_learning_loop
from support.person4 import migration_config
from support.task37_fixture import (
    governance_record,
    stored_source_history,
    synthetic_assessor_decision,
)
from support.task37_worker import validate_synthetic_config
from test_task38_benchmark_integration import _stop_owned_processes

from app.api import audit_dependencies, learning_event_dependencies
from app.api.assessment_dependencies import get_assessment_evaluation_executor
from app.api.feedback_dependencies import get_feedback_application, get_feedback_executor
from app.api.security_dependencies import get_request_security_guard
from app.core.config import Settings, settings
from app.core.readiness import MIGRATION_HEAD
from app.db.session import create_db_engine, create_session_factory, get_db_session
from app.main import create_app
from app.models.activity_continuation import ActivityProgress, ActivitySuggestion
from app.models.assessment import AssessmentDecision, AssessmentEvaluationJob
from app.models.audit import AuditAction, AuditEvent
from app.models.continuation import ContinuationJob
from app.models.enums import LearningEventType
from app.models.human_assessment import HumanAssessmentAction, HumanCriterionDecision
from app.models.learner_model import LearnerModelSnapshot
from app.models.learning_evidence import LearningEvidence
from app.models.lms import SubmissionAttempt
from app.models.persistence import (
    FeedbackRecord,
    LearningEvent,
    ResearchEvaluation,
    WorkflowRun,
    WorkflowStage,
)
from app.models.research_governance import ResearchGovernanceEvent
from app.models.terminal_integration import TerminalIntegrationOutbox
from app.services.feedback.application import FeedbackWorkflowApplication
from app.services.feedback.errors import LostWorkflowLeaseError
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository
from app.services.research.governance import (
    GovernanceDenied,
    ResearchGovernanceService,
    research_processing_approved,
)
from scripts.learning_backup import create_bundle, restore_bundle, verify_bundle
from scripts.verify_sqlite_backup import database_manifest

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")

BACKEND = Path(__file__).resolve().parents[1]
ORIGIN = "http://127.0.0.1:4710"


class LostApiDispatch:
    """Simulate the API disappearing after its durable acceptance transaction."""

    async def execute(self, *args, **kwargs):
        pass


def clear_audit_caches():
    audit_dependencies.get_student_audit_tracker.cache_clear()
    audit_dependencies.get_feedback_audit_events.cache_clear()


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def wait_for(predicate, *, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.1)
    raise AssertionError("Task 37 timed out waiting for durable recovery evidence")


def checked(client, method, path, *, headers, payload=None, expected=200):
    response = client.request(method, "/api/v1/" + path, json=payload, headers=headers)
    assert response.status_code == expected, response.text
    return response.json()


def login(client, fixture):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": fixture["student_email"], "password": fixture["student_password"]},
    )
    assert response.status_code == 200, response.text
    token = client.cookies.get(settings.csrf_cookie_name)
    assert token
    return {settings.csrf_header_name: token, "Origin": ORIGIN}


def typed_episode(client, fixture, headers):
    template = json.loads((BACKEND / "tests/fixtures/task38_benchmark/episode.json").read_text())
    payload = copy.deepcopy(template["response"])
    path = f"students/me/tasks/{fixture['task_id']}"
    started = checked(
        client,
        "POST",
        path + "/start",
        headers=headers,
        payload={"task_form_version_id": fixture["form_id"]},
    )
    payload["assessment_work_start_id"] = started["assessment_work_start_id"]
    for stage in ("supported", "transfer"):
        if stage == "transfer":
            transition = checked(
                client, "POST", path + "/episode/transfer", headers=headers, payload=payload
            )
            payload["episode"]["transfer"] = {
                **copy.deepcopy(template["transfer"]),
                "stage_start_id": transition["transfer"]["stage_start_id"],
                "part_id": transition["transfer"]["part_id"],
            }
        transfer = payload["episode"].get("transfer") if stage == "transfer" else None
        part_id = transfer["part_id"] if transfer else "supported"
        stage_id = transfer["stage_start_id"] if transfer else None
        saved = checked(
            client,
            "POST",
            path + "/episode/checkpoints",
            headers=headers,
            payload={"response": payload, "part_id": part_id, "stage_start_id": stage_id},
        )
        payload = {
            k: v for k, v in saved["draft"].items() if k not in {"id", "task_id", "updated_at"}
        }
        circuit = transfer["content"]["circuit"] if transfer else payload["circuit"]
        simulation = checked(
            client,
            "POST",
            "students/me/simulate",
            headers=headers,
            payload={
                "task_id": fixture["task_id"],
                **circuit,
                "shots": 1024,
                "seed": 42,
                "prediction_checkpoint_id": saved["checkpoint_id"],
                "episode_stage_start_id": stage_id,
                "episode_part_id": part_id,
                "request_key": "task37-simulation-" + stage,
            },
        )
        assert simulation["status"] == "completed"
        evidence = (
            payload["episode"]["transfer"]["process"]
            if transfer
            else payload["episode"]["supported"]
        )
        evidence["simulation_references"] = [
            {
                "run_id": simulation["run_id"],
                "circuit_version_id": simulation["circuit_version_id"],
            }
        ]
    checked(client, "PUT", path + "/draft", headers=headers, payload=payload)
    saved = checked(client, "GET", path + "/draft", headers=headers)
    assert saved["episode"] == payload["episode"]
    return payload


def assert_denied_research(session, study, fixture):
    policy = ResearchGovernanceService(session)
    with pytest.raises(GovernanceDenied, match="consent_inactive"):
        policy.participant(
            study,
            fixture["course_id"],
            fixture["student_id"],
            fields={"case_id"},
            purposes={"technical_pair"},
        )
    with pytest.raises(GovernanceDenied, match="grant_inactive"):
        policy.grant(study, fixture["course_id"], fixture["teacher_id"], {"case_id"})
    assert research_processing_approved() is False


@pytest.mark.parametrize(
    "changed",
    [
        "outside_database",
        "outside_uploads",
        "research",
        "provider",
        "credential",
        "missing_database",
    ],
)
def test_task37_worker_refuses_nonisolated_configuration(tmp_path, changed):
    (tmp_path / "study.sqlite").touch()
    (tmp_path / "uploads").mkdir()
    fields = dict(
        database_url="sqlite:///" + (tmp_path / "study.sqlite").as_posix(),
        rag_upload_dir=str(tmp_path / "uploads"),
        app_env="test",
        research_enabled=False,
        llm_provider="local",
        llm_api_key=None,
        llm_api_base_url="https://127.0.0.1:1",
    )
    validate_synthetic_config(Settings(_env_file=None, **fields), tmp_path)
    if changed == "outside_database":
        fields["database_url"] = "sqlite:///" + (tmp_path.parent / "unrelated.db").as_posix()
    elif changed == "outside_uploads":
        fields["rag_upload_dir"] = str(tmp_path.parent)
    elif changed == "research":
        fields["research_enabled"] = True
    elif changed == "provider":
        fields["llm_provider"] = "openai"
    elif changed == "credential":
        fields["llm_api_key"] = "synthetic-unwanted-key"
    else:
        (tmp_path / "study.sqlite").unlink()
    with pytest.raises(ValueError, match="isolated synthetic"):
        validate_synthetic_config(Settings(_env_file=None, **fields), tmp_path)


def test_task37_accepted_episode_recovers_once_and_restores_all_history(
    tmp_path_factory, monkeypatch, request
):
    # Keep the verified bundle paths short enough for Windows file APIs.
    tmp_path = tmp_path_factory.mktemp("recovery")
    database, uploads = tmp_path / "study.sqlite", tmp_path / "uploads"
    uploads.mkdir()
    database_url = "sqlite:///" + database.as_posix()
    command.upgrade(migration_config(database_url), "head")
    engine = create_db_engine(database_url)
    request.addfinalizer(engine.dispose)
    request.addfinalizer(get_request_security_guard.cache_clear)
    request.addfinalizer(clear_audit_caches)
    factory = create_session_factory(engine)
    for dependency in (audit_dependencies, learning_event_dependencies):
        monkeypatch.setattr(dependency, "SessionLocal", factory)
    clear_audit_caches()
    for name, value in {
        "llm_api_key": None,
        "llm_provider": "local",
        "llm_api_base_url": "https://127.0.0.1:1",
        "research_enabled": False,
        "rag_upload_dir": str(uploads),
        "frontend_origin": ORIGIN,
        "cors_allowed_origins": ORIGIN,
        "csrf_enabled": True,
        "rate_limit_enabled": True,
        "session_cookie_secure": False,
        "session_secret_key": SecretStr(secrets.token_urlsafe(48)),
        "learning_event_pseudonym_secret": SecretStr(secrets.token_urlsafe(48)),
        "feedback_job_lease_seconds": 30,
    }.items():
        monkeypatch.setattr(settings, name, value)
    get_request_security_guard.cache_clear()
    with factory() as session:
        fixture = seed_learning_loop(session)
        source_hashes = stored_source_history(session, fixture["course_id"], uploads)
        study = governance_record(session, fixture)
        assert_denied_research(session, study, fixture)
        assert session.scalar(select(func.count()).select_from(SubmissionAttempt)) == 0

    app = create_app()

    def storage():
        with factory() as session:
            yield session

    def dispatch(session: Session = Depends(get_db_session)):
        return FeedbackWorkflowApplication(
            SqlAlchemyFeedbackWorkflowRepository(session), lease_duration=timedelta(milliseconds=1)
        )

    app.dependency_overrides[get_db_session] = storage
    app.dependency_overrides[get_feedback_application] = dispatch
    app.dependency_overrides[get_feedback_executor] = LostApiDispatch
    # Simulate losing both post-acceptance tasks. In particular, never let the
    # default assessment executor open its separate module-global database.
    app.dependency_overrides[get_assessment_evaluation_executor] = LostApiDispatch
    environment = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(BACKEND), str(BACKEND / "tests")]),
        "APP_ENV": "test",
        "DATABASE_URL": database_url,
        "RAG_UPLOAD_DIR": str(uploads),
        "LLM_API_KEY": "",
        "LLM_PROVIDER": "local",
        "LLM_MODEL": "local-template",
        "LLM_API_BASE_URL": "https://127.0.0.1:1",
        "RESEARCH_ENABLED": "false",
        "WORKER_ADAPTER_FACTORY": "app.worker:build_offline_worker_adapters",
        "WORKER_STALE_SECONDS": "30",
        "WORKER_HEARTBEAT_SECONDS": "1",
        "WORKER_POLL_SECONDS": "0.1",
        "FEEDBACK_JOB_LEASE_SECONDS": "30",
        "LEARNING_EVENT_PSEUDONYM_SECRET": settings.learning_event_pseudonym_secret.get_secret_value(),
    }
    processes, logs = [], []

    def launch(paused):
        log = (tmp_path / ("paused.log" if paused else "resumed.log")).open("w", encoding="utf-8")
        logs.append(log)
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "support.task37_worker",
                "--directory",
                str(tmp_path),
                *(["--pause"] if paused else []),
            ],
            cwd=tmp_path,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        processes.append(process)
        return process

    try:
        with TestClient(app, base_url=ORIGIN) as client:
            headers = login(client, fixture)
            payload = typed_episode(client, fixture, headers)
            accepted_before = datetime.now(UTC)
            response = checked(
                client,
                "POST",
                f"students/me/tasks/{fixture['task_id']}/submissions",
                headers=headers,
                payload={**payload, "idempotency_key": "task37-one-api-submission"},
                expected=201,
            )
            response_id = response["id"]
            with factory() as session:
                saved_response = session.get(SubmissionAttempt, response_id)
                frozen_episode = copy.deepcopy(saved_response.episode)
                accepted_at = utc(saved_response.submitted_at)
                assert accepted_before <= accepted_at <= datetime.now(UTC)
                initial = session.scalar(
                    select(WorkflowRun).where(WorkflowRun.submission_id == response_id)
                )
                workflow_id = initial.id
                assert initial.execution_attempt_count == 1
            paused = launch(True)

            def claimed():
                assert paused.poll() is None, "Paused worker exited; inspect paused.log"
                marker = tmp_path / "claimed.json"
                if not marker.exists():
                    return False
                try:
                    return json.loads(marker.read_text())
                except json.JSONDecodeError:
                    return False

            assert wait_for(claimed) == {"submission_id": response_id, "workflow_id": workflow_id}
            with factory() as session:
                claimed_work = session.get(WorkflowRun, workflow_id)
                stale_token = claimed_work.execution_token
                assert stale_token and claimed_work.execution_attempt_count == 2
                claimed_at = utc(claimed_work.started_at)
                assert accepted_at <= claimed_at
                assert session.scalar(select(func.count()).select_from(FeedbackRecord)) == 0
            paused.kill()
            paused.wait(timeout=10)
            # Respect real ownership and job leases. No database timestamp is rewritten.
            reclaim_at = datetime.now(UTC) + timedelta(seconds=31)
            wait_for(lambda: datetime.now(UTC) >= reclaim_at, timeout=35)
            resumed = launch(False)

            def recovered():
                assert resumed.poll() is None, "Recovery worker exited; inspect resumed.log"
                with factory() as session:
                    row = session.get(WorkflowRun, workflow_id)
                    progress = session.get(ActivityProgress, workflow_id)
                    suggestion = session.get(ActivitySuggestion, workflow_id)
                    continuation = session.get(ContinuationJob, workflow_id)
                    assessment = session.scalar(
                        select(AssessmentEvaluationJob).where(
                            AssessmentEvaluationJob.response_version_id == response_id
                        )
                    )
                    return (
                        row.current_stage is WorkflowStage.COMPLETED
                        and progress is not None
                        and suggestion is not None
                        and continuation is not None
                        and continuation.state.value == "completed"
                        and assessment is not None
                        and assessment.state.value == "review_required"
                    )

            wait_for(recovered)
            feedback_path = f"submissions/{response_id}/feedback"
            feedback = checked(client, "GET", feedback_path, headers=headers)
            assert feedback["status"] == "validated"
            assert checked(client, "GET", feedback_path, headers=headers) == feedback
            result_path = f"students/me/responses/{response_id}/result"
            assert checked(client, "GET", result_path, headers=headers)["result"] is None
            with factory() as session:
                workflow = session.get(WorkflowRun, workflow_id)
                assert workflow.execution_attempt_count == 3
                recovered_at, completed_at = utc(workflow.started_at), utc(workflow.completed_at)
                assert accepted_at <= claimed_at <= recovered_at <= completed_at
                with pytest.raises(LostWorkflowLeaseError):
                    SqlAlchemyFeedbackWorkflowRepository(session).record_stage(
                        workflow_id, WorkflowStage.GENERATING, execution_token=stale_token
                    )
                for model in (
                    SubmissionAttempt,
                    WorkflowRun,
                    FeedbackRecord,
                    LearnerModelSnapshot,
                    ActivityProgress,
                    ActivitySuggestion,
                    ContinuationJob,
                ):
                    assert session.scalar(select(func.count()).select_from(model)) == 1, (
                        model.__name__
                    )
                assert session.scalar(select(func.count()).select_from(ResearchEvaluation)) == 0
                feedback_views = list(
                    session.scalars(
                        select(LearningEvent).where(
                            LearningEvent.event_type == LearningEventType.FEEDBACK_VIEW
                        )
                    )
                )
                assert len(feedback_views) == 1
                feedback_view_id = feedback_views[0].id
                audit_view_ids = list(
                    session.scalars(
                        select(AuditEvent.id).where(
                            AuditEvent.action == AuditAction.FEEDBACK_VIEWED
                        )
                    )
                )
                assert len(audit_view_ids) == 1
                outbox = list(session.scalars(select(TerminalIntegrationOutbox)))
                assert len(outbox) == 1 and outbox[0].state.value == "completed"
                assert outbox[0].integration_type.value == "continuation"
                assert session.get(SubmissionAttempt, response_id).episode == frozen_episode
                evidence = list(session.scalars(select(LearningEvidence)))
                evidence_ids = sorted(item.id for item in evidence)
                assert {e.evidence_type.value for e in evidence} >= {
                    "RESPONSE",
                    "PREDICTION",
                    "EXPLANATION",
                    "REASONING",
                    "REFLECTION",
                    "TRANSFER",
                }
                snapshot_id = session.get(ActivityProgress, workflow_id).snapshot_id
                synthetic_assessor_decision(session, fixture, response_id)
                decision = session.scalar(select(AssessmentDecision))
                decision_id = decision.id
                assert session.scalar(select(func.count()).select_from(AssessmentDecision)) == 1
                assert session.scalar(select(func.count()).select_from(HumanAssessmentAction)) == 1
                human_action_id = session.scalar(select(HumanAssessmentAction.id))
                human_criterion_ids = sorted(session.scalars(select(HumanCriterionDecision.id)))
                assert len(human_criterion_ids) == 3
                assert_denied_research(session, study, fixture)
            released_result = checked(client, "GET", result_path, headers=headers)
            assert released_result["result"] == "PASS"
            # Human review changes the release context. Cached assessed feedback
            # from before that action must be withheld, independently of restore.
            post_review_feedback = checked(client, "GET", feedback_path, headers=headers)
            assert post_review_feedback["status"] == "fallback"
            assert (
                post_review_feedback["feedback"]["feedback_id"]
                == feedback["feedback"]["feedback_id"]
            )
            progress_page = checked(
                client, "GET", f"progress/{fixture['course_id']}", headers=headers
            )
            assert datetime.fromisoformat(
                progress_page["generated_at"].replace("Z", "+00:00")
            ).utcoffset() == timedelta(0)
    finally:
        try:
            _stop_owned_processes(processes, logs)
        finally:
            app.dependency_overrides.clear()
            get_request_security_guard.cache_clear()
            engine.dispose()

    before = database_manifest(database)
    bundle = create_bundle(database, uploads, tmp_path / "backups")
    manifest = verify_bundle(bundle)
    assert manifest["database"]["migration_head"] == MIGRATION_HEAD
    assert {key: value["sha256"] for key, value in manifest["uploads"].items()} == source_hashes
    restored = restore_bundle(bundle, tmp_path / "restored")
    restored_database = restored / "database.sqlite3"
    assert database_manifest(restored_database) == before
    for key, digest in source_hashes.items():
        assert hashlib.sha256((restored / "uploads" / key).read_bytes()).hexdigest() == digest
    restored_engine = create_db_engine("sqlite:///" + restored_database.as_posix())
    try:
        restored_factory = create_session_factory(restored_engine)
        for dependency in (audit_dependencies, learning_event_dependencies):
            monkeypatch.setattr(dependency, "SessionLocal", restored_factory)
        clear_audit_caches()
        with restored_factory() as session:
            assert session.get(SubmissionAttempt, response_id).episode == frozen_episode
            assert session.get(WorkflowRun, workflow_id).current_stage is WorkflowStage.COMPLETED
            assert session.get(ActivityProgress, workflow_id).snapshot_id == snapshot_id
            assert session.get(AssessmentDecision, decision_id).result.value == "PASS"
            assert sorted(session.scalars(select(LearningEvidence.id))) == evidence_ids
            assert session.get(LearningEvent, feedback_view_id) is not None
            assert session.get(AuditEvent, audit_view_ids[0]) is not None
            assert session.get(HumanAssessmentAction, human_action_id) is not None
            assert sorted(session.scalars(select(HumanCriterionDecision.id))) == human_criterion_ids
            assert session.scalar(select(func.count()).select_from(ResearchGovernanceEvent)) == 7
            assert_denied_research(session, study, fixture)
            assert session.execute(text("PRAGMA foreign_key_check")).all() == []
        with restored_engine.begin() as connection:
            for statement, guard in (
                (
                    "UPDATE assessment_decisions SET result='INCOMPLETE'",
                    "matching assessor review",
                ),
                ("DELETE FROM human_assessment_actions", "append-only"),
                ("UPDATE human_criterion_decisions SET reason='altered'", "append-only"),
                ("DELETE FROM research_governance_events", "immutable"),
                ("UPDATE source_revisions SET source_label='altered'", "append-only"),
            ):
                with pytest.raises(IntegrityError, match=guard):
                    connection.execute(text(statement))

        # Read restored results through the same real API routes on the restored storage.
        def restored_storage():
            with restored_factory() as session:
                yield session

        restored_app = create_app()
        monkeypatch.setattr(settings, "rag_upload_dir", str(restored / "uploads"))
        restored_app.dependency_overrides[get_db_session] = restored_storage
        with TestClient(restored_app, base_url=ORIGIN) as client:
            headers = login(client, fixture)
            assert checked(client, "GET", feedback_path, headers=headers) == post_review_feedback
            assert checked(client, "GET", result_path, headers=headers) == released_result
        with restored_factory() as session:
            assert list(
                session.scalars(
                    select(LearningEvent.id).where(
                        LearningEvent.event_type == LearningEventType.FEEDBACK_VIEW
                    )
                )
            ) == [feedback_view_id]
            assert (
                list(
                    session.scalars(
                        select(AuditEvent.id).where(
                            AuditEvent.action == AuditAction.FEEDBACK_VIEWED
                        )
                    )
                )
                == audit_view_ids
            )
        restored_app.dependency_overrides.clear()
    finally:
        get_request_security_guard.cache_clear()
        restored_engine.dispose()
    (tmp_path / "task37-receipt.json").write_text(
        json.dumps(
            {
                "evidence_class": "synthetic local crash/restart/restore only",
                "submission_posts": 1,
                "workflow_id": workflow_id,
                "response_id": response_id,
                "snapshot_id": snapshot_id,
                "decision_id": decision_id,
                "evidence_ids": evidence_ids,
                "feedback_view_id": feedback_view_id,
                "audit_view_ids": audit_view_ids,
                "human_action_id": human_action_id,
                "human_criterion_ids": human_criterion_ids,
                "recovered_feedback_status": feedback["status"],
                "post_review_feedback_status": post_review_feedback["status"],
                "chronology_utc": {
                    "accepted": accepted_at.isoformat(),
                    "claimed": claimed_at.isoformat(),
                    "recovered": recovered_at.isoformat(),
                    "completed": completed_at.isoformat(),
                },
                "migration_head": MIGRATION_HEAD,
                "database_sha256": manifest["database_sha256"],
                "source_sha256": source_hashes,
                "research_processing_approved": research_processing_approved(),
                "later_withdrawal_reconciliation": "A backup cannot know future governance events; reconcile authoritative later records before research use.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
