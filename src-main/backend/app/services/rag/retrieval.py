"""Course-isolated semantic retrieval behind generic embedding/index contracts."""

from __future__ import annotations

import hashlib
import time
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import LearningMaterial, MaterialChunk, MaterialIndexStatus, RetrievalAudit
from app.services.rag.contracts import (
    EmbeddingProvider,
    RetrievalHit,
    RetrievalQuery,
    RetrievalResult,
    VectorQuery,
    VectorStore,
)
from app.services.rag.normalisation import normalise_text

NO_RESULT_MESSAGE = "No relevant passage was found in the authorised course materials."


class RetrievalService:
    def __init__(
        self, session: Session, embedding: EmbeddingProvider, vectors: VectorStore
    ) -> None:
        self.session, self.embedding, self.vectors = session, embedding, vectors

    def search(self, query: RetrievalQuery) -> RetrievalResult:
        started = time.perf_counter()
        text = normalise_text(query.text)
        if not text or len(text) > settings.rag_query_max_chars:
            raise ValueError("query must be non-empty and within the configured length")
        vector_matches = self.vectors.query(
            VectorQuery(
                query.course_id,
                self.embedding.embed_query(text),
                settings.rag_candidate_count,
                query.module_id,
                query.allowed_chunk_ids,
            )
        )
        hits: list[RetrievalHit] = []
        seen_hashes: set[str] = set()
        for match in vector_matches:
            chunk = self.session.get(MaterialChunk, match.chunk_id)
            if not chunk or chunk.chunk_hash in seen_hashes:
                continue
            material = self.session.get(LearningMaterial, chunk.material_id)
            if (
                not material
                or material.course_id != query.course_id
                or material.indexing_status != MaterialIndexStatus.INDEXED
            ):
                continue
            if query.module_id and material.module_id != query.module_id:
                continue
            if query.allowed_chunk_ids and chunk.id not in query.allowed_chunk_ids:
                continue
            score = max(0.0, min(1.0, 1.0 - match.distance))
            if score < query.min_relevance:
                continue
            seen_hashes.add(chunk.chunk_hash)
            label = " — ".join(
                part
                for part in [
                    material.original_filename or material.source_url or "Material",
                    chunk.location_label,
                    chunk.heading,
                ]
                if part
            )
            hits.append(
                RetrievalHit(
                    chunk.id,
                    material.id,
                    material.course_id,
                    chunk.chunk_text,
                    label,
                    score,
                    chunk.chunk_index,
                )
            )
        hits.sort(key=lambda hit: (-hit.relevance_score, hit.chunk_id))
        hits = hits[: query.top_k]
        latency = int((time.perf_counter() - started) * 1000)
        result = RetrievalResult(
            str(uuid.uuid4()),
            bool(hits),
            tuple(hits),
            None if hits else NO_RESULT_MESSAGE,
            latency,
            self.embedding.model_id,
        )
        self.session.add(
            RetrievalAudit(
                course_id=query.course_id,
                module_id=query.module_id,
                task_id=query.task_id,
                purpose=query.purpose.value,
                query_hash=hashlib.sha256(text.encode()).hexdigest(),
                top_k=query.top_k,
                minimum_relevance=query.min_relevance,
                result_chunk_ids=[hit.chunk_id for hit in hits],
                result_scores=[hit.relevance_score for hit in hits],
                hit_count=len(hits),
                latency_ms=latency,
                embedding_model=self.embedding.model_id,
            )
        )
        self.session.commit()
        return result
