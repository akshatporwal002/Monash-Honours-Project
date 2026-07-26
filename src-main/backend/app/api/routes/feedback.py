from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Request, Response

from app.api.analytics_dependencies import get_analytics_pseudonymizer
from app.api.audit_dependencies import get_student_audit_tracker
from app.api.contract_responses import sanitized_errors
from app.api.feedback_dependencies import (
    FeedbackApiException,
    get_feedback_access_policy,
    get_feedback_application,
    get_feedback_executor,
    require_actor,
)
from app.api.learning_event_dependencies import get_feedback_view_tracker
from app.api.security_dependencies import (
    RequestSecurityGuard,
    get_request_security_guard,
)
from app.schemas.feedback_api import (
    AuthenticatedActor,
    FeedbackReportRequest,
    FeedbackReportResponse,
    FeedbackWorkflowResponse,
    FeedbackWorkflowStatus,
)
from app.services.analytics import AnalyticsPseudonymizer
from app.services.audit_events import NullStudentAuditTracker, StudentAuditTracker
from app.services.feedback.application import (
    FeedbackAccessPolicy,
    FeedbackBackgroundExecutor,
    FeedbackWorkflowApplication,
    workflow_response,
)
from app.services.feedback.contracts import FeedbackReportWrite
from app.services.feedback.errors import FeedbackReportConflictError
from app.services.learning_events import FeedbackViewTracker

router = APIRouter()
SubmissionPathId = Annotated[
    str,
    Path(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$"),
]
FeedbackPathId = Annotated[
    str,
    Path(
        min_length=36,
        max_length=36,
        pattern=(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-"
            r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
        ),
    ),
]


async def _require_submission_access(
    policy: FeedbackAccessPolicy,
    actor: AuthenticatedActor,
    submission_id: str,
) -> None:
    if not await policy.can_access_submission(actor, submission_id):
        raise FeedbackApiException(404, "feedback_not_found", "Feedback was not found.")


@router.post(
    "/submissions/{submission_id}/feedback",
    response_model=FeedbackWorkflowResponse,
    status_code=202,
    responses={
        200: {
            "model": FeedbackWorkflowResponse,
            "description": "Existing terminal workflow",
        },
        **sanitized_errors(401, 403, 404, 422, 429, 503),
    },
)
async def start_feedback(
    submission_id: SubmissionPathId,
    background_tasks: BackgroundTasks,
    request: Request,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    policy: FeedbackAccessPolicy = Depends(get_feedback_access_policy),
    application: FeedbackWorkflowApplication = Depends(get_feedback_application),
    executor: FeedbackBackgroundExecutor = Depends(get_feedback_executor),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
) -> FeedbackWorkflowResponse:
    correlation_id = _set_common_headers(request, response)
    await security.enforce(request, actor, "generation", mutating=True)
    await _require_submission_access(policy, actor, submission_id)
    claim = application.start(submission_id, correlation_id=correlation_id)
    view = workflow_response(claim)
    if view.status in {FeedbackWorkflowStatus.VALIDATED, FeedbackWorkflowStatus.FALLBACK}:
        response.status_code = 200
    else:
        response.status_code = 202
        response.headers["Location"] = request.url.path
        response.headers["Retry-After"] = "2"
        if claim.should_start:
            background_tasks.add_task(
                executor.execute,
                claim.workflow_run_id,
                submission_id,
                claim.execution_token,
                correlation_id,
            )
    return view


@router.get(
    "/submissions/{submission_id}/feedback",
    response_model=FeedbackWorkflowResponse,
    responses=sanitized_errors(401, 403, 404, 422, 429, 503),
)
async def get_feedback(
    submission_id: SubmissionPathId,
    request: Request,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    policy: FeedbackAccessPolicy = Depends(get_feedback_access_policy),
    application: FeedbackWorkflowApplication = Depends(get_feedback_application),
    tracker: FeedbackViewTracker = Depends(get_feedback_view_tracker),
    audit_tracker: StudentAuditTracker | NullStudentAuditTracker = Depends(
        get_student_audit_tracker
    ),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
) -> FeedbackWorkflowResponse:
    correlation_id = _set_common_headers(request, response)
    await security.enforce(request, actor, "generation", mutating=False)
    await _require_submission_access(policy, actor, submission_id)
    claim = application.get(submission_id)
    if claim is None:
        raise FeedbackApiException(404, "feedback_not_found", "Feedback was not found.")
    view = workflow_response(claim)
    if view.status is FeedbackWorkflowStatus.PROCESSING:
        response.headers["Retry-After"] = "2"
    elif view.status is FeedbackWorkflowStatus.FAILED and claim.retryable:
        response.headers["Retry-After"] = str(claim.retry_after_seconds or 0)
    if (
        view.status
        in {
            FeedbackWorkflowStatus.VALIDATED,
            FeedbackWorkflowStatus.FALLBACK,
        }
        and claim.course_id is not None
        and claim.task_id is not None
    ):
        tracker.record_terminal_view(
            actor_reference=actor.actor_reference,
            course_id=claim.course_id,
            task_id=claim.task_id,
            workflow_run_id=claim.workflow_run_id,
            correlation_id=correlation_id,
            feedback_status=view.status.value,
        )
        if view.feedback is not None:
            audit_tracker.record_feedback_view(
                actor_reference=actor.actor_reference,
                feedback_id=view.feedback.feedback_id,
                correlation_id=correlation_id,
            )
    return view


@router.post(
    "/feedback/{feedback_id}/report",
    response_model=FeedbackReportResponse,
    status_code=201,
    responses={
        200: {
            "model": FeedbackReportResponse,
            "description": "Exact report replay",
        },
        **sanitized_errors(401, 403, 404, 409, 422, 429, 503),
    },
)
async def report_feedback(
    feedback_id: FeedbackPathId,
    request: FeedbackReportRequest,
    http_request: Request,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    policy: FeedbackAccessPolicy = Depends(get_feedback_access_policy),
    application: FeedbackWorkflowApplication = Depends(get_feedback_application),
    audit_tracker: StudentAuditTracker | NullStudentAuditTracker = Depends(
        get_student_audit_tracker
    ),
    pseudonymizer: AnalyticsPseudonymizer = Depends(get_analytics_pseudonymizer),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
) -> FeedbackReportResponse:
    correlation_id = _set_common_headers(http_request, response)
    await security.enforce(http_request, actor, "reports", mutating=True)
    submission_id = application.released_submission_id(feedback_id)
    if submission_id is None:
        raise FeedbackApiException(404, "feedback_not_found", "Feedback was not found.")
    await _require_submission_access(policy, actor, submission_id)
    try:
        reporter_reference = pseudonymizer.pseudonymize(
            "feedback-report-actor",
            actor.actor_reference,
        )
    except FeedbackApiException:
        raise
    except Exception:
        raise FeedbackApiException(
            503,
            "pseudonymization_unavailable",
            "Feedback reporting is temporarily unavailable.",
        ) from None
    try:
        result = application.report(
            FeedbackReportWrite(
                feedback_id=feedback_id,
                reporter_reference=reporter_reference,
                category=request.category,
                note=request.note,
            )
        )
    except FeedbackReportConflictError:
        raise FeedbackApiException(
            409,
            "feedback_report_conflict",
            "A different report has already been received.",
        ) from None
    if not result.created:
        response.status_code = 200
    audit_tracker.record_feedback_report(
        actor_reference=actor.actor_reference,
        report_id=result.report_id,
        correlation_id=correlation_id,
    )
    return FeedbackReportResponse(report_id=result.report_id)


def _set_common_headers(request: Request, response: Response) -> str:
    correlation_id = _correlation_id(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Correlation-ID"] = correlation_id
    return correlation_id


def _correlation_id(request: Request) -> str:
    contextual = getattr(request.state, "correlation_id", None)
    if isinstance(contextual, str):
        return contextual
    supplied = request.headers.get("x-correlation-id")
    if supplied is not None:
        try:
            return str(UUID(supplied))
        except ValueError:
            pass
    return str(uuid4())
