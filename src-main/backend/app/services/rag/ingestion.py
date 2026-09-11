"""Recoverable synchronous extraction, chunk persistence, and vector indexing."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.models import LearningMaterial, MaterialChunk, MaterialIndexStatus
from app.services.material_scanning import MalwareScanner, scan_for_extraction
from app.services.rag.chunking import HeadingAwareChunker, WhitespaceTokenCounter
from app.services.rag.contracts import (
    DocumentExtractor,
    EmbeddingProvider,
    VectorRecord,
    VectorStore,
)
from app.services.rag.errors import InvalidMaterialStateError
from app.services.rag.normalisation import ensure_document_size, normalise_text
from app.services.rag.processing_claims import LostMaterialClaim, MaterialProcessingClaims, utc_now
from app.services.rag.source_history import snapshot_source
from app.services.rag.storage import FileStorage


class MaterialProcessor:
    def __init__(
        self,
        session: Session,
        storage: FileStorage,
        extractors: dict[str, DocumentExtractor],
        embedding: EmbeddingProvider,
        vectors: VectorStore,
        *,
        now: Callable[[], datetime] = utc_now,
        configured_settings: Settings = settings,
        scanner: MalwareScanner | None = None,
    ) -> None:
        self.scanner = scanner
        self.claims = MaterialProcessingClaims(
            session, now=now, configured_settings=configured_settings
        )
        self.session, self.storage, self.extractors, self.embedding, self.vectors = (
            session,
            storage,
            extractors,
            embedding,
            vectors,
        )

    def process(
        self, material: LearningMaterial, force: bool = False, *, recover: bool = False
    ) -> tuple[int, int]:
        self.session.refresh(material)
        if material.retired_at is not None:
            raise InvalidMaterialStateError()
        if material.indexing_status == MaterialIndexStatus.INDEXED and not force:
            from app.services.material_scanning import require_clean_material

            require_clean_material(self.session, material, self.claims.config)
            self.session.expire(material, ["chunks"])
            return len(material.chunks), len(material.chunks)
        claim = self.claims.claim(material, backend="semantic", force=force, recover=recover)
        try:
            extractor = self.extractors[material.mime_type]
            if not material.storage_key:
                raise InvalidMaterialStateError()
            with scan_for_extraction(self.claims, claim, self.storage, self.scanner) as source:
                extracted = extractor.extract(source)
            normalised = [
                block.__class__(
                    block.ordinal,
                    normalise_text(block.text),
                    block.heading,
                    block.location_label,
                    block.block_type,
                )
                for block in extracted.blocks
            ]
            ensure_document_size(
                [block.text for block in normalised], self.claims.config.rag_max_extracted_chars
            )
            drafts = HeadingAwareChunker(
                WhitespaceTokenCounter(),
                self.claims.config.rag_chunk_target_tokens,
                self.claims.config.rag_chunk_max_tokens,
                self.claims.config.rag_chunk_overlap_tokens,
            ).chunk(tuple(normalised))
            embeddings = self.embedding.embed_documents([draft.text for draft in drafts])
            if len(embeddings) != len(drafts):
                raise ValueError("Embedding count does not match extracted passages")
            self.claims.guard_publication(claim)
            self.session.refresh(material)
            self.session.execute(
                delete(MaterialChunk).where(MaterialChunk.material_id == material.id)
            )
            chunks = [
                MaterialChunk(
                    material_id=material.id,
                    chunk_index=draft.chunk_index,
                    chunk_text=draft.text,
                    heading=draft.heading,
                    location_label=draft.location_label,
                    token_count=draft.token_count,
                    chunk_hash=draft.chunk_hash,
                )
                for draft in drafts
            ]
            self.session.add_all(chunks)
            material.indexing_status, material.extracted_at = (
                MaterialIndexStatus.EXTRACTED,
                datetime.now(UTC),
            )
            self.session.flush()
            self.vectors.delete_material(material.id)
            self.vectors.upsert(
                [
                    VectorRecord(
                        chunk.id,
                        vector,
                        chunk.chunk_text,
                        {
                            "course_id": material.course_id,
                            "module_id": material.module_id or "",
                            "material_id": material.id,
                            "chunk_index": chunk.chunk_index,
                            "source_label": self._source_label(material, chunk),
                            "chunk_hash": chunk.chunk_hash,
                            "embedding_model": self.embedding.model_id,
                        },
                    )
                    for chunk, vector in zip(chunks, embeddings, strict=True)
                ]
            )
            now = datetime.now(UTC)
            for chunk in chunks:
                (
                    chunk.embedding_model,
                    chunk.embedding_version,
                    chunk.embedding_dimension,
                    chunk.indexed_at,
                ) = self.embedding.model_id, "v1", self.embedding.dimension, now
            snapshot_source(
                self.session,
                material,
                chunks,
                blocks=normalised,
                extraction_version="heading-chunker-v1",
            )
            material.indexing_status, material.indexed_at = MaterialIndexStatus.INDEXED, now
            material.extraction_error = material.failure_stage = material.error_code = None
            self.claims.complete(claim)
            self.session.refresh(material)
            return len(chunks), len(chunks)
        except LostMaterialClaim:
            self.session.rollback()
            raise
        except Exception as error:
            self.claims.fail(claim, error)
            self.session.refresh(material)
            raise

    @staticmethod
    def _source_label(material: LearningMaterial, chunk: MaterialChunk) -> str:
        parts = [
            material.original_filename or material.source_url or "Material",
            chunk.location_label,
            chunk.heading,
        ]
        return " — ".join(part for part in parts if part)
