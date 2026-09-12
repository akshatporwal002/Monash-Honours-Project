"""Transfer freezes the requesting learner's supported work in one transaction."""

import copy

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from test_task14_lifecycle import setup_episode, supported

from app.models.episode import EpisodeCheckpoint, EpisodeStageStart
from app.models.learning_evidence import EvidenceArtifact, LearningEvidence
from app.models.lms import SubmissionDraft
from app.models.user import User
from app.schemas.episode import EpisodePayloadV1, ResponseContent
from app.schemas.lms import DraftWrite
from app.services.episodes import EpisodeService
from app.services.lms import LmsService
from app.services.task_review import TaskReviewError

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def checkpointed_supported(lms, student, task, started):
    receipt = lms.episode_checkpoint(student, task.id, supported(started), "supported", None)
    return DraftWrite.model_validate(
        receipt["draft"].model_dump(exclude={"id", "task_id", "updated_at"})
    )


def with_reflection(payload, reflection):
    # Reflection can evolve while the prior prediction and exact circuit input
    # remain bound to the existing immutable checkpoint.
    raw = payload.episode.model_dump(mode="json")
    raw["supported"]["reflection"] = reflection
    return payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(raw)})


def committed_state(engine):
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
            for model in (
                SubmissionDraft,
                EpisodeStageStart,
                EpisodeCheckpoint,
                LearningEvidence,
                EvidenceArtifact,
            )
        }


def test_transfer_freezes_request_snapshot_before_independent_draft_save(db_session):
    lms, student, task, started = setup_episode(db_session)
    original = checkpointed_supported(lms, student, task, started)
    competitor = with_reflection(original, "A later reflection saved by another request")
    engine, student_id, task_id = db_session.get_bind(), student.id, task.id
    interleaved = []

    def save_competing_request(_session):
        if interleaved:
            return
        interleaved.append(True)
        with Session(engine, expire_on_commit=False) as competing_session:
            LmsService(competing_session).save_draft(
                competing_session.get(User, student_id), task_id, competitor
            )

    event.listen(db_session, "after_commit", save_competing_request)
    try:
        receipt = lms.episode_transfer(student, task_id, original)
    finally:
        event.remove(db_session, "after_commit", save_competing_request)

    assert interleaved == [True]
    with Session(engine) as inspect:
        stage = inspect.get(EpisodeStageStart, receipt["transfer"]["stage_start_id"])
        assert stage.supported_snapshot == {
            "content": ResponseContent(
                answer=original.answer, code=original.code, circuit=original.circuit
            ).model_dump(mode="json"),
            "process": original.episode.supported.model_dump(mode="json"),
        }
        draft = inspect.scalar(
            select(SubmissionDraft).where(
                SubmissionDraft.student_id == student_id, SubmissionDraft.task_id == task_id
            )
        )
        assert draft.episode["supported"]["reflection"] == competitor.episode.supported.reflection
        checkpoint = inspect.get(
            EpisodeCheckpoint, original.episode.supported.prediction_checkpoint_id
        )
        assert checkpoint.prediction == original.episode.supported.prediction.model_dump(
            mode="json"
        )


def test_transfer_failure_rolls_back_draft_and_stage_then_retry_preserves_history(
    db_session, monkeypatch
):
    lms, student, task, started = setup_episode(db_session)
    original = checkpointed_supported(lms, student, task, started)
    request = with_reflection(original, "Reflection included in the transfer-start request")
    engine, student_id, task_id = db_session.get_bind(), student.id, task.id
    before = committed_state(engine)
    start_transfer = EpisodeService.start_transfer

    def fail_after_stage_flush(self, draft):
        start_transfer(self, draft)
        self.session.flush()
        raise TaskReviewError("Synthetic late transfer fault", 503)

    with monkeypatch.context() as scoped:
        scoped.setattr(EpisodeService, "start_transfer", fail_after_stage_flush)
        with pytest.raises(TaskReviewError, match="Synthetic late transfer fault"):
            lms.episode_transfer(student, task_id, request)
        # Match the mounted Lms dependency's rollback for a failed command.
        db_session.rollback()

    assert committed_state(engine) == before
    retried = lms.episode_transfer(db_session.get(User, student_id), task_id, request)
    replayed = lms.episode_transfer(db_session.get(User, student_id), task_id, request)
    assert retried["transfer"]["stage_start_id"] == replayed["transfer"]["stage_start_id"]
    with Session(engine) as inspect:
        stage = inspect.get(EpisodeStageStart, retried["transfer"]["stage_start_id"])
        assert stage.supported_snapshot["process"] == request.episode.supported.model_dump(
            mode="json"
        )
        assert stage.supported_snapshot["process"]["prediction_checkpoint_id"] == (
            original.episode.supported.prediction_checkpoint_id
        )
    after = committed_state(engine)
    for table in ("episode_checkpoints", "learning_evidence", "evidence_artifacts"):
        assert after[table] == before[table]
    assert len(after["episode_stage_starts"]) == len(before["episode_stage_starts"]) + 1
