"""Safety policy for non-diagnostic, evidence-based learner-model inference."""

from __future__ import annotations

import re
from collections.abc import Mapping

from app.domain.platform_enums import ModelSource

_NORMALIZE = re.compile(r"[^a-z0-9]+")
_BANNED_CLAIM_PARTS = frozenset(
    {
        "diagnosis",
        "disability",
        "neurodivergen",
        "medical",
        "demographic",
        "psychological",
        "motivation",
        "fixedability",
        "learningstyle",
    }
)


class LearnerModelSafetyError(ValueError):
    """A proposed learner-model claim falls outside the approved evidence scope."""


class LearnerModelReviewRequiredError(LearnerModelSafetyError):
    """A non-rule model cannot create an inference without a human reviewer."""


class LearnerModelConflictError(LearnerModelSafetyError):
    """An idempotency key was reused for a different immutable snapshot."""


class LearnerModelPersistenceError(LearnerModelSafetyError):
    """Snapshot storage failed without exposing database details to callers."""


class LearnerModelProviderError(LearnerModelSafetyError):
    """A versioned advisory provider could not produce a safe candidate."""


def require_safe_claim_text(value: str) -> str:
    """Return a normalized reason code only when it contains no banned trait claim."""

    normalized = _NORMALIZE.sub("", value.casefold())
    if any(part in normalized for part in _BANNED_CLAIM_PARTS):
        raise LearnerModelSafetyError("learner-model claim uses a banned trait category")
    return value


def reject_banned_fields(values: Mapping[str, object]) -> None:
    """Reject unsafe generated payload fields before any persistence attempt."""

    for key in values:
        require_safe_claim_text(key)


def require_human_review_for_model_source(
    source: ModelSource,
    reviewed_by_reference: str | None,
) -> None:
    """Keep future advisory-model integrations behind an explicit review threshold."""

    if source is not ModelSource.RULE_BASED and not reviewed_by_reference:
        raise LearnerModelReviewRequiredError(
            "non-rule learner-model inference requires an authorized human review"
        )


__all__ = [
    "LearnerModelConflictError",
    "LearnerModelPersistenceError",
    "LearnerModelProviderError",
    "LearnerModelReviewRequiredError",
    "LearnerModelSafetyError",
    "reject_banned_fields",
    "require_human_review_for_model_source",
    "require_safe_claim_text",
]
