"""Reuse successful validation reads only inside one explicit service read."""

from contextvars import ContextVar
from functools import wraps
from inspect import signature

from sqlalchemy import event

_active = ContextVar("validation_read_scope", default=None)


def validation_read_scope(operation):
    """Discard all reuse when this operation returns, raises, or mutates data."""

    @wraps(operation)
    def read(self, *args, **kwargs):
        cache = {}
        session = self.session
        token = _active.set((session, cache))

        def invalidate(*unused):
            cache.clear()

        def statement(execution):
            if not execution.is_select:
                cache.clear()

        events = [
            ("after_flush", invalidate),
            ("after_commit", invalidate),
            ("after_rollback", invalidate),
            ("do_orm_execute", statement),
        ]
        for name, handler in events:
            event.listen(session, name, handler)
        try:
            return operation(self, *args, **kwargs)
        finally:
            for name, handler in events:
                event.remove(session, name, handler)
            _active.reset(token)

    return read


def reuse_validation_read(operation):
    """Opt in a side-effect-free validation; outside a scope always re-read."""

    parameters = signature(operation)

    @wraps(operation)
    def read(self, *args, **kwargs):
        active = _active.get()
        if active is None or active[0] is not self.session:
            return operation(self, *args, **kwargs)
        cache = active[1]
        if self.session.new or self.session.dirty or self.session.deleted:
            cache.clear()
            return operation(self, *args, **kwargs)
        bound = parameters.bind(self, *args, **kwargs)
        bound.apply_defaults()
        key = (
            operation,
            tuple((name, value) for name, value in bound.arguments.items() if name != "self"),
        )
        if key not in cache:
            cache[key] = operation(self, *args, **kwargs)
        return cache[key]

    return read
