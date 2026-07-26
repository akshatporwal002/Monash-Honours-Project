from __future__ import annotations

import asyncio
from decimal import Decimal

import httpx
import pytest
from sqlalchemy.orm import Session

from app.models.lms import SystemSetting
from app.services.feedback.contracts import StructuredLlmRequest
from app.services.llm import (
    ResponsesStructuredLlmClient,
    StructuredModelError,
    runtime_model_selection,
)


def test_responses_client_returns_validated_json_usage_and_cost() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/responses"
        assert request.headers["authorization"] == "Bearer test-key"
        payload = __import__("json").loads(request.content)
        assert payload["store"] is False
        assert payload["text"]["format"]["type"] == "json_schema"
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": '{"answer":"ready"}'}],
                    }
                ],
                "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
            },
        )

    client = ResponsesStructuredLlmClient(
        api_key="test-key",
        model="test-model",
        base_url="https://models.example/v1",
        input_cost_per_million=Decimal("2"),
        output_cost_per_million=Decimal("10"),
        transport=httpx.MockTransport(handler),
    )
    response = asyncio.run(
        client.generate_structured(
            StructuredLlmRequest(
                system_prompt="Return JSON.",
                user_prompt="Ready?",
                response_schema={
                    "type": "object",
                    "properties": {"answer": {"type": "string"}},
                    "required": ["answer"],
                    "additionalProperties": False,
                },
                schema_name="answer",
                prompt_version="test-v1",
            )
        )
    )

    assert response.output == {"answer": "ready"}
    assert response.token_usage.total_tokens == 120
    assert response.estimated_cost == Decimal("0.0004")
    assert response.usage_complete is True


def test_responses_client_sanitizes_provider_failures() -> None:
    client = ResponsesStructuredLlmClient(
        api_key="test-key",
        model="test-model",
        transport=httpx.MockTransport(lambda _: httpx.Response(503, text="secret provider error")),
    )

    with pytest.raises(StructuredModelError, match="configured model"):
        asyncio.run(
            client.generate_structured(
                StructuredLlmRequest(
                    system_prompt="Return JSON.",
                    user_prompt="Ready?",
                    response_schema={"type": "object"},
                    schema_name="answer",
                    prompt_version="test-v1",
                )
            )
        )


def test_runtime_model_selection_uses_administrator_managed_values(
    db_session: Session,
) -> None:
    db_session.add_all(
        [
            SystemSetting(
                key="llm_provider",
                value="local-deterministic",
                description="Runtime provider",
            ),
            SystemSetting(
                key="llm_model",
                value="quantumlearn-local-v2",
                description="Runtime model",
            ),
        ]
    )
    db_session.commit()

    selected = runtime_model_selection(db_session)

    assert selected.provider == "local-deterministic"
    assert selected.model == "quantumlearn-local-v2"
    assert selected.local is True
