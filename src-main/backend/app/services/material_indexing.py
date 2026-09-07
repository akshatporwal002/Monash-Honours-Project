"""Offline material indexing used by the runnable LMS authoring flow."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.models import LearningMaterial, MaterialChunk, MaterialIndexStatus
from app.services.rag.chunking import HeadingAwareChunker, WhitespaceTokenCounter
from app.services.rag.errors import (
    InvalidMaterialStateError,
)
from app.services.rag.extraction.docx import DocxDocumentExtractor
from app.services.rag.extraction.pdf import PdfDocumentExtractor
from app.services.rag.extraction.pptx import PptxDocumentExtractor
from app.services.rag.normalisation import ensure_document_size, normalise_text
from app.services.rag.processing_claims import LostMaterialClaim, MaterialProcessingClaims, utc_now
from app.services.rag.source_history import snapshot_source
from app.services.rag.storage import FileStorage


class OfflineMaterialProcessor:
    """Compatibility adapter for the explicit material processing endpoint."""

    def __init__(
        self,
        session: Session,
        storage: FileStorage,
        *,
        now: Callable[[], datetime] = utc_now,
        configured_settings: Settings = settings,
    ) -> None:
        self.session = session
        self.storage = storage
        self.now = now
        self.config = configured_settings

    def process(
        self, material: LearningMaterial, force: bool = False, *, recover: bool = False
    ) -> tuple[int, int]:
        self.session.refresh(material)
        if material.retired_at is not None:
            raise InvalidMaterialStateError()
        if material.indexing_status is MaterialIndexStatus.INDEXED and not force:
            count = self._chunk_count(material.id)
            return count, count
        index_material_offline(
            self.session,
            self.storage,
            material,
            force=force,
            recover=recover,
            now=self.now,
            configured_settings=self.config,
        )
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
    *,
    force: bool = False,
    recover: bool = False,
    now: Callable[[], datetime] = utc_now,
    configured_settings: Settings = settings,
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
    claims = MaterialProcessingClaims(session, now=now, configured_settings=configured_settings)
    claim = claims.claim(material, backend="offline", force=force, recover=recover)
    try:
        extractor = extractors[material.mime_type]
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
            configured_settings.rag_max_extracted_chars,
        )
        drafts = HeadingAwareChunker(
            WhitespaceTokenCounter(),
            configured_settings.rag_chunk_target_tokens,
            configured_settings.rag_chunk_max_tokens,
            configured_settings.rag_chunk_overlap_tokens,
        ).chunk(blocks)
        claims.guard_publication(claim)
        session.refresh(material)
        session.execute(delete(MaterialChunk).where(MaterialChunk.material_id == material.id))
        finished_at = claims.now()
        chunks = [
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
                indexed_at=finished_at,
            )
            for draft in drafts
        ]
        session.add_all(chunks)
        snapshot_source(
            session, material, chunks, blocks=blocks, extraction_version="heading-chunker-v1"
        )
        material.extraction_error = material.failure_stage = material.error_code = None
        material.indexing_status = MaterialIndexStatus.INDEXED
        material.extracted_at = finished_at
        material.indexed_at = finished_at
        claims.complete(claim)
    except LostMaterialClaim:
        session.rollback()
        raise
    except Exception as error:
        claims.fail(claim, error)
        session.refresh(material)
        raise
    session.refresh(material)
    return material
