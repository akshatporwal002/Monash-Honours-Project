from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.analytics_dependencies import (
    get_analytics_access_policy,
    get_analytics_application,
)
from app.api.contract_responses import sanitized_errors
from app.api.feedback_dependencies import FeedbackApiException, require_actor
from app.api.security_dependencies import (
    RequestSecurityGuard,
    get_request_security_guard,
)
from app.models.enums import ExperimentalCondition, JudgeDecision
from app.schemas.analytics import AnalyticsFilterOptions, InactiveLearnerPage
from app.schemas.feedback_api import AuthenticatedActor
from app.services.analytics import (
    AnalyticsAccessPolicy,
    AnalyticsApplication,
    AnalyticsPersistenceError,
    AnalyticsQuery,
    LearningMetricsResult,
    ResearchMetricsResult,
)

router = APIRouter(prefix="/analytics")
_MAX_ANALYTICS_COURSES = 1_000


@router.get(
    "/learning",
    response_model=LearningMetricsResult,
    responses=sanitized_errors(401, 403, 422, 429, 503),
)
async def learning_analytics(
    request: Request,
    response: Response,
    course_id: str | None = Query(default=None, min_length=1, max_length=255),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    actor: AuthenticatedActor = Depends(require_actor),
    policy: AnalyticsAccessPolicy = Depends(get_analytics_access_policy),
    application: AnalyticsApplication = Depends(get_analytics_application),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
) -> LearningMetricsResult:
    _headers(request, response)
    await security.enforce(request, actor, "analytics", mutating=False)
    query = await _authorized_query(
        actor,
        policy,
        course_id=course_id,
        date_from=date_from,
        date_to=date_to,
    )
    try:
        return await application.learning(query)
    except AnalyticsPersistenceError:
        raise FeedbackApiException(
            503,
            "analytics_unavailable",
            "Analytics are temporarily unavailable.",
        ) from None
    except FeedbackApiException:
        raise
    except Exception:
        raise FeedbackApiException(
            503,
            "analytics_adapter_unavailable",
            "Analytics are temporarily unavailable.",
        ) from None


@router.get(
    "/research",
    response_model=ResearchMetricsResult,
    responses=sanitized_errors(401, 403, 422, 429, 503),
)
async def research_analytics(
    request: Request,
    response: Response,
    course_id: str | None = Query(default=None, min_length=1, max_length=255),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    experimental_condition: ExperimentalCondition | None = Query(default=None),
    task_type: str | None = Query(default=None, min_length=1, max_length=255),
    model: str | None = Query(default=None, min_length=1, max_length=255),
    judge_decision: JudgeDecision | None = Query(default=None),
    actor: AuthenticatedActor = Depends(require_actor),
    policy: AnalyticsAccessPolicy = Depends(get_analytics_access_policy),
    application: AnalyticsApplication = Depends(get_analytics_application),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
) -> ResearchMetricsResult:
    _headers(request, response)
    await security.enforce(request, actor, "analytics", mutating=False)
    query = await _authorized_query(
        actor,
        policy,
        course_id=course_id,
        date_from=date_from,
        date_to=date_to,
        experimental_condition=experimental_condition,
        task_type=task_type,
        model=model,
        judge_decision=judge_decision,
    )
    try:
        return application.research(query)
    except AnalyticsPersistenceError:
        raise FeedbackApiException(
            503,
            "analytics_unavailable",
            "Analytics are temporarily unavailable.",
        ) from None


@router.get(
    "/filter-options",
    response_model=AnalyticsFilterOptions,
    responses=sanitized_errors(401, 403, 422, 429, 503),
)
async def analytics_filter_options(
    request: Request,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    policy: AnalyticsAccessPolicy = Depends(get_analytics_access_policy),
    application: AnalyticsApplication = Depends(get_analytics_application),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
) -> AnalyticsFilterOptions:
    _headers(request, response)
    await security.enforce(request, actor, "analytics", mutating=False)
    course_ids = await policy.authorized_course_ids(actor.actor_reference)
    if not course_ids:
        raise FeedbackApiException(
            403,
            "analytics_forbidden",
            "Analytics access is not permitted.",
        )
    _validate_course_scope(course_ids)
    try:
        return application.filter_options(course_ids)
    except AnalyticsPersistenceError:
        raise FeedbackApiException(
            503,
            "analytics_unavailable",
            "Analytics are temporarily unavailable.",
        ) from None


@router.get(
    "/inactive-learners",
    response_model=InactiveLearnerPage,
    responses=sanitized_errors(401, 403, 422, 429, 503),
)
async def inactive_learners(
    request: Request,
    response: Response,
    course_id: str | None = Query(default=None, min_length=1, max_length=255),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    actor: AuthenticatedActor = Depends(require_actor),
    policy: AnalyticsAccessPolicy = Depends(get_analytics_access_policy),
    application: AnalyticsApplication = Depends(get_analytics_application),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
) -> InactiveLearnerPage:
    _headers(request, response)
    await security.enforce(request, actor, "analytics", mutating=False)
    query = await _authorized_query(
        actor,
        policy,
        course_id=course_id,
        date_from=date_from,
        date_to=date_to,
    )
    try:
        return await application.inactive_learners(
            query,
            page=page,
            page_size=page_size,
        )
    except AnalyticsPersistenceError:
        raise FeedbackApiException(
            503,
            "analytics_unavailable",
            "Analytics are temporarily unavailable.",
        ) from None
    except FeedbackApiException:
        raise
    except Exception:
        raise FeedbackApiException(
            503,
            "analytics_adapter_unavailable",
            "Analytics are temporarily unavailable.",
        ) from None


async def _authorized_query(
    actor: AuthenticatedActor,
    policy: AnalyticsAccessPolicy,
    *,
    course_id: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    experimental_condition: ExperimentalCondition | None = None,
    task_type: str | None = None,
    model: str | None = None,
    judge_decision: JudgeDecision | None = None,
) -> AnalyticsQuery:
    authorized = await policy.authorized_course_ids(actor.actor_reference)
    if course_id is not None:
        if course_id not in authorized:
            raise FeedbackApiException(
                403,
                "analytics_forbidden",
                "Analytics access is not permitted.",
            )
        selected = (course_id,)
    else:
        _validate_course_scope(authorized)
        selected = tuple(sorted(authorized))
    if not selected:
        raise FeedbackApiException(
            403,
            "analytics_forbidden",
            "Analytics access is not permitted.",
        )

    end_at = _as_utc(date_to or datetime.now(UTC))
    start_at = _as_utc(date_from or (end_at - timedelta(days=30)))
    if end_at <= start_at or end_at - start_at > timedelta(days=365):
        raise FeedbackApiException(
            422,
            "invalid_analytics_range",
            "The analytics date range is invalid.",
        )
    return AnalyticsQuery(
        course_ids=selected,
        start_at=start_at,
        end_at=end_at,
        experimental_condition=experimental_condition,
        task_type=task_type,
        model=model,
        judge_decision=judge_decision,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _validate_course_scope(course_ids: set[str]) -> None:
    if len(course_ids) > _MAX_ANALYTICS_COURSES or any(
        not isinstance(course_id, str) or not course_id.strip() or len(course_id) > 255
        for course_id in course_ids
    ):
        raise FeedbackApiException(
            503,
            "analytics_scope_unavailable",
            "Analytics authorization is temporarily unavailable.",
        )


def _headers(request: Request, response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    correlation_id = getattr(request.state, "correlation_id", None)
    if isinstance(correlation_id, str):
        response.headers["X-Correlation-ID"] = correlation_id
