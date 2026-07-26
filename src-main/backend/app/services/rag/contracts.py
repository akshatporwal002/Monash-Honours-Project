"""Stable, dependency-free contracts shared by RAG implementation stages."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, BinaryIO, Literal, Protocol


class RetrievalPurpose(StrEnum):
    SEARCH = "search"
    FEEDBACK = "feedback"
    TASK_GENERATION = "task_generation"


@dataclass(frozen=True, slots=True)
class ExtractedBlock:
    ordinal: int
    text: str
    heading: str | None
    location_label: str
    block_type: Literal["heading", "paragraph", "code", "table"]


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    blocks: tuple[ExtractedBlock, ...]
    title: str | None
    character_count: int


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    chunk_index: int
    text: str
    heading: str | None
    location_label: str
    token_count: int
    chunk_hash: str


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    course_id: str
    text: str
    purpose: RetrievalPurpose
    module_id: str | None = None
    task_id: str | None = None
    allowed_chunk_ids: tuple[str, ...] = ()
    top_k: int = 5
    min_relevance: float = 0.45


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    chunk_id: str
    material_id: str
    course_id: str
    chunk_text: str
    source_label: str
    relevance_score: float
    chunk_index: int


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    request_id: str
    found: bool
    hits: tuple[RetrievalHit, ...]
    message: str | None
    latency_ms: int
    embedding_model: str


@dataclass(frozen=True, slots=True)
class VectorRecord:
    chunk_id: str
    embedding: list[float]
    document: str
    metadata: dict[str, str | int | float | bool]


@dataclass(frozen=True, slots=True)
class VectorQuery:
    course_id: str
    embedding: list[float]
    candidate_count: int
    module_id: str | None = None
    allowed_chunk_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VectorMatch:
    chunk_id: str
    distance: float
    metadata: dict[str, str | int | float | bool]


@dataclass(frozen=True, slots=True)
class TaskGenerationRequest:
    prompt_version: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TaskGenerationResponse:
    tasks: tuple[dict[str, Any], ...]
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0


class DocumentExtractor(Protocol):
    supported_mime_types: frozenset[str]

    def extract(self, source: BinaryIO) -> ExtractedDocument: ...


class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...

    def split_to_token_limit(self, text: str, limit: int) -> list[str]: ...


class EmbeddingProvider(Protocol):
    @property
    def model_id(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class VectorStore(Protocol):
    def upsert(self, records: Sequence[VectorRecord]) -> None: ...

    def query(self, request: VectorQuery) -> list[VectorMatch]: ...

    def delete_material(self, material_id: str) -> None: ...

    def contains_material(self, material_id: str) -> bool: ...


class CourseAccessPolicy(Protocol):
    def require_read(self, actor_id: str, course_id: str) -> None: ...

    def require_manage(self, actor_id: str, course_id: str) -> None: ...


class TaskGenerationClient(Protocol):
    async def generate_structured(
        self,
        request: TaskGenerationRequest,
    ) -> TaskGenerationResponse: ...
