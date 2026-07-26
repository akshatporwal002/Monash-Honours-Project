from collections.abc import Iterator

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.feedback_dependencies import (
    FeedbackApiException,
    feedback_api_exception_handler,
)
from app.api.security_dependencies import RequestSecurityGuard
from app.core.config import Settings, settings
from app.core.security import (
    DoubleSubmitCsrfPolicy,
    InMemoryRateLimiter,
    RateLimit,
    RequestSizeLimitMiddleware,
    SecurityPolicyError,
)
from app.main import create_app
from app.schemas.feedback_api import AuthenticatedActor


def test_csrf_policy_rejects_cross_origin_and_cookie_token_mismatch() -> None:
    app = FastAPI()
    policy = DoubleSubmitCsrfPolicy({"https://learn.example"})

    @app.post("/")
    async def mutate(request: Request) -> dict[str, bool]:
        await policy.validate(request)
        return {"ok": True}

    @app.exception_handler(SecurityPolicyError)
    async def handle(_: Request, error: SecurityPolicyError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"error": error.code})

    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.update({"session": "opaque", "ql_csrf": "expected"})
    cross_origin = client.post(
        "/",
        headers={"origin": "https://evil.example"},
    )
    mismatch = client.post(
        "/",
        headers={"origin": "https://learn.example", "x-csrf-token": "wrong"},
    )
    accepted = client.post(
        "/",
        headers={"origin": "https://learn.example", "x-csrf-token": "expected"},
    )

    assert cross_origin.json()["error"] == "csrf_origin_rejected"
    assert mismatch.json()["error"] == "csrf_validation_failed"
    assert accepted.json() == {"ok": True}


def test_bearer_style_request_without_cookies_does_not_require_csrf_token() -> None:
    app = FastAPI()
    policy = DoubleSubmitCsrfPolicy({"https://learn.example"})

    @app.post("/")
    async def mutate(request: Request) -> dict[str, bool]:
        await policy.validate(request)
        return {"ok": True}

    response = TestClient(app).post(
        "/",
        headers={
            "origin": "https://learn.example",
            "authorization": "Bearer opaque",
        },
    )

    assert response.status_code == 200


def test_per_actor_rate_limiter_returns_retry_after() -> None:
    times: Iterator[float] = iter([0.0, 1.0, 2.0, 11.0])
    limiter = InMemoryRateLimiter(
        {"generation": RateLimit(requests=2, window_seconds=10)},
        clock=lambda: next(times),
    )

    limiter.check("v1_actor", "generation")
    limiter.check("v1_actor", "generation")
    with pytest.raises(SecurityPolicyError) as captured:
        limiter.check("v1_actor", "generation")
    limiter.check("v1_actor", "generation")

    assert captured.value.code == "rate_limit_exceeded"
    assert captured.value.retry_after_seconds == 8


def test_request_size_limit_rejects_body_before_route_execution() -> None:
    app = FastAPI()
    app.add_middleware(RequestSizeLimitMiddleware, maximum_bytes=8)
    calls = 0

    @app.post("/")
    async def mutate() -> dict[str, bool]:
        nonlocal calls
        calls += 1
        return {"ok": True}

    response = TestClient(app).post("/", content=b"0123456789")

    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["error"]["code"] == "request_too_large"
    assert calls == 0


def test_configured_cors_rejects_unlisted_origins_methods_and_headers() -> None:
    client = TestClient(create_app())
    base_headers = {
        "origin": settings.allowed_cors_origins[0],
        "access-control-request-method": "POST",
        "access-control-request-headers": "content-type,x-correlation-id",
    }

    accepted = client.options("/api/v1/learning-events", headers=base_headers)
    bad_origin = client.options(
        "/api/v1/learning-events",
        headers={**base_headers, "origin": "https://untrusted.example"},
    )
    bad_method = client.options(
        "/api/v1/learning-events",
        headers={**base_headers, "access-control-request-method": "DELETE"},
    )
    bad_header = client.options(
        "/api/v1/learning-events",
        headers={**base_headers, "access-control-request-headers": "x-private-token"},
    )

    assert accepted.status_code == 200
    assert accepted.headers["access-control-allow-origin"] == settings.allowed_cors_origins[0]
    assert bad_origin.status_code == 400
    assert "access-control-allow-origin" not in bad_origin.headers
    assert bad_method.status_code == 400
    assert bad_header.status_code == 400


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "file:///private/app",
        "https://learn.example/private",
        "https://learn.example?token=private",
    ],
)
def test_settings_reject_non_origin_cors_values(origin: str) -> None:
    with pytest.raises(ValueError, match="explicit HTTP"):
        Settings(cors_allowed_origins=origin)


def test_settings_accept_multiple_explicit_cors_origins() -> None:
    configured = Settings(cors_allowed_origins="https://learn.example, http://localhost:5173/")

    assert configured.allowed_cors_origins == [
        "https://learn.example",
        "http://localhost:5173",
    ]


def test_rate_limit_response_is_sanitized_and_includes_retry_after() -> None:
    app = FastAPI()
    app.add_exception_handler(FeedbackApiException, feedback_api_exception_handler)
    guard = RequestSecurityGuard(
        DoubleSubmitCsrfPolicy({"https://learn.example"}),
        InMemoryRateLimiter({"exports": RateLimit(requests=1, window_seconds=60)}),
    )
    actor = AuthenticatedActor(actor_reference="opaque-actor", role="researcher")

    @app.get("/")
    async def limited(request: Request) -> dict[str, bool]:
        await guard.enforce(request, actor, "exports", mutating=False)
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/").status_code == 200
    rejected = client.get("/")

    assert rejected.status_code == 429
    assert rejected.headers["retry-after"] == "60"
    assert rejected.headers["cache-control"] == "no-store"
    assert rejected.json()["error"]["code"] == "rate_limit_exceeded"


def test_production_disables_interactive_api_documentation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "api_docs_enabled", False)
    client = TestClient(create_app())

    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_application_size_rejection_keeps_correlation_and_security_headers() -> None:
    correlation_id = "00000000-0000-4000-8000-000000000001"
    response = TestClient(create_app()).post(
        "/api/v1/learning-events",
        content=b"x" * (settings.max_request_body_bytes + 1),
        headers={
            "content-type": "application/json",
            "x-correlation-id": correlation_id,
        },
    )

    assert response.status_code == 413
    assert response.headers["x-correlation-id"] == correlation_id
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.json()["error"]["code"] == "request_too_large"
