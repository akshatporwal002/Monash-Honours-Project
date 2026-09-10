"""Authenticated learning-check commands with CSRF and scoped course access."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentEducator, CurrentStudent, CurrentUser
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.misconceptions import (
    MisconceptionAnswer,
    MisconceptionCandidateRead,
    MisconceptionExit,
    MisconceptionOpen,
    MisconceptionRead,
    MisconceptionReview,
)
from app.services.learner_model.safety import LearnerModelSafetyError
from app.services.lms import LmsServiceError
from app.services.misconceptions import MisconceptionService
from app.services.task_review import TaskReviewError

router = APIRouter(tags=["misconception checks"])


def get_service(response: Response, session: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    try:
        yield MisconceptionService(session)
    except (LmsServiceError, TaskReviewError) as error:
        session.rollback()
        raise HTTPException(error.status_code, str(error)) from error
    except LearnerModelSafetyError as error:
        session.rollback()
        raise HTTPException(422, "This learning-model update needs review") from error
    except (IntegrityError, OperationalError) as error:
        session.rollback()
        raise HTTPException(
            409, "The learning check changed or is busy. Refresh before retrying."
        ) from error


Service = Annotated[MisconceptionService, Depends(get_service)]
Security = Annotated[RequestSecurityGuard, Depends(get_request_security_guard)]


async def secure(request, actor, security):
    await security.enforce(
        request,
        AuthenticatedActor(
            actor_reference=str(actor.id),
            role=actor.role.value,
        ),
        "misconceptions",
        mutating=True,
    )


@router.post("/misconceptions/{identity}/exit", response_model=MisconceptionRead, status_code=201)
async def exit_check(
    identity: str,
    command: MisconceptionExit,
    request: Request,
    actor: CurrentUser,
    service: Service,
    security: Security,
):
    await secure(request, actor, security)
    return service.exit(actor, identity, command)


@router.get("/students/me/tasks/{task_id}/misconceptions", response_model=list[MisconceptionRead])
def mine(task_id: str, learner: CurrentStudent, service: Service):
    return service.list_for(learner, task_id, learner.id)


@router.get(
    "/educators/tasks/{task_id}/learners/{learner_id}/misconceptions",
    response_model=list[MisconceptionRead],
)
def teaching(task_id: str, learner_id: int, actor: CurrentEducator, service: Service):
    return service.list_for(actor, task_id, learner_id)


@router.get("/misconceptions/teaching", response_model=list[MisconceptionCandidateRead])
def candidates(actor: CurrentEducator, service: Service, offset: int = Query(0, ge=0)):
    return service.candidates(actor, offset)


@router.get("/misconceptions", response_model=list[MisconceptionRead])
def owned(actor: CurrentUser, service: Service, offset: int = Query(0, ge=0)):
    return service.list_owned(actor, offset)


@router.get("/misconceptions/{identity}", response_model=MisconceptionRead)
def read(identity: str, actor: CurrentUser, service: Service):
    return service.read(actor, identity)


@router.post("/misconceptions", response_model=MisconceptionRead, status_code=201)
async def open_check(
    command: MisconceptionOpen,
    request: Request,
    actor: CurrentEducator,
    service: Service,
    security: Security,
):
    await secure(request, actor, security)
    return service.open(actor, command)


@router.post(
    "/misconceptions/{identity}/responses", response_model=MisconceptionRead, status_code=201
)
async def answer(
    identity: str,
    command: MisconceptionAnswer,
    request: Request,
    learner: CurrentStudent,
    service: Service,
    security: Security,
):
    await secure(request, learner, security)
    return service.answer(learner, identity, command)


@router.post(
    "/misconceptions/{identity}/reviews", response_model=MisconceptionRead, status_code=201
)
async def review(
    identity: str,
    command: MisconceptionReview,
    request: Request,
    actor: CurrentEducator,
    service: Service,
    security: Security,
):
    await secure(request, actor, security)
    return service.review(actor, identity, command)
