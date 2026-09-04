from pydantic import ValidationError

from app.schemas.feedback import (
    FeedbackAgentOutput,
    FeedbackContext,
    FeedbackRegenerationContext,
    FeedbackSourceAttribution,
    GeneratedFeedback,
)
from app.services.feedback.contracts import FeedbackGenerator, StructuredLlmClient
from app.services.feedback.errors import (
    AssessedFeedbackNotReadyError,
    FeedbackClientError,
    InvalidFeedbackOutputError,
)
from app.services.feedback.prompt import FeedbackPromptBuilder

AI_GENERATED_NOTICE = "AI-generated feedback. Verify important details and report any concerns."


class PendingAssessmentFeedbackGenerator:
    """Fail safely until criteria-based assessed feedback is implemented in Step 4."""

    def __init__(self, delegate: FeedbackGenerator) -> None:
        self._delegate = delegate

    async def generate(
        self,
        context: FeedbackContext,
        regeneration: FeedbackRegenerationContext | None = None,
    ) -> GeneratedFeedback:
        if context.assessment_context is not None:
            raise AssessedFeedbackNotReadyError()
        return await self._delegate.generate(context, regeneration)


class LlmFeedbackGenerator:
    def __init__(
        self,
        client: StructuredLlmClient,
        prompt_builder: FeedbackPromptBuilder | None = None,
    ) -> None:
        self._client = client
        self._prompt_builder = prompt_builder or FeedbackPromptBuilder()

    async def generate(
        self,
        context: FeedbackContext,
        regeneration: FeedbackRegenerationContext | None = None,
    ) -> GeneratedFeedback:
        request = self._prompt_builder.build(context, regeneration)
        try:
            response = await self._client.generate_structured(request)
        except Exception:
            raise FeedbackClientError() from None

        try:
            output = FeedbackAgentOutput.model_validate(response.output)
            self._validate_references(context, output)
            content = output.model_dump(mode="json")
            content["ai_generated_notice"] = AI_GENERATED_NOTICE
            labels_by_source = {
                item.source_id: item.source_label for item in context.retrieval_context
            }
            return GeneratedFeedback(
                feedback_content=content,
                provider=response.provider,
                model=response.model,
                prompt_version=request.prompt_version,
                source_references=output.source_references,
                source_attributions=[
                    FeedbackSourceAttribution(
                        source_id=source_id,
                        label=labels_by_source[source_id],
                    )
                    for source_id in output.source_references
                ],
                simulation_references=output.simulation_references,
                token_usage=response.token_usage,
                estimated_cost=response.estimated_cost,
                usage_complete=response.usage_complete,
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
