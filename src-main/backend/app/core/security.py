from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hmac import compare_digest
from threading import Lock
from time import monotonic
from typing import Protocol

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a non-empty password using Argon2id."""
    if not password:
        raise ValueError("Password must not be empty")
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return whether a password matches an encoded Argon2 hash."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


class SecurityPolicyError(Exception):
    def __init__(self, code: str, *, retry_after_seconds: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.retry_after_seconds = retry_after_seconds


class CsrfPolicy(Protocol):
    async def validate(self, request: Request) -> None: ...


class DoubleSubmitCsrfPolicy:
    """Protect cookie-authenticated mutations without constraining bearer clients."""

    def __init__(
        self,
        allowed_origins: set[str],
        *,
        cookie_name: str = "ql_csrf",
        header_name: str = "x-csrf-token",
    ) -> None:
        self._allowed_origins = {origin.rstrip("/") for origin in allowed_origins}
        self._cookie_name = cookie_name
        self._header_name = header_name

    async def validate(self, request: Request) -> None:
        if request.method.upper() in SAFE_METHODS:
            return

        origin = request.headers.get("origin")
        if origin is not None and origin.rstrip("/") not in self._allowed_origins:
            raise SecurityPolicyError("csrf_origin_rejected")

        # A request without cookies is expected to use an authorization header and
        # is not vulnerable to ambient-cookie CSRF.
        if not request.cookies:
            return

        cookie_token = request.cookies.get(self._cookie_name)
        header_token = request.headers.get(self._header_name)
        if (
            cookie_token is None
            or header_token is None
            or not compare_digest(cookie_token, header_token)
        ):
            raise SecurityPolicyError("csrf_validation_failed")


@dataclass(frozen=True, slots=True)
class RateLimit:
    requests: int
    window_seconds: int

    def __post_init__(self) -> None:
        if self.requests < 1 or self.window_seconds < 1:
            raise ValueError("rate limits must be positive")


class RateLimitPolicy(Protocol):
    def check(self, actor_reference: str, bucket: str) -> None: ...


class InMemoryRateLimiter:
    """A bounded process-local hook suitable for the single-worker SQLite default."""

    def __init__(
        self,
        limits: Mapping[str, RateLimit],
        *,
        clock: Callable[[], float] = monotonic,
        maximum_keys: int = 10_000,
    ) -> None:
        if maximum_keys < 1:
            raise ValueError("maximum_keys must be positive")
        self._limits = dict(limits)
        self._clock = clock
        self._maximum_keys = maximum_keys
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, actor_reference: str, bucket: str) -> None:
        limit = self._limits.get(bucket)
        if limit is None:
            raise SecurityPolicyError("rate_limit_policy_missing")
        key = (actor_reference, bucket)
        now = self._clock()
        cutoff = now - limit.window_seconds
        with self._lock:
            if key not in self._events and len(self._events) >= self._maximum_keys:
                self._evict_one(now)
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit.requests:
                retry_after = max(1, int(events[0] + limit.window_seconds - now + 0.999))
                raise SecurityPolicyError(
                    "rate_limit_exceeded",
                    retry_after_seconds=retry_after,
                )
            events.append(now)

    def _evict_one(self, now: float) -> None:
        oldest_key: tuple[str, str] | None = None
        oldest_time = now
        for key, events in self._events.items():
            if not events:
                oldest_key = key
                break
            if events[-1] <= oldest_time:
                oldest_key = key
                oldest_time = events[-1]
        if oldest_key is not None:
            del self._events[oldest_key]


class RequestSizeLimitMiddleware:
    """Reject oversized request bodies before routing or parsing them."""

    def __init__(self, app: ASGIApp, *, maximum_bytes: int) -> None:
        if maximum_bytes < 1:
            raise ValueError("maximum_bytes must be positive")
        self._app = app
        self._maximum_bytes = maximum_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") in SAFE_METHODS:
            await self._app(scope, receive, send)
            return

        content_length = _content_length(scope)
        if content_length is not None and content_length > self._maximum_bytes:
            await self._reject(send)
            return

        messages: list[Message] = []
        received = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            received += len(body)
            if received > self._maximum_bytes:
                await self._reject(send)
                return
            if not message.get("more_body", False):
                break

        message_iterator = iter(messages)

        async def replay() -> Message:
            try:
                return next(message_iterator)
            except StopIteration:
                return {"type": "http.request", "body": b"", "more_body": False}

        await self._app(scope, replay, send)

    @staticmethod
    async def _reject(send: Send) -> None:
        body = (
            b'{"error":{"code":"request_too_large",'
            b'"message":"The request exceeds the allowed size."}}'
        )
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"cache-control", b"no-store"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name.lower() == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None
