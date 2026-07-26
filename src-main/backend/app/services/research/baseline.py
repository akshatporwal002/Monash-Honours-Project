from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.schemas.feedback import FeedbackAgentOutput, FeedbackContext, GeneratedFeedback
from app.services.feedback.contracts import StructuredLlmClient, StructuredLlmRequest
from app.services.feedback.errors import FeedbackClientError

BASELINE_PROMPT_VERSION = "baseline-v1"
BASELINE_SYSTEM_PROMPT = """You provide concise educational feedback for an introductory quantum
computing task. Use only the supplied task and student answer. Do not claim to have retrieved
sources, run a simulation, or used any other context. Return one object matching the response
schema. Source and simulation references must be empty."""


class BaselineOutputError(Exception):
    """The baseline provider returned unusable or policy-violating output."""


class BaselineModelMismatchError(BaselineOutputError):
    """The baseline did not use the agentic condition's provider and base model."""


class BaselinePromptBuilder:
    def build(self, context: FeedbackContext) -> StructuredLlmRequest:
        task = context.task
        submission = context.submission
        task_payload: dict[str, Any] = {
            "task_type": task.task_type,
            "prompt": task.prompt,
            "difficulty": task.difficulty,
            "learning_outcome": task.learning_outcome_id,
        }
        if task.expected_answer is not None:
            task_payload["expected_answer"] = task.expected_answer
        if task.marking_criteria is not None:
            task_payload["marking_criteria"] = task.marking_criteria
        payload = {
            "task": task_payload,
            "submission": {
                "submitted_answer": submission.submitted_answer,
            },
        }
        return StructuredLlmRequest(
            system_prompt=BASELINE_SYSTEM_PROMPT,
            user_prompt=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            response_schema=FeedbackAgentOutput.model_json_schema(),
            schema_name="baseline_feedback",
            prompt_version=BASELINE_PROMPT_VERSION,
            temperature=0,
        )


class BaselineGenerator:
    def __init__(
        self,
        client: StructuredLlmClient,
        prompt_builder: BaselinePromptBuilder | None = None,
    ) -> None:
        self._client = client
        self._prompt_builder = prompt_builder or BaselinePromptBuilder()

    async def generate(
        self,
        context: FeedbackContext,
        *,
        expected_provider: str,
        expected_model: str,
    ) -> GeneratedFeedback:
        request = self._prompt_builder.build(context)
        try:
            response = await self._client.generate_structured(request)
        except Exception:
            raise FeedbackClientError() from None
        if response.provider != expected_provider or response.model != expected_model:
            raise BaselineModelMismatchError(
                "baseline provider/model does not match the agentic generator"
            )
        try:
            output = FeedbackAgentOutput.model_validate(response.output)
        except ValidationError:
            raise BaselineOutputError("baseline output failed schema validation") from None
        if output.source_references or output.simulation_references:
            raise BaselineOutputError("baseline output cannot contain external references")
        return GeneratedFeedback(
            feedback_content=output.model_dump(mode="json"),
            provider=response.provider,
            model=response.model,
            prompt_version=request.prompt_version,
            source_references=[],
            source_attributions=[],
            simulation_references=[],
            token_usage=response.token_usage,
            estimated_cost=response.estimated_cost,
            usage_complete=response.usage_complete,
        )
