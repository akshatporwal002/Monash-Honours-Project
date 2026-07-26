import math

import pytest

from app.services.rag.contracts import (
    ExtractedBlock,
    ExtractedDocument,
    RetrievalPurpose,
    VectorQuery,
    VectorRecord,
)
from app.services.rag.errors import CourseAccessDeniedError
from app.services.rag.fakes import (
    DenyAllCourseAccessPolicy,
    DeterministicEmbeddingProvider,
    InMemoryVectorStore,
    StaticDocumentExtractor,
)


def test_contract_values_are_immutable_and_preserve_source_metadata() -> None:
    block = ExtractedBlock(0, "Hadamard gate", "Gates", "Page 1", "paragraph")
    document = ExtractedDocument((block,), "Week one", len(block.text))

    assert document.blocks[0].location_label == "Page 1"
    with pytest.raises(AttributeError):
        block.text = "changed"  # type: ignore[misc]


def test_deterministic_embeddings_are_repeatable_unit_vectors() -> None:
    provider = DeterministicEmbeddingProvider(dimension=8)
    first = provider.embed_query("superposition")

    assert first == provider.embed_documents(["superposition"])[0]
    assert math.isclose(sum(value * value for value in first), 1.0)


def test_in_memory_vector_store_enforces_course_and_allowed_chunk_filters() -> None:
    provider = DeterministicEmbeddingProvider()
    store = InMemoryVectorStore()
    store.upsert(
        [
            VectorRecord("allowed", provider.embed_query("gate"), "gate", {"course_id": "course-1", "material_id": "m1"}),
            VectorRecord("other-course", provider.embed_query("gate"), "gate", {"course_id": "course-2", "material_id": "m2"}),
        ]
    )

    matches = store.query(
        VectorQuery("course-1", provider.embed_query("gate"), 5, allowed_chunk_ids=("allowed",))
    )

    assert [match.chunk_id for match in matches] == ["allowed"]


def test_static_extractor_and_denied_access_fake_are_offline() -> None:
    document = ExtractedDocument((), None, 0)
    extractor = StaticDocumentExtractor(document)

    assert extractor.extract(None).character_count == 0  # type: ignore[arg-type]
    assert extractor.calls == 1
    with pytest.raises(CourseAccessDeniedError):
        DenyAllCourseAccessPolicy().require_read("actor", "course")


def test_retrieval_purpose_is_a_stable_string_enum() -> None:
    assert RetrievalPurpose.FEEDBACK == "feedback"
