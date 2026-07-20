from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from app.schemas.feedback import (
    FeedbackContext,
    FeedbackPipelineResult,
    GeneratedFeedback,
    JudgeResult,
    RetrievalContext,
    SimulationContext,
    SubmissionContext,
    TaskContext,
    TokenUsage,
)


@dataclass(frozen=True, slots=True)
class StructuredLlmRequest:
    system_prompt: str
    user_prompt: str
    response_schema: dict[str, Any]
    schema_name: str
    prompt_version: str
    temperature: float = 0.0


@dataclass(frozen=True, slots=True)
class StructuredLlmResponse:
    output: dict[str, Any]
    provider: str
    model: str
    token_usage: TokenUsage
    estimated_cost: Decimal = Decimal("0")


class StructuredLlmClient(Protocol):
    async def generate_structured(
        self,
        request: StructuredLlmRequest,
    ) -> StructuredLlmResponse: ...


class SubmissionProvider(Protocol):
    async def get_submission(self, submission_id: str) -> SubmissionContext | None: ...


class TaskProvider(Protocol):
    async def get_task(self, task_id: str) -> TaskContext | None: ...


class RetrievalProvider(Protocol):
    async def get_retrieval_context(
        self,
        task: TaskContext,
        submission: SubmissionContext,
    ) -> list[RetrievalContext]: ...


class SimulationProvider(Protocol):
    async def get_simulation_context(
        self,
        task: TaskContext,
        submission: SubmissionContext,
    ) -> SimulationContext | None: ...


class FeedbackContextCollector(Protocol):
    async def collect(
        self,
        submission: SubmissionContext,
        correlation_id: str,
    ) -> FeedbackContext: ...


class FeedbackGenerator(Protocol):
    async def generate(self, context: FeedbackContext) -> GeneratedFeedback: ...


class FeedbackJudge(Protocol):
    async def evaluate(
        self,
        context: FeedbackContext,
        feedback: GeneratedFeedback,
    ) -> JudgeResult: ...


@dataclass(frozen=True, slots=True)
class PipelinePersistenceRequest:
    result: FeedbackPipelineResult
    generated_feedback: GeneratedFeedback
    started_at: datetime
    completed_at: datetime


class FeedbackWorkflowRepository(Protocol):
    def get_by_submission(self, submission_id: str) -> FeedbackPipelineResult | None: ...

    def save_result(self, request: PipelinePersistenceRequest) -> FeedbackPipelineResult: ...
