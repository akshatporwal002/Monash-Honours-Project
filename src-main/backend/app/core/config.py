from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "QuantumLearn API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./quantumlearn.db"
    frontend_origin: str = "http://localhost:5173"
    llm_api_key: str | None = None

    rag_data_dir: str = "./data/rag"
    rag_upload_dir: str = "./data/rag/uploads"
    rag_chroma_dir: str = "./data/rag/chroma"
    rag_model_cache_dir: str = "./data/rag/models"
    rag_collection_name: str = "quantumlearn_material_chunks_v1"

    rag_max_file_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    rag_max_extracted_chars: int = Field(default=2_000_000, gt=0)
    rag_chunk_target_tokens: int = Field(default=200, gt=0)
    rag_chunk_max_tokens: int = Field(default=240, gt=0)
    rag_chunk_overlap_tokens: int = Field(default=40, ge=0)
    rag_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    rag_embedding_batch_size: int = Field(default=32, gt=0)
    rag_default_top_k: int = Field(default=5, gt=0)
    rag_max_top_k: int = Field(default=10, gt=0)
    rag_candidate_count: int = Field(default=20, gt=0)
    rag_min_relevance: float = Field(default=0.45, ge=0.0, le=1.0)
    rag_query_max_chars: int = Field(default=4_000, gt=0)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_rag_limits(self) -> "Settings":
        if self.rag_chunk_target_tokens > self.rag_chunk_max_tokens:
            raise ValueError("rag_chunk_target_tokens must not exceed rag_chunk_max_tokens")
        if self.rag_chunk_overlap_tokens >= self.rag_chunk_target_tokens:
            raise ValueError("rag_chunk_overlap_tokens must be smaller than rag_chunk_target_tokens")
        if self.rag_default_top_k > self.rag_max_top_k:
            raise ValueError("rag_default_top_k must not exceed rag_max_top_k")
        if self.rag_candidate_count < self.rag_max_top_k:
            raise ValueError("rag_candidate_count must be at least rag_max_top_k")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
