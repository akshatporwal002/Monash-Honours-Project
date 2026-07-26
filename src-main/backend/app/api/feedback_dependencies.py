from dataclasses import dataclass
from datetime import timedelta
from typing import NoReturn
from uuid import UUID, uuid4

from fastapi import Depends, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.audit_dependencies import get_feedback_audit_events
from app.api.dependencies.authentication import get_current_user
from app.core.config import settings
from app.db.session import SessionLocal, get_db_session
from app.models import LearningTask
from app.models.lms import Course, SubmissionAttempt
from app.models.user import User, UserRole
from app.schemas.feedback_api import AuthenticatedActor, FeedbackApiErrorResponse
from app.services.audit_events import FeedbackAuditEvents
from app.services.feedback.application import (
    FeedbackAccessPolicy,
    FeedbackBackgroundExecutor,
    FeedbackWorkflowApplication,
    InProcessFeedbackExecutor,
)
from app.services.feedback.errors import FeedbackPipelineError
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository
from app.services.feedback.runtime import build_feedback_pipeline_for_repository


@dataclass
class FeedbackApiException(Exception):
    status_code: int
    code: str
    message: str
    retry_after_seconds: int | None = None


async def feedback_api_exception_handler(
    request: Request,
    error: FeedbackApiException,
) -> JSONResponse:
    body = FeedbackApiErrorResponse(error={"code": error.code, "message": error.message})
    headers = _error_headers(request)
    if error.retry_after_seconds is not None:
        headers["Retry-After"] = str(error.retry_after_seconds)
    return JSONResponse(
        status_code=error.status_code,
        content=body.model_dump(mode="json"),
        headers=headers,
    )


async def feedback_pipeline_exception_handler(
    request: Request,
    _: FeedbackPipelineError,
) -> JSONResponse:
    body = FeedbackApiErrorResponse(
        error={
            "code": "feedback_service_unavailable",
            "message": "The feedback service is temporarily unavailable.",
        }
    )
    return JSONResponse(
        status_code=503,
        content=body.model_dump(mode="json"),
        headers=_error_headers(request),
    )


async def feedback_request_validation_handler(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    if request.url.path.endswith("/learning-events"):
        body = FeedbackApiErrorResponse(
            error={
                "code": "invalid_learning_event",
                "message": "The learning event is invalid.",
            }
        )
        return JSONResponse(
            status_code=422,
            content=body.model_dump(mode="json"),
            headers=_error_headers(request),
        )
    if "/analytics/" in request.url.path or request.url.path.endswith("/research/exports"):
        body = FeedbackApiErrorResponse(
            error={
                "code": "invalid_analytics_request",
                "message": "The analytics request is invalid.",
            }
        )
        return JSONResponse(
            status_code=422,
            content=body.model_dump(mode="json"),
            headers=_error_headers(request),
        )
    if request.url.path.endswith("/feedback") or request.url.path.endswith("/report"):
        body = FeedbackApiErrorResponse(
            error={
                "code": "invalid_feedback_request",
                "message": "The feedback request is invalid.",
            }
        )
        return JSONResponse(
            status_code=422,
            content=body.model_dump(mode="json"),
            headers=_error_headers(request),
        )
    return await request_validation_exception_handler(request, error)


async def get_authenticated_actor(
    user: User = Depends(get_current_user),
) -> AuthenticatedActor:
    return AuthenticatedActor(
        actor_reference=str(user.id),
        role=user.role.value,
    )


class DatabaseFeedbackAccessPolicy:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def can_access_submission(
        self,
        actor: AuthenticatedActor,
        submission_id: str,
    ) -> bool:
        attempt = self._session.get(SubmissionAttempt, submission_id)
        if attempt is None:
            return False
        try:
            actor_id = int(actor.actor_reference)
            role = UserRole(actor.role)
        except (TypeError, ValueError):
            return False
        if role is UserRole.ADMINISTRATOR:
            return True
        if role is UserRole.STUDENT:
            return attempt.student_id == actor_id
        if role is not UserRole.EDUCATOR:
            return False
        task = self._session.get(LearningTask, attempt.task_id)
        if task is None or task.course_id is None:
            return False
        course = self._session.get(Course, task.course_id)
        return course is not None and course.educator_id == actor_id


def get_feedback_access_policy(
    session: Session = Depends(get_db_session),
) -> FeedbackAccessPolicy:
    return DatabaseFeedbackAccessPolicy(session)


def get_feedback_executor(
    audit_events: FeedbackAuditEvents = Depends(get_feedback_audit_events),
) -> FeedbackBackgroundExecutor:
    return InProcessFeedbackExecutor(
        SessionLocal,
        build_feedback_pipeline_for_repository,
        audit_events=audit_events,
    )


def get_feedback_application(
    session: Session = Depends(get_db_session),
    audit_events: FeedbackAuditEvents = Depends(get_feedback_audit_events),
) -> FeedbackWorkflowApplication:
    return FeedbackWorkflowApplication(
        SqlAlchemyFeedbackWorkflowRepository(session),
        lease_duration=timedelta(seconds=settings.feedback_job_lease_seconds),
        audit_events=audit_events,
    )


def require_actor(
    actor: AuthenticatedActor | None = Depends(get_authenticated_actor),
) -> AuthenticatedActor:
    if actor is None:
        raise FeedbackApiException(401, "authentication_required", "Authentication is required.")
    return actor


def _unavailable(code: str, message: str) -> NoReturn:
    raise FeedbackApiException(503, code, message)


def _error_headers(request: Request) -> dict[str, str]:
    contextual = getattr(request.state, "correlation_id", None)
    if isinstance(contextual, str):
        return {
            "Cache-Control": "no-store",
            "X-Correlation-ID": contextual,
        }
    supplied = request.headers.get("x-correlation-id")
    correlation_id: str
    if supplied is not None:
        try:
            correlation_id = str(UUID(supplied))
        except ValueError:
            correlation_id = str(uuid4())
    else:
        correlation_id = str(uuid4())
    return {
        "Cache-Control": "no-store",
        "X-Correlation-ID": correlation_id,
    }
