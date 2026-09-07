"""Assessor-only context and historical evidence for frozen work."""

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.episode import FrozenResponseRead


class FrozenAssessmentContextRead(BaseModel):
    task_revision_id: str
    task_title: str
    supported_prompt: str
    supported_instructions: str
    starter_code: str | None = None
    starter_circuit: dict[str, Any] | None = None
    transfer_prompt: str | None = None
    transfer_instructions: str | None = None
    transfer_starter_code: str | None = None
    transfer_starter_circuit: dict[str, Any] | None = None
    outcome_title: str
    outcome_statement: str
    bloom_process: str
    knowledge_dimension: str
    pass_rule_expression: dict[str, Any]


class HistoricalResponseEvidenceRead(BaseModel):
    response_version_id: str
    response: FrozenResponseRead | None = None
    simulations: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
