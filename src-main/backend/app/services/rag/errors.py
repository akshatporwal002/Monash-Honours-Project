"""Controlled errors exposed by RAG service and API boundaries."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(eq=False)
class RagError(Exception):
    code: str
    safe_message: str
    http_status: int

    def __str__(self) -> str:
        return self.safe_message


class CourseAccessDeniedError(RagError):
    def __init__(self) -> None:
        super().__init__("course_access_denied", "Course access is denied.", 403)


class UnsupportedMaterialTypeError(RagError):
    def __init__(self) -> None:
        super().__init__("unsupported_material_type", "This material type is not supported.", 415)


class EmbeddingProviderUnavailableError(RagError):
    def __init__(self) -> None:
        super().__init__("embedding_provider_unavailable", "The embedding provider is unavailable.", 503)


class VectorStoreUnavailableError(RagError):
    def __init__(self) -> None:
        super().__init__("vector_store_unavailable", "The vector store is unavailable.", 503)
