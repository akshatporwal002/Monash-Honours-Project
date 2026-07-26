from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

REDACTED = "[REDACTED]"
SENSITIVE_KEY_PARTS = frozenset(
    {
        "access_token",
        "answer",
        "api_key",
        "authorization",
        "cookie",
        "csrf",
        "draft",
        "email",
        "name",
        "password",
        "prompt",
        "provider_output",
        "raw",
        "secret",
        "source_chunk",
        "token",
    }
)

_EMAIL_PATTERN = re.compile(r"(?i)\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{8,}")
_JWT_PATTERN = re.compile(r"\beyJ[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\b")
_SECRET_PATTERN = re.compile(r"(?i)\b(?:sk|pk|api|csrf|token|secret|password)[-_][a-z0-9_-]{8,}\b")


def is_sensitive_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _redact_string(value: str, *, max_length: int) -> str:
    redacted = _EMAIL_PATTERN.sub(REDACTED, value)
    redacted = _BEARER_PATTERN.sub(REDACTED, redacted)
    redacted = _JWT_PATTERN.sub(REDACTED, redacted)
    redacted = _SECRET_PATTERN.sub(REDACTED, redacted)
    if len(redacted) > max_length:
        return f"{redacted[:max_length]}[TRUNCATED]"
    return redacted


def redact_sensitive(
    value: Any,
    *,
    max_depth: int = 5,
    max_items: int = 50,
    max_string_length: int = 500,
    _depth: int = 0,
) -> Any:
    if _depth >= max_depth:
        return "[TRUNCATED]"
    if isinstance(value, Mapping):
        bounded_items = list(value.items())[:max_items]
        redacted = {
            str(key)[:100]: (
                REDACTED
                if is_sensitive_key(key)
                else redact_sensitive(
                    item,
                    max_depth=max_depth,
                    max_items=max_items,
                    max_string_length=max_string_length,
                    _depth=_depth + 1,
                )
            )
            for key, item in bounded_items
        }
        if len(value) > max_items:
            redacted["[TRUNCATED]"] = len(value) - max_items
        return redacted
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        bounded = list(value[:max_items])
        redacted_items = [
            redact_sensitive(
                item,
                max_depth=max_depth,
                max_items=max_items,
                max_string_length=max_string_length,
                _depth=_depth + 1,
            )
            for item in bounded
        ]
        if len(value) > max_items:
            redacted_items.append(f"[TRUNCATED {len(value) - max_items} ITEMS]")
        return redacted_items
    if isinstance(value, str):
        return _redact_string(value, max_length=max_string_length)
    return value
