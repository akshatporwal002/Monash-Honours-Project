from __future__ import annotations

from functools import lru_cache

from fastapi import Request

from app.api.feedback_dependencies import FeedbackApiException
from app.core.config import settings
from app.core.security import (
    DoubleSubmitCsrfPolicy,
    InMemoryRateLimiter,
    RateLimit,
    SecurityPolicyError,
)
from app.schemas.feedback_api import AuthenticatedActor


class RequestSecurityGuard:
    def __init__(
        self,
        csrf_policy: DoubleSubmitCsrfPolicy,
        rate_limiter: InMemoryRateLimiter,
    ) -> None:
        self._csrf_policy = csrf_policy
        self._rate_limiter = rate_limiter

    async def enforce(
        self,
        request: Request,
        actor: AuthenticatedActor,
        bucket: str,
        *,
        mutating: bool,
    ) -> None:
        try:
            if mutating and settings.csrf_enabled:
                await self._csrf_policy.validate(request)
            if settings.rate_limit_enabled:
                self._rate_limiter.check(actor.actor_reference, bucket)
        except SecurityPolicyError as error:
            status_code = 429 if error.code == "rate_limit_exceeded" else 403
            raise FeedbackApiException(
                status_code,
                error.code,
                (
                    "Too many requests. Try again later."
                    if status_code == 429
                    else "The request failed a security policy."
                ),
                retry_after_seconds=error.retry_after_seconds,
            )


@lru_cache
def get_request_security_guard() -> RequestSecurityGuard:
    csrf = DoubleSubmitCsrfPolicy(
        set(settings.allowed_cors_origins),
        cookie_name=settings.csrf_cookie_name,
        header_name=settings.csrf_header_name,
    )
    limiter = InMemoryRateLimiter(
        {
            "generation": RateLimit(120, 60),
            "reports": RateLimit(120, 60),
            "learning-events": RateLimit(300, 60),
            "analytics": RateLimit(300, 60),
            "exports": RateLimit(10, 60),
        }
    )
    return RequestSecurityGuard(csrf, limiter)
