"""Reminder delivery is optional, read-independent and safe across retries."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier

import pytest
from pydantic import ValidationError
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from support.task_review import approve_fixture_task, bootstrap_reviewed_demo

from app.models.lms import Course, Reminder, SystemSetting
from app.models.persistence import LearningEvent, LearningTask
from app.models.reminders import DeadlineArrangement, ReminderPreference
from app.models.user import User, UserRole
from app.schemas.lms import CourseUpdate, SubmissionCreate
from app.schemas.reminders import DeadlineArrangementWrite, ReminderPreferenceWrite
from app.services.lms import LmsService
from app.services.reminders import ReminderError, ReminderService, ReminderWorker, course_instant
from scripts.verify_sqlite_backup import database_manifest

NOW = datetime(2030, 1, 1, 23, 59, tzinfo=UTC)


def context(session):
    users, _ = bootstrap_reviewed_demo(session)
    student = next(user for user in users if user.role == UserRole.STUDENT)
    task = session.scalar(select(LearningTask).order_by(LearningTask.position))
    task.due_at = NOW - timedelta(days=2)
    session.commit()
    approve_fixture_task(session, task)
    course = session.get(Course, task.course_id)
    return student, task, session.get(User, course.educator_id)


def test_dashboard_reads_do_not_write_any_records(db_session):
    student, _, _ = context(db_session)
    path = Path(db_session.get_bind().url.database)
    before = database_manifest(path)
    statements = []

    def observe(conn, cursor, statement, parameters, ctx, many):
        statements.append(statement.lstrip().split()[0].upper())

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", observe)
    try:
        for _ in range(2):
            dashboard = LmsService(db_session).student_dashboard(student)
            assert dashboard.recommendations
            assert dashboard.reminders == []
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert set(statements) == {"SELECT"}
    assert database_manifest(path) == before


def test_preferences_pause_resume_replay_and_current_submission(db_session):
    student, task, _ = context(db_session)
    service = ReminderService(db_session, now=NOW)
    command = ReminderPreferenceWrite(
        expected_revision=0,
        idempotency_key="pause",
        enabled=True,
        paused_until=NOW + timedelta(hours=2),
    )
    assert service.save_preference(student.id, command).revision == 1
    assert service.save_preference(student.id, command).revision == 1
    assert service.send(student.id, task.id, overdue_only=True) is None
    with pytest.raises(ReminderError, match="already used"):
        service.save_preference(student.id, command.model_copy(update={"enabled": False}))
    db_session.rollback()
    with pytest.raises(ReminderError, match="changed"):
        service.save_preference(student.id, command.model_copy(update={"idempotency_key": "stale"}))
    db_session.rollback()
    later = ReminderService(db_session, now=NOW + timedelta(hours=3))
    assert later.send(student.id, task.id, overdue_only=True) is not None
    db_session.commit()
    off = ReminderPreferenceWrite(expected_revision=1, idempotency_key="off", enabled=False)
    assert not later.save_preference(student.id, off).enabled
    assert (
        ReminderService(db_session, now=NOW + timedelta(days=2)).send(student.id, task.id) is None
    )
    LmsService(db_session).submit(
        student, task.id, SubmissionCreate(answer=task.expected_answer, idempotency_key="submitted")
    )
    later.save_preference(
        student.id,
        off.model_copy(update={"expected_revision": 2, "idempotency_key": "on", "enabled": True}),
    )
    assert (
        ReminderService(db_session, now=NOW + timedelta(days=3)).send(student.id, task.id) is None
    )
    assert db_session.scalar(select(func.count()).select_from(ReminderPreference)) == 3
    with pytest.raises(IntegrityError, match="immutable"):
        db_session.execute(text("DELETE FROM reminder_preferences"))
    db_session.rollback()


def test_rolling_limit_crosses_midnight_and_is_enforced_by_database(db_session):
    student, task, _ = context(db_session)
    first = ReminderService(db_session, now=NOW).send(student.id, task.id)
    db_session.commit()
    assert (
        ReminderService(db_session, now=NOW + timedelta(minutes=2)).send(student.id, task.id)
        is None
    )
    db_session.rollback()
    with pytest.raises(IntegrityError, match="24 hours"):
        db_session.execute(
            text(
                "INSERT INTO reminders (id, student_id, task_id, title, message, dedupe_window, is_read, created_at) VALUES ('bypass', :student, :task, 'Reminder', 'Resume', 'different-window', 0, :now)"
            ),
            {
                "student": student.id,
                "task": task.id,
                "now": (NOW + timedelta(minutes=2)).replace(tzinfo=None),
            },
        )
    db_session.rollback()
    assert (
        ReminderService(db_session, now=NOW + timedelta(hours=24)).send(student.id, task.id)
        is not None
    )
    db_session.commit()
    first.is_read = True
    db_session.commit()
    with pytest.raises(IntegrityError, match="immutable"):
        db_session.execute(text("UPDATE reminders SET created_at='2000-01-01'"))
    db_session.rollback()


def test_concurrent_reminders_create_one_delivery(db_session):
    student, task, _ = context(db_session)
    student_id, task_id = student.id, task.id
    engine = db_session.get_bind()
    db_session.commit()
    barrier = Barrier(2)

    def send():
        with Session(engine) as session:
            barrier.wait(timeout=10)
            record = ReminderService(session, now=NOW).send(student_id, task_id)
            session.commit()
            return record is not None

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(send) for _ in range(2)]
        assert sorted(future.result(timeout=30) for future in futures) == [False, True]
    assert db_session.scalar(select(func.count()).select_from(Reminder)) == 1


def test_deadline_extension_access_plan_and_revocation_preserve_history(db_session):
    student, task, owner = context(db_session)
    course = db_session.get(Course, task.course_id)
    course.time_zone = "Australia/Sydney"
    db_session.commit()
    service = ReminderService(db_session, now=NOW)
    command = DeadlineArrangementWrite(
        expected_revision=0,
        idempotency_key="extension",
        kind="EXTENSION",
        time_zone=course.time_zone,
        local_due_at=datetime(2030, 1, 5, 17),
        reason="PRIVATE approved scheduling arrangement",
        learner_notice="Your deadline is now 5 January at 17:00 Sydney time.",
    )
    saved = service.save_arrangement(owner, student.id, task.id, command)
    assert saved.due_at == datetime(2030, 1, 5, 6, tzinfo=UTC)
    assert service.save_arrangement(owner, student.id, task.id, command).id == saved.id
    public = service.deadline(student.id, task)
    assert "PRIVATE" not in public.model_dump_json()
    assert public.effective_due_at == saved.due_at
    assert LmsService(db_session).get_task_for_actor(student, task.id).due_at == saved.due_at
    assert service.send(student.id, task.id) is None
    db_session.rollback()
    with pytest.raises(ReminderError, match="Only the course owner"):
        service.save_arrangement(student, student.id, task.id, command)
    db_session.rollback()
    revoked = command.model_copy(
        update={
            "expected_revision": 1,
            "idempotency_key": "revoke",
            "active": False,
            "local_due_at": None,
            "learner_notice": "The original course deadline applies.",
        }
    )
    service.save_arrangement(owner, student.id, task.id, revoked)
    assert service.deadline(student.id, task).effective_due_at == task.due_at.replace(tzinfo=UTC)
    plan = command.model_copy(
        update={
            "expected_revision": 2,
            "idempotency_key": "plan",
            "kind": "ACCESS_PLAN",
            "local_due_at": None,
            "reminders_paused": True,
        }
    )
    service.save_arrangement(owner, student.id, task.id, plan)
    assert service.send(student.id, task.id) is None
    assert len(service.history(owner, student.id, task.id)) == 3
    assert db_session.scalar(select(func.count()).select_from(DeadlineArrangement)) == 3
    with pytest.raises(IntegrityError, match="immutable"):
        db_session.execute(text("UPDATE deadline_arrangements SET reason='replace'"))
    db_session.rollback()


def test_course_local_time_requires_an_explicit_ambiguous_occurrence():
    repeated = datetime(2026, 4, 5, 2, 30)
    with pytest.raises(ReminderError, match="occurs twice"):
        course_instant(repeated, "Australia/Sydney", None)
    assert course_instant(repeated, "Australia/Sydney", 1) - course_instant(
        repeated, "Australia/Sydney", 0
    ) == timedelta(hours=1)
    with pytest.raises(ReminderError, match="does not exist"):
        course_instant(datetime(2026, 10, 4, 2, 30), "Australia/Sydney", None)


def test_invalid_zone_and_stale_or_shortened_deadlines_do_not_create_history(db_session):
    with pytest.raises(ValidationError, match="valid IANA"):
        CourseUpdate(time_zone="Not/AZone")
    student, task, owner = context(db_session)
    service = ReminderService(db_session, now=NOW)
    command = DeadlineArrangementWrite(
        expected_revision=0,
        idempotency_key="extension",
        kind="EXTENSION",
        time_zone="UTC",
        local_due_at=(NOW - timedelta(days=3)).replace(tzinfo=None),
        reason="Scheduling decision",
        learner_notice="Deadline changed.",
    )
    with pytest.raises(ReminderError, match="earlier than"):
        service.save_arrangement(owner, student.id, task.id, command)
    db_session.rollback()
    with pytest.raises(ReminderError, match="time zone changed"):
        service.save_arrangement(
            owner, student.id, task.id, command.model_copy(update={"time_zone": "Australia/Sydney"})
        )
    db_session.rollback()
    with pytest.raises(ReminderError, match="changed. Reload"):
        service.save_arrangement(
            owner, student.id, task.id, command.model_copy(update={"expected_revision": 1})
        )
    db_session.rollback()
    assert service.history(owner, student.id, task.id) == []


def test_worker_restart_and_global_disable_do_not_duplicate_or_invent_task_views(db_session):
    student, task, _ = context(db_session)
    factory = sessionmaker(bind=db_session.get_bind())
    db_session.commit()
    event_count = db_session.scalar(select(func.count()).select_from(LearningEvent))
    assert asyncio.run(ReminderWorker(factory, now=lambda: NOW).run_once())
    assert asyncio.run(ReminderWorker(factory, now=lambda: NOW).run_once())
    assert db_session.scalar(select(func.count()).select_from(LearningEvent)) == event_count
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(Reminder)
            .where(Reminder.student_id == student.id, Reminder.task_id == task.id)
        )
        == 1
    )
    setting = db_session.scalar(
        select(SystemSetting).where(SystemSetting.key == "reminders_enabled")
    )
    setting.value = False
    db_session.commit()
    assert (
        ReminderService(db_session, now=NOW + timedelta(days=2)).send(student.id, task.id) is None
    )
