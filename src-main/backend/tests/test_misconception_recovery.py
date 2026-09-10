"""Exit, drift, correction and rollback checks for the reviewed teaching cycle."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import select
from sqlalchemy.orm import Session
from support.migration_assertions import protected_history_manifest
from test_migrations import migration_config
from test_misconceptions import answer, context, finish, review_command

from app.db.session import create_db_engine
from app.domain.platform_enums import CorrectionAction, CorrectionTargetKind, InferenceStatus
from app.models.learner_model import LearnerModelCorrectionSnapshotLink
from app.models.misconceptions import MisconceptionReviewRecord
from app.models.persistence import LearningTask
from app.schemas.misconceptions import MisconceptionExit
from app.services.learner_model.correction_contracts import (
    CorrectionTarget,
    EducatorCorrectionReviewCommand,
    LearnerAnnotationCommand,
)
from app.services.learner_model.correction_repository import (
    SqlAlchemyLearnerModelCorrectionRepository,
)
from app.services.learner_model.corrections import LearnerModelCorrectionService
from app.services.learner_model.repository import SqlAlchemyLearnerModelRepository
from app.services.lms import LmsServiceError
from app.services.misconception_state import active_fresh_check
from app.services.task_review import TaskReviewError
from app.services.tutor import TutorService


def test_exit_after_approval_drift_restores_help_and_preserves_history(db_session):
    _, _, educator, _, student, service, opened, saved = context(db_session)
    first, _ = answer(service, student, saved)
    second, _ = answer(service, student, first)
    assert active_fresh_check(db_session, student.id, saved.task_id) == saved.id
    task = db_session.get(LearningTask, saved.task_id)
    description = task.description
    task.description = "Changed material needs a new review"
    db_session.commit()
    with pytest.raises((LmsServiceError, TaskReviewError)):
        answer(service, student, second)
    db_session.rollback()
    leave = MisconceptionExit(
        request_key="leave",
        expected_version=2,
        reason="Please review the changed question before I continue.",
        disposition="DEFERRED",
    )
    closed = service.exit(student, saved.id, leave)
    assert service.exit(student, saved.id, leave).closure == closed.closure
    assert closed.closure.disposition == "DEFERRED"
    assert closed.next_stage is None and len(closed.responses) == 2
    assert active_fresh_check(db_session, student.id, saved.task_id) is None
    task.description = description
    db_session.commit()
    assert TutorService(db_session).read(student, saved.task_id).instructional_help_available
    with pytest.raises(LmsServiceError, match="fresh question"):
        service.open(educator, opened.model_copy(update={"request_key": "same-prompt"}))
    db_session.rollback()
    replacement = service.open(
        educator,
        opened.model_copy(
            update={
                "request_key": "new-check",
                "fresh_question": "Compare a different circuit and explain its independent prediction.",
            }
        ),
    )
    assert replacement.id != saved.id and replacement.state == "UNCERTAIN"
    with pytest.raises(LmsServiceError, match="ended"):
        answer(service, student, second)
    db_session.rollback()


def test_accepted_estimate_correction_is_linked_before_review_moves_model_head(db_session):
    _, _, educator, _, student, service, _, saved = context(db_session)
    complete = finish(service, student, saved)
    first = service.review(educator, saved.id, review_command(complete))
    repository = SqlAlchemyLearnerModelRepository(db_session)
    scope = dict(course_id=saved.course_id, learner_id=str(student.id), outcome_id=saved.outcome_id)
    head = repository.current(**scope)
    corrections = LearnerModelCorrectionService(
        SqlAlchemyLearnerModelCorrectionRepository(db_session)
    )
    target = CorrectionTarget(
        target_kind=CorrectionTargetKind.ESTIMATE, estimate_id=head.estimates[0].estimate_id
    )
    annotation = LearnerAnnotationCommand(
        annotation_id=str(uuid4()),
        **scope,
        target=target,
        actor_reference=str(student.id),
        correlation_id=str(uuid4()),
        idempotency_key=str(uuid4()),
        occurred_at=datetime.now(UTC),
        record_version=1,
        note="Please review how my explanation was interpreted.",
    )
    corrections.annotate(annotation)
    reviewed = EducatorCorrectionReviewCommand(
        review_id=str(uuid4()),
        annotation_id=annotation.annotation_id,
        **scope,
        target=target,
        actor_reference=str(educator.id),
        correlation_id=str(uuid4()),
        idempotency_key=str(uuid4()),
        occurred_at=datetime.now(UTC),
        review_version=1,
        expected_latest_review_version=0,
        action=CorrectionAction.ACCEPTED,
        reason="Retain this context before making another inference.",
    )
    corrections.review(reviewed)
    second = service.review(educator, saved.id, review_command(first, "CORRECTED"))
    current = repository.current(**scope)
    assert current.prior_snapshot_id == head.snapshot_id
    assert current.estimates[0].inference_status == InferenceStatus.NEEDS_REVIEW
    link = db_session.scalar(
        select(LearnerModelCorrectionSnapshotLink).where(
            LearnerModelCorrectionSnapshotLink.review_id == reviewed.review_id
        )
    )
    assert link.snapshot_id == second.reviews[-1].snapshot_id


def test_failed_model_write_rolls_back_review_evidence_and_queue(db_session, monkeypatch):
    _, queue, educator, _, student, service, _, saved = context(db_session)
    complete = finish(service, student, saved)
    before = protected_history_manifest(Path(db_session.bind.url.database))

    def fail(*args, **kwargs):
        raise RuntimeError("injected store failure")

    monkeypatch.setattr(SqlAlchemyLearnerModelRepository, "store", fail)
    with pytest.raises(RuntimeError, match="injected"):
        service.review(educator, saved.id, review_command(complete))
    db_session.rollback()
    assert list(db_session.scalars(select(MisconceptionReviewRecord))) == []
    assert queue.queue(educator, saved.course_id, "ASSESSOR") == []
    assert protected_history_manifest(Path(db_session.bind.url.database)) == before


def test_populated_misconception_history_blocks_downgrade_without_changes(tmp_path):
    path = tmp_path / "misconceptions.db"
    url = f"sqlite:///{path.as_posix()}"
    config = migration_config(url)
    command.upgrade(config, "head")
    engine = create_db_engine(url)
    try:
        with Session(engine) as session:
            _, _, educator, _, student, service, _, saved = context(session)
            complete = finish(service, student, saved)
            service.review(educator, saved.id, review_command(complete))
        before = protected_history_manifest(path)
        with pytest.raises(RuntimeError, match="history is protected"):
            command.downgrade(config, "20260909_0042")
        assert protected_history_manifest(path) == before
        command.upgrade(config, "head")
        assert protected_history_manifest(path) == before
    finally:
        engine.dispose()
