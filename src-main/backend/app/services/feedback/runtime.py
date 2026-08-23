"""Concrete feedback composition used by the integrated LMS."""

from __future__ import annotations

import json
from uuid import uuid4

import anyio
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import LearningMaterial, LearningTask, MaterialChunk
from app.models.lms import SubmissionAttempt
from app.schemas.feedback import (
    ContextProviderStatus,
    RetrievalContext,
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
    PendingAssessmentFeedbackGenerator,
)
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
from app.services.quantum import CircuitOperation, QuantumSimulationError, simulate_circuit
from app.services.terminal_integrations.planner import (
    DurableTerminalIntegrationPlanner,
)


class ConfiguredResearchEligibility:
    async def is_eligible(self, _: object) -> bool:
        return settings.research_enabled


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
            score=float(attempt.score) if attempt.score is not None else None,
            submitted_at=attempt.submitted_at,
        )


class TaskSourceRetrievalProvider:
    """Load only the course chunks already approved for the task."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def get_retrieval_context(
        self,
        task: TaskContext,
        submission: SubmissionContext,
    ) -> RetrievalResult:
        del submission
        if not task.source_references:
            return RetrievalResult(status=ContextProviderStatus.EMPTY)
        references = set(task.source_references)
        direct_materials = list(
            self._session.scalars(
                select(LearningMaterial).where(
                    LearningMaterial.id.in_(references),
                    LearningMaterial.course_id == task.course_id,
                )
            ).all()
        )
        direct_material_ids = {material.id for material in direct_materials}
        chunks = list(
            self._session.scalars(
                select(MaterialChunk)
                .where(
                    (MaterialChunk.id.in_(references))
                    | (MaterialChunk.material_id.in_(direct_material_ids))
                )
                .order_by(MaterialChunk.chunk_index)
                .limit(50)
            ).all()
        )
        materials = {
            material.id: material
            for material in self._session.scalars(
                select(LearningMaterial).where(
                    LearningMaterial.id.in_({chunk.material_id for chunk in chunks}),
                    LearningMaterial.course_id == task.course_id,
                )
            ).all()
        }
        request_id = str(uuid4())
        items = [
            RetrievalContext(
                retrieval_request_id=request_id,
                task_id=task.task_id,
                course_id=task.course_id,
                source_id=(
                    chunk.material_id if chunk.material_id in direct_material_ids else chunk.id
                ),
                document_id=chunk.material_id,
                chunk_id=chunk.id,
                chunk_text=chunk.chunk_text,
                relevance_score=1,
                source_label=_source_label(materials[chunk.material_id], chunk),
            )
            for chunk in chunks
            if chunk.material_id in materials
        ]
        if not items:
            return RetrievalResult(status=ContextProviderStatus.EMPTY)
        return RetrievalResult(
            status=ContextProviderStatus.COMPLETED,
            request_ids=[request_id],
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
        if task.task_type not in {"quantum_circuit", "circuit"}:
            return SimulationResult(status=ContextProviderStatus.NOT_REQUESTED)
        stored = self._session.get(SubmissionAttempt, submission.submission_id)
        circuit = _submission_circuit(stored.circuit if stored is not None else None)
        if circuit is None:
            return SimulationResult(status=ContextProviderStatus.EMPTY)
        try:
            result = await anyio.to_thread.run_sync(
                lambda: simulate_circuit(
                    qubits=circuit["qubits"],
                    operations=circuit["operations"],
                    shots=circuit["shots"],
                )
            )
        except QuantumSimulationError:
            return SimulationResult(status=ContextProviderStatus.FAILED)
        return SimulationResult(
            status=ContextProviderStatus.COMPLETED,
            context=SimulationContext(
                simulation_id=str(uuid4()),
                task_id=task.task_id,
                course_id=task.course_id,
                status="completed",
                circuit_summary=result.circuit_text[:4_000],
                measurement_counts=result.counts,
                probability_distribution=result.probabilities,
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
    generator = PendingAssessmentFeedbackGenerator(base_generator)
    judge = LlmFeedbackJudge(client) if client is not None else LocalFeedbackJudge()
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
        research_eligibility=ConfiguredResearchEligibility(),
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
    operations = raw.get("operations")
    if (
        not isinstance(qubits, int)
        or not isinstance(shots, int)
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
    return {"qubits": qubits, "shots": shots, "operations": parsed}


def _circuit_answer(raw: dict[str, object] | None) -> str:
    if not isinstance(raw, dict):
        return ""
    return json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
