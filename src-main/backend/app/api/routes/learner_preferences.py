"""Authenticated self-only settings. Query parameters never select an owner."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentStudent
from app.api.routes.lms import get_lms_service
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.learner_preferences import (
    EffectivePreferences,
    PreferenceHistory,
    PreferenceRead,
    PreferenceReset,
    PreferenceUpdate,
)
from app.services.learner_preferences import (
    LearnerPreferenceService,
    PreferenceConflict,
    PreferenceUnavailable,
)
from app.services.lms import LmsService

router = APIRouter(prefix="/learner-preferences", tags=["learner preferences"])


@router.get("/me/tasks/{task_id}/effective", response_model=EffectivePreferences)
def effective(
    task_id: str,
    request: Request,
    response: Response,
    student: CurrentStudent,
    service: LmsService = Depends(get_lms_service),
):
    _query(request, response)
    return service.effective_preferences(student, task_id)


def _query(request: Request, response: Response, allowed: tuple[str, ...] = ()):
    response.headers["Cache-Control"] = "no-store"
    if any(key not in allowed for key in request.query_params):
        raise HTTPException(422, "Unexpected preference query field")


@router.get("/me", response_model=PreferenceRead)
def read(
    request: Request,
    response: Response,
    student: CurrentStudent,
    session: Session = Depends(get_db),
):
    _query(request, response)
    return LearnerPreferenceService(session).read(student)


@router.get("/me/history", response_model=PreferenceHistory)
def history(
    request: Request,
    response: Response,
    student: CurrentStudent,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_db),
):
    _query(request, response, ("offset", "limit"))
    return LearnerPreferenceService(session).history(student, offset=offset, limit=limit)


async def _write(payload, request, response, student, session, security):
    _query(request, response)
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(student.id), role=student.role.value),
        "learner-preferences",
        mutating=True,
    )
    try:
        return LearnerPreferenceService(session).save(student, payload)
    except PreferenceConflict as error:
        raise HTTPException(409, str(error)) from None
    except PreferenceUnavailable as error:
        raise HTTPException(503, str(error)) from None


@router.put("/me", response_model=PreferenceRead)
async def save(
    payload: PreferenceUpdate,
    request: Request,
    response: Response,
    student: CurrentStudent,
    session: Session = Depends(get_db),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    return await _write(payload, request, response, student, session, security)


@router.post("/me/reset", response_model=PreferenceRead)
async def reset(
    payload: PreferenceReset,
    request: Request,
    response: Response,
    student: CurrentStudent,
    session: Session = Depends(get_db),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    return await _write(payload, request, response, student, session, security)
