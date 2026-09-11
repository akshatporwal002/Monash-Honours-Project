"""Candidate scans skip impossible deadlines before taking the delivery write lock."""

from datetime import timedelta

import pytest
from sqlalchemy import event, select
from support.task_review import approve_fixture_task
from test_reminder_controls import NOW, context

from app.models.lms import Reminder
from app.models.persistence import LearningTask
from app.models.reminders import DeadlineArrangement
from app.services.reminders import ReminderService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


@pytest.mark.parametrize(
    "base_hours, arrangements, eligible",
    [
        (None, [], False),
        (-48, [], True),
        (-24, [], True),
        (-23, [], False),
        (None, [(-24, True, False)], True),
        (None, [(24, True, False)], False),
        (-48, [(24, True, False)], False),
        (24, [(-48, True, False)], False),
        (-48, [(24, True, False), (None, False, False)], True),
        (None, [(-48, True, False), (None, False, False)], False),
        (None, [(-48, True, False), (24, True, False)], False),
        (None, [(24, True, False), (-24, True, False)], True),
        (-48, [(None, True, True)], False),
        (-48, [(None, True, True), (None, False, False)], True),
    ],
)
def test_candidates_match_latest_effective_deadline(
    db_session, monkeypatch, base_hours, arrangements, eligible
):
    student, task, owner = context(db_session)
    for row in db_session.scalars(select(LearningTask)):
        row.due_at = None
    task.due_at = NOW + timedelta(hours=base_hours) if base_hours is not None else None
    # Append history directly to cover a course deadline changed after an arrangement,
    # as well as revoked and superseded arrangements without mutating their history.
    for revision, (hours, active, paused) in enumerate(arrangements, 1):
        db_session.add(
            DeadlineArrangement(
                student_id=student.id,
                task_id=task.id,
                actor_id=owner.id,
                revision=revision,
                request_key=f"candidate-{revision}",
                kind="ACCESS_PLAN" if paused else "EXTENSION",
                active=active,
                due_at=NOW + timedelta(hours=hours) if hours is not None else None,
                reminders_paused=paused,
                time_zone="UTC",
                reason="Synthetic approved scheduling decision",
                learner_notice="Your scheduling arrangement has changed.",
            )
        )
    db_session.commit()
    service = ReminderService(db_session, now=NOW)
    deadline = service.deadline(student.id, task)
    assert (
        not deadline.reminders_paused
        and deadline.effective_due_at is not None
        and deadline.effective_due_at <= NOW - timedelta(hours=24)
    ) is eligible
    calls = []
    monkeypatch.setattr(service, "send", lambda *args, **kwargs: calls.append((args, kwargs)))
    batch = service.process_due()
    assert ((student.id, task.id), {"overdue_only": True}) in calls if eligible else not calls
    assert batch.scanned == len(calls)


def test_no_deadline_scan_is_read_only_and_does_not_validate_tasks(db_session, monkeypatch):
    context(db_session)
    for task in db_session.scalars(select(LearningTask)):
        task.due_at = None
    db_session.commit()
    service = ReminderService(db_session, now=NOW)

    def unexpected_send(*args, **kwargs):
        pytest.fail("Tasks without an effective deadline must not enter delivery validation")

    monkeypatch.setattr(service, "send", unexpected_send)
    statements = []
    engine = db_session.get_bind()

    def observe(conn, cursor, statement, parameters, ctx, many):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(engine, "before_cursor_execute", observe)
    try:
        batch = service.process_due()
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert (batch.scanned, batch.created, batch.cursor) == (0, 0, None)
    assert statements == ["SELECT"]


def test_arranged_deadline_without_base_is_delivered_and_rate_limited(db_session):
    student, task, owner = context(db_session)
    for row in db_session.scalars(select(LearningTask)):
        row.due_at = None
    db_session.commit()
    approve_fixture_task(db_session, task)
    db_session.add(
        DeadlineArrangement(
            student_id=student.id,
            task_id=task.id,
            actor_id=owner.id,
            revision=1,
            request_key="arranged-overdue",
            kind="EXTENSION",
            active=True,
            due_at=NOW - timedelta(hours=24),
            reminders_paused=False,
            time_zone="UTC",
            reason="Synthetic approved scheduling decision",
            learner_notice="Your individual deadline applies.",
        )
    )
    db_session.commit()
    service = ReminderService(db_session, now=NOW)
    assert service.process_due().created == 1
    assert service.process_due().created == 0
    records = db_session.scalars(select(Reminder)).all()
    assert [(row.student_id, row.task_id) for row in records] == [(student.id, task.id)]
