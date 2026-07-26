from pathlib import Path

from app.core.config import settings
from app.services.rag.contracts import VectorQuery, VectorRecord
from app.services.rag.vector_store import ChromaVectorStore


def test_chroma_vectors_survive_restart_and_keep_course_filtering(tmp_path: Path) -> None:
    original = settings.rag_chroma_dir
    settings.rag_chroma_dir = str(tmp_path / "chroma")
    try:
        store = ChromaVectorStore("test-model", 2)
        store.upsert([
            VectorRecord("chunk-1", [1.0, 0.0], "text", {"course_id": "course-1", "module_id": "", "material_id": "m1", "chunk_index": 0, "source_label": "source", "chunk_hash": "hash", "embedding_model": "test-model"}),
            VectorRecord("chunk-2", [1.0, 0.0], "text", {"course_id": "course-2", "module_id": "", "material_id": "m2", "chunk_index": 0, "source_label": "source", "chunk_hash": "hash2", "embedding_model": "test-model"}),
        ])
        restarted = ChromaVectorStore("test-model", 2)
        matches = restarted.query(VectorQuery("course-1", [1.0, 0.0], 5))
        assert [match.chunk_id for match in matches] == ["chunk-1"]
    finally:
        settings.rag_chroma_dir = original
