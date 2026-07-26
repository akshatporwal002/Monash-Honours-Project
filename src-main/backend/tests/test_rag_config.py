import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_rag_settings_have_safe_defaults() -> None:
    settings = Settings()

    assert settings.rag_max_file_bytes == 20 * 1024 * 1024
    assert settings.max_request_body_bytes == 21 * 1024 * 1024
    assert settings.max_request_body_bytes > settings.rag_max_file_bytes
    assert settings.rag_chunk_target_tokens <= settings.rag_chunk_max_tokens
    assert 0 <= settings.rag_min_relevance <= 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"rag_chunk_target_tokens": 241, "rag_chunk_max_tokens": 240},
        {"rag_chunk_overlap_tokens": 200},
        {"rag_default_top_k": 11, "rag_max_top_k": 10},
        {"rag_candidate_count": 9, "rag_max_top_k": 10},
        {
            "max_request_body_bytes": 20 * 1024 * 1024,
            "rag_max_file_bytes": 20 * 1024 * 1024,
        },
    ],
)
def test_rag_settings_reject_inconsistent_limits(overrides: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        Settings(**overrides)
