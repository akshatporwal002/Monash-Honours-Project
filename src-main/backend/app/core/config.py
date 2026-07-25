from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "QuantumLearn API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./quantumlearn.db"
    frontend_origin: str = "http://localhost:5173"
    llm_api_key: str | None = None
    session_secret_key: SecretStr = Field(min_length=32)
    session_ttl_minutes: int = Field(default=60, gt=0, le=1440)
    session_cookie_name: str = "quantumlearn_session"
    session_cookie_secure: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
