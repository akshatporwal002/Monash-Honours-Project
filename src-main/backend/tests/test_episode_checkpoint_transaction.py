"""Checkpoint requests freeze their own input and commit evidence atomically."""

import copy
import json

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from test_task14_lifecycle import setup_episode, supported

from app.models.episode import EpisodeCheckpoint
from app.models.learning_evidence import EvidenceArtifact, LearningEvidence
from app.models.lms import SubmissionDraft
from app.models.user import User
from app.schemas.episode import EpisodePayloadV1
from app.services.episodes import EpisodeService
from app.services.evidence.live import LiveEvidenceCapture
from app.services.evidence.safety import EvidencePersistenceError
from app.services.lms import LmsService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def changed_prediction(payload):
    raw = payload.episode.model_dump(mode="json")
    raw["supported"]["prediction"] = {"answer": "One for the changed X input"}
    return payload.model_copy(
        update={
            "answer": "A different response from a second request",
            "circuit": {"qubits": 1, "operations": [{"gate": "x", "targets": [0]}]},
            "episode": EpisodePayloadV1.model_validate(raw),
        }
    )


def stored_records(engine):
    """Inspect committed rows in an independent session, including protected content."""
    with Session(engine) as session:
        return {
            model.__tablename__: copy.deepcopy(
                [
                    dict(row)
                    for row in session.execute(
                        select(model.__table__).order_by(model.__table__.c.id)
                    ).mappings()
                ]
            )
            for model in (SubmissionDraft, EpisodeCheckpoint, LearningEvidence, EvidenceArtifact)
        }


def test_checkpoint_freezes_request_input_before_independent_draft_save(db_session):
    lms, student, task, started = setup_episode(db_session)
    original = supported(started)
    competitor = changed_prediction(original)
    engine, student_id, task_id = db_session.get_bind(), student.id, task.id
    interleaved = []

    def save_competing_request(_session):
        # This is the real seam exposed by save_draft's intermediate commit.
        # Once checkpoint capture shares that transaction, the competing request
        # can only run after the original checkpoint and evidence are committed.
        if interleaved:
            return
        interleaved.append(True)
        with Session(engine, expire_on_commit=False) as competing_session:
            competing_student = competing_session.get(User, student_id)
            LmsService(competing_session).save_draft(competing_student, task_id, competitor)

    event.listen(db_session, "after_commit", save_competing_request)
    try:
        receipt = lms.episode_checkpoint(student, task_id, original, "supported", None)
    finally:
        event.remove(db_session, "after_commit", save_competing_request)

    assert interleaved == [True]
    with Session(engine) as inspect:
        checkpoint = inspect.get(EpisodeCheckpoint, receipt["checkpoint_id"])
        assert checkpoint.prediction == original.episode.supported.prediction.model_dump(
            mode="json"
        )
        assert checkpoint.input_content["answer"] == original.answer
        assert checkpoint.input_content["circuit"] == original.circuit
        evidence = inspect.scalar(
            select(LearningEvidence).where(
                LearningEvidence.source_interaction_id == checkpoint.id,
                LearningEvidence.evidence_type == "PREDICTION",
            )
        )
        assert evidence is not None
        artifact = json.loads(inspect.get(EvidenceArtifact, evidence.artifact_id).content)
        assert artifact["value"]["prediction"] == checkpoint.prediction
        assert artifact["value"]["input"] == checkpoint.input_content
        saved_draft = inspect.scalar(
            select(SubmissionDraft).where(
                SubmissionDraft.student_id == student_id, SubmissionDraft.task_id == task_id
            )
        )
        assert saved_draft.answer == competitor.answer
        assert saved_draft.episode["supported"][
            "prediction"
        ] == competitor.episode.supported.prediction.model_dump(mode="json")


@pytest.mark.parametrize("failure_stage", ["checkpoint", "evidence"])
def test_checkpoint_failure_rolls_back_draft_and_new_evidence_without_losing_history(
    db_session, monkeypatch, failure_stage
):
    lms, student, task, started = setup_episode(db_session)
    original = supported(started)
    first = lms.episode_checkpoint(student, task.id, original, "supported", None)
    changed = changed_prediction(original)
    engine, student_id, task_id = db_session.get_bind(), student.id, task.id
    before = stored_records(engine)
    target = EpisodeService if failure_stage == "checkpoint" else LiveEvidenceCapture
    capture = target.checkpoint

    def fail_after_capture(self, *args, **kwargs):
        capture(self, *args, **kwargs)
        self.session.flush()
        raise EvidencePersistenceError("Synthetic late checkpoint persistence fault")

    with monkeypatch.context() as scoped:
        scoped.setattr(target, "checkpoint", fail_after_capture)
        with pytest.raises(EvidencePersistenceError, match="Synthetic late checkpoint"):
            lms.episode_checkpoint(student, task_id, changed, "supported", None)
        # Match the request dependency's rollback when evidence persistence fails.
        db_session.rollback()

    assert stored_records(engine) == before
    retried = lms.episode_checkpoint(
        db_session.get(User, student_id), task_id, changed, "supported", None
    )
    assert retried["checkpoint_id"] != first["checkpoint_id"]
    with Session(engine) as inspect:
        preserved = inspect.get(EpisodeCheckpoint, first["checkpoint_id"])
        assert preserved.prediction == original.episode.supported.prediction.model_dump(mode="json")
        checkpoint = inspect.get(EpisodeCheckpoint, retried["checkpoint_id"])
        assert checkpoint.prediction == changed.episode.supported.prediction.model_dump(mode="json")
        assert checkpoint.input_content["circuit"] == changed.circuit
        evidence = inspect.scalar(
            select(LearningEvidence).where(
                LearningEvidence.source_interaction_id == checkpoint.id,
                LearningEvidence.evidence_type == "PREDICTION",
            )
        )
        assert evidence is not None
