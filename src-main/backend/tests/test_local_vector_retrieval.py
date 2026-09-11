"""Real offline vectors; synthetic source approvals do not certify content quality."""

import math
import sqlite3
from contextlib import closing
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from test_task16_retrieval import source

from app.core.config import settings
from app.models import RetrievalAudit
from app.models.source_history import SourceApproval, SourcePassage
from app.services.rag.contracts import RetrievalPurpose, RetrievalQuery
from app.services.rag.errors import RagError
from app.services.rag.local_vectors import LocalTextEmbedding
from app.services.rag.runtime import build_retrieval_service
from app.services.rag.vector_retrieval import LocalVectorRetrievalService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


@pytest.fixture
def vectors(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "rag_upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "rag_retrieval_backend", "local_vector")
    return build_retrieval_service(db_session)


def current_source(session, name, text, **kwargs):
    material, revision, passage = source(session, name, text, **kwargs)
    material.current_source_revision_id = revision.id
    session.commit()
    return material, revision, passage


def query(text="alpha beta", **kwargs):
    return RetrievalQuery("course", text, RetrievalPurpose.SEARCH, **kwargs)


def test_cosine_rank_threshold_and_persistent_cache_rebuild(db_session, vectors, monkeypatch):
    _, _, exact = current_source(db_session, "exact", "alpha beta")
    _, _, partial = current_source(db_session, "partial", "alpha")
    current_source(db_session, "irrelevant", "photosynthesis sunlight")
    result = vectors.search(query())
    assert [hit.chunk_id for hit in result.hits] == [exact.id, partial.id]
    assert result.hits[0].relevance_score == pytest.approx(1)
    assert result.hits[1].relevance_score == pytest.approx(1 / math.sqrt(2))
    assert [hit.chunk_id for hit in vectors.search(query(min_relevance=0.8)).hits] == [exact.id]
    audit = db_session.scalars(select(RetrievalAudit).order_by(RetrievalAudit.created_at)).all()[-1]
    assert audit.embedding_model == LocalTextEmbedding.model_id
    assert audit.minimum_relevance == 0.8

    reopened = build_retrieval_service(db_session)
    with monkeypatch.context() as patch:

        def no_reembedding(_texts):
            raise AssertionError("Persisted unchanged vectors should be reused")

        patch.setattr(reopened.embedding, "embed_documents", no_reembedding)
        assert reopened.search(query()).hits == result.hits
    with closing(sqlite3.connect(vectors.cache.path)) as cache, cache:
        cache.execute("UPDATE vectors SET payload='broken'")
    assert reopened.search(query()).hits == result.hits
    # A disposable cache can be removed after stopping its owned users.
    vectors.cache.path.unlink()
    assert build_retrieval_service(db_session).search(query()).hits == result.hits


def test_authoritative_scope_approval_and_scan_gates_filter_before_ranking(db_session, vectors):
    _, _, good = current_source(db_session, "good", "alpha beta")
    current_source(db_session, "foreign", "alpha beta", course="other")
    current_source(db_session, "unapproved", "alpha beta", approved=False)
    retired, _, _ = current_source(db_session, "retired", "alpha beta")
    retired.retired_at = datetime.now(UTC)
    db_session.commit()
    assert [hit.chunk_id for hit in vectors.search(query(top_k=1)).hits] == [good.id]
    assert not vectors.search(query(module_id="foreign-module")).hits
    assert not vectors.search(query(allowed_chunk_ids=("foreign-passage", "good"))).hits


def test_sentence_vectors_preserve_whole_passage_and_real_cosine(db_session, vectors):
    text = "alpha beta. Photosynthesis converts sunlight into chemical energy."
    _, _, passage = current_source(db_session, "mixed", text)
    result = vectors.search(query("Question framing. alpha beta", min_relevance=0.99))
    assert result.hits[0].chunk_id == passage.id
    assert result.hits[0].chunk_text == text
    assert result.hits[0].relevance_score == pytest.approx(1.0)


@pytest.mark.parametrize("backend", ["local_vector", "lexical"])
@pytest.mark.parametrize("change", ["revoked", "policy", "retired", "rejected"])
def test_cached_vectors_never_override_later_controls(
    db_session, vectors, monkeypatch, change, backend
):
    monkeypatch.setattr(settings, "rag_retrieval_backend", backend)
    vectors = build_retrieval_service(db_session)
    material, revision, passage = current_source(db_session, "cached", "alpha beta")
    assert vectors.search(query()).found
    if change == "revoked":
        db_session.add(
            SourceApproval(
                revision_id=revision.id,
                sequence=2,
                state="REVOKED",
                actor_id="reviewer",
                reason="Synthetic revocation",
            )
        )
    elif change == "policy":
        monkeypatch.setattr(settings, "material_scan_policy_version", "new-policy")
    elif change == "retired":
        material.retired_at = datetime.now(UTC)
    else:
        from app.models.intake_history import MaterialScan

        db_session.add(
            MaterialScan(
                material_id=material.id,
                content_hash=material.content_hash,
                processing_revision=2,
                claim_token="synthetic-rescan",
                policy_version="synthetic-policy-v1",
                scanner="synthetic",
                scanner_version="v1",
                status="REJECTED",
                code="synthetic_rejected",
            )
        )
    db_session.commit()
    assert not vectors.search(query()).found
    assert not vectors.search(query(allowed_chunk_ids=(passage.id,))).found
    assert db_session.get(SourcePassage, passage.id).chunk_text == "alpha beta"


def test_frozen_passage_survives_replacement_without_lending_scan_to_new_bytes(db_session, vectors):
    material, _, passage = current_source(db_session, "original", "alpha beta")
    before = vectors.search(query()).hits
    material.content_hash = "replacement-bytes"
    material.current_source_revision_id = None
    material.scan_status = "QUARANTINED"
    material.current_scan_id = None
    db_session.commit()
    assert not vectors.search(query()).found
    assert vectors.search(query(allowed_chunk_ids=(passage.id,))).hits == before


def test_corrupt_cache_fails_safely_and_lexical_is_explicit(db_session, vectors, monkeypatch):
    current_source(db_session, "good", "alpha beta")
    assert vectors.search(query()).found
    vectors.cache.path.write_bytes(b"not a sqlite database")
    with pytest.raises(RagError, match="vector index is unavailable") as error:
        vectors.search(query())
    assert error.value.http_status == 503
    monkeypatch.setattr(settings, "rag_retrieval_backend", "lexical")
    fallback = build_retrieval_service(db_session).search(query())
    assert fallback.found
    assert fallback.embedding_model == "local-approved-lexical-v1"
    monkeypatch.setattr(settings, "rag_retrieval_backend", "local_vector")
    assert isinstance(build_retrieval_service(db_session), LocalVectorRetrievalService)
