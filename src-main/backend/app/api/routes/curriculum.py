"""Mounted, scoped curriculum and diagnostic commands."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentEducator, CurrentStudent, CurrentUser
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db
from app.schemas.curriculum import (
    DiagnosticConfirm,
    DiagnosticRead,
    DiagnosticStart,
    DiagnosticSubmit,
    PathwayPublish,
    PathwayRead,
)
from app.schemas.feedback_api import AuthenticatedActor
from app.services.curriculum import CurriculumService

router = APIRouter(prefix="/curriculum", tags=["curriculum"])


def _read(request, response, allowed=()):
    response.headers["Cache-Control"] = "no-store"
    if any(key not in allowed for key in request.query_params):
        raise HTTPException(422, "Unexpected curriculum query field")


async def _guard(request, response, actor, security):
    _read(request, response)
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(actor.id), role=actor.role.value),
        "curriculum",
        mutating=True,
    )


@router.get("/courses/{course_id}/pathways", response_model=list[PathwayRead])
def pathways(
    course_id: str,
    request: Request,
    response: Response,
    actor: CurrentUser,
    session: Session = Depends(get_db),
):
    _read(request, response)
    return CurriculumService(session).list_paths(actor, course_id)


@router.post("/outcomes/{outcome_id}/pathways", response_model=PathwayRead)
async def publish(
    outcome_id: str,
    payload: PathwayPublish,
    request: Request,
    response: Response,
    actor: CurrentEducator,
    session: Session = Depends(get_db),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    await _guard(request, response, actor, security)
    return CurriculumService(session).publish(actor, outcome_id, payload)


@router.get("/courses/{course_id}/diagnostics", response_model=list[DiagnosticRead])
def diagnostics(
    course_id: str,
    request: Request,
    response: Response,
    actor: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_db),
):
    _read(request, response, ("offset", "limit"))
    return CurriculumService(session).list_diagnostics(actor, course_id, offset=offset, limit=limit)


@router.post("/diagnostics", response_model=DiagnosticRead)
async def start(
    payload: DiagnosticStart,
    request: Request,
    response: Response,
    actor: CurrentStudent,
    session: Session = Depends(get_db),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    await _guard(request, response, actor, security)
    return CurriculumService(session).start(actor, payload)


@router.get("/diagnostics/{identity}", response_model=DiagnosticRead)
def read(
    identity: str,
    request: Request,
    response: Response,
    actor: CurrentUser,
    session: Session = Depends(get_db),
):
    _read(request, response)
    return CurriculumService(session).read(actor, identity)


@router.post("/diagnostics/{identity}/response", response_model=DiagnosticRead)
async def submit(
    identity: str,
    payload: DiagnosticSubmit,
    request: Request,
    response: Response,
    actor: CurrentStudent,
    session: Session = Depends(get_db),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    await _guard(request, response, actor, security)
    return CurriculumService(session).submit(actor, identity, payload)


@router.post("/diagnostics/{identity}/confirmation", response_model=DiagnosticRead)
async def confirm(
    identity: str,
    payload: DiagnosticConfirm,
    request: Request,
    response: Response,
    actor: CurrentUser,
    session: Session = Depends(get_db),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    await _guard(request, response, actor, security)
    return CurriculumService(session).confirm(actor, identity, payload)
