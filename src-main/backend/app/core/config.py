from decimal import Decimal
from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEVELOPMENT_PSEUDONYM_SECRET = "development-only-pseudonym-secret-change-before-production"
DEVELOPMENT_SESSION_SECRET = "development-only-session-secret-change-me"
BUILTIN_OFFLINE_WORKER_ADAPTER_FACTORY = "app.worker:build_offline_worker_adapters"


class Settings(BaseSettings):
    app_name: str = "QuantumLearn API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./quantumlearn.db"
    frontend_origin: str = "http://localhost:5173"
    cors_allowed_origins: str = ""
    api_docs_enabled: bool = False
    csrf_enabled: bool = True
    csrf_header_name: str = "X-CSRF-Token"
    csrf_cookie_name: str = "ql_csrf"
    rate_limit_enabled: bool = True
    llm_api_key: SecretStr | None = None
    llm_api_base_url: str = "https://api.openai.com/v1"
    llm_provider: str = "openai"
    llm_model: str = ""
    llm_input_cost_per_million: Decimal = Field(default=Decimal("0"), ge=0)
    llm_output_cost_per_million: Decimal = Field(default=Decimal("0"), ge=0)
    learning_event_pseudonym_secret: SecretStr | None = SecretStr(DEVELOPMENT_PSEUDONYM_SECRET)
    feedback_job_lease_seconds: int = Field(default=300, ge=30, le=3600)
    provider_timeout_seconds: int = Field(default=60, ge=1, le=60)
    max_infrastructure_attempts: int = Field(default=3, ge=1, le=3)
    research_export_row_limit: int = Field(default=100_000, ge=1, le=100_000)
    research_export_batch_size: int = Field(default=1_000, ge=1, le=10_000)
    max_request_body_bytes: int = Field(
        default=21 * 1024 * 1024,
        ge=1_024,
        le=25 * 1024 * 1024,
    )
    worker_stale_seconds: int = Field(default=120, ge=30, le=3_600)
    worker_poll_seconds: float = Field(default=1, gt=0, le=60)
    worker_heartbeat_seconds: float = Field(default=30, gt=0, le=300)
    worker_adapter_factory: str = ""
    research_enabled: bool = True
    production_adapters_ready: bool = False
    session_secret_key: SecretStr = SecretStr(DEVELOPMENT_SESSION_SECRET)
    session_ttl_minutes: int = Field(default=60, gt=0, le=1440)
    session_cookie_name: str = "quantumlearn_session"
    session_cookie_secure: bool = False

    rag_upload_dir: str = "./data/rag/uploads"

    rag_max_file_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    rag_max_extracted_chars: int = Field(default=2_000_000, gt=0)
    rag_chunk_target_tokens: int = Field(default=200, gt=0)
    rag_chunk_max_tokens: int = Field(default=240, gt=0)
    rag_chunk_overlap_tokens: int = Field(default=40, ge=0)
    rag_default_top_k: int = Field(default=5, gt=0)
    rag_max_top_k: int = Field(default=10, gt=0)
    rag_candidate_count: int = Field(default=20, gt=0)
    rag_min_relevance: float = Field(default=0.45, ge=0.0, le=1.0)
    rag_query_max_chars: int = Field(default=4_000, gt=0)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_configuration(self) -> "Settings":
        if self.rag_chunk_target_tokens > self.rag_chunk_max_tokens:
            raise ValueError("rag_chunk_target_tokens must not exceed rag_chunk_max_tokens")
        if self.rag_chunk_overlap_tokens >= self.rag_chunk_target_tokens:
            raise ValueError(
                "rag_chunk_overlap_tokens must be smaller than rag_chunk_target_tokens"
            )
        if self.rag_default_top_k > self.rag_max_top_k:
            raise ValueError("rag_default_top_k must not exceed rag_max_top_k")
        if self.rag_candidate_count < self.rag_max_top_k:
            raise ValueError("rag_candidate_count must be at least rag_max_top_k")
        if self.max_request_body_bytes <= self.rag_max_file_bytes:
            raise ValueError(
                "max_request_body_bytes must exceed rag_max_file_bytes "
                "to allow multipart upload overhead"
            )
        if self.worker_heartbeat_seconds >= self.worker_stale_seconds:
            raise ValueError("worker heartbeat interval must be shorter than its stale timeout")
        parsed_llm_url = urlsplit(self.llm_api_base_url)
        if parsed_llm_url.scheme != "https" or not parsed_llm_url.netloc:
            raise ValueError("LLM API base URL must be an HTTPS origin or path")
        configured_origins = {
            self.frontend_origin.rstrip("/"),
            *self.allowed_cors_origins,
        }
        for origin in configured_origins:
            parsed = urlsplit(origin)
            if (
                origin == "*"
                or parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Frontend and CORS origins must be explicit HTTP(S) origins")
        if self.app_env.casefold() in {"prod", "production"}:
            pseudonym_secret = (
                self.learning_event_pseudonym_secret.get_secret_value()
                if self.learning_event_pseudonym_secret is not None
                else ""
            )
            if (
                len(pseudonym_secret.encode("utf-8")) < 32
                or pseudonym_secret == DEVELOPMENT_PSEUDONYM_SECRET
            ):
                raise ValueError("production requires a unique learning-event pseudonym secret")
            session_secret = self.session_secret_key.get_secret_value()
            if (
                len(session_secret.encode("utf-8")) < 32
                or session_secret == DEVELOPMENT_SESSION_SECRET
                or session_secret == pseudonym_secret
            ):
                raise ValueError(
                    "production requires a distinct, unique session secret of at least 32 bytes"
                )
            if not self.session_cookie_secure:
                raise ValueError("production requires secure session cookies")
            if any(urlsplit(origin).scheme != "https" for origin in configured_origins):
                raise ValueError("production frontend and CORS origins must use HTTPS")
        return self

    @property
    def allowed_cors_origins(self) -> list[str]:
        configured = [
            value.strip().rstrip("/")
            for value in self.cors_allowed_origins.split(",")
            if value.strip()
        ]
        return configured or [self.frontend_origin.rstrip("/")]

    @property
    def production(self) -> bool:
        return self.app_env.casefold() in {"prod", "production"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
