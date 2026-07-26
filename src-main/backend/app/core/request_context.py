from __future__ import annotations

import logging
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

CORRELATION_HEADER = "X-Correlation-ID"
logger = logging.getLogger("quantumlearn.request")


def resolve_correlation_id(value: str | None) -> str:
    if value is not None:
        try:
            parsed = UUID(value)
            if parsed.version == 4:
                return str(parsed)
        except ValueError:
            pass
    return str(uuid4())


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # Alembic's logging configuration may disable pre-existing application
        # loggers in the same process; request observability must remain active.
        logger.disabled = False
        correlation_id = resolve_correlation_id(request.headers.get(CORRELATION_HEADER))
        request.state.correlation_id = correlation_id
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.error(
                "request_failed correlation_id=%s route=%s status=500 "
                "latency_ms=%s failure_category=unhandled_request",
                correlation_id,
                _route_template(request),
                max(0, int((perf_counter() - started) * 1000)),
            )
            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "internal_server_error",
                        "message": "The request could not be completed.",
                    }
                },
            )
        _apply_response_headers(request, response, correlation_id)
        route_template = _route_template(request)
        if response.status_code < 500:
            logger.info(
                "request_completed correlation_id=%s method=%s route=%s status=%s latency_ms=%s",
                correlation_id,
                request.method,
                route_template,
                response.status_code,
                max(0, int((perf_counter() - started) * 1000)),
            )
        return response


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    value = getattr(route, "path", None)
    return value if isinstance(value, str) else "unmatched"


def _apply_response_headers(
    request: Request,
    response: Response,
    correlation_id: str,
) -> None:
    response.headers[CORRELATION_HEADER] = correlation_id
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'none'; frame-ancestors 'none'",
    )
    if request.url.scheme == "https":
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
