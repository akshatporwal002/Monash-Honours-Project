"""Build the grounded task-generation service from runtime settings."""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.llm import (
    ResponsesStructuredLlmClient,
    ResponsesTaskGenerationClient,
    runtime_model_selection,
)
from app.services.local_ai import LocalTaskGenerationClient
from app.services.rag.contracts import TaskGenerationClient
from app.services.rag.local_retrieval import LocalCourseRetrievalService
from app.services.rag.task_generation import GroundedTaskGenerationService
from app.services.runtime_policy import read_runtime_policy


def configured_task_generation_client(session: Session) -> TaskGenerationClient:
    """Resolve the administrator-selected task generator for each request."""

    policy = read_runtime_policy(session)
    selection = runtime_model_selection(session)
    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key is not None else ""
    if selection.local or not api_key or not selection.model:
        return LocalTaskGenerationClient()
    return ResponsesTaskGenerationClient(
        ResponsesStructuredLlmClient(
            api_key=api_key,
            model=selection.model,
            base_url=settings.llm_api_base_url,
            provider=selection.provider,
            timeout_seconds=policy.provider_timeout_seconds,
            max_infrastructure_attempts=policy.max_infrastructure_attempts,
            input_cost_per_million=settings.llm_input_cost_per_million,
            output_cost_per_million=settings.llm_output_cost_per_million,
        )
    )


def build_grounded_task_generation_service(
    session: Session,
) -> GroundedTaskGenerationService:
    return GroundedTaskGenerationService(
        session,
        LocalCourseRetrievalService(session),
        configured_task_generation_client(session),
    )
