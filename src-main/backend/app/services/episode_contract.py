"""Read-only episode port and reviewed-plan validation, independent of persistence."""

from __future__ import annotations

from typing import Any, Protocol

from app.schemas.assessment import AssessmentVersionReference
from app.schemas.episode import EpisodePlanV1, FrozenResponseRead


class FrozenResponseError(ValueError):
    """A frozen response cannot safely be consumed."""


class FrozenResponseMissing(FrozenResponseError):
    pass


class FrozenResponseStale(FrozenResponseError):
    pass


class FrozenResponseInvalid(FrozenResponseError):
    pass


class FrozenResponseReader(Protocol):
    def read(self, *, assessment: AssessmentVersionReference) -> FrozenResponseRead: ...


def validate_reviewed_episode_plan(
    marking_criteria: dict[str, Any] | None,
    frozen_plan: dict[str, Any] | EpisodePlanV1 | None = None,
) -> EpisodePlanV1 | None:
    """Validate the reviewed private plan; reject a different frozen form copy."""
    raw = (marking_criteria or {}).get("episode_plan")
    if raw is None:
        if frozen_plan is not None:
            raise ValueError("The frozen episode plan was not part of the reviewed task")
        return None
    reviewed = EpisodePlanV1.model_validate(raw)
    if frozen_plan is not None and EpisodePlanV1.model_validate(frozen_plan) != reviewed:
        raise ValueError("The frozen episode plan differs from the reviewed task")
    return reviewed


def learner_episode_plan(plan: EpisodePlanV1) -> dict[str, Any]:
    """Only policy and supported work are visible before transfer entry."""
    return {
        "schema_version": plan.schema_version,
        "supported_part_id": plan.supported_part_id,
        "prediction_required": plan.prediction_required,
        "required_responses": list(plan.required_responses),
        "supported_hints": list(plan.supported_hints),
        "representation_choices": [
            {
                "item_index": len(plan.supported_hints) + index,
                "title": f"{item.mode.replace('_', ' ').capitalize()} support {index + 1}",
                "mode": item.mode,
            }
            for index, item in enumerate(plan.support_representations)
        ],
        "accessibility_support": list(plan.accessibility_support),
        "transfer_part_id": plan.transfer.part_id,
    }
