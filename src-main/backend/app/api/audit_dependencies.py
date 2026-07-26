from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.audit import BestEffortAuditSink, IndependentAuditRecorder
from app.services.audit_events import (
    FeedbackAuditEvents,
    NullStudentAuditTracker,
    StudentAuditTracker,
)
from app.services.learning_events import HmacSha256Pseudonymizer


@lru_cache
def get_feedback_audit_events() -> FeedbackAuditEvents:
    recorder = IndependentAuditRecorder(SessionLocal)
    sink = BestEffortAuditSink(lambda: recorder)
    return FeedbackAuditEvents(sink)


@lru_cache
def get_student_audit_tracker() -> StudentAuditTracker | NullStudentAuditTracker:
    configured = settings.learning_event_pseudonym_secret
    if configured is None:
        return NullStudentAuditTracker()
    secret = configured.get_secret_value()
    try:
        pseudonymizer = HmacSha256Pseudonymizer(secret)
    except Exception:
        return NullStudentAuditTracker()
    return StudentAuditTracker(get_feedback_audit_events(), pseudonymizer)
