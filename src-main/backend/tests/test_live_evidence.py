"""Operational evidence through the existing learner command boundary."""

from sqlalchemy import select
from test_task14_lifecycle import complete, setup_episode

from app.models.learning_evidence import LearningEvidence
from app.schemas.lms import SubmissionCreate


def test_episode_commands_capture_ordered_evidence_and_replay(db_session):
    lms, student, task, started = setup_episode(db_session)
    payload = complete(lms, student, task, started)
    command = SubmissionCreate(**payload.model_dump(), idempotency_key="live-evidence")
    response = lms.submit(student, task.id, command)
    page = lms.evidence_history(student, task.id)
    kinds = {item.evidence_type.value for item in page.items}
    assert {"PREDICTION", "RESPONSE", "REASONING", "EXPLANATION", "REFLECTION", "TRANSFER"} <= kinds
    assert [item.occurred_at for item in page.items] == sorted(
        item.occurred_at for item in page.items
    )
    assert all(item.outcome_id == task.learning_outcome_id for item in page.items)
    assert all(item.task_id == task.id for item in page.items)
    before = list(db_session.scalars(select(LearningEvidence.id)))
    assert lms.submit(student, task.id, command).id == response.id
    assert list(db_session.scalars(select(LearningEvidence.id))) == before
    assert response.score is None


def test_failed_evidence_write_rolls_back_submission_and_keeps_prior_history(
    db_session, monkeypatch
):
    import pytest

    from app.models.lms import SubmissionAttempt
    from app.services.evidence.repository import SqlAlchemyEvidenceRepository
    from app.services.evidence.safety import EvidencePersistenceError

    lms, student, task, started = setup_episode(db_session)
    payload = complete(lms, student, task, started)
    before = [item.evidence_id for item in lms.evidence_history(student, task.id).items]
    original = SqlAlchemyEvidenceRepository.capture

    def unavailable(self, capture, *, commit=True):
        if capture.record.evidence_type.value == "REASONING":
            raise EvidencePersistenceError("temporary evidence fault")
        return original(self, capture, commit=commit)

    with monkeypatch.context() as scoped:
        scoped.setattr(SqlAlchemyEvidenceRepository, "capture", unavailable)
        with pytest.raises(EvidencePersistenceError):
            lms.submit(
                student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="retry")
            )
        db_session.rollback()
    assert [item.evidence_id for item in lms.evidence_history(student, task.id).items] == before
    assert (
        db_session.scalar(select(SubmissionAttempt).where(SubmissionAttempt.task_id == task.id))
        is None
    )
    assert lms.get_draft(student, task.id) is not None
    lms.submit(student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="retry"))
    assert len(lms.evidence_history(student, task.id).items) > len(before)


def test_mounted_submission_failure_rolls_back_request_transaction(db_session, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session

    from app.api.dependencies.authentication import get_current_user
    from app.db.session import get_db
    from app.main import create_app
    from app.models.lms import SubmissionAttempt
    from app.models.user import User
    from app.services.evidence.repository import SqlAlchemyEvidenceRepository
    from app.services.evidence.safety import EvidencePersistenceError
    from app.services.lms import LmsService

    lms, student, task, started = setup_episode(db_session)
    payload = complete(lms, student, task, started)
    expected_history = [item.evidence_id for item in lms.evidence_history(student, task.id).items]
    original = SqlAlchemyEvidenceRepository.capture

    def unavailable(self, capture, *, commit=True):
        if capture.record.evidence_type.value == "REASONING":
            raise EvidencePersistenceError("temporary evidence fault")
        return original(self, capture, commit=commit)

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: student
    with monkeypatch.context() as scoped, TestClient(app) as client:
        scoped.setattr(SqlAlchemyEvidenceRepository, "capture", unavailable)
        response = client.post(
            f"/api/v1/students/me/tasks/{task.id}/submissions",
            json=SubmissionCreate(
                **payload.model_dump(), idempotency_key="mounted-failure"
            ).model_dump(mode="json"),
        )
    assert response.status_code == 503
    with Session(db_session.get_bind()) as inspect:
        assert (
            inspect.scalar(select(SubmissionAttempt).where(SubmissionAttempt.task_id == task.id))
            is None
        )
        assert [
            item.evidence_id
            for item in LmsService(inspect)
            .evidence_history(inspect.get(User, student.id), task.id)
            .items
        ] == expected_history


def test_support_is_explicit_separate_and_replay_safe(db_session):
    from app.schemas.episode import EpisodeHelpUseWrite

    lms, student, task, started = setup_episode(db_session)
    for kind in ("conceptual_hint", "accessibility"):
        command = EpisodeHelpUseWrite(
            assessment_work_start_id=started.assessment_work_start_id,
            kind=kind,
            item_index=0,
            request_key=kind,
        )
        lms.episode_help_use(student, task.id, command)
        lms.episode_help_use(student, task.id, command)
    rows = lms.evidence_history(student, task.id).items
    assert len(rows) == 2
    assert rows[0].evidence_type.value == "HINT"
    assert rows[0].instructional_support_level == 2
    assert rows[1].access_support_state.value == "PROVIDED"
    assert rows[1].instructional_support_level == 0


def test_history_pages_do_not_write_and_preserve_exact_protected_content(db_session):
    import json

    from app.models.learning_evidence import EvidenceArtifact

    lms, student, task, started = setup_episode(db_session)
    payload = complete(lms, student, task, started)
    submitted = lms.submit(
        student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="history")
    )
    before = list(db_session.scalars(select(LearningEvidence.id)))
    first = lms.evidence_history(student, task.id, limit=1)
    assert first.next_offset == 1
    rest = lms.evidence_history(student, task.id, offset=1)
    assert len(rest.items) + 1 == len(before)
    assert list(db_session.scalars(select(LearningEvidence.id))) == before
    row = db_session.scalar(
        select(LearningEvidence).where(
            LearningEvidence.response_version_id == submitted.id,
            LearningEvidence.evidence_type == "RESPONSE",
        )
    )
    content = json.loads(db_session.get(EvidenceArtifact, row.artifact_id).content)
    assert content["value"]["answer"] == payload.answer
    assert content["context"]["assessment_work_start_id"] == started.assessment_work_start_id
    assert content["context"]["task_form_version_id"]
    assert "Supported answer" not in first.model_dump_json() + rest.model_dump_json()


def test_hints_link_supported_evidence_but_not_independent_transfer(db_session):
    from app.schemas.episode import EpisodeHelpUseWrite

    lms, student, task, started = setup_episode(db_session)
    lms.episode_help_use(
        student,
        task.id,
        EpisodeHelpUseWrite(
            assessment_work_start_id=started.assessment_work_start_id,
            kind="conceptual_hint",
            item_index=0,
            request_key="hint",
        ),
    )
    payload = complete(lms, student, task, started)
    lms.submit(
        student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="assisted")
    )
    rows = lms.evidence_history(student, task.id).items
    hint = next(row for row in rows if row.evidence_type.value == "HINT")
    response = next(row for row in rows if row.evidence_type.value == "RESPONSE")
    transfer = next(row for row in rows if row.evidence_type.value == "TRANSFER")
    assert response.instructional_support_level == 2
    assert hint.evidence_id in response.related_evidence_ids
    assert transfer.instructional_support_level == 0


def test_mounted_history_is_self_scoped_and_read_only(db_session):
    from fastapi.testclient import TestClient

    from app.api.dependencies.authentication import get_current_user
    from app.db.session import get_db
    from app.main import create_app
    from app.models.user import User, UserRole

    lms, student, task, started = setup_episode(db_session)
    payload = complete(lms, student, task, started)
    lms.submit(student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="api"))
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: student
    with TestClient(app) as client:
        url = f"/api/v1/student/tasks/{task.id}/evidence"
        first = client.get(url, params={"limit": 1})
        assert first.status_code == 200, first.text
        assert first.json()["next_offset"] == 1
        assert client.get(url, params={"limit": 101}).status_code == 422
        stranger = User(
            email="stranger@example.test",
            password_hash="unused",
            full_name="Other",
            role=UserRole.STUDENT,
        )
        db_session.add(stranger)
        db_session.commit()
        app.dependency_overrides[get_current_user] = lambda: stranger
        assert client.get(url).status_code == 404


def test_optional_prediction_simulation_keeps_work_and_recovery_evidence(db_session):
    import json
    from datetime import UTC, datetime, timedelta

    from app.models.learning_evidence import EvidenceArtifact
    from app.services.quantum import CircuitOperation
    from app.services.simulation_evidence import SimulationEvidenceService

    lms, student, task, started = setup_episode(db_session, prediction_required=False)
    now = [datetime.now(UTC)]
    service = SimulationEvidenceService(db_session, now=lambda: now[0])
    run_id, created = service.prepare(
        owner_id=student.id,
        task_id=task.id,
        qubits=1,
        operations=[CircuitOperation("h", (0,))],
        request_key="interrupted",
    )
    assert created
    now[0] += timedelta(minutes=5)
    assert service.recover_expired() == 1
    rows = lms.evidence_history(student, task.id).items
    assert len(rows) == 1
    assert rows[0].evidence_type.value == "SYSTEM_FAULT"
    record = db_session.get(LearningEvidence, rows[0].evidence_id)
    artifact = json.loads(db_session.get(EvidenceArtifact, record.artifact_id).content)
    assert artifact["context"]["assessment_work_start_id"] == started.assessment_work_start_id
    assert artifact["context"]["task_form_version_id"]
    assert artifact["value"]["run_id"] == run_id
    assert artifact["value"]["result"] is None
    assert service.recover_expired() == 0
    assert len(lms.evidence_history(student, task.id).items) == 1


def test_response_links_only_the_referenced_simulation(db_session):
    from app.schemas.student import SimulationRequest

    lms, student, task, started = setup_episode(db_session, prediction_required=False)
    runs = [
        lms.simulate_student_circuit(
            student,
            SimulationRequest(
                task_id=task.id,
                qubits=1,
                operations=[{"gate": "h", "targets": [0]}],
                request_key=f"simulation-{i}",
            ),
        )
        for i in range(2)
    ]
    payload = complete(lms, student, task, started)
    raw = payload.model_dump()
    raw["episode"]["supported"]["prediction_checkpoint_id"] = None
    raw["episode"]["supported"]["simulation_references"] = [
        {"run_id": runs[0]["run_id"], "circuit_version_id": runs[0]["circuit_version_id"]}
    ]
    lms.submit(student, task.id, SubmissionCreate(**raw, idempotency_key="simulation-response"))
    rows = lms.evidence_history(student, task.id).items
    response = next(row for row in rows if row.evidence_type.value == "RESPONSE")
    sims = {
        row.source_interaction_id: row.evidence_id
        for row in rows
        if row.evidence_type.value == "SIMULATION"
    }
    assert sims[runs[0]["run_id"]] in response.related_evidence_ids
    assert sims[runs[1]["run_id"]] not in response.related_evidence_ids


def test_acknowledgement_requires_released_feedback_and_learner_scope(db_session):
    from types import SimpleNamespace
    from uuid import uuid4

    from fastapi.testclient import TestClient

    from app.api.dependencies.authentication import get_current_user
    from app.api.feedback_dependencies import get_feedback_application
    from app.core.config import settings
    from app.db.session import get_db, get_db_session
    from app.main import create_app
    from app.models.user import User, UserRole
    from app.schemas.feedback_api import FeedbackWorkflowStatus

    lms, student, task, started = setup_episode(db_session)
    payload = complete(lms, student, task, started)
    response = lms.submit(
        student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="ack")
    )
    feedback_id = str(uuid4())
    workflow_id = str(uuid4())

    class ReleasedFeedback:
        status = FeedbackWorkflowStatus.VALIDATED

        def get(self, submission_id):
            return SimpleNamespace(workflow_run_id=workflow_id)

        async def response(self, claim):
            return SimpleNamespace(
                status=self.status, feedback=SimpleNamespace(feedback_id=feedback_id)
            )

    release = ReleasedFeedback()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: student
    app.dependency_overrides[get_feedback_application] = lambda: release
    with TestClient(app) as client:
        client.cookies.set(settings.csrf_cookie_name, "evidence-test-csrf")
        headers = {
            settings.csrf_header_name: "evidence-test-csrf",
            "Origin": settings.allowed_cors_origins[0],
        }
        url = f"/api/v1/submissions/{response.id}/feedback/acknowledgement"
        release.status = FeedbackWorkflowStatus.FALLBACK
        assert (
            client.post(url, json={"feedback_id": feedback_id}, headers=headers).status_code == 409
        )
        release.status = FeedbackWorkflowStatus.VALIDATED
        assert (
            client.post(url, json={"feedback_id": str(uuid4())}, headers=headers).status_code == 409
        )
        first = client.post(url, json={"feedback_id": feedback_id}, headers=headers)
        assert first.status_code == 200, first.text
        assert (
            client.post(url, json={"feedback_id": feedback_id}, headers=headers).json()
            == first.json()
        )
        rows = lms.evidence_history(student, task.id).items
        acknowledgements = [
            row for row in rows if row.evidence_type.value == "FEEDBACK_INTERACTION"
        ]
        assert len(acknowledgements) == 1
        assert acknowledgements[0].observation_type.value == "SELF_REPORTED"
        stranger = User(
            email="ack-other@example.test",
            password_hash="unused",
            full_name="Other",
            role=UserRole.STUDENT,
        )
        db_session.add(stranger)
        db_session.commit()
        app.dependency_overrides[get_current_user] = lambda: stranger
        assert (
            client.post(url, json={"feedback_id": feedback_id}, headers=headers).status_code == 404
        )


def test_concurrent_submission_replay_creates_one_evidence_set(db_session):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy.orm import Session

    from app.models.lms import SubmissionAttempt
    from app.models.user import User
    from app.services.lms import LmsService

    lms, student, task, started = setup_episode(db_session)
    payload = complete(lms, student, task, started)
    command = SubmissionCreate(**payload.model_dump(), idempotency_key="concurrent")
    learner_id, task_id, bind = student.id, task.id, db_session.get_bind()
    db_session.rollback()
    barrier = Barrier(2)

    def submit():
        with Session(bind) as session:
            learner = session.get(User, learner_id)
            barrier.wait(timeout=10)
            return LmsService(session).submit(learner, task_id, command).id

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: submit(), range(2)))
    assert responses[0] == responses[1]
    assert (
        len(
            list(
                db_session.scalars(
                    select(SubmissionAttempt).where(SubmissionAttempt.task_id == task_id)
                )
            )
        )
        == 1
    )
    rows = lms.evidence_history(student, task_id).items
    assert sum(row.evidence_type.value == "RESPONSE" for row in rows) == 1
    assert len({row.evidence_id for row in rows}) == len(rows)


def test_revision_links_prior_response_and_preserves_original(db_session):
    from app.models.learning_evidence import EvidenceArtifact

    lms, student, task, started = setup_episode(db_session)
    payload = complete(lms, student, task, started)
    first = lms.submit(
        student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="first")
    )
    before = {row.id: row.content for row in db_session.scalars(select(EvidenceArtifact))}
    raw = payload.model_dump()
    raw["episode"]["supported"]["revision"] = {
        "previous_response_version_id": first.id,
        "reason": "Clarify reasoning",
    }
    raw["episode"]["supported"]["reasoning"] = "Revised reasoning about amplitudes"
    second = lms.submit(student, task.id, SubmissionCreate(**raw, idempotency_key="second"))
    rows = lms.evidence_history(student, task.id).items
    first_root = next(
        row
        for row in rows
        if row.response_version_id == first.id and row.evidence_type.value == "RESPONSE"
    )
    second_root = next(
        row
        for row in rows
        if row.response_version_id == second.id and row.evidence_type.value == "RESPONSE"
    )
    assert first_root.evidence_id in second_root.related_evidence_ids
    assert all(
        db_session.get(EvidenceArtifact, identity).content == content
        for identity, content in before.items()
    )


def test_explicit_revision_can_link_an_older_response(db_session):
    lms, student, task, started = setup_episode(db_session)
    payload = complete(lms, student, task, started)
    first = lms.submit(
        student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="oldest")
    )
    lms.submit(student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="middle"))
    raw = payload.model_dump()
    raw["episode"]["supported"]["revision"] = {
        "previous_response_version_id": first.id,
        "reason": "Return to my original reasoning",
    }
    last = lms.submit(student, task.id, SubmissionCreate(**raw, idempotency_key="newest"))
    rows = lms.evidence_history(student, task.id).items
    original = next(
        row
        for row in rows
        if row.response_version_id == first.id and row.evidence_type.value == "RESPONSE"
    )
    revisions = [
        row
        for row in rows
        if row.response_version_id == last.id and row.evidence_type.value == "REVISION"
    ]
    assert any(original.evidence_id in row.related_evidence_ids for row in revisions)


def test_simulation_records_support_available_when_it_started(db_session):
    from app.schemas.episode import EpisodeHelpUseWrite
    from app.schemas.student import SimulationRequest

    lms, student, task, started = setup_episode(db_session, prediction_required=False)
    lms.episode_help_use(
        student,
        task.id,
        EpisodeHelpUseWrite(
            assessment_work_start_id=started.assessment_work_start_id,
            kind="conceptual_hint",
            item_index=0,
            request_key="before-simulation",
        ),
    )
    lms.simulate_student_circuit(
        student,
        SimulationRequest(
            task_id=task.id,
            qubits=1,
            operations=[{"gate": "h", "targets": [0]}],
            request_key="supported-simulation",
        ),
    )
    rows = lms.evidence_history(student, task.id).items
    hint = next(row for row in rows if row.evidence_type.value == "HINT")
    simulation = next(row for row in rows if row.evidence_type.value == "SIMULATION")
    assert simulation.instructional_support_level == 2
    assert hint.evidence_id in simulation.related_evidence_ids


def test_simulation_finish_evidence_failure_rolls_back_and_can_recover(db_session, monkeypatch):
    from datetime import UTC, datetime, timedelta

    import pytest

    from app.schemas.student import SimulationRequest
    from app.services.evidence.repository import SqlAlchemyEvidenceRepository
    from app.services.evidence.safety import EvidencePersistenceError
    from app.services.simulation_evidence import SimulationEvidenceService

    lms, student, task, _ = setup_episode(db_session, prediction_required=False)
    original = SqlAlchemyEvidenceRepository.capture

    def unavailable(self, capture, *, commit=True):
        if capture.record.evidence_type.value == "SIMULATION":
            raise EvidencePersistenceError("temporary evidence fault")
        return original(self, capture, commit=commit)

    with monkeypatch.context() as scoped:
        scoped.setattr(SqlAlchemyEvidenceRepository, "capture", unavailable)
        with pytest.raises(EvidencePersistenceError):
            lms.simulate_student_circuit(
                student,
                SimulationRequest(
                    task_id=task.id,
                    qubits=1,
                    operations=[{"gate": "h", "targets": [0]}],
                    request_key="retry-finish",
                ),
            )
    db_session.rollback()
    assert lms.evidence_history(student, task.id).items == []
    recovery = SimulationEvidenceService(
        db_session,
        now=lambda: datetime.now(UTC) + timedelta(minutes=10),
    )
    assert recovery.recover_expired() == 1
    assert [row.evidence_type.value for row in lms.evidence_history(student, task.id).items] == [
        "SYSTEM_FAULT"
    ]
