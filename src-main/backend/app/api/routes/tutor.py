"""Learner-owned tutor dialogue with the same CSRF and rate controls as feedback."""

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentStudent
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.tutor import TutorConversationRead, TutorTurnRead, TutorTurnWrite
from app.services.lms import LmsServiceError
from app.services.task_review import TaskReviewError
from app.services.tutor import TutorService

router = APIRouter(prefix="/students/me/tasks", tags=["tutor"])


def get_tutor(
    response: Response, session: Session = Depends(get_db)
) -> Generator[TutorService, None, None]:
    response.headers["Cache-Control"] = "no-store"
    try:
        yield TutorService(session)
    except (LmsServiceError, TaskReviewError) as error:
        session.rollback()
        raise HTTPException(error.status_code, error.detail) from error


Tutor = Annotated[TutorService, Depends(get_tutor)]


@router.get("/{task_id}/tutor", response_model=TutorConversationRead)
def read_conversation(
    task_id: str, student: CurrentStudent, service: Tutor, offset: int = Query(0, ge=0)
):
    return service.read(student, task_id, offset=offset)


@router.post("/{task_id}/tutor", response_model=TutorTurnRead, status_code=201)
async def send_message(
    task_id: str,
    payload: TutorTurnWrite,
    request: Request,
    student: CurrentStudent,
    service: Tutor,
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(student.id), role=student.role.value),
        "tutor",
        mutating=True,
    )
    return service.send(student, task_id, payload)
