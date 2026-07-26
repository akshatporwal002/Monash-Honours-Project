from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.api.analytics_dependencies import get_analytics_pseudonymizer
from app.api.contract_responses import sanitized_errors
from app.api.feedback_dependencies import FeedbackApiException, require_actor
from app.api.research_export_dependencies import (
    ResearchExportAccessPolicy,
    get_research_export_access_policy,
    get_research_export_service,
)
from app.api.security_dependencies import (
    RequestSecurityGuard,
    get_request_security_guard,
)
from app.models.enums import ExperimentalCondition, JudgeDecision
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.research_export import (
    ResearchExportFilters,
    ResearchExportFormat,
)
from app.services.analytics import AnalyticsPseudonymizer
from app.services.audit import AuditError
from app.services.research_export import (
    ResearchExportError,
    ResearchExportService,
    ResearchExportTooLargeError,
)

router = APIRouter(prefix="/research")
_MAX_EXPORT_COURSES = 1_000


@router.get(
    "/exports",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Audited research export stream",
            "content": {
                "application/json": {
                    "schema": {"type": "string", "format": "binary"},
                },
                "text/csv": {
                    "schema": {"type": "string", "format": "binary"},
                },
            },
        },
        **sanitized_errors(401, 403, 413, 422, 429, 503),
    },
)
async def research_export(
    request: Request,
    format: ResearchExportFormat = Query(...),
    course_id: str | None = Query(default=None, min_length=1, max_length=255),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    experimental_condition: ExperimentalCondition | None = Query(default=None),
    task_type: str | None = Query(default=None, min_length=1, max_length=255),
    model: str | None = Query(default=None, min_length=1, max_length=255),
    judge_decision: JudgeDecision | None = Query(default=None),
    actor: AuthenticatedActor = Depends(require_actor),
    access_policy: ResearchExportAccessPolicy = Depends(get_research_export_access_policy),
    pseudonymizer: AnalyticsPseudonymizer = Depends(get_analytics_pseudonymizer),
    service: ResearchExportService = Depends(get_research_export_service),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
) -> StreamingResponse:
    await security.enforce(request, actor, "exports", mutating=False)
    authorized = await access_policy.authorized_course_ids(actor)
    if course_id is not None:
        if course_id not in authorized:
            raise FeedbackApiException(
                403,
                "research_export_forbidden",
                "Research export access is not permitted.",
            )
        selected = [course_id]
    else:
        if len(authorized) > _MAX_EXPORT_COURSES or any(
            not isinstance(value, str) or not value.strip() or len(value) > 255
            for value in authorized
        ):
            raise FeedbackApiException(
                503,
                "research_export_scope_unavailable",
                "Research export authorization is temporarily unavailable.",
            )
        selected = sorted(authorized)
    if not selected:
        raise FeedbackApiException(
            403,
            "research_export_forbidden",
            "Research export access is not permitted.",
        )

    end_at = _utc(date_to or datetime.now(UTC))
    start_at = _utc(date_from or (end_at - timedelta(days=30)))
    try:
        filters = ResearchExportFilters(
            course_id=course_id,
            course_ids=selected,
            date_from=start_at,
            date_to=end_at,
            experimental_condition=experimental_condition,
            task_type=task_type,
            model=model,
            judge_decision=judge_decision,
        )
    except ValueError:
        raise FeedbackApiException(
            422,
            "invalid_research_export",
            "The research export filters are invalid.",
        ) from None

    correlation_id = getattr(request.state, "correlation_id", None)
    if not isinstance(correlation_id, str):
        raise FeedbackApiException(
            503,
            "request_context_unavailable",
            "Research export is temporarily unavailable.",
        )
    try:
        actor_pseudonym = pseudonymizer.pseudonymize(
            "audit-actor",
            actor.actor_reference,
        )
        prepared = service.prepare(
            export_format=format,
            filters=filters,
            actor_reference=actor_pseudonym,
            correlation_id=correlation_id,
        )
    except ResearchExportTooLargeError:
        raise FeedbackApiException(
            413,
            "research_export_too_large",
            "The research export exceeds the synchronous row limit.",
        ) from None
    except (AuditError, ResearchExportError):
        # Fail closed: this path is reached before StreamingResponse can emit bytes.
        raise FeedbackApiException(
            503,
            "research_export_unavailable",
            "Research export is temporarily unavailable.",
        ) from None
    except Exception:
        raise FeedbackApiException(
            503,
            "research_export_adapter_unavailable",
            "Research export is temporarily unavailable.",
        ) from None

    return StreamingResponse(
        prepared.body,
        media_type=prepared.media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="{prepared.filename}"',
            "X-Correlation-ID": correlation_id,
            "X-Export-ID": prepared.export_id,
            "X-Content-Type-Options": "nosniff",
        },
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
