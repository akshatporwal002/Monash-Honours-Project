"""Concrete feedback composition used by the integrated LMS."""

from __future__ import annotations

import json

import anyio
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import LearningMaterial, LearningTask, MaterialChunk
from app.models.lms import SubmissionAttempt
from app.schemas.feedback import (
    ContextProviderStatus,
    RetrievalResult,
    SimulationContext,
    SimulationResult,
    SubmissionContext,
    TaskContext,
)
from app.services.assessment.feedback_context import (
    SqlAlchemyAssessmentFeedbackContextProvider,
)
from app.services.feedback.agent import (
    LlmFeedbackGenerator,
)
from app.services.feedback.assessed import AssessedFeedbackGenerator, AssessedFeedbackJudge
from app.services.feedback.context import DefaultFeedbackContextCollector
from app.services.feedback.judge import LlmFeedbackJudge
from app.services.feedback.pipeline import FeedbackPipeline
from app.services.feedback.providers import (
    SqlAlchemyTaskProvider,
)
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository
from app.services.learning_events import HmacSha256Pseudonymizer
from app.services.llm import (
    ResponsesStructuredLlmClient,
    runtime_model_selection,
)
from app.services.local_ai import LocalFeedbackGenerator, LocalFeedbackJudge
from app.services.quantum import SIMULATION_POLICY_VERSION, CircuitOperation, QuantumSimulationError
from app.services.rag.feedback_adapter import RagFeedbackRetrievalProvider
from app.services.rag.local_retrieval import LocalCourseRetrievalService
from app.services.research.governance import research_processing_approved
from app.services.simulation_evidence import (
    SimulationEvidenceError,
    SimulationEvidenceService,
    engine_versions,
)
from app.services.terminal_integrations.planner import (
    DurableTerminalIntegrationPlanner,
)


class ConfiguredResearchEligibility:
    """Gate plus current scoped consent; never influences operational continuation."""

    def __init__(self, session: Session | None = None):
        self._session = session

    async def is_eligible(self, context: object) -> bool:
        if (
            not settings.research_enabled
            or not research_processing_approved()
            or self._session is None
        ):
            return False
        from app.services.research.governance import GovernanceDenied, ResearchGovernanceService

        try:
            ResearchGovernanceService(self._session).processing_scope(
                context.task.course_id, int(context.submission.student_id)
            )
        except (GovernanceDenied, ValueError, AttributeError):
            return False
        return True


class LmsSubmissionProvider:
    """Adapt immutable LMS attempts to the mature feedback pipeline."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def get_submission(self, submission_id: str) -> SubmissionContext | None:
        attempt = self._session.get(SubmissionAttempt, submission_id)
        if attempt is None:
            return None
        task = self._session.get(LearningTask, attempt.task_id)
        if task is None:
            return None
        submitted_answer = (
            attempt.answer.strip()
            or (attempt.code or "").strip()
            or _circuit_answer(attempt.circuit)
            or ("Frozen multipart response" if attempt.episode else "")
        )
        if not submitted_answer:
            return None
        return SubmissionContext(
            submission_id=attempt.id,
            task_id=attempt.task_id,
            course_id=task.course_id,
            student_id=str(attempt.student_id),
            attempt_number=attempt.attempt_number,
            submitted_answer=submitted_answer,
            submitted_at=attempt.submitted_at,
        )


class TaskSourceRetrievalProvider:
    """Retrieve checked passages through the existing scoped retrieval adapter."""

    def __init__(self, session: Session) -> None:
        self._provider = RagFeedbackRetrievalProvider(LocalCourseRetrievalService(session))

    async def get_retrieval_context(
        self, task: TaskContext, submission: SubmissionContext
    ) -> RetrievalResult:
        items = await self._provider.get_retrieval_context(task, submission)
        return RetrievalResult(
            status=ContextProviderStatus.COMPLETED if items else ContextProviderStatus.EMPTY,
            request_ids=sorted({item.retrieval_request_id for item in items}),
            items=items,
        )


class SubmittedCircuitSimulationProvider:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def get_simulation_context(
        self,
        task: TaskContext,
        submission: SubmissionContext,
    ) -> SimulationResult:
        if task.assessed or task.task_type not in {"quantum_circuit", "circuit"}:
            return SimulationResult(status=ContextProviderStatus.NOT_REQUESTED)
        stored = self._session.get(SubmissionAttempt, submission.submission_id)
        persisted_task = self._session.get(LearningTask, task.task_id)
        if (
            stored is None
            or stored.task_id != task.task_id
            or str(stored.student_id) != submission.student_id
            or submission.task_id != task.task_id
            or submission.course_id != task.course_id
            or persisted_task is None
            or persisted_task.course_id != task.course_id
        ):
            return SimulationResult(status=ContextProviderStatus.FAILED)
        circuit = _submission_circuit(stored.circuit if stored is not None else None)
        if circuit is None:
            return SimulationResult(status=ContextProviderStatus.EMPTY)
        try:
            service = SimulationEvidenceService(self._session)
            owner_id = stored.student_id
            record = await anyio.to_thread.run_sync(
                lambda: service.execute(
                    owner_id=owner_id,
                    task_id=task.task_id,
                    submission_id=submission.submission_id,
                    request_key="feedback:"
                    + submission.submission_id
                    + ":"
                    + SIMULATION_POLICY_VERSION
                    + ":"
                    + "/".join(engine_versions().values()),
                    qubits=circuit["qubits"],
                    operations=circuit["operations"],
                    shots=circuit["shots"],
                    seed=circuit["seed"],
                )
            )
        except (QuantumSimulationError, SimulationEvidenceError):
            return SimulationResult(status=ContextProviderStatus.FAILED)
        if record["status"] != "completed" or record["result"] is None:
            return SimulationResult(status=ContextProviderStatus.FAILED)
        result = record["result"]
        return SimulationResult(
            status=ContextProviderStatus.COMPLETED,
            context=SimulationContext(
                simulation_id=record["run_id"],
                task_id=task.task_id,
                course_id=task.course_id,
                status="completed",
                circuit_summary=result["circuit_text"][:4_000],
                measurement_counts=result["counts"],
                probability_distribution=result["probabilities"],
            ),
        )


def build_feedback_pipeline(
    session: Session,
    repository: SqlAlchemyFeedbackWorkflowRepository,
) -> FeedbackPipeline:
    client = _configured_model_client(session)
    base_generator = (
        LlmFeedbackGenerator(client) if client is not None else LocalFeedbackGenerator()
    )
    generator = AssessedFeedbackGenerator(base_generator)
    judge = AssessedFeedbackJudge(
        LlmFeedbackJudge(client) if client is not None else LocalFeedbackJudge()
    )
    collector = DefaultFeedbackContextCollector(
        SqlAlchemyTaskProvider(session),
        retrieval_provider=TaskSourceRetrievalProvider(session),
        simulation_provider=SubmittedCircuitSimulationProvider(session),
        assessment_context_provider=SqlAlchemyAssessmentFeedbackContextProvider(session),
        provider_timeout_seconds=settings.provider_timeout_seconds,
    )
    secret_setting = settings.learning_event_pseudonym_secret
    pseudonymizer = (
        HmacSha256Pseudonymizer(secret_setting.get_secret_value())
        if secret_setting is not None
        else None
    )
    selection = runtime_model_selection(session)
    integrations = DurableTerminalIntegrationPlanner(
        pseudonymizer,
        research_eligibility=ConfiguredResearchEligibility(session),
        fallback_provider=selection.provider,
        fallback_model=selection.model or "local-default",
    )
    return FeedbackPipeline(
        LmsSubmissionProvider(session),
        collector,
        generator,
        judge,
        repository,
        terminal_integration_planner=integrations,
        provider_timeout_seconds=settings.provider_timeout_seconds,
    )


def build_feedback_pipeline_for_repository(
    repository: SqlAlchemyFeedbackWorkflowRepository,
) -> FeedbackPipeline:
    """Factory shape required by the in-process background executor."""
    return build_feedback_pipeline(repository.session, repository)


def _configured_model_client(
    session: Session,
) -> ResponsesStructuredLlmClient | None:
    selection = runtime_model_selection(session)
    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key is not None else ""
    if selection.local or not api_key or not selection.model:
        return None
    return ResponsesStructuredLlmClient(
        api_key=api_key,
        model=selection.model,
        base_url=settings.llm_api_base_url,
        provider=selection.provider,
        timeout_seconds=settings.provider_timeout_seconds,
        input_cost_per_million=settings.llm_input_cost_per_million,
        output_cost_per_million=settings.llm_output_cost_per_million,
    )


def _source_label(material: LearningMaterial, chunk: MaterialChunk) -> str:
    base = material.original_filename or material.source_url or "Course material"
    location = chunk.location_label or chunk.heading
    return f"{base} - {location}" if location else base


def _submission_circuit(raw: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(raw, dict):
        return None
    qubits = raw.get("qubits", 2)
    shots = raw.get("shots", 1024)
    seed = raw.get("seed", 42)
    operations = raw.get("operations")
    if (
        not isinstance(qubits, int)
        or not isinstance(shots, int)
        or not isinstance(seed, int)
        or not isinstance(operations, list)
    ):
        return None
    parsed: list[CircuitOperation] = []
    for operation in operations:
        if not isinstance(operation, dict):
            return None
        gate = operation.get("gate")
        targets = operation.get("targets")
        if (
            not isinstance(gate, str)
            or not isinstance(targets, list)
            or not all(isinstance(target, int) for target in targets)
        ):
            return None
        parsed.append(CircuitOperation(gate=gate, targets=tuple(targets)))
    return {"qubits": qubits, "shots": shots, "seed": seed, "operations": parsed}


def _circuit_answer(raw: dict[str, object] | None) -> str:
    if not isinstance(raw, dict):
        return ""
    return json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
