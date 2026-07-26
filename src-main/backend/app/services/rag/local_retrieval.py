"""Offline, course-scoped retrieval for the deterministic MVP adapters."""

from __future__ import annotations

import hashlib
import re
import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    LearningMaterial,
    MaterialChunk,
    MaterialIndexStatus,
    RetrievalAudit,
)
from app.services.rag.contracts import RetrievalHit, RetrievalQuery, RetrievalResult
from app.services.rag.normalisation import normalise_text
from app.services.rag.retrieval import NO_RESULT_MESSAGE

_MODEL_ID = "local-lexical-v1"
_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "apply",
        "describe",
        "explain",
        "for",
        "how",
        "in",
        "of",
        "the",
        "to",
        "what",
    }
)


class LocalCourseRetrievalService:
    """Rank authorised SQLite chunks without a model download or vector process.

    The same adapter serves task generation, feedback grounding, and the retrieval
    API so local and hosted deployments share one predictable MVP path.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def search(self, query: RetrievalQuery) -> RetrievalResult:
        started = time.perf_counter()
        text = normalise_text(query.text)
        if not text or len(text) > settings.rag_query_max_chars:
            raise ValueError("query must be non-empty and within the configured length")

        statement = (
            select(MaterialChunk, LearningMaterial)
            .join(
                LearningMaterial,
                MaterialChunk.material_id == LearningMaterial.id,
            )
            .where(
                LearningMaterial.course_id == query.course_id,
                LearningMaterial.indexing_status == MaterialIndexStatus.INDEXED,
            )
        )
        if query.module_id is not None:
            statement = statement.where(LearningMaterial.module_id == query.module_id)
        if query.allowed_chunk_ids:
            statement = statement.where(MaterialChunk.id.in_(query.allowed_chunk_ids))

        query_terms = _terms(text)
        ranked: list[tuple[float, MaterialChunk, LearningMaterial]] = []
        for chunk, material in self.session.execute(statement).all():
            chunk_terms = _terms(chunk.chunk_text)
            overlap = len(query_terms & chunk_terms)
            if overlap == 0:
                continue
            coverage = overlap / max(1, len(query_terms))
            relevance = min(1.0, 0.5 + (coverage / 2))
            if relevance >= query.min_relevance:
                ranked.append((relevance, chunk, material))

        ranked.sort(key=lambda item: (-item[0], item[1].chunk_index, item[1].id))
        hits = tuple(
            RetrievalHit(
                chunk_id=chunk.id,
                material_id=material.id,
                course_id=material.course_id,
                chunk_text=chunk.chunk_text,
                source_label=_source_label(material, chunk),
                relevance_score=relevance,
                chunk_index=chunk.chunk_index,
            )
            for relevance, chunk, material in ranked[: query.top_k]
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        result = RetrievalResult(
            request_id=str(uuid.uuid4()),
            found=bool(hits),
            hits=hits,
            message=None if hits else NO_RESULT_MESSAGE,
            latency_ms=latency_ms,
            embedding_model=_MODEL_ID,
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
                latency_ms=latency_ms,
                embedding_model=_MODEL_ID,
            )
        )
        self.session.commit()
        return result


def _terms(text: str) -> set[str]:
    terms = set(_WORD_PATTERN.findall(text.casefold()))
    meaningful = terms - _STOP_WORDS
    return meaningful or terms


def _source_label(material: LearningMaterial, chunk: MaterialChunk) -> str:
    source = material.original_filename or material.source_url or "Material"
    return " - ".join(part for part in (source, chunk.location_label, chunk.heading) if part)
