from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from app.models.enums import FeedbackReportCategory, WorkflowStage
from app.schemas.feedback import (
    FeedbackContext,
    FeedbackPipelineResult,
    FeedbackRegenerationContext,
    GeneratedFeedback,
    JudgeEvaluationOutcome,
    RetrievalResult,
    SimulationResult,
    SubmissionContext,
    TaskContext,
    TokenUsage,
)
from app.services.terminal_integrations.contracts import TerminalIntegrationIntent


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
    usage_complete: bool = False


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
    ) -> RetrievalResult: ...


class SimulationProvider(Protocol):
    async def get_simulation_context(
        self,
        task: TaskContext,
        submission: SubmissionContext,
    ) -> SimulationResult: ...


class FeedbackContextCollector(Protocol):
    async def collect(
        self,
        submission: SubmissionContext,
        correlation_id: str,
    ) -> FeedbackContext: ...


class FeedbackGenerator(Protocol):
    async def generate(
        self,
        context: FeedbackContext,
        regeneration: FeedbackRegenerationContext | None = None,
    ) -> GeneratedFeedback: ...


class FeedbackJudge(Protocol):
    async def evaluate(
        self,
        context: FeedbackContext,
        feedback: GeneratedFeedback,
    ) -> JudgeEvaluationOutcome: ...


@dataclass(frozen=True, slots=True)
class FeedbackAttemptPersistence:
    feedback_id: str
    generation_attempt: int
    generated_feedback: GeneratedFeedback
    judge_evaluation: JudgeEvaluationOutcome


@dataclass(frozen=True, slots=True)
class PipelinePersistenceRequest:
    result: FeedbackPipelineResult
    attempts: tuple[FeedbackAttemptPersistence, ...]
    started_at: datetime
    completed_at: datetime
    execution_token: str | None = None
    course_id: str | None = None
    task_id: str | None = None
    terminal_integrations: tuple[TerminalIntegrationIntent, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkflowClaim:
    workflow_run_id: str
    submission_id: str
    stage: WorkflowStage
    should_start: bool
    execution_token: str | None = None
    execution_attempt_count: int = 0
    lease_expires_at: datetime | None = None
    course_id: str | None = None
    task_id: str | None = None
    retryable: bool = False
    retry_after_seconds: int | None = None
    terminal_result: FeedbackPipelineResult | None = None
    failure_category: str | None = None


@dataclass(frozen=True, slots=True)
class FeedbackReportWrite:
    feedback_id: str
    reporter_reference: str
    category: FeedbackReportCategory
    note: str | None


@dataclass(frozen=True, slots=True)
class FeedbackReportWriteResult:
    report_id: str
    created: bool


class FeedbackWorkflowRepository(Protocol):
    def get_by_submission(self, submission_id: str) -> FeedbackPipelineResult | None: ...

    def save_result(self, request: PipelinePersistenceRequest) -> FeedbackPipelineResult: ...

    def claim_workflow(
        self,
        submission_id: str,
        workflow_run_id: str,
        *,
        started_at: datetime,
        lease_expires_at: datetime,
    ) -> WorkflowClaim: ...

    def claim_next_recoverable(
        self,
        *,
        started_at: datetime,
        lease_expires_at: datetime,
    ) -> WorkflowClaim | None: ...

    def finalize_next_exhausted(self, *, observed_at: datetime) -> str | None: ...

    def get_workflow_claim(self, submission_id: str) -> WorkflowClaim | None: ...

    def record_stage(
        self,
        workflow_run_id: str,
        stage: WorkflowStage,
        *,
        execution_token: str | None = None,
        lease_expires_at: datetime | None = None,
    ) -> None: ...

    def mark_failed(
        self,
        workflow_run_id: str,
        failure_category: str,
        completed_at: datetime,
        *,
        execution_token: str | None = None,
        retryable: bool = False,
        next_retry_at: datetime | None = None,
    ) -> None: ...

    def get_released_submission_id(self, feedback_id: str) -> str | None: ...

    def save_report(self, report: FeedbackReportWrite) -> FeedbackReportWriteResult: ...

    def recover_terminal_integrations(
        self,
        workflow_run_id: str,
        *,
        observed_at: datetime,
    ) -> int: ...


class WorkflowProgressRecorder(Protocol):
    def record_stage(
        self,
        workflow_run_id: str,
        stage: WorkflowStage,
        *,
        execution_token: str | None = None,
        lease_expires_at: datetime | None = None,
    ) -> None: ...


class TerminalFeedbackObserver(Protocol):
    async def after_terminal_feedback(
        self,
        context: FeedbackContext,
        result: FeedbackPipelineResult,
        attempts: tuple[FeedbackAttemptPersistence, ...],
    ) -> None: ...


class TerminalIntegrationPlanner(Protocol):
    async def plan(
        self,
        context: FeedbackContext,
        result: FeedbackPipelineResult,
        attempts: tuple[FeedbackAttemptPersistence, ...],
    ) -> tuple[TerminalIntegrationIntent, ...]: ...
