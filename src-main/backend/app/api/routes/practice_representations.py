"""Self-only reviewed practice content with explicit, idempotent delivery."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentStudent
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.practice_representations import (
    PracticeRepresentationCatalog,
    PracticeRepresentationReceipt,
    PracticeRepresentationRequest,
)
from app.services.lms import LmsServiceError
from app.services.practice_representations import PracticeRepresentationService
from app.services.task_review import TaskReviewError

router = APIRouter(prefix="/practice-representations", tags=["practice representations"])


def _headers(request, response):
    response.headers["Cache-Control"] = "no-store"
    if request.query_params:
        raise HTTPException(422, "Unexpected representation query field")


def _call(operation):
    try:
        return operation()
    except (LmsServiceError, TaskReviewError) as error:
        raise HTTPException(error.status_code, error.detail) from None
    except PermissionError:
        raise HTTPException(403, "Only the enrolled learner can request this content") from None


@router.get("/tasks/{task_id}", response_model=PracticeRepresentationCatalog)
def catalog(
    task_id: str,
    request: Request,
    response: Response,
    student: CurrentStudent,
    session: Session = Depends(get_db),
):
    _headers(request, response)
    return _call(lambda: PracticeRepresentationService(session).catalog(student, task_id))


@router.post("/tasks/{task_id}/deliver", response_model=PracticeRepresentationReceipt)
async def deliver(
    task_id: str,
    command: PracticeRepresentationRequest,
    request: Request,
    response: Response,
    student: CurrentStudent,
    session: Session = Depends(get_db),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    _headers(request, response)
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(student.id), role=student.role.value),
        "practice-representations",
        mutating=True,
    )
    return _call(lambda: PracticeRepresentationService(session).deliver(student, task_id, command))
