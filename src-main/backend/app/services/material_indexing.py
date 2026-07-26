"""Offline material indexing used by the runnable LMS authoring flow."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import LearningMaterial, MaterialChunk, MaterialIndexStatus
from app.services.rag.chunking import HeadingAwareChunker, WhitespaceTokenCounter
from app.services.rag.errors import (
    InvalidMaterialStateError,
    MaterialAlreadyProcessingError,
)
from app.services.rag.extraction.docx import DocxDocumentExtractor
from app.services.rag.extraction.pdf import PdfDocumentExtractor
from app.services.rag.extraction.pptx import PptxDocumentExtractor
from app.services.rag.normalisation import ensure_document_size, normalise_text
from app.services.rag.storage import FileStorage


class OfflineMaterialProcessor:
    """Compatibility adapter for the explicit material processing endpoint."""

    def __init__(self, session: Session, storage: FileStorage) -> None:
        self.session = session
        self.storage = storage

    def process(
        self,
        material: LearningMaterial,
        force: bool = False,
    ) -> tuple[int, int]:
        if material.indexing_status is MaterialIndexStatus.PROCESSING:
            raise MaterialAlreadyProcessingError()
        if material.indexing_status is MaterialIndexStatus.INDEXED and not force:
            count = self._chunk_count(material.id)
            return count, count
        if material.indexing_status not in {
            MaterialIndexStatus.PENDING,
            MaterialIndexStatus.FAILED,
            MaterialIndexStatus.EXTRACTED,
            MaterialIndexStatus.INDEXED,
        }:
            raise InvalidMaterialStateError()
        if force:
            material.processing_revision += 1
            self.session.commit()
        index_material_offline(self.session, self.storage, material)
        count = self._chunk_count(material.id)
        return count, count

    def _chunk_count(self, material_id: str) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(MaterialChunk)
                .where(MaterialChunk.material_id == material_id)
            )
            or 0
        )


def index_material_offline(
    session: Session,
    storage: FileStorage,
    material: LearningMaterial,
) -> LearningMaterial:
    """Extract and persist chunks without downloading an embedding model."""
    extractors = {
        "application/pdf": PdfDocumentExtractor(),
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ): DocxDocumentExtractor(),
        (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ): PptxDocumentExtractor(),
    }
    extractor = extractors[material.mime_type]
    if not material.storage_key:
        raise ValueError("Uploaded material has no storage key")
    material.indexing_status = MaterialIndexStatus.PROCESSING
    session.commit()
    try:
        with storage.open_read(material.storage_key) as source:
            extracted = extractor.extract(source)
        blocks = tuple(
            block.__class__(
                block.ordinal,
                normalise_text(block.text),
                block.heading,
                block.location_label,
                block.block_type,
            )
            for block in extracted.blocks
        )
        ensure_document_size(
            [block.text for block in blocks],
            settings.rag_max_extracted_chars,
        )
        drafts = HeadingAwareChunker(
            WhitespaceTokenCounter(),
            settings.rag_chunk_target_tokens,
            settings.rag_chunk_max_tokens,
            settings.rag_chunk_overlap_tokens,
        ).chunk(blocks)
        session.execute(delete(MaterialChunk).where(MaterialChunk.material_id == material.id))
        now = datetime.now(UTC)
        session.add_all(
            [
                MaterialChunk(
                    material_id=material.id,
                    chunk_index=draft.chunk_index,
                    chunk_text=draft.text,
                    heading=draft.heading,
                    location_label=draft.location_label,
                    token_count=draft.token_count,
                    chunk_hash=draft.chunk_hash,
                    embedding_model="local-lexical-v1",
                    embedding_version="v1",
                    embedding_dimension=0,
                    indexed_at=now,
                )
                for draft in drafts
            ]
        )
        material.indexing_status = MaterialIndexStatus.INDEXED
        material.extracted_at = now
        material.indexed_at = now
        session.commit()
    except Exception:
        session.rollback()
        stored = session.get(LearningMaterial, material.id)
        if stored is not None:
            stored.indexing_status = MaterialIndexStatus.FAILED
            stored.failure_stage = "extraction"
            stored.error_code = "local_indexing_failed"
            stored.extraction_error = "The material was saved but its text could not be indexed."
            session.commit()
        raise
    session.refresh(material)
    return material
