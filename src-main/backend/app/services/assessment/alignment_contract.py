"""Prospective feedback and adaptation declarations for new BP3 approvals.

This is an authoring contract, not learner feedback or a runtime routing policy.
Historical approved definitions are never rewritten or revalidated here.
"""

from collections.abc import Mapping, Sequence
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Declaration = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=4000)
]
Reference = Annotated[
    str, StringConstraints(strict=True, min_length=1, max_length=255, pattern=r"\S")
]


class _ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CriterionFeedbackPlan(_ContractModel):
    criterion_key: Reference
    evidence_source_types: list[Reference] = Field(min_length=1, max_length=64)
    met: Declaration
    not_met: Declaration
    not_evaluable: Declaration


class ResultAdaptationPlan(_ContractModel):
    feedback: Declaration
    adaptation: Declaration


class ApprovalAlignmentContract(_ContractModel):
    """Version one declarations refer to criteria within the containing version."""

    schema_version: int = Field(strict=True, ge=1, le=1)
    criterion_feedback: list[CriterionFeedbackPlan] = Field(min_length=1, max_length=256)
    result_adaptation: dict[Literal["PASS", "INCOMPLETE"], ResultAdaptationPlan]

    @model_validator(mode="after")
    def require_complete_results(self) -> "ApprovalAlignmentContract":
        if set(self.result_adaptation) != {"PASS", "INCOMPLETE"}:
            raise ValueError("result_adaptation requires PASS and INCOMPLETE declarations")
        return self


def validate_next_action_alignment(
    next_action_contract: object, criteria: Mapping[str, Sequence[str]]
) -> None:
    """Check explicit links without inventing decisions or requiring learner records."""
    if not isinstance(next_action_contract, dict):
        raise ValueError("next_action_contract requires an alignment object for new approval")
    contract = ApprovalAlignmentContract.model_validate(next_action_contract.get("alignment"))
    keys = [plan.criterion_key for plan in contract.criterion_feedback]
    if len(keys) != len(set(keys)) or set(keys) != set(criteria):
        raise ValueError("criterion_feedback must reference every current criterion exactly once")
    for plan in contract.criterion_feedback:
        sources = plan.evidence_source_types
        if len(sources) != len(set(sources)) or set(sources) != set(criteria[plan.criterion_key]):
            raise ValueError(
                "criterion_feedback evidence sources must match the referenced criterion"
            )
