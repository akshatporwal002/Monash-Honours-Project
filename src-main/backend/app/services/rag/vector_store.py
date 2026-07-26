"""Persistent Chroma adapter; SQLite remains the authoritative source."""

from __future__ import annotations

from collections.abc import Sequence

from app.core.config import settings
from app.services.rag.contracts import VectorMatch, VectorQuery, VectorRecord
from app.services.rag.errors import IndexConfigurationError, VectorStoreUnavailableError


class ChromaVectorStore:
    def __init__(self, model_id: str, dimension: int) -> None:
        try:
            import chromadb

            client = chromadb.PersistentClient(path=settings.rag_chroma_dir)
            metadata = {"model_id": model_id, "dimension": dimension, "hnsw:space": "cosine"}
            self.collection = client.get_or_create_collection(
                settings.rag_collection_name, metadata=metadata, embedding_function=None
            )
            existing = self.collection.metadata or {}
            if existing.get("model_id") != model_id or existing.get("dimension") != dimension:
                raise IndexConfigurationError()
        except IndexConfigurationError:
            raise
        except Exception as error:
            raise VectorStoreUnavailableError() from error

    def upsert(self, records: Sequence[VectorRecord]) -> None:
        if not records:
            return
        self.collection.upsert(
            ids=[record.chunk_id for record in records],
            embeddings=[record.embedding for record in records],
            documents=[record.document for record in records],
            metadatas=[record.metadata for record in records],
        )

    def query(self, request: VectorQuery) -> list[VectorMatch]:
        where: dict[str, object] = {"course_id": request.course_id}
        if request.module_id is not None:
            where = {"$and": [{"course_id": request.course_id}, {"module_id": request.module_id}]}
        result = self.collection.query(
            query_embeddings=[request.embedding],
            n_results=request.candidate_count,
            where=where,
            include=["distances", "metadatas"],
        )
        ids, distances, metadata = result["ids"][0], result["distances"][0], result["metadatas"][0]
        allowed = set(request.allowed_chunk_ids)
        return [
            VectorMatch(chunk_id, float(distance), item)
            for chunk_id, distance, item in zip(ids, distances, metadata, strict=True)
            if not allowed or chunk_id in allowed
        ]

    def delete_material(self, material_id: str) -> None:
        self.collection.delete(where={"material_id": material_id})

    def contains_material(self, material_id: str) -> bool:
        return bool(self.collection.get(where={"material_id": material_id}, limit=1)["ids"])
