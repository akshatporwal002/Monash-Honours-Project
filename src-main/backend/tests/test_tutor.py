"""Tutor turns preserve reviewed help, replay and independent transfer boundaries."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from test_task14_lifecycle import setup_episode, supported

from app.models.episode import EpisodeHelpUse
from app.models.learning_evidence import LearningEvidence
from app.models.tutor import TutorTurn
from app.schemas.lms import DraftWrite
from app.schemas.tutor import TutorTurnWrite
from app.services.lms import LmsServiceError
from app.services.tutor import FALLBACK, TutorService


def send(service, student, task, key, message="I think the gates change the state."):
    state = service.read(student, task.id)
    return service.send(
        student,
        task.id,
        TutorTurnWrite(
            message=message,
            idempotency_key=key,
            expected_revision=state.revision,
            context_token=state.context_token,
        ),
    )


def test_tutor_sequences_hints_records_evidence_and_restores_history(db_session):
    lms, student, task, started = setup_episode(db_session)
    tutor = TutorService(db_session)
    assert send(tutor, student, task, "one").kind == "probe"
    hint = send(tutor, student, task, "two")
    assert hint.kind == "hint"
    assert hint.reply == "Consider how H changes the input state."
    assert send(tutor, student, task, "three").kind == "reasoning"
    assert send(tutor, student, task, "four").kind == "hint"
    state = tutor.read(student, task.id)
    replay = tutor.send(
        student,
        task.id,
        TutorTurnWrite(
            message="I think the gates change the state.",
            idempotency_key="two",
            expected_revision=1,
            context_token=state.context_token,
        ),
    )
    assert replay.id == hint.id
    assert len(list(db_session.scalars(select(EpisodeHelpUse)))) == 2
    assert (
        len(
            list(
                db_session.scalars(
                    select(LearningEvidence).where(
                        LearningEvidence.source_interaction_id == hint.id
                    )
                )
            )
        )
        == 1
    )
    db_session.expire_all()
    assert len(TutorService(db_session).read(student, task.id).turns) == 4
    assert (
        lms.get_draft(student, task.id).assessment_work_start_id == started.assessment_work_start_id
    )
    with pytest.raises(IntegrityError, match="immutable"):
        db_session.execute(text("UPDATE tutor_turns SET reply='changed'"))
    db_session.rollback()


def test_transfer_hides_dialogue_and_rejects_new_or_replayed_help(db_session):
    lms, student, task, started = setup_episode(db_session)
    tutor = TutorService(db_session)
    state = tutor.read(student, task.id)
    request = TutorTurnWrite(
        message="Help me reason",
        idempotency_key="one",
        expected_revision=0,
        context_token=state.context_token,
    )
    tutor.send(student, task.id, request)
    checkpoint = lms.episode_checkpoint(student, task.id, supported(started), "supported", None)
    payload = DraftWrite.model_validate(
        checkpoint["draft"].model_dump(exclude={"id", "task_id", "updated_at"})
    )
    lms.episode_transfer(student, task.id, payload)
    hidden = tutor.read(student, task.id)
    assert not hidden.instructional_help_available
    assert hidden.turns == []
    with pytest.raises(LmsServiceError, match="unavailable"):
        tutor.send(student, task.id, request)
    assert len(list(db_session.scalars(select(TutorTurn)))) == 1


def test_rejected_output_retries_once_then_preserves_safe_fallback(db_session):
    _, student, task, _ = setup_episode(db_session)
    calls = []

    def bad_output(candidate, attempt):
        calls.append(attempt)
        return "NEVER REVEAL solution"

    tutor = TutorService(db_session, generate=bad_output)
    receipt = send(tutor, student, task, "unsafe")
    assert calls == [0, 1]
    assert receipt.reply == FALLBACK and receipt.kind == "fallback"
    row = db_session.get(TutorTurn, receipt.id)
    assert [item["decision"] for item in row.quality] == ["REJECTED", "REJECTED"]
    assert "NEVER REVEAL" not in tutor.read(student, task.id).model_dump_json()


def test_answer_seeking_redirects_without_integrity_finding(db_session):
    _, student, task, _ = setup_episode(db_session)
    tutor = TutorService(db_session)
    receipt = send(tutor, student, task, "request-answer", "Just give me the answer")
    assert receipt.kind == "redirect"
    assert "reasoning" in receipt.reply
    assert "misconduct" not in receipt.reply
    assert db_session.scalar(select(EpisodeHelpUse)) is None


def test_stale_conversation_preserves_accepted_turn_and_request_text(db_session):
    _, student, task, _ = setup_episode(db_session)
    tutor = TutorService(db_session)
    state = tutor.read(student, task.id)
    send(tutor, student, task, "first")
    with pytest.raises(LmsServiceError, match="changed"):
        tutor.send(
            student,
            task.id,
            TutorTurnWrite(
                message="My other draft",
                idempotency_key="second",
                expected_revision=0,
                context_token=state.context_token,
            ),
        )
    assert len(tutor.read(student, task.id).turns) == 1


def test_reasoning_required_before_further_hints_without_a_saved_work_start(db_session):
    from app.models.lms import SubmissionDraft

    _, student, task, _ = setup_episode(db_session)
    draft = db_session.scalar(select(SubmissionDraft).where(SubmissionDraft.task_id == task.id))
    db_session.delete(draft)
    db_session.commit()
    tutor = TutorService(db_session)
    assert send(tutor, student, task, "probe").kind == "probe"
    assert send(tutor, student, task, "hint").kind == "hint"
    assert send(tutor, student, task, "reasoning").kind == "reasoning"


def test_reapproved_task_hides_old_turns_and_rejects_old_replay(db_session):
    from support.task_review import approve_fixture_task

    from app.models.lms import SubmissionDraft

    _, student, task, _ = setup_episode(db_session)
    db_session.delete(
        db_session.scalar(select(SubmissionDraft).where(SubmissionDraft.task_id == task.id))
    )
    db_session.commit()
    tutor = TutorService(db_session)
    state = tutor.read(student, task.id)
    request = TutorTurnWrite(
        message="My reasoning",
        idempotency_key="old",
        expected_revision=0,
        context_token=state.context_token,
    )
    tutor.send(student, task.id, request)
    task.instructions += " Explain your observation."
    db_session.commit()
    approve_fixture_task(db_session, task)
    assert tutor.read(student, task.id).turns == []
    with pytest.raises(LmsServiceError, match="task changed"):
        tutor.send(student, task.id, request)
    assert db_session.scalar(select(TutorTurn)).learner_text == "My reasoning"


def test_generation_failure_has_no_quality_decision_and_evidence_failure_rolls_back(
    db_session, monkeypatch
):
    from app.services.evidence.live import LiveEvidenceCapture

    _, student, task, _ = setup_episode(db_session)

    def unavailable(candidate, attempt):
        raise TimeoutError("provider unavailable")

    tutor = TutorService(db_session, generate=unavailable)
    turn = send(tutor, student, task, "failure")
    quality = db_session.get(TutorTurn, turn.id).quality
    assert all(item["status"] == "FAILED" and item["decision"] is None for item in quality)

    def capture_failure(*args):
        raise RuntimeError("Evidence write failed")

    monkeypatch.setattr(LiveEvidenceCapture, "tutor", capture_failure)
    with pytest.raises(RuntimeError, match="Evidence write failed"):
        send(tutor, student, task, "atomic")
    assert len(tutor.read(student, task.id).turns) == 1


def test_tutor_routes_enforce_csrf_and_authentication(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.dependencies.authentication import get_current_user
    from app.core.config import settings
    from app.db.session import get_db
    from app.main import create_app

    _, student, task, _ = setup_episode(db_session)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: student
    client = TestClient(app)
    path = f"/api/v1/students/me/tasks/{task.id}/tutor"
    state = client.get(path)
    assert state.status_code == 200 and state.headers["Cache-Control"] == "no-store"
    monkeypatch.setattr(settings, "csrf_enabled", True)
    client.cookies.set(settings.csrf_cookie_name, "test-csrf-token")
    denied = client.post(
        path,
        json={
            "message": "Help",
            "idempotency_key": "csrf",
            "expected_revision": 0,
            "context_token": state.json()["context_token"],
        },
    )
    assert denied.status_code == 403
    assert db_session.scalar(select(TutorTurn)) is None
    app.dependency_overrides.pop(get_current_user)
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("personalisation", [True, False])
def test_tutor_consumes_current_shared_evidence_and_respects_opt_out(db_session, personalisation):
    from test_learner_model import _command, _service, _store_evidence
    from test_task20_formal_result_isolation import _preferences

    from app.domain.platform_enums import EvidenceLinkRelation, EvidenceType
    from app.services.learner_model.contracts import LearnerModelEvidenceSignal
    from app.services.learner_preferences.repository import SqlAlchemyLearnerPreferencesRepository
    from app.services.learner_preferences.service import LearnerPreferencesService
    from app.services.tutor import PROBE, REFLECTION

    _, student, task, _ = setup_episode(db_session)
    scope = {
        "course_one": task.course_id,
        "outcome_one": task.learning_outcome_id,
        "task_one": task.id,
        "learner_id": str(student.id),
        "actor_reference": str(student.id),
    }
    _store_evidence(
        db_session, scope, evidence_id="reasoning", evidence_type=EvidenceType.REASONING
    )
    _service(db_session)._build(
        _command(
            scope,
            (
                LearnerModelEvidenceSignal(
                    evidence_id="reasoning", relation=EvidenceLinkRelation.CONTRADICTS
                ),
            ),
        )
    )
    LearnerPreferencesService(SqlAlchemyLearnerPreferencesRepository(db_session)).save(
        student.id,
        _preferences(expected_revision=0, key="choice", slower=personalisation),
    )
    receipt = send(TutorService(db_session), student, task, "model")
    assert receipt.reply == (REFLECTION if personalisation else PROBE)
    row = db_session.get(TutorTurn, receipt.id)
    assert bool(row.context["model_snapshot_id"]) is personalisation
    assert row.context["preference_revision"] == 1


@pytest.mark.parametrize("same_key", [True, False])
def test_simultaneous_turns_keep_one_revision_and_one_evidence_record(db_session, same_key):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy.orm import Session

    from app.models.user import User

    _, student, task, _ = setup_episode(db_session)
    student_id, task_id = student.id, task.id
    context_token = TutorService(db_session).read(student, task_id).context_token
    db_session.rollback()
    engine = db_session.get_bind()
    barrier = Barrier(2)

    def submit(index):
        with Session(engine) as session:
            learner = session.get(User, student_id)
            payload = TutorTurnWrite(
                message="My reasoning",
                idempotency_key="same" if same_key else f"key-{index}",
                expected_revision=0,
                context_token=context_token,
            )
            barrier.wait(timeout=10)
            try:
                return TutorService(session).send(learner, task_id, payload).id
            except LmsServiceError as error:
                assert error.status_code == 409
                return None

    with ThreadPoolExecutor(max_workers=2) as workers:
        replies = list(workers.map(submit, (1, 2)))
    assert len(set(reply for reply in replies if reply)) == 1
    assert sum(reply is not None for reply in replies) == (2 if same_key else 1)
    rows = list(db_session.scalars(select(TutorTurn)))
    assert len(rows) == 1
    assert (
        len(
            list(
                db_session.scalars(
                    select(LearningEvidence).where(
                        LearningEvidence.source_interaction_id == rows[0].id
                    )
                )
            )
        )
        == 1
    )
