"""Mounted learner choices and course-owner overrides."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.background_execution import run_session_work
from app.api.dependencies.roles import CurrentEducator, CurrentUser
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db
from app.models.activity_continuation import ActivityProgress
from app.models.persistence import WorkflowRun
from app.schemas.activity_continuation import ActivityAction, ActivityRead
from app.schemas.feedback_api import AuthenticatedActor
from app.services.continuation.activity import ActivityService
from app.services.curriculum import CurriculumService

router = APIRouter(prefix="/activity-continuation", tags=["activity-continuation"])


def read_headers(request, response, allowed=()):
    response.headers["Cache-Control"] = "no-store"
    if any(key not in allowed for key in request.query_params):
        raise HTTPException(422, "Unexpected activity query field")


@router.get("/submissions/{submission_id}", response_model=ActivityRead | None)
def submission(
    submission_id: str,
    request: Request,
    response: Response,
    actor: CurrentUser,
    session: Session = Depends(get_db),
):
    read_headers(request, response)
    workflow = session.scalar(select(WorkflowRun).where(WorkflowRun.submission_id == submission_id))
    if not workflow:
        raise HTTPException(404, "Activity continuation is unavailable")
    return ActivityService(session).read(actor, workflow.id)


@router.get("/courses/{course_id}", response_model=list[ActivityRead])
def course(
    course_id: str,
    request: Request,
    response: Response,
    actor: CurrentEducator,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_db),
):
    read_headers(request, response, ("offset", "limit"))
    CurriculumService(session)._access(actor, course_id, owner=True)
    ids = session.scalars(
        select(ActivityProgress.workflow_id)
        .where(ActivityProgress.course_id == course_id)
        .order_by(ActivityProgress.created_at.desc(), ActivityProgress.workflow_id)
        .offset(offset)
        .limit(limit)
    )
    return [ActivityService(session).read(actor, identity) for identity in ids]


@router.get("/{workflow_id}", response_model=ActivityRead)
def read(
    workflow_id: str,
    request: Request,
    response: Response,
    actor: CurrentUser,
    session: Session = Depends(get_db),
):
    read_headers(request, response)
    return ActivityService(session).read(actor, workflow_id)


@router.post("/{workflow_id}/actions", response_model=ActivityRead)
async def action(
    workflow_id: str,
    payload: ActivityAction,
    request: Request,
    response: Response,
    actor: CurrentUser,
    session: Session = Depends(get_db),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    read_headers(request, response)
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(actor.id), role=actor.role.value),
        "activity_continuation",
        mutating=True,
    )

    def perform():
        try:
            return ActivityService(session).act(actor, workflow_id, payload)
        except SQLAlchemyError:
            session.rollback()
            raise HTTPException(
                503, "The choice could not be saved. Retry the original request"
            ) from None

    return await run_session_work(perform)
