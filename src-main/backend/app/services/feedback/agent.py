from pydantic import ValidationError

from app.schemas.feedback import FeedbackAgentOutput, FeedbackContext, GeneratedFeedback
from app.services.feedback.contracts import StructuredLlmClient
from app.services.feedback.errors import FeedbackClientError, InvalidFeedbackOutputError
from app.services.feedback.prompt import FeedbackPromptBuilder


AI_GENERATED_NOTICE = "AI-generated feedback. Verify important details and report any concerns."


class LlmFeedbackGenerator:
    def __init__(
        self,
        client: StructuredLlmClient,
        prompt_builder: FeedbackPromptBuilder | None = None,
    ) -> None:
        self._client = client
        self._prompt_builder = prompt_builder or FeedbackPromptBuilder()

    async def generate(self, context: FeedbackContext) -> GeneratedFeedback:
        request = self._prompt_builder.build(context)
        try:
            response = await self._client.generate_structured(request)
        except Exception:
            raise FeedbackClientError() from None

        try:
            output = FeedbackAgentOutput.model_validate(response.output)
            self._validate_references(context, output)
            content = output.model_dump(mode="json")
            content["ai_generated_notice"] = AI_GENERATED_NOTICE
            return GeneratedFeedback(
                feedback_content=content,
                provider=response.provider,
                model=response.model,
                prompt_version=request.prompt_version,
                source_references=output.source_references,
                simulation_references=output.simulation_references,
                token_usage=response.token_usage,
                estimated_cost=response.estimated_cost,
            )
        except (ValidationError, ValueError):
            raise InvalidFeedbackOutputError() from None

    @staticmethod
    def _validate_references(
        context: FeedbackContext,
        output: FeedbackAgentOutput,
    ) -> None:
        allowed_sources = {item.source_id for item in context.retrieval_context}
        if not set(output.source_references).issubset(allowed_sources):
            raise ValueError("feedback references an unavailable source")

        allowed_simulations = (
            {context.simulation_context.simulation_id}
            if context.simulation_context is not None
            else set()
        )
        if not set(output.simulation_references).issubset(allowed_simulations):
            raise ValueError("feedback references an unavailable simulation")
