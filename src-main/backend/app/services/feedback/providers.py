"""SQLAlchemy-backed context providers for the production feedback composition."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import LearningTask
from app.schemas.feedback import TaskContext
from app.services.task_context import to_feedback_task_context


class SqlAlchemyTaskProvider:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def get_task(self, task_id: str) -> TaskContext | None:
        task = self._session.get(LearningTask, task_id)
        return to_feedback_task_context(task) if task is not None else None
