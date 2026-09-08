"""Scoped tutor conversation commands and learner-safe history."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class TutorContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TutorTurnWrite(TutorContract):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    idempotency_key: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    expected_revision: int = Field(ge=0)
    context_token: Annotated[str, StringConstraints(min_length=64, max_length=64)]


class TutorTurnRead(TutorContract):
    id: str
    revision: int
    message: str
    reply: str
    kind: str
    created_at: datetime
    source_references: list[str]


class TutorConversationRead(TutorContract):
    context_token: str
    revision: int
    instructional_help_available: bool
    status: str
    turns: list[TutorTurnRead]
    next_offset: int | None = None
