"""Deterministic test doubles for RAG dependency boundaries."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from typing import BinaryIO

from app.services.rag.contracts import (
    ExtractedDocument,
    TaskGenerationRequest,
    TaskGenerationResponse,
    VectorMatch,
    VectorQuery,
    VectorRecord,
)
from app.services.rag.errors import CourseAccessDeniedError


class AllowAllCourseAccessPolicy:
    def require_read(self, actor_id: str, course_id: str) -> None:
        return None

    def require_manage(self, actor_id: str, course_id: str) -> None:
        return None


class DenyAllCourseAccessPolicy:
    def require_read(self, actor_id: str, course_id: str) -> None:
        raise CourseAccessDeniedError()

    def require_manage(self, actor_id: str, course_id: str) -> None:
        raise CourseAccessDeniedError()


class DeterministicEmbeddingProvider:
    """Small, offline unit vectors derived solely from input text."""

    def __init__(self, dimension: int = 8, model_id: str = "deterministic-test-v1") -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [float(digest[index % len(digest)]) / 255.0 for index in range(self.dimension)]
        magnitude = math.sqrt(sum(value * value for value in values))
        return [value / magnitude for value in values]


class InMemoryVectorStore:
    def __init__(self) -> None:
        self.records: dict[str, VectorRecord] = {}

    def upsert(self, records: Sequence[VectorRecord]) -> None:
        self.records.update({record.chunk_id: record for record in records})

    def query(self, request: VectorQuery) -> list[VectorMatch]:
        matches: list[VectorMatch] = []
        allowed = set(request.allowed_chunk_ids)
        for record in self.records.values():
            metadata = record.metadata
            if metadata.get("course_id") != request.course_id:
                continue
            if request.module_id is not None and metadata.get("module_id") != request.module_id:
                continue
            if allowed and record.chunk_id not in allowed:
                continue
            distance = 1.0 - sum(a * b for a, b in zip(request.embedding, record.embedding, strict=True))
            matches.append(VectorMatch(record.chunk_id, distance, metadata))
        return sorted(matches, key=lambda match: (match.distance, match.chunk_id))[: request.candidate_count]

    def delete_material(self, material_id: str) -> None:
        matching_ids = [
            chunk_id
            for chunk_id, record in self.records.items()
            if record.metadata.get("material_id") == material_id
        ]
        for chunk_id in matching_ids:
            del self.records[chunk_id]

    def contains_material(self, material_id: str) -> bool:
        return any(record.metadata.get("material_id") == material_id for record in self.records.values())


class StaticDocumentExtractor:
    supported_mime_types = frozenset({"application/test"})

    def __init__(self, document: ExtractedDocument) -> None:
        self.document = document
        self.calls = 0

    def extract(self, source: BinaryIO) -> ExtractedDocument:
        self.calls += 1
        return self.document


class RecordingTaskGenerationClient:
    def __init__(self, response: TaskGenerationResponse) -> None:
        self.response = response
        self.requests: list[TaskGenerationRequest] = []

    async def generate_structured(self, request: TaskGenerationRequest) -> TaskGenerationResponse:
        self.requests.append(request)
        return self.response
