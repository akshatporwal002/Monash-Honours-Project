"""Output reports, managed queues and human sampling."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentStudent, CurrentUser
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db
from app.schemas.escalation import (
    EscalationActionWrite,
    EscalationQueueRead,
    EscalationRead,
    EscalationStaffRead,
    OutputReportWrite,
    QueueKind,
    QueueRead,
    QueueWrite,
    SamplingWrite,
)
from app.schemas.feedback_api import AuthenticatedActor
from app.services.assessment.access import ScopedRoleAccessDeniedError
from app.services.escalation import EscalationService
from app.services.lms import LmsServiceError
from app.services.task_review import TaskReviewError

router = APIRouter(tags=["escalation"])


def get_service(response: Response, session: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    try:
        yield EscalationService(session)
    except (LmsServiceError, TaskReviewError) as error:
        session.rollback()
        raise HTTPException(error.status_code, str(error)) from error
    except ScopedRoleAccessDeniedError as error:
        session.rollback()
        raise HTTPException(403, "Assessor permission is required for this course") from error
    except (IntegrityError, OperationalError) as error:
        session.rollback()
        raise HTTPException(409, "The queue changed or is busy. Reload before retrying.") from error


Service = Annotated[EscalationService, Depends(get_service)]
Security = Annotated[RequestSecurityGuard, Depends(get_request_security_guard)]


async def secure(request, actor, security):
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(actor.id), role=actor.role.value),
        "escalation",
        mutating=True,
    )


@router.get("/escalations/queues", response_model=list[EscalationQueueRead])
def queues(actor: CurrentUser, service: Service):
    return service.queues(actor)


@router.get(
    "/escalations/courses/{course_id}/{kind}/configuration", response_model=EscalationQueueRead
)
def setup(course_id: str, kind: QueueKind, actor: CurrentUser, service: Service):
    return service.setup(actor, course_id, kind)


@router.post(
    "/escalations/courses/{course_id}/{kind}/configuration",
    response_model=QueueRead,
    status_code=201,
)
async def configure(
    course_id: str,
    kind: QueueKind,
    payload: QueueWrite,
    request: Request,
    actor: CurrentUser,
    service: Service,
    security: Security,
):
    await secure(request, actor, security)
    return service.configure(actor, course_id, kind, payload)


@router.get(
    "/escalations/courses/{course_id}/{kind}/cases", response_model=list[EscalationStaffRead]
)
def queue(
    course_id: str,
    kind: QueueKind,
    actor: CurrentUser,
    service: Service,
    offset: int = Query(0, ge=0),
):
    return service.queue(actor, course_id, kind, offset)


@router.post("/escalations/reports", response_model=EscalationRead, status_code=201)
async def report(
    payload: OutputReportWrite,
    request: Request,
    learner: CurrentStudent,
    service: Service,
    security: Security,
):
    await secure(request, learner, security)
    return service.report(learner, payload)


@router.get("/students/me/tasks/{task_id}/reports", response_model=list[EscalationRead])
def notices(task_id: str, learner: CurrentStudent, service: Service):
    return service.learner_cases(learner, task_id)


@router.post("/escalations/{case_id}/actions", response_model=EscalationStaffRead, status_code=201)
async def act(
    case_id: str,
    payload: EscalationActionWrite,
    request: Request,
    actor: CurrentUser,
    service: Service,
    security: Security,
):
    await secure(request, actor, security)
    return service.act(actor, case_id, payload)


@router.get("/escalations/{case_id}/evidence", response_model=dict)
def evidence(case_id: str, actor: CurrentUser, service: Service):
    return service.evidence(actor, case_id)


@router.get("/escalations/courses/{course_id}/samples", response_model=list[str])
def samples(course_id: str, actor: CurrentUser, service: Service, offset: int = Query(0, ge=0)):
    return service.samples(actor, course_id, offset)


@router.post(
    "/escalations/courses/{course_id}/samples", response_model=EscalationStaffRead, status_code=201
)
async def sample(
    course_id: str,
    payload: SamplingWrite,
    request: Request,
    actor: CurrentUser,
    service: Service,
    security: Security,
):
    await secure(request, actor, security)
    return service.sample(actor, course_id, payload)
