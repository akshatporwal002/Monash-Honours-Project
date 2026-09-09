"""Learner-owned results and course-scoped assessor review requests."""

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentStudent, CurrentUser
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.learner_results import (
    AppealResolutionWrite,
    LearnerAppealRead,
    LearnerAppealWrite,
    LearnerResultRead,
)
from app.services.assessment.access import ScopedRoleAccessDeniedError
from app.services.assessment.learner_results import LearnerResultService
from app.services.lms import LmsServiceError

router = APIRouter(tags=["learner results"])


def get_result_service(
    response: Response, session: Session = Depends(get_db)
) -> Generator[LearnerResultService, None, None]:
    response.headers["Cache-Control"] = "no-store"
    try:
        yield LearnerResultService(session)
    except LmsServiceError as error:
        session.rollback()
        raise HTTPException(error.status_code, error.detail) from error
    except ScopedRoleAccessDeniedError as error:
        session.rollback()
        raise HTTPException(403, "Assessor access is required for this course") from error


Results = Annotated[LearnerResultService, Depends(get_result_service)]
Security = Annotated[RequestSecurityGuard, Depends(get_request_security_guard)]


@router.get("/students/me/responses/{response_id}/result", response_model=LearnerResultRead)
def read_result(response_id: str, student: CurrentStudent, service: Results):
    return service.read(student, response_id)


@router.post(
    "/students/me/responses/{response_id}/review-requests",
    response_model=LearnerAppealRead,
    status_code=201,
)
async def request_review(
    response_id: str,
    payload: LearnerAppealWrite,
    request: Request,
    student: CurrentStudent,
    service: Results,
    security: Security,
):
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(student.id), role=student.role.value),
        "review-requests",
        mutating=True,
    )
    return service.request_review(student, response_id, payload)


@router.get(
    "/assessment/courses/{course_id}/review-requests", response_model=list[LearnerAppealRead]
)
def review_requests(
    course_id: str, actor: CurrentUser, service: Results, offset: int = Query(0, ge=0)
):
    return service.queue(actor, course_id, offset=offset)


@router.post("/assessment/review-requests/{appeal_id}/resolve", response_model=LearnerAppealRead)
async def resolve_review(
    appeal_id: str,
    payload: AppealResolutionWrite,
    request: Request,
    actor: CurrentUser,
    service: Results,
    security: Security,
):
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(actor.id), role=actor.role.value),
        "review-requests",
        mutating=True,
    )
    return service.resolve(actor, appeal_id, payload)
