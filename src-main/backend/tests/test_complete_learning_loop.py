"""Connected episode and shipped-worker regression, with isolated synthetic approvals."""

import asyncio
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from support.learning_loop import seed_learning_loop
from support.task16 import setup_task16_episode
from test_task14_lifecycle import complete, supported

from app.core.config import Settings, settings
from app.db.session import create_session_factory
from app.models.activity_continuation import ActivityProgress, ActivitySuggestion
from app.models.learner_model import LearnerModelSnapshot
from app.models.learning_evidence import LearningEvidence
from app.models.persistence import FeedbackRecord, WorkflowRun
from app.schemas.lms import SubmissionCreate
from app.worker import build_database_worker, build_offline_worker_adapters

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


@pytest.fixture(autouse=True)
def local_providers_only(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", None)
    monkeypatch.setattr(settings, "research_enabled", False)


def test_complete_episode_reaches_checked_feedback_and_model_after_restart(db_session, tmp_path):
    lms, student, task, started = setup_task16_episode(db_session)
    unused = lms.episode_checkpoint(student, task.id, supported(started), "supported", None)
    payload = complete(lms, student, task, started)
    response = lms.submit(
        student,
        task.id,
        SubmissionCreate(**payload.model_dump(), idempotency_key="complete-loop-response"),
    )
    workflow = db_session.scalar(
        select(WorkflowRun).where(WorkflowRun.submission_id == response.id)
    )
    identity = workflow.id
    factory = create_session_factory(db_session.get_bind())
    config = Settings(_env_file=None, research_enabled=False)
    now = datetime.now(UTC) + timedelta(minutes=10)
    marker = tmp_path / "model-committed"
    backend = Path(__file__).resolve().parents[1]
    environment = {
        **os.environ,
        "PYTHONPATH": str(backend),
        "LLM_API_KEY": "",
        "RESEARCH_ENABLED": "false",
        "MATERIAL_SCAN_POLICY": "required",
        "MATERIAL_SCAN_POLICY_VERSION": "synthetic-policy-v1",
        "LEARNING_EVENT_PSEUDONYM_SECRET": "learning-loop-test-only-pseudonym-secret-32-bytes",
    }
    with (tmp_path / "interrupted-worker.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "tests/support/learning_loop_worker.py",
                str(db_session.get_bind().url),
                now.isoformat(),
                str(marker),
            ],
            cwd=backend,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            deadline = time.monotonic() + 30
            while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.1)
            assert marker.exists(), "Worker did not reach its committed model receipt"
            db_session.expire_all()
            saved_snapshot = db_session.get(ActivityProgress, identity).snapshot_id
            assert saved_snapshot is not None
            assert db_session.get(ActivitySuggestion, identity) is None
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
    # Reclaim the terminated worker and continuation leases without changing history.
    now += timedelta(minutes=10)
    worker = build_database_worker(
        build_offline_worker_adapters(config),
        configured_settings=config,
        engine=db_session.get_bind(),
        session_factory=factory,
        now=lambda: now,
    )
    for _ in range(4):
        asyncio.run(worker.run_once())
    db_session.expire_all()
    workflow = db_session.get(WorkflowRun, identity)
    assert workflow.current_stage.value == "completed"
    feedback = db_session.scalar(
        select(FeedbackRecord).where(FeedbackRecord.workflow_run_id == identity)
    )
    assert feedback is not None and feedback.status.value == "accepted"
    progress = db_session.get(ActivityProgress, identity)
    assert progress is not None and progress.state == "observations_recorded"
    assert progress.snapshot_id == saved_snapshot
    assert len(list(db_session.scalars(select(LearnerModelSnapshot)))) == 1
    assert db_session.get(LearnerModelSnapshot, progress.snapshot_id) is not None
    assert db_session.get(ActivitySuggestion, identity) is not None
    evidence = db_session.scalars(
        select(LearningEvidence).where(LearningEvidence.task_id == task.id)
    ).all()
    assert {item.evidence_type.value for item in evidence} >= {
        "RESPONSE",
        "PREDICTION",
        "REASONING",
        "EXPLANATION",
        "REFLECTION",
        "TRANSFER",
    }
    assert {
        item.id for item in evidence if item.source_interaction_id != unused["checkpoint_id"]
    } <= set(progress.evidence_ids), {
        item.evidence_type.value for item in evidence if item.id not in progress.evidence_ids
    }
    assert all(
        item.id not in progress.evidence_ids
        for item in evidence
        if item.source_interaction_id == unused["checkpoint_id"]
    )


def test_approved_quantum_loop_fixture_has_no_prebuilt_results(db_session):
    from app.models.assessment import AssessmentDecision
    from app.models.user import User
    from app.services.lms import LmsService

    fixture = seed_learning_loop(db_session)
    assert fixture["next_task_id"] != fixture["task_id"]
    assert db_session.scalar(select(AssessmentDecision)) is None
    assert db_session.scalar(select(FeedbackRecord)) is None
    student = db_session.get(User, fixture["student_id"])
    lms = LmsService(db_session)
    lms.student_dashboard(student)
    visible = lms.get_task_for_actor(student, fixture["task_id"]).model_dump_json().lower()
    assert "x followed by two hadamard gates" not in visible
    assert "the final state is one" not in visible
    assert "zero is restored" not in visible


def test_full_quantum_loop_revision_simulation_and_human_result(db_session):
    from app.domain.assessment import AssessmentResult, CriterionDecision
    from app.models.assessment import AssessmentAttempt, AssessmentDecision
    from app.models.escalation import EscalationCase
    from app.models.lms import SubmissionAttempt
    from app.models.persistence import LearningTask
    from app.models.user import User
    from app.schemas.activity_continuation import ActivityAction
    from app.schemas.episode import EpisodePayloadV1
    from app.schemas.lms import DraftWrite
    from app.schemas.student import SimulationRequest
    from app.services.assessment.access import RoleAssignmentService
    from app.services.assessment.human_review import (
        HumanAssessmentRequest,
        HumanAssessmentService,
        HumanCriterionInput,
    )
    from app.services.assessment.learner_results import LearnerResultService
    from app.services.continuation.activity import ActivityService
    from app.services.episode_responses import SqlAlchemyFrozenResponseReader
    from app.services.lms import LmsService

    fixture = seed_learning_loop(db_session)
    student = db_session.get(User, fixture["student_id"])
    teacher = db_session.get(User, fixture["teacher_id"])
    task = db_session.get(LearningTask, fixture["task_id"])
    lms = LmsService(db_session)
    started = lms.start_assessment_work(student, task.id, fixture["form_id"])
    payload = supported(started)
    saved = lms.episode_checkpoint(student, task.id, payload, "supported", None)
    payload = DraftWrite.model_validate(
        saved["draft"].model_dump(exclude={"id", "task_id", "updated_at"})
    )
    single = lms.simulate_student_circuit(
        student,
        SimulationRequest(
            task_id=task.id,
            qubits=1,
            operations=[{"gate": "h", "targets": [0]}],
            prediction_checkpoint_id=saved["checkpoint_id"],
            request_key="loop-single-h",
        ),
    )
    assert single["status"] == "completed"
    assert single["result"]["probabilities"] == pytest.approx({"0": 0.5, "1": 0.5}, abs=1e-12)
    raw = payload.episode.model_dump(mode="json")
    raw["supported"]["simulation_references"] = [
        {"run_id": single["run_id"], "circuit_version_id": single["circuit_version_id"]}
    ]
    payload = payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(raw)})
    state = lms.episode_transfer(student, task.id, payload)
    transfer = state["transfer"]
    circuit = {
        "qubits": 1,
        "operations": [
            {"gate": "x", "targets": [0]},
            {"gate": "h", "targets": [0]},
            {"gate": "h", "targets": [0]},
        ],
    }
    raw["transfer"] = {
        "stage_start_id": transfer["stage_start_id"],
        "part_id": transfer["part_id"],
        "content": {"answer": "The fresh circuit ends in state one.", "circuit": circuit},
        "process": {
            "prediction": {"answer": "One with probability one."},
            "reasoning": "X prepares one, then H squared restores that input.",
            "explanation": "The output is one after applying all three gates.",
            "reflection": "This differs from a single H.",
        },
    }
    payload = payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(raw)})
    checkpoint = lms.episode_checkpoint(
        student, task.id, payload, transfer["part_id"], transfer["stage_start_id"]
    )
    payload = DraftWrite.model_validate(
        checkpoint["draft"].model_dump(exclude={"id", "task_id", "updated_at"})
    )
    fresh = lms.simulate_student_circuit(
        student,
        SimulationRequest(
            task_id=task.id,
            **circuit,
            prediction_checkpoint_id=checkpoint["checkpoint_id"],
            episode_stage_start_id=transfer["stage_start_id"],
            episode_part_id=transfer["part_id"],
            request_key="loop-fresh-x-h-h",
        ),
    )
    assert fresh["status"] == "completed"
    assert fresh["result"]["probabilities"]["1"] == pytest.approx(1, abs=1e-12)
    raw = payload.episode.model_dump(mode="json")
    raw["transfer"]["process"]["simulation_references"] = [
        {"run_id": fresh["run_id"], "circuit_version_id": fresh["circuit_version_id"]}
    ]
    payload = payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(raw)})
    factory = create_session_factory(db_session.get_bind())
    config = Settings(_env_file=None, research_enabled=False)
    clock = datetime.now(UTC) + timedelta(minutes=10)
    worker = build_database_worker(
        build_offline_worker_adapters(config),
        configured_settings=config,
        engine=db_session.get_bind(),
        session_factory=factory,
        now=lambda: clock,
    )
    ids = []
    for index in range(2):
        if ids:
            raw["supported"]["revision"] = {
                "previous_response_version_id": ids[0],
                "reason": "I reviewed the checked feedback.",
            }
            raw["supported"]["reflection"] = "Exact probabilities differ from sampled counts."
            payload = payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(raw)})
        command = SubmissionCreate(
            **payload.model_dump(), idempotency_key=f"loop-submission-{index}"
        )
        response = lms.submit(student, task.id, command)
        ids.append(response.id)
        assert lms.submit(student, task.id, command).id == response.id
        for _ in range(3):
            asyncio.run(worker.run_once())
        db_session.expire_all()
        workflow = db_session.scalar(
            select(WorkflowRun).where(WorkflowRun.submission_id == response.id)
        )
        assert workflow.current_stage.value == "completed"
        feedback = db_session.scalar(
            select(FeedbackRecord).where(FeedbackRecord.workflow_run_id == workflow.id)
        )
        assert feedback.status.value == "accepted" and feedback.source_references
        progress = db_session.get(ActivityProgress, workflow.id)
        assert progress.state == "observations_recorded"
        suggestion = ActivityService(db_session).read(student, workflow.id)
        assert suggestion.next_task_id == fixture["next_task_id"]
        assert suggestion.uncertainty == 1
        assert LearnerResultService(db_session).read(student, response.id).result is None
        escalation = db_session.scalar(
            select(EscalationCase)
            .join(AssessmentAttempt, AssessmentAttempt.id == EscalationCase.source_id)
            .where(AssessmentAttempt.response_version_id == response.id)
        )
        assert escalation.queue_kind == "ASSESSOR"
        assert escalation.trigger == "HUMAN_EVALUATION_REQUIRED"
    assert len(list(db_session.scalars(select(LearnerModelSnapshot)))) == 2
    assert db_session.get(SubmissionAttempt, ids[0]).episode["supported"].get("revision") is None
    assert (
        db_session.get(SubmissionAttempt, ids[1]).episode["supported"]["revision"][
            "previous_response_version_id"
        ]
        == ids[0]
    )
    assert db_session.scalar(select(AssessmentDecision)) is None
    action = ActivityService(db_session).act(
        student,
        workflow.id,
        ActivityAction(expected_version=0, request_key="loop-choice", action="accept"),
    )
    assert action.next_task_id == fixture["next_task_id"]
    attempt = db_session.scalar(
        select(AssessmentAttempt).where(AssessmentAttempt.response_version_id == ids[1])
    )
    human = HumanAssessmentService(
        db_session,
        assignments=RoleAssignmentService(db_session),
        reader=SqlAlchemyFrozenResponseReader(db_session),
    )
    detail = human.detail(teacher, assessment_attempt_id=attempt.id)
    request = HumanAssessmentRequest(
        idempotency_key="loop-human-review",
        expected_token=detail["expected_token"],
        reason="Synthetic human checked every frozen criterion.",
        criteria=tuple(
            HumanCriterionInput(
                item["criterion_version_id"],
                CriterionDecision.MET,
                "The frozen response demonstrates this criterion.",
                (ids[1],),
            )
            for item in detail["criteria"]
        ),
    )
    receipt = human.finalise(teacher, assessment_attempt_id=attempt.id, request=request)
    assert receipt["result"] == AssessmentResult.PASS
    assert human.finalise(teacher, assessment_attempt_id=attempt.id, request=request)["replayed"]
    assert LearnerResultService(db_session).read(student, ids[1]).result == AssessmentResult.PASS
    assert LearnerResultService(db_session).read(student, ids[0]).result is None
    assert all(
        not hasattr(db_session.get(SubmissionAttempt, identity), "score") for identity in ids
    )
