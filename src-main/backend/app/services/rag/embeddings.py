"""Lazy local Sentence Transformers embedding provider."""

from __future__ import annotations

from collections.abc import Sequence

from app.core.config import settings
from app.services.rag.errors import EmbeddingProviderUnavailableError


class SentenceTransformerEmbeddingProvider:
    def __init__(self) -> None:
        self._model = None

    @property
    def model_id(self) -> str:
        return settings.rag_embedding_model

    @property
    def dimension(self) -> int:
        return self._get_model().get_sentence_embedding_dimension()

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode("encode_document", texts)

    def embed_query(self, text: str) -> list[float]:
        if not text.strip() or len(text) > settings.rag_query_max_chars:
            raise ValueError("query must be non-empty and within the configured length")
        return self._encode("encode_query", [text])[0]

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(
                    self.model_id,
                    cache_folder=settings.rag_model_cache_dir,
                    device="cpu",
                    trust_remote_code=False,
                )
            except Exception as error:
                raise EmbeddingProviderUnavailableError() from error
        return self._model

    def _encode(self, method_name: str, texts: Sequence[str]) -> list[list[float]]:
        model = self._get_model()
        values = getattr(model, method_name)(
            list(texts), batch_size=settings.rag_embedding_batch_size, normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False,
        )
        return [list(map(float, value)) for value in values]
