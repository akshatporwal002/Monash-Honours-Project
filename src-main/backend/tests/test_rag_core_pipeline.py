import io
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import LearningMaterial, MaterialIndexStatus, RetrievalAudit
from app.services.rag.contracts import (
    ExtractedBlock,
    ExtractedDocument,
    RetrievalPurpose,
    RetrievalQuery,
)
from app.services.rag.fakes import (
    DeterministicEmbeddingProvider,
    InMemoryVectorStore,
    StaticDocumentExtractor,
)
from app.services.rag.ingestion import MaterialProcessor
from app.services.rag.retrieval import NO_RESULT_MESSAGE, RetrievalService
from app.services.rag.storage import LocalFileStorage


def _session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{(tmp_path / 'rag.db').as_posix()}")
    Base.metadata.create_all(engine)
    return Session(engine)


def _stored_material(
    session: Session, storage: LocalFileStorage, course_id: str
) -> LearningMaterial:
    staged = storage.stage_upload("notes.pdf", io.BytesIO(b"%PDF-1.4\nplaceholder"))
    material = LearningMaterial(
        course_id=course_id,
        original_filename="notes.pdf",
        mime_type="application/pdf",
        content_hash=f"sha256:{course_id}",
        indexing_status=MaterialIndexStatus.PENDING,
        file_size_bytes=staged.file_size_bytes,
    )
    session.add(material)
    session.flush()
    material.storage_key = storage.commit(staged, material.id)
    session.commit()
    return material


def test_processor_persists_normalised_chunks_and_indexes_them(tmp_path: Path) -> None:
    session = _session(tmp_path)
    storage = LocalFileStorage(tmp_path / "uploads", 1024 * 1024)
    material = _stored_material(session, storage, "course-1")
    document = ExtractedDocument(
        (
            ExtractedBlock(
                0,
                "Hadamard\r\n gate creates a superposition state.",
                "Gates",
                "Page 1",
                "paragraph",
            ),
        ),
        "Notes",
        50,
    )
    embedding, vectors = DeterministicEmbeddingProvider(), InMemoryVectorStore()
    processor = MaterialProcessor(
        session, storage, {"application/pdf": StaticDocumentExtractor(document)}, embedding, vectors
    )

    chunk_count, indexed_chunk_count = processor.process(material)
    session.refresh(material)

    assert (chunk_count, indexed_chunk_count) == (1, 1)
    assert material.indexing_status is MaterialIndexStatus.INDEXED
    assert material.chunks[0].chunk_hash
    assert material.chunks[0].embedding_dimension == embedding.dimension
    assert vectors.contains_material(material.id)


def test_retrieval_revalidates_course_scope_and_writes_privacy_safe_audit(tmp_path: Path) -> None:
    session = _session(tmp_path)
    storage = LocalFileStorage(tmp_path / "uploads", 1024 * 1024)
    first, second = (
        _stored_material(session, storage, "course-1"),
        _stored_material(session, storage, "course-2"),
    )
    document = ExtractedDocument(
        (
            ExtractedBlock(
                0,
                "Hadamard gate creates a quantum superposition state.",
                "Gates",
                "Page 1",
                "paragraph",
            ),
        ),
        None,
        50,
    )
    embedding, vectors = DeterministicEmbeddingProvider(), InMemoryVectorStore()
    extractor = {"application/pdf": StaticDocumentExtractor(document)}
    processor = MaterialProcessor(session, storage, extractor, embedding, vectors)
    processor.process(first)
    processor.process(second)
    service = RetrievalService(session, embedding, vectors)

    result = service.search(
        RetrievalQuery("course-1", "Hadamard superposition", RetrievalPurpose.SEARCH)
    )

    assert result.found
    assert {hit.course_id for hit in result.hits} == {"course-1"}
    audit = session.query(RetrievalAudit).one()
    assert audit.query_hash != "Hadamard superposition"
    assert not hasattr(audit, "query")

    no_result = service.search(
        RetrievalQuery(
            "course-1", "unrelated classical weather", RetrievalPurpose.SEARCH, min_relevance=1.0
        )
    )
    assert not no_result.found
    assert no_result.message == NO_RESULT_MESSAGE
