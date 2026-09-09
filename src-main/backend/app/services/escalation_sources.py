"""Resolve retained evidence and append replay-safe escalation signals."""

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from app.models.assessment import AssessmentAttempt
from app.models.escalation import EscalationCase
from app.models.lms import SubmissionAttempt
from app.models.persistence import FeedbackRecord, LearningTask
from app.models.tutor import TutorTurn


@dataclass(frozen=True)
class EscalationSource:
    student_id: int
    task: LearningTask
    record: object


def source_for(session, kind, source_id):
    if kind == "FEEDBACK":
        record = session.get(FeedbackRecord, source_id)
        response = session.get(SubmissionAttempt, record.submission_id) if record else None
    elif kind == "TUTOR":
        record = response = session.get(TutorTurn, source_id)
    elif kind == "ASSESSMENT":
        record = response = session.get(AssessmentAttempt, source_id)
    else:
        return None
    if response is None:
        return None
    task = session.get(LearningTask, response.task_id)
    if task is None or task.course_id is None:
        return None
    return EscalationSource(response.student_id, task, record)


def record_signal(
    session,
    *,
    source_kind,
    source_id,
    trigger,
    reason,
    queue_kind="ASSESSOR",
    severity="HIGH",
    request_key=None,
):
    """Join the producer transaction; older opaque workflows have no learner case."""
    key = request_key or f"{trigger}:{source_kind}:{source_id}"
    existing = session.scalar(select(EscalationCase).where(EscalationCase.request_key == key))
    if existing:
        return existing
    source = source_for(session, source_kind, source_id)
    if source is None:
        return None
    case = EscalationCase(
        id=str(uuid5(NAMESPACE_URL, f"learnlens-escalation:{key}")),
        course_id=source.task.course_id,
        task_id=source.task.id,
        student_id=source.student_id,
        source_kind=source_kind,
        source_id=source_id,
        queue_kind=queue_kind,
        trigger=trigger,
        severity=severity,
        reason=reason,
        request_key=key,
    )
    session.add(case)
    session.flush()
    return case


def route_feedback_report(session, report):
    return record_signal(
        session,
        source_kind="FEEDBACK",
        source_id=report.feedback_id,
        trigger="LEARNER_REPORT",
        reason=report.note or report.category.value,
        severity="NORMAL",
        request_key=f"feedback-report:{report.id}",
    )
