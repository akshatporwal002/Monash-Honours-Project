"""Approved, scanned, course-scoped local vector retrieval over frozen passages."""

from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import LearningMaterial, MaterialIndexStatus, RetrievalAudit
from app.models.source_history import SourcePassage, SourceRevision
from app.services.material_scanning import revision_scan_is_clean
from app.services.rag.contracts import RetrievalHit, RetrievalQuery, RetrievalResult
from app.services.rag.errors import RagError
from app.services.rag.local_retrieval import _terms
from app.services.rag.local_vectors import LocalTextEmbedding, SqliteVectorCache, text_fragments
from app.services.rag.normalisation import normalise_text
from app.services.rag.retrieval import NO_RESULT_MESSAGE
from app.services.rag.source_history import latest_approval, passage_label


class LocalVectorRetrievalService:
    def __init__(self, session: Session, *, use_vectors: bool = True):
        self.session = session
        self.use_vectors = use_vectors
        self.embedding = LocalTextEmbedding()
        self.model_id = self.embedding.model_id if use_vectors else "local-approved-lexical-v1"
        self.cache = SqliteVectorCache(
            Path(settings.rag_upload_dir) / ".vector-cache.sqlite3", self.embedding
        )

    def _sources(self, query: RetrievalQuery):
        statement = (
            select(SourcePassage, SourceRevision, LearningMaterial)
            .join(SourceRevision, SourcePassage.revision_id == SourceRevision.id)
            .join(LearningMaterial, SourceRevision.material_id == LearningMaterial.id)
            .where(
                SourcePassage.course_id == query.course_id,
                SourceRevision.course_id == query.course_id,
                LearningMaterial.course_id == query.course_id,
                LearningMaterial.retired_at.is_(None),
            )
        )
        if query.module_id is not None:
            statement = statement.where(SourceRevision.module_id == query.module_id)
        if query.allowed_chunk_ids:
            # Exact frozen passages survive replacement/reindex; aliases never expand.
            statement = statement.where(SourcePassage.id.in_(query.allowed_chunk_ids))
        else:
            statement = statement.where(
                LearningMaterial.current_source_revision_id == SourceRevision.id,
                LearningMaterial.indexing_status == MaterialIndexStatus.INDEXED,
                LearningMaterial.content_hash == SourceRevision.content_hash,
            )
        eligible = []
        checked = {}
        for passage, revision, material in self.session.execute(statement):
            if revision.id not in checked:
                approval = latest_approval(self.session, revision.id)
                checked[revision.id] = (
                    approval is not None
                    and approval.state == "APPROVED"
                    and revision_scan_is_clean(self.session, revision)
                )
            if checked[revision.id]:
                eligible.append((passage, revision, material))
        return eligible

    def _scores(self, sources, text):
        if not self.use_vectors:
            terms = _terms(text)
            return [
                0.5 + overlap / (2 * len(terms)) if overlap else 0.0
                for passage, _, _ in sources
                for overlap in [len(terms & _terms(passage.chunk_text))]
            ]
        try:
            vectors = self.cache.vectors(sources)
        except (sqlite3.Error, OSError) as error:
            raise RagError(
                "vector_index_unavailable",
                "The local vector index is unavailable; rebuild its disposable cache.",
                503,
            ) from error
        query_vectors = [self.embedding.embed_query(fragment) for fragment in text_fragments(text)]
        nonzero = [
            [(index, value) for index, value in enumerate(vector) if value]
            for vector in query_vectors
        ]
        scores = []
        for passage_vectors in vectors:
            # True cosine of unit vectors; no boost or threshold substitution.
            score = max(
                0.0,
                min(
                    1.0,
                    max(
                        (
                            sum(value * vector[index] for index, value in query_terms)
                            for vector in passage_vectors
                            for query_terms in nonzero
                        ),
                        default=0.0,
                    ),
                ),
            )
            scores.append(score)
        return scores

    def search(self, query: RetrievalQuery) -> RetrievalResult:
        started = time.perf_counter()
        text = normalise_text(query.text)
        if not text or len(text) > settings.rag_query_max_chars:
            raise ValueError("query must be non-empty and within the configured length")
        if not 1 <= query.top_k <= settings.rag_max_top_k or not 0 <= query.min_relevance <= 1:
            raise ValueError("retrieval limits must be within the configured range")
        sources = self._sources(query)
        scores = self._scores(sources, text)
        ranked = []
        for (passage, revision, material), score in zip(sources, scores, strict=True):
            if score > 0 and score >= query.min_relevance:
                ranked.append(
                    RetrievalHit(
                        passage.id,
                        material.id,
                        query.course_id,
                        passage.chunk_text,
                        passage_label(passage, revision),
                        score,
                        passage.chunk_index,
                    )
                )
        ranked.sort(key=lambda hit: (-hit.relevance_score, hit.chunk_index, hit.chunk_id))
        hits = tuple(ranked[: query.top_k])
        latency = int((time.perf_counter() - started) * 1000)
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
                embedding_model=self.model_id,
            )
        )
        self.session.commit()
        return RetrievalResult(
            str(uuid4()),
            bool(hits),
            hits,
            None if hits else NO_RESULT_MESSAGE,
            latency,
            self.model_id,
        )
