"""Dependencies and safe error mapping for assessment APIs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, get_db
from app.models.user import ScopedRole, User
from app.services.assessment.access import (
    RoleAssignmentConflictError,
    RoleAssignmentNotFoundError,
    RoleAssignmentPolicyRequiredError,
    RoleAssignmentService,
    RoleAssignmentValidationError,
    ScopedRoleAccessDeniedError,
)
from app.services.assessment.definitions import (
    AssessmentDefinitionConflictError,
    AssessmentDefinitionService,
    AssessmentDefinitionValidationError,
)
from app.services.assessment.evaluation import AssessmentEvaluationService
from app.services.assessment.jobs import (
    AssessmentEvaluationApplication,
    AssessmentEvaluationExecutor,
    SqlAlchemyAssessmentEvaluationJobRepository,
)
from app.services.assessment.runtime import build_assessment_evaluation_service

ScopedRoleEligibility = Callable[[User, ScopedRole], bool] | None
AssessmentPublicationPolicy = Callable[[User, str], bool]


def get_scoped_role_eligibility() -> ScopedRoleEligibility:
    """Fail closed until the product owner supplies an eligibility policy."""

    return None


def get_assessment_publication_policy() -> AssessmentPublicationPolicy:
    """Fail closed until the live-pilot publication policy is approved."""

    return lambda _actor, _course_id: False


def get_role_assignment_service(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    eligibility: Annotated[ScopedRoleEligibility, Depends(get_scoped_role_eligibility)],
) -> RoleAssignmentService:
    return RoleAssignmentService(
        session,
        correlation_id=getattr(request.state, "correlation_id", None),
        assignment_eligibility=eligibility,
    )


def get_assessment_definition_service(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> AssessmentDefinitionService:
    return AssessmentDefinitionService(
        session,
        correlation_id=getattr(request.state, "correlation_id", None),
    )


def get_assessment_evaluation_service(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> AssessmentEvaluationService:
    correlation_id = getattr(request.state, "correlation_id", None)
    return build_assessment_evaluation_service(
        session,
        correlation_id if isinstance(correlation_id, str) else str(uuid4()),
    )


def get_assessment_evaluation_application(
    session: Annotated[Session, Depends(get_db)],
) -> AssessmentEvaluationApplication:
    return AssessmentEvaluationApplication(
        SqlAlchemyAssessmentEvaluationJobRepository(session),
        lease_duration=timedelta(seconds=settings.feedback_job_lease_seconds),
    )


def raise_assignment_http_error(error: Exception) -> None:
    if isinstance(error, ScopedRoleAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        ) from error
    if isinstance(error, RoleAssignmentNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found"
        ) from error
    if isinstance(error, RoleAssignmentConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Assignment conflict"
        ) from error
    if isinstance(error, RoleAssignmentPolicyRequiredError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Scoped-role eligibility policy is not configured",
        ) from error
    if isinstance(error, RoleAssignmentValidationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
    raise error


def raise_definition_http_error(error: Exception) -> None:
    if isinstance(error, AssessmentDefinitionConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assessment definition version conflict",
        ) from error
    if isinstance(error, AssessmentDefinitionValidationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
    raise error


def get_assessment_evaluation_executor() -> AssessmentEvaluationExecutor:
    return AssessmentEvaluationExecutor(
        SessionLocal,
        build_assessment_evaluation_service,
    )


__all__ = [
    "AssessmentPublicationPolicy",
    "ScopedRoleEligibility",
    "get_assessment_definition_service",
    "get_assessment_evaluation_application",
    "get_assessment_evaluation_executor",
    "get_assessment_evaluation_service",
    "get_assessment_publication_policy",
    "get_role_assignment_service",
    "get_scoped_role_eligibility",
    "raise_assignment_http_error",
    "raise_definition_http_error",
]
