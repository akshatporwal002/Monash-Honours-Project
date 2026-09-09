"""Scoped notification preferences and individual deadline arrangements."""

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentEducator, CurrentStudent
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db
from app.models.persistence import LearningTask
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.reminders import (
    DeadlineArrangementRead,
    DeadlineArrangementWrite,
    LearnerDeadlineRead,
    ReminderPreferenceRead,
    ReminderPreferenceWrite,
)
from app.services.lms import LmsService, LmsServiceError
from app.services.reminders import ReminderError, ReminderService
from app.services.task_review import TaskReviewError

router = APIRouter(tags=["reminders"])


def get_service(
    response: Response, session: Annotated[Session, Depends(get_db)]
) -> Generator[ReminderService, None, None]:
    response.headers["Cache-Control"] = "no-store"
    try:
        yield ReminderService(session)
    except (ReminderError, LmsServiceError, TaskReviewError) as error:
        session.rollback()
        raise HTTPException(
            error.status_code, error.detail, headers={"Cache-Control": "no-store"}
        ) from error
    except (IntegrityError, OperationalError) as error:
        session.rollback()
        raise HTTPException(
            409,
            "Reminder settings changed or are busy. Reload before retrying.",
            headers={"Cache-Control": "no-store"},
        ) from error


Reminders = Annotated[ReminderService, Depends(get_service)]
Security = Annotated[RequestSecurityGuard, Depends(get_request_security_guard)]


@router.get("/students/me/reminder-preferences", response_model=ReminderPreferenceRead)
def preferences(learner: CurrentStudent, service: Reminders):
    return service.preference(learner.id)


@router.put("/students/me/reminder-preferences", response_model=ReminderPreferenceRead)
async def save_preferences(
    payload: ReminderPreferenceWrite,
    request: Request,
    learner: CurrentStudent,
    service: Reminders,
    security: Security,
):
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(learner.id), role=learner.role.value),
        "reminders",
        mutating=True,
    )
    return service.save_preference(learner.id, payload)


@router.get("/students/me/tasks/{task_id}/deadline", response_model=LearnerDeadlineRead)
def learner_deadline(task_id: str, learner: CurrentStudent, service: Reminders):
    LmsService(service.session).get_task_for_actor(learner, task_id)
    return service.deadline(learner.id, service.session.get(LearningTask, task_id))


@router.get(
    "/tasks/{task_id}/deadline-arrangements/{student_id}",
    response_model=list[DeadlineArrangementRead],
)
def history(
    task_id: str,
    student_id: int,
    educator: CurrentEducator,
    service: Reminders,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    return service.history(educator, student_id, task_id, limit=limit, offset=offset)


@router.put(
    "/tasks/{task_id}/deadline-arrangements/{student_id}", response_model=DeadlineArrangementRead
)
async def save_arrangement(
    task_id: str,
    student_id: int,
    payload: DeadlineArrangementWrite,
    request: Request,
    educator: CurrentEducator,
    service: Reminders,
    security: Security,
):
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(educator.id), role=educator.role.value),
        "reminders",
        mutating=True,
    )
    return service.save_arrangement(educator, student_id, task_id, payload)
