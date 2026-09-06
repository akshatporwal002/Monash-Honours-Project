"""Shared validation for stored phrase rules at approval and evaluation."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.domain.assessment import BloomProcess

Phrase = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class RuleSettings(BaseModel):
    """Bounded phrase checks, with explicit exclusions for contradictory evidence."""

    model_config = ConfigDict(extra="forbid", strict=True)

    all_of: list[Phrase] = Field(default_factory=list, max_length=64)
    any_of: list[Phrase] = Field(default_factory=list, max_length=64)
    relation_markers: list[Phrase] = Field(default_factory=list, max_length=64)
    none_of: list[Phrase] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def require_satisfiable_evidence(self) -> "RuleSettings":
        if not self.all_of and not self.any_of:
            raise ValueError("rule settings require all_of or any_of evidence")
        excluded = [phrase.casefold() for phrase in self.none_of]

        def forbidden(phrase: str) -> bool:
            return any(item in phrase.casefold() for item in excluded)

        if any(forbidden(phrase) for phrase in self.all_of) or any(
            group and all(forbidden(phrase) for phrase in group)
            for group in (self.any_of, self.relation_markers)
        ):
            raise ValueError("rule settings contain contradictory required and excluded phrases")
        return self


def validate_rule_settings(anchors: object, bloom_process: BloomProcess) -> RuleSettings:
    settings = RuleSettings.model_validate(anchors)
    if bloom_process is not BloomProcess.REMEMBER:
        raise ValueError("phrase rules only support REMEMBER; use human assessment for reasoning")
    return settings
