"""Mounted API boundary checks for learner-model corrections."""

import pytest
from fastapi import HTTPException
from test_lms_core_api import lms_context as lms_context

from app.api.routes.learner_model import _decode_cursor, _encode_cursor, _request_identity


def test_correction_request_identity_is_stable_per_actor_and_idempotency_key():
    first = _request_identity("annotation", "learner-1", "retry-key")
    assert first == _request_identity("annotation", "learner-1", "retry-key")
    assert first != _request_identity("annotation", "learner-1", "other-key")
    assert first != _request_identity("review", "learner-1", "retry-key")


def test_timeline_cursor_is_opaque_stable_and_rejects_invalid_values():
    key = ("2026-09-08T00:00:00+00:00", "ANNOTATION", "annotation-1")
    assert _decode_cursor(_encode_cursor(key)) == key
    with pytest.raises(HTTPException) as error:
        _decode_cursor("not-a-timeline-cursor")
    assert error.value.status_code == 422


def test_learner_model_timeline_requires_an_authenticated_student(lms_context):
    client, _ = lms_context
    response = client.get("/api/v1/learner-model/me/timeline?course_id=missing&outcome_id=missing")
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
