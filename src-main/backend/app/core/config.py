from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    rate_limit_enabled: bool = True
    llm_api_key: SecretStr | None = None
    learning_event_pseudonym_secret: SecretStr | None = None
    feedback_job_lease_seconds: int = Field(default=300, ge=30, le=3600)
    provider_timeout_seconds: int = Field(default=60, ge=1, le=60)
    max_infrastructure_attempts: int = Field(default=3, ge=1, le=3)
    research_export_row_limit: int = Field(default=100_000, ge=1, le=100_000)
    research_export_batch_size: int = Field(default=1_000, ge=1, le=10_000)
    max_request_body_bytes: int = Field(
        default=262_144,
        ge=1_024,
        le=1_048_576,
    )
    worker_stale_seconds: int = Field(default=120, ge=30, le=3_600)
    worker_poll_seconds: float = Field(default=1, gt=0, le=60)
    worker_heartbeat_seconds: float = Field(default=30, gt=0, le=300)
    worker_adapter_factory: str = ""
    research_enabled: bool = False
    production_adapters_ready: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def require_production_pseudonym_secret(self) -> "Settings":
        if self.worker_heartbeat_seconds >= self.worker_stale_seconds:
            raise ValueError("worker heartbeat interval must be shorter than its stale timeout")
        for origin in self.allowed_cors_origins:
            parsed = urlsplit(origin)
            if (
                origin == "*"
                or parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("CORS origins must be explicit HTTP(S) origins")
        if self.app_env.casefold() in {"prod", "production"}:
            secret = (
                self.learning_event_pseudonym_secret.get_secret_value()
                if self.learning_event_pseudonym_secret is not None
                else ""
            )
            if len(secret.encode("utf-8")) < 32:
                raise ValueError(
                    "production requires a learning-event pseudonym secret of at least 32 bytes"
                )
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
