"""The shipped adapter can acknowledge progress in its existing fenced commit."""

import pytest
from sqlalchemy import event, func, select
from test_activity_continuation import context as context
from test_activity_continuation import run_worker
from test_continuation_repository import _claim, _notice, _released_workflow

from app.models.activity_continuation import ActivityProgress
from app.models.continuation import ContinuationJob
from app.models.learner_model import LearnerModelSnapshot
from app.services.continuation.repository import SqlAlchemyContinuationRepository

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def test_progress_flag_and_receipt_are_durable_together_without_an_extra_commit(context):
    _, identity, factory, _ = context
    committed = []

    def observe(session):
        with factory() as reader:
            receipt = reader.get(ActivityProgress, identity)
            job = reader.get(ContinuationJob, identity)
            committed.append(
                (
                    receipt is not None,
                    job.progress_recorded,
                    reader.scalar(select(func.count()).select_from(LearnerModelSnapshot)),
                )
            )

    event.listen(factory.class_, "after_commit", observe)
    try:
        result = run_worker(factory)
    finally:
        event.remove(factory.class_, "after_commit", observe)
    assert result.state.value == "completed"
    assert committed == [(False, False, 0)] + [(True, True, 1)] * 3


def test_already_recorded_progress_releases_its_read_transaction(db_session):
    workflow = _released_workflow(db_session)
    repository = SqlAlchemyContinuationRepository(db_session)
    repository.ensure_pending(_notice(workflow.id))
    current_claim = _claim(repository)
    assert repository.mark_progress_recorded(current_claim)
    assert not db_session.in_transaction()
    # The next adapter opens an independent writer session. Do not leave a
    # read transaction/connection behind when its acknowledgement is a replay.
    assert repository.mark_progress_recorded(current_claim)
    assert not db_session.in_transaction()
