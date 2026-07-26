import json
import math
import re
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models.enums import ExperimentalCondition, JudgeDecision, ResearchStatus

ExternalId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
PseudonymousReference = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^v1_[0-9a-f]{64}$",
    ),
]
SourceLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000),
]
FailureCategory = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9_.-]*$",
    ),
]

_MAX_GENERATED_OUTPUT_BYTES = 65_536
_MAX_EXPORT_COURSES = 1_000
_MAX_EXPORT_RECORDS = 100_000
_MAX_JSON_DEPTH = 8
_MAX_JSON_NODES = 1_024
_MAX_JSON_COLLECTION_ITEMS = 100
_MAX_JSON_STRING_BYTES = 12_000
_FORBIDDEN_JSON_KEYS = frozenset(
    {
        "access_token",
        "answer",
        "api_key",
        "authorization",
        "chunk_text",
        "cookie",
        "csrf",
        "csrf_token",
        "direct_student_id",
        "draft",
        "draft_content",
        "email",
        "exception",
        "name",
        "password",
        "prompt",
        "prompt_content",
        "provider_output",
        "provider_response",
        "raw_answer",
        "raw_exception",
        "raw_output",
        "refresh_token",
        "retrieved_chunk",
        "secret",
        "source_chunk",
        "source_chunks",
        "stacktrace",
        "student_id",
        "submitted_answer",
        "submission_id",
        "system_prompt",
        "traceback",
        "user_prompt",
    }
)
_FORBIDDEN_COMPACT_JSON_KEYS = frozenset(key.replace("_", "") for key in _FORBIDDEN_JSON_KEYS)
_SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{8,}"),
    re.compile(r"\bsk-[a-zA-Z0-9_-]{12,}\b"),
    re.compile(r"\beyJ[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\b"),
    re.compile(
        r"(?i)\b(?:api[_ -]?key|access[_ -]?token|csrf[_ -]?token|password)"
        r"\s*[:=]\s*\S+"
    ),
    re.compile(r"(?i)\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+\b"),
)


class ResearchExportFormat(str, Enum):
    CSV = "csv"
    JSON = "json"


class ResearchExportContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _contains_sensitive_value(value: str) -> bool:
    return any(pattern.search(value) is not None for pattern in _SENSITIVE_VALUE_PATTERNS)


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _validate_privacy_safe_json(value: JsonValue) -> None:
    remaining_nodes = _MAX_JSON_NODES

    def visit(item: JsonValue, *, depth: int) -> None:
        nonlocal remaining_nodes
        remaining_nodes -= 1
        if remaining_nodes < 0:
            raise ValueError("generated output exceeds the structural limit")
        if depth > _MAX_JSON_DEPTH:
            raise ValueError("generated output exceeds the nesting limit")
        if isinstance(item, str):
            if len(item.encode("utf-8")) > _MAX_JSON_STRING_BYTES:
                raise ValueError("generated output contains oversized text")
            if _contains_sensitive_value(item):
                raise ValueError("generated output contains a sensitive value")
            return
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("generated output contains a non-finite number")
        if isinstance(item, list):
            if len(item) > _MAX_JSON_COLLECTION_ITEMS:
                raise ValueError("generated output exceeds the list limit")
            for child in item:
                visit(child, depth=depth + 1)
            return
        if isinstance(item, dict):
            if len(item) > _MAX_JSON_COLLECTION_ITEMS:
                raise ValueError("generated output exceeds the object limit")
            for key, child in item.items():
                normalized = _normalized_key(key)
                if (
                    normalized in _FORBIDDEN_JSON_KEYS
                    or normalized.replace("_", "") in _FORBIDDEN_COMPACT_JSON_KEYS
                ):
                    raise ValueError("generated output contains a forbidden field")
                if len(key.encode("utf-8")) > 255:
                    raise ValueError("generated output contains an oversized field name")
                visit(child, depth=depth + 1)

    visit(value, depth=0)


class ResearchExportRetrievedSource(ResearchExportContract):
    source_id: ExternalId
    label: SourceLabel
    relevance_score: Annotated[float, Field(ge=0, le=1)]

    @field_validator("label")
    @classmethod
    def reject_sensitive_label(cls, value: str) -> str:
        if _contains_sensitive_value(value):
            raise ValueError("retrieved source label contains a sensitive value")
        return value


class ResearchExportFilters(ResearchExportContract):
    course_id: ExternalId | None = None
    course_ids: list[ExternalId] = Field(
        default_factory=list,
        max_length=_MAX_EXPORT_COURSES,
    )
    date_from: datetime
    date_to: datetime
    experimental_condition: ExperimentalCondition | None = None
    task_type: ExternalId | None = None
    model: ExternalId | None = None
    judge_decision: JudgeDecision | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "ResearchExportFilters":
        if self.date_to <= self.date_from:
            raise ValueError("date_to must be later than date_from")
        if self.date_to - self.date_from > timedelta(days=365):
            raise ValueError("research exports are limited to 365 days")
        return self


class ResearchExportRecord(ResearchExportContract):
    case_id: ExternalId
    pseudonymous_user_id: PseudonymousReference
    course_id: ExternalId
    task_id: ExternalId
    task_type: ExternalId
    submission_reference: PseudonymousReference
    experimental_condition: ExperimentalCondition
    input_reference: list[ExternalId] = Field(default_factory=list, max_length=100)
    retrieved_sources: list[ResearchExportRetrievedSource] = Field(
        default_factory=list,
        max_length=100,
    )
    simulation_reference: ExternalId | None = None
    generated_output: dict[str, JsonValue] = Field(default_factory=dict)
    judge_decision: JudgeDecision | None = None
    judge_reason: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=12_000),
        ]
        | None
    ) = None
    correctness_score: int | None = Field(default=None, ge=0, le=100)
    relevance_score: int | None = Field(default=None, ge=0, le=100)
    grounding_score: int | None = Field(default=None, ge=0, le=100)
    actionability_score: int | None = Field(default=None, ge=0, le=100)
    safety_score: int | None = Field(default=None, ge=0, le=100)
    unsupported_claim_count: int = Field(default=0, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost: Decimal = Field(ge=0)
    regeneration_count: int = Field(ge=0, le=1)
    fallback_used: bool
    status: ResearchStatus
    failure_category: FailureCategory | None = None
    comparable: bool
    usage_complete: bool
    measurement_schema_version: ExternalId
    created_at: datetime
    completed_at: datetime | None = None

    @field_validator("generated_output")
    @classmethod
    def bound_generated_output(
        cls,
        value: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        try:
            encoded = json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError):
            raise ValueError("generated output is not valid JSON") from None
        if len(encoded) > _MAX_GENERATED_OUTPUT_BYTES:
            raise ValueError("generated output exceeds the export size limit")
        _validate_privacy_safe_json(value)
        return value

    @field_validator("input_reference")
    @classmethod
    def reject_sensitive_input_references(cls, value: list[str]) -> list[str]:
        if any(_contains_sensitive_value(reference) for reference in value):
            raise ValueError("input reference contains a sensitive value")
        return value

    @field_validator("judge_reason")
    @classmethod
    def reject_sensitive_judge_reason(cls, value: str | None) -> str | None:
        if value is not None and _contains_sensitive_value(value):
            raise ValueError("judge reason contains a sensitive value")
        return value

    @model_validator(mode="after")
    def validate_terminal_status(self) -> "ResearchExportRecord":
        if (self.status is ResearchStatus.FAILED) != (self.failure_category is not None):
            raise ValueError("failed export records require one sanitized failure category")
        return self


class ResearchJsonEnvelope(ResearchExportContract):
    schema_version: str = "quantumlearn.research-export.v1"
    generated_at: datetime
    filters: ResearchExportFilters
    record_count: int = Field(ge=0)
    records: list[ResearchExportRecord] = Field(max_length=_MAX_EXPORT_RECORDS)
