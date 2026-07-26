from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response

from app.api.contract_responses import sanitized_errors
from app.api.feedback_dependencies import FeedbackApiException, require_actor
from app.api.learning_event_dependencies import (
    get_learning_event_access_policy,
    get_learning_event_recorder,
)
from app.api.security_dependencies import (
    RequestSecurityGuard,
    get_request_security_guard,
)
from app.models.enums import LearningEventType
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.learning_events import (
    BrowserLearningEventRequest,
    LearningEventReceipt,
)
from app.services.learning_events import (
    LearningEventAccessPolicy,
    LearningEventCommand,
    LearningEventConflictError,
    LearningEventPersistenceError,
    LearningEventRecorder,
)

router = APIRouter()


@router.post(
    "/learning-events",
    response_model=LearningEventReceipt,
    status_code=201,
    responses={
        200: {
            "model": LearningEventReceipt,
            "description": "Exact event replay",
        },
        **sanitized_errors(401, 403, 404, 409, 422, 429, 503),
    },
)
async def record_browser_learning_event(
    command: BrowserLearningEventRequest,
    request: Request,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    policy: LearningEventAccessPolicy = Depends(get_learning_event_access_policy),
    recorder: LearningEventRecorder = Depends(get_learning_event_recorder),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
) -> LearningEventReceipt:
    await security.enforce(request, actor, "learning-events", mutating=True)
    scope = await policy.resolve_task_scope(actor, command.task_id)
    if scope is None or scope.task_id != command.task_id:
        raise FeedbackApiException(
            404,
            "learning_event_task_not_found",
            "The task was not found.",
        )

    correlation_id = _correlation_id(request)
    try:
        result = recorder.record(
            LearningEventCommand(
                actor_reference=actor.actor_reference,
                course_id=scope.course_id,
                task_id=scope.task_id,
                event_type=LearningEventType(command.event_type),
                client_event_id=command.event_id,
                correlation_id=correlation_id,
                metadata=command.metadata.model_dump(mode="json", exclude_none=True),
            )
        )
    except LearningEventConflictError:
        raise FeedbackApiException(
            409,
            "learning_event_conflict",
            "The event identifier has already been used.",
        ) from None
    except (LearningEventPersistenceError, ValueError):
        raise FeedbackApiException(
            503,
            "learning_event_recording_unavailable",
            "Learning-event recording is temporarily unavailable.",
        ) from None

    if not result.created:
        response.status_code = 200
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Correlation-ID"] = correlation_id
    return result.receipt


def _correlation_id(request: Request) -> str:
    contextual = getattr(request.state, "correlation_id", None)
    if isinstance(contextual, str):
        return contextual
    supplied = request.headers.get("X-Correlation-ID")
    if supplied is not None:
        try:
            return str(UUID(supplied))
        except ValueError:
            pass
    return str(uuid4())
