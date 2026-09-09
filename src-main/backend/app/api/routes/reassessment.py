"""Scoped reassessment authorisation and learner-owned outcome results."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentStudent, CurrentUser
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.reassessment import (
    EquivalentFormRead,
    EquivalentFormWrite,
    OutcomePolicyRead,
    OutcomePolicyWrite,
    OutcomeResultRead,
    ReassessmentRead,
    ReassessmentSetup,
    ReassessmentWrite,
)
from app.services.assessment.access import ScopedRoleAccessDeniedError
from app.services.assessment.equivalent_forms import EquivalentFormService
from app.services.assessment.outcome_results import OutcomeResultService
from app.services.assessment.reassessment import ReassessmentService
from app.services.lms import LmsServiceError
from app.services.task_review import TaskReviewError

router = APIRouter(tags=["reassessment"])


def get_service(response: Response, session: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    try:
        yield ReassessmentService(session)
    except (LmsServiceError, TaskReviewError) as error:
        session.rollback()
        raise HTTPException(error.status_code, str(error)) from error
    except ScopedRoleAccessDeniedError as error:
        session.rollback()
        raise HTTPException(403, "Assessor access is required for this course") from error
    except (IntegrityError, OperationalError) as error:
        session.rollback()
        raise HTTPException(
            409, "The assessment changed or is busy. Reload before retrying."
        ) from error


Service = Annotated[ReassessmentService, Depends(get_service)]
Security = Annotated[RequestSecurityGuard, Depends(get_request_security_guard)]


@router.post(
    "/assessment/definitions/{definition_id}/equivalent-forms",
    response_model=EquivalentFormRead,
    status_code=201,
)
async def equivalent_form(
    definition_id: str,
    payload: EquivalentFormWrite,
    request: Request,
    actor: CurrentUser,
    service: Service,
    security: Security,
):
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(actor.id), role=actor.role.value),
        "reassessment",
        mutating=True,
    )
    return EquivalentFormService(service.session).publish(actor, definition_id, payload)


@router.get("/assessment/decisions/{decision_id}/reassessment", response_model=ReassessmentSetup)
def setup(decision_id: str, actor: CurrentUser, service: Service):
    return service.setup(actor, decision_id)


@router.post(
    "/assessment/definitions/{definition_id}/outcome-policy",
    response_model=OutcomePolicyRead,
    status_code=201,
)
async def publish_policy(
    definition_id: str,
    payload: OutcomePolicyWrite,
    request: Request,
    actor: CurrentUser,
    service: Service,
    security: Security,
):
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(actor.id), role=actor.role.value),
        "reassessment",
        mutating=True,
    )
    return service.publish_policy(actor, definition_id, payload)


@router.post(
    "/assessment/decisions/{decision_id}/reassessment",
    response_model=ReassessmentRead,
    status_code=201,
)
async def authorise(
    decision_id: str,
    payload: ReassessmentWrite,
    request: Request,
    actor: CurrentUser,
    service: Service,
    security: Security,
):
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(actor.id), role=actor.role.value),
        "reassessment",
        mutating=True,
    )
    return service.authorise(actor, decision_id, payload)


@router.get("/students/me/responses/{response_id}/outcome-result", response_model=OutcomeResultRead)
def outcome_result(response_id: str, student: CurrentStudent, service: Service):
    return OutcomeResultService(service.session).read(student, response_id)
