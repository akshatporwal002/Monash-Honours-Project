"""Explicit educator review of immutable task revisions."""

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentEducator, CurrentUser
from app.db.session import get_db
from app.schemas.task_review import (
    TaskReviewEventRead,
    TaskReviewHistoryRead,
    TaskReviewSummary,
    TaskReviewWrite,
)
from app.services.task_review import TaskReviewError, TaskReviewService

router = APIRouter(prefix="/tasks/{task_id}/review")


def get_task_review_service(
    request: Request, session: Annotated[Session, Depends(get_db)]
) -> Generator[TaskReviewService, None, None]:
    try:
        yield TaskReviewService(
            session, correlation_id=getattr(request.state, "correlation_id", None)
        )
    except TaskReviewError as error:
        session.rollback()
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


Review = Annotated[TaskReviewService, Depends(get_task_review_service)]


@router.get("", response_model=TaskReviewSummary)
def get_review(task_id: str, actor: CurrentUser, service: Review) -> dict:
    return service.review_summary(actor, task_id)


@router.get("/history", response_model=list[TaskReviewHistoryRead])
def get_history(
    task_id: str,
    actor: CurrentUser,
    service: Review,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict]:
    return service.history(actor, task_id, limit=limit, offset=offset)


@router.post("", response_model=TaskReviewEventRead)
def record_review(task_id: str, payload: TaskReviewWrite, actor: CurrentEducator, service: Review):
    return service.record(actor, task_id, **payload.model_dump())
