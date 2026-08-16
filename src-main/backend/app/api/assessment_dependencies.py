"""Dependencies and safe error mapping for assessment setup APIs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
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
