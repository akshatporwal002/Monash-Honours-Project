"""Order task-view telemetry writes without gating other database operations."""

import asyncio
import sqlite3
import threading
import time
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from weakref import WeakKeyDictionary

from sqlalchemy import Engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool


def _busy_error() -> OperationalError:
    error = sqlite3.OperationalError("database is locked: task-view admission budget expired")
    error.sqlite_errorcode = sqlite3.SQLITE_BUSY
    error.sqlite_errorname = "SQLITE_BUSY"
    return OperationalError(None, None, error)


class _Admission:
    def __init__(self) -> None:
        self.condition = threading.Condition()
        self.queue: deque[object] = deque()
        self.owner: object | None = None

    def acquire(self, deadline: float) -> object:
        ticket = object()
        with self.condition:
            self.queue.append(ticket)
            try:
                while self.owner is not None or self.queue[0] is not ticket:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise _busy_error()
                    self.condition.wait(remaining)
                if time.monotonic() >= deadline:
                    raise _busy_error()
                self.queue.popleft()
                self.owner = ticket
                return ticket
            finally:
                if ticket in self.queue:
                    self.queue.remove(ticket)
                    self.condition.notify_all()

    def release(self, ticket: object) -> None:
        with self.condition:
            if self.owner is ticket:
                self.owner = None
                self.condition.notify_all()


_admissions: WeakKeyDictionary[Engine, _Admission] = WeakKeyDictionary()
_registry_lock = threading.Lock()


def _admission_for(engine: Engine) -> _Admission:
    with _registry_lock:
        if engine not in _admissions:
            _admissions[engine] = _Admission()
        return _admissions[engine]


def _eligible_engine(bind: Any) -> bool:
    if not isinstance(bind, Engine) or not isinstance(bind.pool, NullPool):
        return False
    if bind.dialect.name != "sqlite":
        return False
    url = bind.url
    return (
        url.database not in {None, "", ":memory:"}
        and url.query.get("mode") != "memory"
        and not url.database.startswith("file::memory:")
    )


def _set_busy_timeout(driver: Any, milliseconds: int) -> None:
    cursor = driver.cursor()
    try:
        cursor.execute("PRAGMA busy_timeout=" + str(milliseconds))
    finally:
        cursor.close()


class _WriteBudget:
    def __init__(self, driver: Any, deadline: float) -> None:
        self.driver = driver
        self.deadline = deadline

    def refresh(self, *_args: Any) -> None:
        # A listener whose removal failed must become inert and stop retaining
        # the old physical connection before this scope exits.
        if self.driver is None:
            return
        remaining_ms = max(0, int((self.deadline - time.monotonic()) * 1000))
        if remaining_ms <= 0:
            raise _busy_error()
        _set_busy_timeout(self.driver, remaining_ms)


@contextmanager
def task_view_write_admission(session: Session) -> Iterator[None]:
    """Wrap only the final TASK_VIEW event and commit after access projection.

    The eligible path starts without caller writes and owns its failure cleanup.
    Other engine pools, existing transactions and async callers retain their
    original behavior. Each engine/process orders only its own task-view writes;
    SQLite still arbitrates against every other writer.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        yield
        return
    if session.new or session.dirty or session.deleted:
        yield
        return
    bind = session.get_bind()
    if not _eligible_engine(bind):
        yield
        return
    connection = session.connection()
    driver = connection.connection.driver_connection
    if driver.in_transaction:
        yield
        return
    cursor = driver.cursor()
    try:
        original_ms = int(cursor.execute("PRAGMA busy_timeout").fetchone()[0])
    finally:
        cursor.close()
    if original_ms <= 0:
        yield
        return

    deadline = time.monotonic() + original_ms / 1000
    admission = _admission_for(bind)
    ticket = admission.acquire(deadline)
    budget = _WriteBudget(driver, deadline)
    refresh = budget.refresh
    listeners: list[str] = []
    primary_error: BaseException | None = None
    try:
        # The only pending INSERT is the task-view event. Refresh after its
        # flush as well so COMMIT cannot add a second full SQLite wait budget.
        for name in ("before_flush", "after_flush_postexec"):
            listeners.append(name)
            event.listen(session, name, refresh)
        budget.refresh()
        yield
    except BaseException as error:
        primary_error = error
        try:
            session.rollback()
        except BaseException:
            try:
                session.invalidate()
            except BaseException:
                # Keep the operation's original error; request/session cleanup
                # still runs, and admission must release even if the driver fails.
                pass
        raise
    finally:
        budget.driver = None
        cleanup_errors: list[BaseException] = []
        try:
            failed_removals = []
            for name in listeners:
                try:
                    event.remove(session, name, refresh)
                except BaseException as error:
                    cleanup_errors.append(error)
                    failed_removals.append(name)
            # Attempt every listener first, then retry any still-attached one.
            # Persistent removal failures leave only the inert budget above.
            for name in failed_removals:
                try:
                    if event.contains(session, name, refresh):
                        event.remove(session, name, refresh)
                except BaseException as error:
                    cleanup_errors.append(error)
            # NullPool physically closes the driver on successful commit or
            # rollback. A live connection must regain its previous setting.
            if not connection.closed and not connection.invalidated:
                try:
                    _set_busy_timeout(driver, original_ms)
                except BaseException as error:
                    cleanup_errors.append(error)
                    try:
                        connection.invalidate()
                    except BaseException as invalidation_error:
                        cleanup_errors.append(invalidation_error)
        finally:
            admission.release(ticket)
        if cleanup_errors and primary_error is None:
            raise cleanup_errors[0]
