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


class MaterialNotFoundError(RagError):
    def __init__(self) -> None:
        super().__init__("material_not_found", "The learning material was not found.", 404)


class MaterialTooLargeError(RagError):
    def __init__(self) -> None:
        super().__init__("material_too_large", "The material exceeds the maximum file size.", 413)


class DuplicateMaterialError(RagError):
    def __init__(self, material_id: str) -> None:
        super().__init__("duplicate_material", "An identical material already exists in this course.", 409)
        self.material_id = material_id


class InvalidDocumentError(RagError):
    def __init__(self) -> None:
        super().__init__("invalid_document", "The uploaded file does not match its supported document type.", 422)


class EncryptedDocumentError(RagError):
    def __init__(self) -> None:
        super().__init__("encrypted_document", "Encrypted documents are not supported.", 422)


class NoExtractableTextError(RagError):
    def __init__(self) -> None:
        super().__init__("no_extractable_text", "No extractable text was found in this document.", 422)


class MaterialAlreadyProcessingError(RagError):
    def __init__(self) -> None:
        super().__init__("material_already_processing", "This material is already processing.", 409)


class InvalidMaterialStateError(RagError):
    def __init__(self) -> None:
        super().__init__("invalid_material_state", "This material cannot be processed in its current state.", 409)


class ExtractedContentTooLargeError(RagError):
    def __init__(self) -> None:
        super().__init__("extracted_content_too_large", "The extracted content exceeds the allowed size.", 422)


class IndexConfigurationError(RagError):
    def __init__(self) -> None:
        super().__init__("index_configuration_mismatch", "The vector index configuration does not match.", 503)


class EmbeddingProviderUnavailableError(RagError):
    def __init__(self) -> None:
        super().__init__("embedding_provider_unavailable", "The embedding provider is unavailable.", 503)


class VectorStoreUnavailableError(RagError):
    def __init__(self) -> None:
        super().__init__("vector_store_unavailable", "The vector store is unavailable.", 503)
