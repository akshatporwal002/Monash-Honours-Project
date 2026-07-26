from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Generator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    AuditAction,
    AuditEvent,
    AuditOutcome,
    FeedbackRecord,
    FeedbackStatus,
    JudgeDecision,
    JudgeEvaluationStatus,
    LearningEvent,
    LearningEventType,
    WorkflowOutcome,
    WorkflowRun,
)
from app.schemas.feedback import (
    ContextProviderStatus,
    FeedbackContext,
    FeedbackPipelineResult,
    FeedbackPipelineStatus,
    FeedbackRegenerationContext,
    GeneratedFeedback,
    JudgeEvaluationOutcome,
    JudgeResult,
    RetrievalContext,
    RetrievalResult,
    SimulationContext,
    SimulationResult,
    SubmissionContext,
    TaskContext,
    TokenUsage,
)
from app.services.audit import IndependentAuditRecorder
from app.services.audit_events import FeedbackAuditEvents
from app.services.continuation import (
    ContinuationScheduleReceipt,
    ContinuationState,
    ContinuationTerminalFeedbackObserver,
    TerminalFeedbackNotice,
)
from app.services.feedback import (
    DefaultFeedbackContextCollector,
    FakeFeedbackJudge,
    FeedbackPipeline,
    InMemorySubmissionProvider,
    InMemoryTaskProvider,
    LlmFeedbackGenerator,
    RecordingStructuredLlmClient,
    SqlAlchemyFeedbackWorkflowRepository,
    StructuredLlmRequest,
    StructuredLlmResponse,
)
from app.services.feedback.contracts import (
    FeedbackGenerator,
    RetrievalProvider,
    SimulationProvider,
    TerminalFeedbackObserver,
)
from app.services.learning_events import (
    BestEffortLearningEventSink,
    HmacSha256Pseudonymizer,
    LearningEventRecorder,
    TrustedLearningEventHooks,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 26, 11, 0, tzinfo=UTC)
COURSE_ID = "course-e2e-scenarios"
PSEUDONYM_SECRET = "scenario-pseudonym-secret-material-32-bytes-minimum"
RAW_SOURCE_CHUNK = "PRIVATE_CODE_DOCUMENTATION_CHUNK_SENTINEL"
RAW_PROVIDER_ERROR = "PRIVATE_PROVIDER_EXCEPTION_SENTINEL_student@example.test"
RAW_SIMULATION_ERROR = "PRIVATE_SIMULATION_EXCEPTION_SENTINEL"


@dataclass(slots=True)
class MigratedDatabase:
    path: Path
    session_factory: sessionmaker[Session]


@dataclass(slots=True)
class ScenarioRun:
    result: FeedbackPipelineResult
    generator: CapturingFeedbackGenerator
    judge: FakeFeedbackJudge
    correlation_id: str


class StructuredClient(Protocol):
    async def generate_structured(
        self,
        request: StructuredLlmRequest,
    ) -> StructuredLlmResponse: ...


class CapturingFeedbackGenerator:
    def __init__(self, delegate: FeedbackGenerator) -> None:
        self._delegate = delegate
        self.contexts: list[FeedbackContext] = []
        self.regenerations: list[FeedbackRegenerationContext | None] = []

    async def generate(
        self,
        context: FeedbackContext,
        regeneration: FeedbackRegenerationContext | None = None,
    ) -> GeneratedFeedback:
        self.contexts.append(context)
        self.regenerations.append(regeneration)
        return await self._delegate.generate(context, regeneration)


class TypedRetrievalProvider:
    def __init__(self, result: RetrievalResult) -> None:
        self.result = result
        self.calls = 0

    async def get_retrieval_context(
        self,
        task: TaskContext,
        submission: SubmissionContext,
    ) -> RetrievalResult:
        del task, submission
        self.calls += 1
        return self.result


class TypedSimulationProvider:
    def __init__(self, result: SimulationResult, *, private_error: str | None = None) -> None:
        self.result = result
        self.private_error = private_error
        self.calls = 0

    async def get_simulation_context(
        self,
        task: TaskContext,
        submission: SubmissionContext,
    ) -> SimulationResult:
        del task, submission
        self.calls += 1
        return self.result


class SlowStructuredClient:
    def __init__(self) -> None:
        self.calls = 0
        self.cancelled = False

    async def generate_structured(
        self,
        request: StructuredLlmRequest,
    ) -> StructuredLlmResponse:
        del request
        self.calls += 1
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        raise RuntimeError(RAW_PROVIDER_ERROR)


class RecordingContinuationScheduler:
    def __init__(self) -> None:
        self.notices: list[TerminalFeedbackNotice] = []

    def after_terminal_feedback(
        self,
        notice: TerminalFeedbackNotice,
    ) -> ContinuationScheduleReceipt:
        self.notices.append(notice)
        return ContinuationScheduleReceipt(
            workflow_run_id=notice.workflow_run_id,
            accepted=True,
            state=ContinuationState.PENDING,
        )


def _migration_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture
def scenario_database(tmp_path: Path) -> Generator[MigratedDatabase, None, None]:
    database_path = tmp_path / "person4-scenarios.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    command.upgrade(_migration_config(database_url), "head")

    from app.db.session import create_db_engine, create_session_factory

    engine = create_db_engine(database_url)
    session_factory = create_session_factory(engine)
    yield MigratedDatabase(database_path, session_factory)
    engine.dispose()


def _task(
    slug: str,
    *,
    task_type: str,
    prompt: str,
    expected_answer: object | None = None,
    marking_criteria: object | None = None,
    source_references: Sequence[str] = (),
) -> TaskContext:
    return TaskContext(
        task_id=f"task-{slug}",
        course_id=COURSE_ID,
        task_type=task_type,
        prompt=prompt,
        difficulty="introductory",
        expected_answer=expected_answer,
        marking_criteria=marking_criteria,
        learning_outcome_id=f"outcome-{slug}",
        source_references=list(source_references),
    )


def _submission(
    slug: str,
    task: TaskContext,
    *,
    answer: str,
    score: float | None,
) -> SubmissionContext:
    return SubmissionContext(
        submission_id=f"submission-{slug}",
        task_id=task.task_id,
        course_id=task.course_id,
        student_id=f"opaque-student-{slug}",
        attempt_number=1,
        submitted_answer=answer,
        score=score,
        submitted_at=NOW,
    )


def _agent_output(
    classification: str,
    *,
    source_references: Sequence[str] = (),
    simulation_references: Sequence[str] = (),
) -> dict[str, object]:
    incorrect = classification == "incorrect"
    return {
        "response_classification": classification,
        "summary": (
            "The response needs a more precise explanation."
            if incorrect
            else "The response correctly applies the required concept."
        ),
        "identified_error": (
            "The response treats measurement as deterministic." if incorrect else None
        ),
        "explanation": ("Use the supplied evidence to connect the state to possible outcomes."),
        "improvement_actions": (
            ["State both possible outcomes and explain their probabilities."] if incorrect else []
        ),
        "recommended_next_step": "Check the result against the marking criteria.",
        "source_references": list(source_references),
        "simulation_references": list(simulation_references),
    }


def _response(output: dict[str, object]) -> StructuredLlmResponse:
    return StructuredLlmResponse(
        output=output,
        provider="deterministic-provider",
        model="deterministic-model",
        token_usage=TokenUsage(input_tokens=18, output_tokens=12, total_tokens=30),
        estimated_cost=Decimal("0.003000"),
        usage_complete=True,
    )


def _judge_outcome(decision: JudgeDecision) -> JudgeEvaluationOutcome:
    passing = decision is JudgeDecision.PASS
    score = 90 if passing else 60
    result = JudgeResult(
        decision=decision,
        correctness_score=score,
        relevance_score=score,
        grounding_score=score,
        actionability_score=score,
        safety_score=100,
        reason=(
            "The feedback is grounded and actionable."
            if passing
            else "The feedback requires a grounded correction."
        ),
        unsupported_claims=[],
        regeneration_instructions=[] if passing else ["Use only the supplied context."],
    )
    return JudgeEvaluationOutcome(
        evaluation_status=JudgeEvaluationStatus.VALID,
        reported_decision=decision,
        judge_result=result,
        reason=result.reason,
        provider="deterministic-provider",
        model="deterministic-judge",
        prompt_version="quality-judge-v1",
        quality_policy_version="quality-policy-v1",
        token_usage=TokenUsage(input_tokens=6, output_tokens=4, total_tokens=10),
        estimated_cost=Decimal("0.001000"),
    )


def _run_scenario(
    database: MigratedDatabase,
    *,
    task: TaskContext,
    submission: SubmissionContext,
    output: dict[str, object],
    retrieval_provider: RetrievalProvider | None = None,
    simulation_provider: SimulationProvider | None = None,
    judge_decisions: Sequence[JudgeDecision] = (JudgeDecision.PASS,),
    client: StructuredClient | None = None,
    terminal_observer: TerminalFeedbackObserver | None = None,
    provider_timeout_seconds: float = 60,
) -> ScenarioRun:
    correlation_id = str(uuid4())
    model_client = client or RecordingStructuredLlmClient(_response(output))
    generator = CapturingFeedbackGenerator(LlmFeedbackGenerator(model_client))
    judge = FakeFeedbackJudge([_judge_outcome(decision) for decision in judge_decisions])
    collector = DefaultFeedbackContextCollector(
        InMemoryTaskProvider({task.task_id: task}),
        retrieval_provider,
        simulation_provider,
        provider_timeout_seconds=provider_timeout_seconds,
    )
    audit_events = FeedbackAuditEvents(
        IndependentAuditRecorder(database.session_factory),
        now=lambda: NOW,
    )
    clock_values = iter([1.0, 1.025])
    with database.session_factory() as session:
        pipeline = FeedbackPipeline(
            InMemorySubmissionProvider({submission.submission_id: submission}),
            collector,
            generator,
            judge,
            SqlAlchemyFeedbackWorkflowRepository(session),
            clock=lambda: next(clock_values),
            now=lambda: NOW,
            terminal_observer=terminal_observer,
            audit_events=audit_events,
            provider_timeout_seconds=provider_timeout_seconds,
        )
        result = asyncio.run(
            pipeline.run(
                submission.submission_id,
                correlation_id=correlation_id,
            )
        )
    return ScenarioRun(result, generator, judge, correlation_id)


def _database_omits(database: MigratedDatabase, *private_values: str) -> None:
    database_bytes = database.path.read_bytes()
    for value in private_values:
        assert value.encode() not in database_bytes


def test_scenario_1_correct_multiple_choice_is_first_pass_and_schedules_continuation(
    scenario_database: MigratedDatabase,
) -> None:
    task = _task(
        "correct-mc",
        task_type="multiple_choice",
        prompt="Which gate creates an equal superposition from |0>?",
        expected_answer={"correct_option": "B", "option": "Hadamard"},
    )
    submission = _submission("correct-mc", task, answer="B", score=100)
    scheduler = RecordingContinuationScheduler()
    pseudonymizer = HmacSha256Pseudonymizer(PSEUDONYM_SECRET)
    continuation = ContinuationTerminalFeedbackObserver(scheduler, pseudonymizer)

    scenario = _run_scenario(
        scenario_database,
        task=task,
        submission=submission,
        output=_agent_output("correct"),
        terminal_observer=continuation,
    )

    assert scenario.result.status is FeedbackPipelineStatus.VALIDATED
    assert scenario.result.regeneration_count == 0
    assert scenario.result.validated_feedback is not None
    assert (
        scenario.result.validated_feedback.feedback_content["response_classification"] == "correct"
    )
    assert len(scheduler.notices) == 1
    notice = scheduler.notices[0]
    assert notice.workflow_run_id == scenario.result.workflow_run_id
    assert notice.correlation_id == scenario.correlation_id
    assert notice.course_reference == COURSE_ID
    assert notice.completed_task_reference == task.task_id
    assert notice.pseudonymous_actor_reference == pseudonymizer.pseudonymize(
        "continuation-actor",
        submission.student_id,
    )
    assert submission.student_id not in repr(notice)

    with scenario_database.session_factory() as session:
        workflow = session.get(WorkflowRun, scenario.result.workflow_run_id)
        assert workflow is not None
        assert workflow.final_outcome is WorkflowOutcome.FIRST_PASS


def test_scenario_2_incorrect_short_answer_has_grounded_action_and_learning_events(
    scenario_database: MigratedDatabase,
) -> None:
    source = RetrievalContext(
        retrieval_request_id="retrieval-incorrect-short",
        task_id="task-incorrect-short",
        course_id=COURSE_ID,
        source_id="source-measurement-notes",
        document_id="document-measurement-notes",
        chunk_id="chunk-measurement-notes",
        chunk_text="Measurement returns zero or one according to the state probabilities.",
        relevance_score=0.96,
        source_label="Measurement notes",
    )
    retrieval = TypedRetrievalProvider(
        RetrievalResult(
            status=ContextProviderStatus.COMPLETED,
            request_ids=[source.retrieval_request_id],
            items=[source],
        )
    )
    task = _task(
        "incorrect-short",
        task_type="short_answer",
        prompt="Explain measurement of a qubit in superposition.",
        marking_criteria="State both outcomes and connect them to probabilities.",
        source_references=[source.source_id],
    )
    submission = _submission(
        "incorrect-short",
        task,
        answer="Measurement always returns zero.",
        score=20,
    )

    scenario = _run_scenario(
        scenario_database,
        task=task,
        submission=submission,
        output=_agent_output("incorrect", source_references=[source.source_id]),
        retrieval_provider=retrieval,
    )
    feedback = scenario.result.validated_feedback
    assert feedback is not None
    assert feedback.feedback_content["response_classification"] == "incorrect"
    assert feedback.feedback_content["improvement_actions"] == [
        "State both possible outcomes and explain their probabilities."
    ]
    assert feedback.source_references == [source.source_id]
    assert feedback.source_attributions[0].label == "Measurement notes"

    recorder = LearningEventRecorder(
        scenario_database.session_factory,
        HmacSha256Pseudonymizer(PSEUDONYM_SECRET),
        now=lambda: NOW,
    )
    hooks = TrustedLearningEventHooks(BestEffortLearningEventSink(recorder))
    assert (
        hooks.record_submission(
            actor_reference=submission.student_id,
            course_id=COURSE_ID,
            task_id=task.task_id,
            source_event_id=str(uuid4()),
            correlation_id=scenario.correlation_id,
            attempt_number=1,
            score=20,
        )
        is not None
    )
    assert (
        hooks.record_completion(
            actor_reference=submission.student_id,
            course_id=COURSE_ID,
            task_id=task.task_id,
            source_event_id=str(uuid4()),
            correlation_id=scenario.correlation_id,
            completion_status="failed",
            score=20,
        )
        is not None
    )
    with scenario_database.session_factory() as session:
        events = list(
            session.scalars(
                select(LearningEvent)
                .where(LearningEvent.task_id == task.task_id)
                .order_by(LearningEvent.event_type)
            )
        )
        assert {event.event_type for event in events} == {
            LearningEventType.SUBMISSION,
            LearningEventType.COMPLETION,
        }
        assert all(event.pseudonymous_user_id.startswith("v1_") for event in events)
        assert all(submission.student_id not in repr(event.metadata_payload) for event in events)
    _database_omits(scenario_database, submission.submitted_answer, submission.student_id)


def test_scenario_3_code_explanation_attributes_retrieval_without_chunk_storage(
    scenario_database: MigratedDatabase,
) -> None:
    task = _task(
        "code-retrieval",
        task_type="code_explanation",
        prompt="Explain what the circuit-building code does.",
        marking_criteria="Explain the gate order and measurement.",
        source_references=["source-sdk-reference"],
    )
    submission = _submission(
        "code-retrieval",
        task,
        answer="It creates a circuit and measures it.",
        score=70,
    )
    source = RetrievalContext(
        retrieval_request_id="retrieval-code-reference",
        task_id=task.task_id,
        course_id=COURSE_ID,
        source_id="source-sdk-reference",
        document_id="document-sdk-reference",
        chunk_id="chunk-sdk-reference",
        chunk_text=RAW_SOURCE_CHUNK,
        relevance_score=0.98,
        source_label="Course SDK reference",
    )
    retrieval = TypedRetrievalProvider(
        RetrievalResult(
            status=ContextProviderStatus.COMPLETED,
            request_ids=[source.retrieval_request_id],
            items=[source],
        )
    )
    client = RecordingStructuredLlmClient(
        _response(_agent_output("correct", source_references=[source.source_id]))
    )

    scenario = _run_scenario(
        scenario_database,
        task=task,
        submission=submission,
        output=_agent_output("correct", source_references=[source.source_id]),
        retrieval_provider=retrieval,
        client=client,
    )

    assert scenario.generator.contexts[0].retrieval_status is ContextProviderStatus.COMPLETED
    assert scenario.generator.contexts[0].retrieval_request_ids == [source.retrieval_request_id]
    prompt_payload = json.loads(client.requests[0].user_prompt)
    assert prompt_payload["retrieved_context"][0]["source_id"] == source.source_id
    assert prompt_payload["retrieved_context"][0]["chunk_text"] == RAW_SOURCE_CHUNK
    assert submission.student_id not in client.requests[0].user_prompt
    assert submission.submission_id not in client.requests[0].user_prompt
    assert COURSE_ID not in client.requests[0].user_prompt

    with scenario_database.session_factory() as session:
        record = session.get(FeedbackRecord, scenario.result.feedback_id)
        assert record is not None
        assert record.source_references == [source.source_id]
        assert record.source_attributions == [
            {"source_id": source.source_id, "label": source.source_label}
        ]
        assert RAW_SOURCE_CHUNK not in json.dumps(record.feedback_content)
        assert RAW_SOURCE_CHUNK not in json.dumps(record.source_attributions)
    _database_omits(scenario_database, RAW_SOURCE_CHUNK)


def test_scenario_4_quantum_simulation_is_scoped_and_referenced(
    scenario_database: MigratedDatabase,
) -> None:
    task = _task(
        "quantum-simulation",
        task_type="quantum_circuit",
        prompt="Predict the measurement distribution after a Hadamard gate.",
        marking_criteria="Use the simulated counts to explain equal probabilities.",
    )
    submission = _submission(
        "quantum-simulation",
        task,
        answer="The outcomes should be approximately balanced.",
        score=85,
    )
    simulation = SimulationContext(
        simulation_id="simulation-hadamard-balanced",
        task_id=task.task_id,
        course_id=COURSE_ID,
        status="completed",
        circuit_summary="Hadamard on |0>, followed by measurement.",
        measurement_counts={"0": 507, "1": 517},
        probability_distribution={"0": 0.495, "1": 0.505},
    )
    provider = TypedSimulationProvider(
        SimulationResult(
            status=ContextProviderStatus.COMPLETED,
            context=simulation,
        )
    )
    client = RecordingStructuredLlmClient(
        _response(
            _agent_output(
                "correct",
                simulation_references=[simulation.simulation_id],
            )
        )
    )

    scenario = _run_scenario(
        scenario_database,
        task=task,
        submission=submission,
        output=_agent_output(
            "correct",
            simulation_references=[simulation.simulation_id],
        ),
        simulation_provider=provider,
        client=client,
    )

    context = scenario.generator.contexts[0]
    assert context.simulation_status is ContextProviderStatus.COMPLETED
    assert context.simulation_context == simulation
    prompt_payload = json.loads(client.requests[0].user_prompt)
    assert prompt_payload["simulation_context"] == {
        "simulation_id": simulation.simulation_id,
        "status": "completed",
        "circuit_summary": simulation.circuit_summary,
        "measurement_counts": {"0": 507, "1": 517},
        "probability_distribution": {"0": 0.495, "1": 0.505},
    }
    assert COURSE_ID not in client.requests[0].user_prompt
    assert task.task_id not in client.requests[0].user_prompt
    assert scenario.result.validated_feedback is not None
    assert scenario.result.validated_feedback.simulation_references == [simulation.simulation_id]

    with scenario_database.session_factory() as session:
        record = session.get(FeedbackRecord, scenario.result.feedback_id)
        assert record is not None
        assert record.simulation_references == [simulation.simulation_id]


def test_scenario_6_two_judge_rejections_release_one_audited_safe_fallback(
    scenario_database: MigratedDatabase,
) -> None:
    task = _task(
        "double-rejection",
        task_type="short_answer",
        prompt="Explain why measurement changes a quantum state.",
        marking_criteria="Connect the measurement outcome to state collapse.",
    )
    submission = _submission(
        "double-rejection",
        task,
        answer="Measurement only reads the state.",
        score=30,
    )

    scenario = _run_scenario(
        scenario_database,
        task=task,
        submission=submission,
        output=_agent_output("incorrect"),
        judge_decisions=(JudgeDecision.FAIL, JudgeDecision.FAIL),
    )

    assert scenario.result.status is FeedbackPipelineStatus.FALLBACK
    assert scenario.result.fallback_used is True
    assert scenario.result.regeneration_count == 1
    assert scenario.result.safe_fallback is not None
    assert scenario.result.safe_fallback.source_references == []
    assert scenario.result.safe_fallback.simulation_references == []
    assert len(scenario.generator.regenerations) == 2
    assert scenario.generator.regenerations[1] is not None
    assert scenario.judge.call_count == 2

    with scenario_database.session_factory() as session:
        records = list(
            session.scalars(
                select(FeedbackRecord).where(
                    FeedbackRecord.workflow_run_id == scenario.result.workflow_run_id
                )
            )
        )
        assert len(records) == 3
        assert sum(record.status is FeedbackStatus.SAFE_FALLBACK for record in records) == 1
        workflow = session.get(WorkflowRun, scenario.result.workflow_run_id)
        assert workflow is not None
        assert workflow.final_outcome is WorkflowOutcome.SAFE_FALLBACK
        fallback_audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == AuditAction.FEEDBACK_FALLBACK_USED,
                AuditEvent.resource_id == scenario.result.workflow_run_id,
            )
        )
        assert fallback_audit is not None
        assert fallback_audit.outcome is AuditOutcome.SUCCESS


def test_scenario_7_external_llm_timeout_is_bounded_and_sanitized(
    scenario_database: MigratedDatabase,
    caplog: pytest.LogCaptureFixture,
) -> None:
    task = _task(
        "provider-timeout",
        task_type="short_answer",
        prompt="Explain quantum interference.",
        marking_criteria="Describe how amplitudes combine.",
    )
    submission = _submission(
        "provider-timeout",
        task,
        answer="Amplitudes can reinforce or cancel.",
        score=None,
    )
    client = SlowStructuredClient()

    started = time.perf_counter()
    scenario = _run_scenario(
        scenario_database,
        task=task,
        submission=submission,
        output=_agent_output("correct"),
        client=client,
        provider_timeout_seconds=0.01,
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 1
    assert client.calls == 1
    assert client.cancelled is True
    assert scenario.result.status is FeedbackPipelineStatus.FALLBACK
    assert scenario.judge.call_count == 0
    with scenario_database.session_factory() as session:
        failed_call = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == AuditAction.FEEDBACK_GENERATION_COMPLETED,
                AuditEvent.resource_id == scenario.result.workflow_run_id,
                AuditEvent.outcome == AuditOutcome.FAILURE,
            )
        )
        assert failed_call is not None
        assert failed_call.failure_category == "provider_unavailable"
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.resource_id == scenario.result.workflow_run_id)
            )
            == 4
        )
    assert RAW_PROVIDER_ERROR not in caplog.text
    _database_omits(scenario_database, RAW_PROVIDER_ERROR)


@pytest.mark.parametrize(
    ("slug", "retrieval_provider", "expected_status", "expected_request_ids"),
    [
        (
            "retrieval-not-configured",
            None,
            ContextProviderStatus.NOT_REQUESTED,
            [],
        ),
        (
            "retrieval-empty",
            TypedRetrievalProvider(
                RetrievalResult(
                    status=ContextProviderStatus.EMPTY,
                    request_ids=["retrieval-empty-request"],
                )
            ),
            ContextProviderStatus.EMPTY,
            ["retrieval-empty-request"],
        ),
    ],
)
def test_scenario_8_missing_retrieval_preserves_typed_state_and_safe_grounding(
    scenario_database: MigratedDatabase,
    slug: str,
    retrieval_provider: RetrievalProvider | None,
    expected_status: ContextProviderStatus,
    expected_request_ids: list[str],
) -> None:
    task = _task(
        slug,
        task_type="code_explanation",
        prompt="Explain this circuit without external documentation.",
        marking_criteria="Use only the task and submitted answer.",
    )
    submission = _submission(
        slug,
        task,
        answer="The code creates a circuit.",
        score=50,
    )
    client = RecordingStructuredLlmClient(_response(_agent_output("correct")))

    scenario = _run_scenario(
        scenario_database,
        task=task,
        submission=submission,
        output=_agent_output("correct"),
        retrieval_provider=retrieval_provider,
        client=client,
    )

    context = scenario.generator.contexts[0]
    assert context.retrieval_status is expected_status
    assert context.retrieval_request_ids == expected_request_ids
    assert context.retrieval_context == []
    assert "retrieved_context" not in json.loads(client.requests[0].user_prompt)
    assert scenario.result.validated_feedback is not None
    assert scenario.result.validated_feedback.source_references == []


def test_scenario_9_simulation_failure_is_typed_and_never_leaks_raw_error(
    scenario_database: MigratedDatabase,
    caplog: pytest.LogCaptureFixture,
) -> None:
    task = _task(
        "simulation-failure",
        task_type="quantum_circuit",
        prompt="Explain the expected circuit behavior.",
        marking_criteria="Reason from the gates when simulation is unavailable.",
    )
    submission = _submission(
        "simulation-failure",
        task,
        answer="The Hadamard gate creates a superposition.",
        score=75,
    )
    provider = TypedSimulationProvider(
        SimulationResult(status=ContextProviderStatus.FAILED),
        private_error=RAW_SIMULATION_ERROR,
    )
    client = RecordingStructuredLlmClient(_response(_agent_output("correct")))

    scenario = _run_scenario(
        scenario_database,
        task=task,
        submission=submission,
        output=_agent_output("correct"),
        simulation_provider=provider,
        client=client,
    )

    context = scenario.generator.contexts[0]
    assert provider.calls == 1
    assert context.simulation_status is ContextProviderStatus.FAILED
    assert context.simulation_context is None
    assert "simulation_context" not in json.loads(client.requests[0].user_prompt)
    assert scenario.result.status is FeedbackPipelineStatus.VALIDATED
    assert scenario.result.validated_feedback is not None
    assert scenario.result.validated_feedback.simulation_references == []
    assert RAW_SIMULATION_ERROR not in caplog.text
    _database_omits(scenario_database, RAW_SIMULATION_ERROR)
