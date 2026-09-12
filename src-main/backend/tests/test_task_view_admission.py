"""Task-view writes keep their event and deadline while waiting their turn."""

import asyncio
import sqlite3
import threading
import time
from contextlib import closing

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, registry
from sqlalchemy.pool import NullPool, QueuePool
from support.learning_loop import seed_learning_loop

from app.db import task_view_admission as admission
from app.db.session import create_db_engine, create_session_factory
from app.models import LearningEvent, LearningEventType, User
from app.models.lms import Enrollment
from app.services.lms import LmsService, LmsServiceError

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


@pytest.fixture
def small_database(tmp_path):
    path = tmp_path / "admission.sqlite"
    engine = create_db_engine(f"sqlite:///{path.as_posix()}")
    mapper = registry(metadata=MetaData())
    table = Table("admission_entries", mapper.metadata, Column("id", Integer, primary_key=True))

    class Entry:
        def __init__(self, identity):
            self.id = identity

    mapper.map_imperatively(Entry, table)
    mapper.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory.begin() as session:
        session.add(Entry(1))
    yield path, engine, factory, Entry
    engine.dispose()
    mapper.dispose()


def join_threads(threads, errors):
    for thread in threads:
        thread.join(3)
        assert not thread.is_alive(), "An admitted writer did not finish"
    assert not errors


def test_real_task_views_wait_after_projection_and_keep_every_event(db_session, monkeypatch):
    fixture = seed_learning_loop(db_session)
    factory = create_session_factory(db_session.get_bind())
    first_inside = threading.Event()
    second_projected = threading.Event()
    second_inside = threading.Event()
    release_first = threading.Event()
    errors, committed, results = [], [], []
    original_projection = LmsService._student_task_projection
    original_event = LmsService._learning_event

    def project(service, *args):
        result = original_projection(service, *args)
        if threading.current_thread().name == "second-view":
            second_projected.set()
        return result

    def record(service, student, task, event_type, *args, **kwargs):
        result = original_event(service, student, task, event_type, *args, **kwargs)
        if event_type is LearningEventType.TASK_VIEW:
            if threading.current_thread().name == "first-view":
                first_inside.set()
                assert release_first.wait(3)
            else:
                second_inside.set()
        return result

    monkeypatch.setattr(LmsService, "_student_task_projection", project)
    monkeypatch.setattr(LmsService, "_learning_event", record)

    def view():
        try:
            with factory() as session:
                event.listen(session, "after_commit", lambda _session: committed.append(1))
                student = session.get(User, fixture["student_id"])
                results.append(LmsService(session).get_student_task(student, fixture["task_id"]))
        except BaseException as error:
            errors.append(error)

    threads = [threading.Thread(target=view, name=name) for name in ("first-view", "second-view")]
    threads[0].start()
    try:
        assert first_inside.wait(3)
        threads[1].start()
        assert second_projected.wait(3), "Admission must not block access validation/projection"
        bypassed_first = second_inside.wait(0.1)
    finally:
        release_first.set()
        join_threads([thread for thread in threads if thread.ident is not None], errors)
    assert not bypassed_first, "The second TASK_VIEW wrote before the first finished its turn"
    assert len(committed) == len(results) == 2
    assert results[0].model_dump() == results[1].model_dump()
    with factory() as session:
        records = session.scalars(
            select(LearningEvent).where(
                LearningEvent.task_id == fixture["task_id"],
                LearningEvent.event_type == LearningEventType.TASK_VIEW,
            )
        ).all()
        assert len(records) == 2
        assert len({record.deduplication_key for record in records}) == 2
        assert all(record.metadata_payload == {"source": "task-page"} for record in records)


def test_denied_task_view_never_enters_admission_or_writes_event(db_session, monkeypatch):
    fixture = seed_learning_loop(db_session)
    enrollment = db_session.scalar(
        select(Enrollment).where(
            Enrollment.student_id == fixture["student_id"],
            Enrollment.course_id == fixture["course_id"],
        )
    )
    db_session.delete(enrollment)
    db_session.commit()
    student = db_session.get(User, fixture["student_id"])

    def unexpected_admission(_session):
        pytest.fail("Access denial must occur before task-view admission")

    monkeypatch.setattr("app.services.lms.task_view_write_admission", unexpected_admission)
    with pytest.raises(LmsServiceError):
        LmsService(db_session).get_student_task(student, fixture["task_id"])
    assert not db_session.scalars(
        select(LearningEvent).where(
            LearningEvent.task_id == fixture["task_id"],
            LearningEvent.event_type == LearningEventType.TASK_VIEW,
        )
    ).all()


@pytest.mark.parametrize("block_commit", [False, True])
def test_queue_and_sqlite_share_budget_and_failed_write_rolls_back(small_database, block_commit):
    path, engine, factory, Entry = small_database
    owner_entered, release_owner = threading.Event(), threading.Event()
    errors = []
    observed_budgets = []

    def owner():
        try:
            with factory() as session, admission.task_view_write_admission(session):
                owner_entered.set()
                assert release_owner.wait(3)
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=owner)
    thread.start()
    assert owner_entered.wait(3)

    def insert_budget(connection, _cursor, statement, *_args):
        if statement.startswith("INSERT"):
            driver = connection.connection.driver_connection
            cursor = driver.cursor()
            try:
                observed_budgets.append(cursor.execute("PRAGMA busy_timeout").fetchone()[0])
            finally:
                cursor.close()

    event.listen(engine, "before_cursor_execute", insert_budget)
    try:
        with closing(sqlite3.connect(path)) as foreign, factory() as session:
            foreign.execute("BEGIN" if block_commit else "BEGIN IMMEDIATE")
            foreign.execute(
                "SELECT * FROM admission_entries"
                if block_commit
                else "UPDATE admission_entries SET id=id"
            ).fetchall()
            session.connection().exec_driver_sql("PRAGMA busy_timeout=180")
            timer = threading.Timer(0.08, release_owner.set)
            timer.start()
            began = time.monotonic()
            try:
                with pytest.raises(OperationalError) as raised:
                    with admission.task_view_write_admission(session):
                        session.add(Entry(2))
                        session.commit()
                assert raised.value.orig.sqlite_errorcode == sqlite3.SQLITE_BUSY
                assert not session.in_transaction(), "Failed task-view transaction must finish"
                assert observed_budgets and 0 < observed_budgets[0] < 150
                # Scheduler/SQLite granularity can overshoot a short test budget.
                assert time.monotonic() - began < 0.8
            finally:
                foreign.rollback()
                timer.join(3)
    finally:
        release_owner.set()
        join_threads([thread], errors)
        event.remove(engine, "before_cursor_execute", insert_budget)
    with factory() as session:
        assert session.get(Entry, 2) is None
        with admission.task_view_write_admission(session):
            session.add(Entry(3))
            session.commit()


def test_queue_expiry_removes_ticket_and_preserves_busy_error_type(small_database):
    _path, _engine, factory, Entry = small_database
    with factory() as owner, admission.task_view_write_admission(owner):
        with factory() as waiting:
            waiting.connection().exec_driver_sql("PRAGMA busy_timeout=30")
            with pytest.raises(OperationalError) as raised:
                with admission.task_view_write_admission(waiting):
                    pytest.fail("Expired writer entered the event body")
            assert raised.value.orig.sqlite_errorcode == sqlite3.SQLITE_BUSY
    with factory() as session, admission.task_view_write_admission(session):
        session.add(Entry(2))
        session.commit()


@pytest.mark.parametrize("guard", ["new", "dirty", "deleted", "transaction", "event_loop"])
def test_existing_work_and_event_loops_bypass_waiting_gate(small_database, guard):
    _path, _engine, factory, Entry = small_database
    with factory() as owner, admission.task_view_write_admission(owner):
        with factory() as session:
            if guard == "new":
                session.add(Entry(2))
            elif guard in {"dirty", "deleted"}:
                row = session.get(Entry, 1)
                if guard == "dirty":
                    row.id = 2
                else:
                    session.delete(row)
            elif guard == "transaction":
                session.connection().exec_driver_sql("BEGIN")
            session.connection().exec_driver_sql("PRAGMA busy_timeout=30")

            def enter():
                with admission.task_view_write_admission(session):
                    return True

            async def enter_async():
                return enter()

            assert asyncio.run(enter_async()) if guard == "event_loop" else enter()
            session.rollback()


@pytest.mark.parametrize("url_kind", ["memory", "memory_nullpool", "pooled_file"])
def test_other_sqlite_pools_keep_original_connection_budget(tmp_path, url_kind):
    url = (
        "sqlite:///:memory:"
        if url_kind.startswith("memory")
        else f"sqlite:///{tmp_path / 'pooled.db'}"
    )
    engine = create_engine(url, poolclass=NullPool if url_kind == "memory_nullpool" else QueuePool)
    try:
        with Session(engine) as session:
            with admission.task_view_write_admission(session):
                session.connection().exec_driver_sql("PRAGMA busy_timeout=1234")
            assert session.connection().exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 1234
            session.commit()
    finally:
        engine.dispose()


@pytest.mark.parametrize("primary_failure", [False, True])
def test_listener_cleanup_attempts_every_removal_and_preserves_primary(
    small_database, monkeypatch, primary_failure
):
    _path, _engine, factory, Entry = small_database
    original_remove, original_listen = event.remove, event.listen
    removals, listeners = [], []
    failed_once = False

    with factory() as session:

        def listen(target, name, function, *args, **kwargs):
            if target is session:
                listeners.append((name, function))
            return original_listen(target, name, function, *args, **kwargs)

        def remove(target, name, function):
            nonlocal failed_once
            if target is session:
                removals.append(name)
                if name == "before_flush" and not failed_once:
                    failed_once = True
                    raise RuntimeError("Synthetic listener cleanup failure")
            return original_remove(target, name, function)

        monkeypatch.setattr(event, "listen", listen)
        monkeypatch.setattr(event, "remove", remove)
        expected = ValueError if primary_failure else RuntimeError
        with pytest.raises(expected) as raised:
            with admission.task_view_write_admission(session):
                if primary_failure:
                    raise ValueError("Original operation failure")
        assert str(raised.value) == (
            "Original operation failure"
            if primary_failure
            else "Synthetic listener cleanup failure"
        )
        assert set(removals) == {"before_flush", "after_flush_postexec"}
        assert all(not event.contains(session, name, function) for name, function in listeners)
        with admission.task_view_write_admission(session):
            session.add(Entry(2))
            session.commit()


def test_timeout_restore_failure_discards_connection_and_releases_turn(small_database, monkeypatch):
    _path, _engine, factory, Entry = small_database
    original = admission._set_busy_timeout
    armed = False

    def fail_restore(driver, milliseconds):
        if armed and milliseconds == 30000:
            raise RuntimeError("Synthetic timeout restoration failure")
        original(driver, milliseconds)

    with factory() as session:
        connection = session.connection()
        monkeypatch.setattr(admission, "_set_busy_timeout", fail_restore)
        with pytest.raises(RuntimeError, match="Synthetic timeout restoration failure"):
            with admission.task_view_write_admission(session):
                armed = True
        assert connection.invalidated or connection.closed
    monkeypatch.setattr(admission, "_set_busy_timeout", original)
    with factory() as session, admission.task_view_write_admission(session):
        session.add(Entry(2))
        session.commit()


def test_rollback_failure_discards_failed_event_and_preserves_primary(small_database, monkeypatch):
    _path, _engine, factory, Entry = small_database
    with factory() as session:

        def fail_rollback():
            raise RuntimeError("Synthetic rollback failure")

        monkeypatch.setattr(session, "rollback", fail_rollback)
        with pytest.raises(ValueError, match="Original event failure"):
            with admission.task_view_write_admission(session):
                session.add(Entry(2))
                session.flush()
                raise ValueError("Original event failure")
        assert not session.in_transaction()
    with factory() as session, admission.task_view_write_admission(session):
        assert session.get(Entry, 2) is None
        session.add(Entry(3))
        session.commit()
