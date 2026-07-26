"""Reusable OpenAPI response declarations for the sanitized API envelope."""

from typing import Any

from app.schemas.feedback_api import FeedbackApiErrorResponse


def sanitized_errors(*status_codes: int) -> dict[int, dict[str, Any]]:
    return {
        status_code: {
            "model": FeedbackApiErrorResponse,
            "description": "Sanitized API error",
        }
        for status_code in status_codes
    }
