"""Self-only reviewed practice content with explicit, idempotent delivery."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentEducator, CurrentStudent
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.practice_representations import (
    PracticeRepresentationCatalog,
    PracticeRepresentationReceipt,
    PracticeRepresentationRequest,
)
from app.schemas.representation_generation import (
    RepresentationGenerationRead,
    RepresentationGenerationWrite,
)
from app.services.llm import StructuredModelError
from app.services.lms import LmsServiceError
from app.services.practice_representations import PracticeRepresentationService
from app.services.provider_usage import ProviderBudgetError
from app.services.representation_drafts import (
    RepresentationDraftService,
    configured_representation_client,
)
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


@router.post("/tasks/{task_id}/generate", response_model=RepresentationGenerationRead)
async def generate_draft(
    task_id: str,
    command: RepresentationGenerationWrite,
    request: Request,
    response: Response,
    educator: CurrentEducator,
    session: Session = Depends(get_db),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    _headers(request, response)
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(educator.id), role=educator.role.value),
        "practice-representations",
        mutating=True,
    )
    try:
        return await RepresentationDraftService(
            session, configured_representation_client(session)
        ).generate(educator, task_id, command)
    except (LmsServiceError, TaskReviewError) as error:
        raise HTTPException(error.status_code, error.detail) from None
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except (StructuredModelError, ProviderBudgetError):
        raise HTTPException(
            503, "Representation generation is unavailable; the saved task is unchanged"
        ) from None
