"""Recoverable synchronous extraction, chunk persistence, and vector indexing."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import LearningMaterial, MaterialChunk, MaterialIndexStatus
from app.services.rag.chunking import HeadingAwareChunker, WhitespaceTokenCounter
from app.services.rag.contracts import (
    DocumentExtractor,
    EmbeddingProvider,
    VectorRecord,
    VectorStore,
)
from app.services.rag.errors import InvalidMaterialStateError, MaterialAlreadyProcessingError
from app.services.rag.normalisation import ensure_document_size, normalise_text
from app.services.rag.storage import FileStorage


class MaterialProcessor:
    def __init__(self, session: Session, storage: FileStorage, extractors: dict[str, DocumentExtractor], embedding: EmbeddingProvider, vectors: VectorStore) -> None:
        self.session, self.storage, self.extractors, self.embedding, self.vectors = session, storage, extractors, embedding, vectors

    def process(self, material: LearningMaterial, force: bool = False) -> tuple[int, int]:
        if material.indexing_status == MaterialIndexStatus.PROCESSING:
            raise MaterialAlreadyProcessingError()
        if material.indexing_status == MaterialIndexStatus.INDEXED and not force:
            return len(material.chunks), len(material.chunks)
        if material.indexing_status not in {MaterialIndexStatus.PENDING, MaterialIndexStatus.FAILED, MaterialIndexStatus.EXTRACTED, MaterialIndexStatus.INDEXED}:
            raise InvalidMaterialStateError()
        material.indexing_status = MaterialIndexStatus.PROCESSING
        if force:
            material.processing_revision += 1
        self.session.commit()
        try:
            extractor = self.extractors[material.mime_type]
            if not material.storage_key:
                raise InvalidMaterialStateError()
            with self.storage.open_read(material.storage_key) as source:
                extracted = extractor.extract(source)
            normalised = [
                block.__class__(block.ordinal, normalise_text(block.text), block.heading, block.location_label, block.block_type)
                for block in extracted.blocks
            ]
            ensure_document_size([block.text for block in normalised], settings.rag_max_extracted_chars)
            drafts = HeadingAwareChunker(WhitespaceTokenCounter(), settings.rag_chunk_target_tokens, settings.rag_chunk_max_tokens, settings.rag_chunk_overlap_tokens).chunk(tuple(normalised))
            self.session.execute(delete(MaterialChunk).where(MaterialChunk.material_id == material.id))
            chunks = [MaterialChunk(material_id=material.id, chunk_index=draft.chunk_index, chunk_text=draft.text, heading=draft.heading, location_label=draft.location_label, token_count=draft.token_count, chunk_hash=draft.chunk_hash) for draft in drafts]
            self.session.add_all(chunks)
            material.indexing_status, material.extracted_at = MaterialIndexStatus.EXTRACTED, datetime.now(UTC)
            self.session.commit()
            embeddings = self.embedding.embed_documents([chunk.chunk_text for chunk in chunks])
            self.vectors.delete_material(material.id)
            self.vectors.upsert([VectorRecord(chunk.id, vector, chunk.chunk_text, {"course_id": material.course_id, "module_id": material.module_id or "", "material_id": material.id, "chunk_index": chunk.chunk_index, "source_label": self._source_label(material, chunk), "chunk_hash": chunk.chunk_hash, "embedding_model": self.embedding.model_id}) for chunk, vector in zip(chunks, embeddings, strict=True)])
            now = datetime.now(UTC)
            for chunk in chunks:
                chunk.embedding_model, chunk.embedding_version, chunk.embedding_dimension, chunk.indexed_at = self.embedding.model_id, "v1", self.embedding.dimension, now
            material.indexing_status, material.indexed_at = MaterialIndexStatus.INDEXED, now
            self.session.commit()
            return len(chunks), len(chunks)
        except Exception:
            self.session.rollback()
            material = self.session.get(LearningMaterial, material.id)
            if material:
                material.indexing_status, material.failure_stage, material.error_code = MaterialIndexStatus.FAILED, "processing", "processing_failed"
                material.extraction_error = "Material processing could not be completed."
                self.session.commit()
            raise

    @staticmethod
    def _source_label(material: LearningMaterial, chunk: MaterialChunk) -> str:
        parts = [material.original_filename or material.source_url or "Material", chunk.location_label, chunk.heading]
        return " — ".join(part for part in parts if part)
