"""Canonical response hashing and lossless evaluation/export representation."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.schemas.episode import EpisodePayloadV1, FrozenResponseRead, ResponseContent


def canonical_response_digest(
    *,
    content: ResponseContent,
    episode: EpisodePayloadV1 | None = None,
    schema_version: str = "assessment.response.v1",
    assessment_work_start_id: str | None = None,
    task_form_version_id: str | None = None,
    declared_conditions: dict | list | None = None,
) -> str:
    payload: dict[str, Any] = content.model_dump(mode="json")
    if schema_version == "practice.response.v1" and (
        episode is None
        or assessment_work_start_id is not None
        or task_form_version_id is not None
        or declared_conditions is not None
    ):
        raise ValueError("Typed practice requires an episode without formal assessment bindings")
    if schema_version in {"assessment.response.v2", "practice.response.v1"}:
        payload.update(
            schema_version=schema_version,
            episode=episode.model_dump(mode="json") if episode else None,
            assessment_work_start_id=assessment_work_start_id,
            task_form_version_id=task_form_version_id,
            declared_conditions=declared_conditions,
        )
    elif schema_version != "assessment.response.v1" or episode is not None:
        raise ValueError("Unsupported response schema or incompatible episode payload")
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
                "utf-8"
            )
        ).hexdigest()
    )


def extract_response_evidence(response: FrozenResponseRead) -> dict[str, Any]:
    """Keep every field and its own immutable reference; never relabel earlier evidence."""
    return response.model_dump(mode="json")


def export_response_snapshot(response: FrozenResponseRead) -> dict[str, Any]:
    """Representation only. Governed export authorization belongs to the caller."""
    return extract_response_evidence(response)
