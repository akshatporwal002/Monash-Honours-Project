import logging
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.privacy import REDACTED, redact_sensitive
from app.core.request_context import CORRELATION_HEADER, RequestContextMiddleware


def test_recursive_redaction_never_retains_nested_sensitive_values() -> None:
    payload = {
        "safe": "visible",
        "source": {
            "email": "private@example.test",
            "nested": [{"submitted_answer": "secret answer"}],
        },
        "api-key": "secret-key",
    }

    redacted = redact_sensitive(payload)

    assert redacted["safe"] == "visible"
    assert redacted["source"]["email"] == REDACTED
    assert redacted["source"]["nested"][0]["submitted_answer"] == REDACTED
    assert redacted["api-key"] == REDACTED
    assert "private@example.test" not in repr(redacted)
    assert "secret answer" not in repr(redacted)
    assert "secret-key" not in repr(redacted)


def test_recursive_redaction_detects_sensitive_values_and_bounds_metadata() -> None:
    payload = {
        "safe_label": "contact private@example.test using Bearer abcdefghijklmnop",
        "items": list(range(60)),
    }

    redacted = redact_sensitive(payload)

    assert "private@example.test" not in repr(redacted)
    assert "abcdefghijklmnop" not in repr(redacted)
    assert len(redacted["items"]) == 51
    assert redacted["items"][-1] == "[TRUNCATED 10 ITEMS]"


def test_request_context_uses_route_template_and_security_headers(
    caplog,
) -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/resources/{resource_id}")
    async def resource(resource_id: str) -> dict[str, bool]:
        return {"found": bool(resource_id)}

    private_id = "private-student-reference"
    requested_correlation = str(uuid4())
    with caplog.at_level(logging.INFO, logger="quantumlearn.request"):
        response = TestClient(app).get(
            f"/resources/{private_id}",
            headers={CORRELATION_HEADER: requested_correlation},
        )

    assert response.headers[CORRELATION_HEADER] == requested_correlation
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "route=/resources/{resource_id}" in caplog.text
    assert private_id not in caplog.text


def test_invalid_correlation_id_is_replaced() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/")
    async def root() -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(app).get("/", headers={CORRELATION_HEADER: "not-a-uuid"})

    assert response.headers[CORRELATION_HEADER] != "not-a-uuid"


def test_unhandled_failures_return_only_sanitized_content_and_safe_headers(
    caplog,
) -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    private_value = "PRIVATE_RAW_ANSWER_SENTINEL_student@example.test"

    @app.get("/resources/{resource_id}")
    async def broken(resource_id: str) -> dict[str, bool]:
        raise RuntimeError(f"{private_value}:{resource_id}")

    correlation_id = str(uuid4())
    with caplog.at_level(logging.ERROR, logger="quantumlearn.request"):
        response = TestClient(app, raise_server_exceptions=False).get(
            "/resources/private-student-id",
            headers={CORRELATION_HEADER: correlation_id},
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "The request could not be completed.",
        }
    }
    assert response.headers[CORRELATION_HEADER] == correlation_id
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "route=/resources/{resource_id}" in caplog.text
    assert private_value not in caplog.text
    assert "private-student-id" not in caplog.text
