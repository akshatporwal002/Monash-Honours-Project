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
        episode_payload = episode.model_dump(mode="json") if episode else None
        if episode_payload is not None:
            # Application was added to the v1 episode contract after these hash
            # versions shipped. Its absent default must not change earlier hashes;
            # actual application content remains part of the immutable digest.
            stages = [episode_payload["supported"]]
            if episode_payload["transfer"] is not None:
                stages.append(episode_payload["transfer"]["process"])
            for stage in stages:
                if stage.get("application") is None:
                    stage.pop("application", None)
        payload.update(
            schema_version=schema_version,
            episode=episode_payload,
            assessment_work_start_id=assessment_work_start_id,
            task_form_version_id=task_form_version_id,
            declared_conditions=declared_conditions,
        )
    elif schema_version != "assessment.response.v1" or episode is not None:
        raise ValueError("Unsupported response schema or incompatible episode payload")
    return _digest(payload)


def response_digest_matches(
    retained_digest: str,
    *,
    content: ResponseContent,
    episode: EpisodePayloadV1 | None = None,
    schema_version: str = "assessment.response.v1",
    assessment_work_start_id: str | None = None,
    task_form_version_id: str | None = None,
    declared_conditions: dict | list | None = None,
) -> bool:
    """Verify exact retained content without replacing its historical digest.

    Between adding ``application`` and restoring canonical v1 episode hashing,
    writers included its null default. Only that complete typed serialization is
    accepted in addition to the canonical one; no populated content is discarded.
    Canonical validation runs first, including schema and practice binding checks.
    """
    canonical = canonical_response_digest(
        content=content,
        episode=episode,
        schema_version=schema_version,
        assessment_work_start_id=assessment_work_start_id,
        task_form_version_id=task_form_version_id,
        declared_conditions=declared_conditions,
    )
    if retained_digest == canonical:
        return True
    if episode is None or schema_version not in {"assessment.response.v2", "practice.response.v1"}:
        return False
    intermediate = {
        **content.model_dump(mode="json"),
        "schema_version": schema_version,
        "episode": episode.model_dump(mode="json"),
        "assessment_work_start_id": assessment_work_start_id,
        "task_form_version_id": task_form_version_id,
        "declared_conditions": declared_conditions,
    }
    return retained_digest == _digest(intermediate)


def _digest(payload: dict[str, Any]) -> str:
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
