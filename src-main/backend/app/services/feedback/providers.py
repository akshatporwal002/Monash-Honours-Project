"""SQLAlchemy-backed context providers for the production feedback composition."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import LearningTask, StudentSubmission
from app.schemas.feedback import SubmissionContext, TaskContext
from app.services.task_context import to_feedback_task_context


class SqlAlchemySubmissionProvider:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def get_submission(self, submission_id: str) -> SubmissionContext | None:
        submission = self._session.get(StudentSubmission, submission_id)
        if submission is None or submission.submitted_at is None or not submission.answer.strip():
            return None
        return SubmissionContext(
            submission_id=submission.id,
            task_id=submission.task_id,
            student_id=submission.student_id,
            attempt_number=max(1, submission.attempts),
            submitted_answer=submission.answer,
            score=float(submission.score),
            submitted_at=submission.submitted_at,
        )


class SqlAlchemyTaskProvider:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def get_task(self, task_id: str) -> TaskContext | None:
        task = self._session.get(LearningTask, task_id)
        return to_feedback_task_context(task) if task is not None else None
