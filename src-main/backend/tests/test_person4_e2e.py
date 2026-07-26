from __future__ import annotations

import asyncio
import csv
import io
import json
from collections.abc import Generator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.analytics_dependencies import (
    get_analytics_access_policy,
    get_analytics_application,
    get_analytics_pseudonymizer,
)
from app.api.audit_dependencies import get_student_audit_tracker
from app.api.feedback_dependencies import (
    get_authenticated_actor,
    get_feedback_access_policy,
    get_feedback_application,
    get_feedback_executor,
)
from app.api.learning_event_dependencies import (
    get_feedback_view_tracker,
    get_learning_event_access_policy,
    get_learning_event_recorder,
)
from app.api.research_export_dependencies import (
    get_research_export_access_policy,
    get_research_export_service,
)
from app.api.routes.health import get_readiness_probe
from app.core.config import Settings
from app.core.readiness import (
    ReadinessProbe,
    SqlAlchemyWorkerHeartbeatRepository,
    WorkerHealthRegistry,
)
from app.db.session import (
    create_db_engine,
    create_session_factory,
)
from app.main import create_app
from app.models import (
    AuditAction,
    AuditEvent,
    ContinuationJob,
    ExperimentalCondition,
    LearningEvent,
    LearningEventType,
    ResearchEvaluation,
    TerminalIntegrationOutbox,
    TerminalIntegrationState,
    WorkflowRun,
    WorkflowStage,
)
from app.schemas.continuation import ContinuationAvailability
from app.schemas.feedback import (
    FeedbackContext,
    FeedbackResponseClassification,
    FeedbackSourceAttribution,
    GeneratedFeedback,
    JudgeEvaluationOutcome,
    JudgeResult,
    RetrievalContext,
    SimulationContext,
    SubmissionContext,
    TaskContext,
    TokenUsage,
)
from app.schemas.feedback_api import AuthenticatedActor
from app.services.analytics import (
    AnalyticsApplication,
    SqlAlchemyAnalyticsRepository,
)
from app.services.audit import BestEffortAuditSink, IndependentAuditRecorder
from app.services.audit_events import FeedbackAuditEvents, StudentAuditTracker
from app.services.continuation import (
    ContinuationClaim,
    ContinuationFailureCategory,
    ContinuationQueryService,
    ContinuationRecord,
    ContinuationState,
    ContinuationWorker,
    NextTaskRequest,
    ProgressUpdate,
    TerminalContinuationService,
    TerminalFeedbackNotice,
)
from app.services.feedback import (
    DefaultFeedbackContextCollector,
    FakeFeedbackGenerator,
    FakeFeedbackJudge,
    FeedbackPipeline,
    InMemorySubmissionProvider,
    InMemoryTaskProvider,
    SqlAlchemyFeedbackWorkflowRepository,
    StaticRetrievalProvider,
    StaticSimulationProvider,
)
from app.services.feedback.application import (
    FeedbackWorkflowApplication,
    InProcessFeedbackExecutor,
)
from app.services.feedback.errors import LostWorkflowLeaseError
from app.services.learning_events import (
    BestEffortFeedbackViewTracker,
    BestEffortLearningEventSink,
    HmacSha256Pseudonymizer,
    LearningEventRecorder,
    LearningEventScope,
    TrustedLearningEventHooks,
)
from app.services.research import (
    BASELINE_PROMPT_VERSION,
    BaselineJobExecutor,
    DatabaseResearchJobDispatcher,
    ResearchCaseFactory,
    SqlAlchemyResearchJobRepository,
)
from app.services.research_export import ResearchExportService
from app.services.research_export_repository import (
    SqlAlchemyResearchExportRepository,
)
from app.services.terminal_integrations.planner import (
    DurableTerminalIntegrationPlanner,
)
from app.services.terminal_integrations.worker import TerminalIntegrationWorker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 26, 10, 0, tzinfo=UTC)
PSEUDONYM_SECRET = "e2e-pseudonym-secret-material-32-bytes-minimum"
SUBMISSION_ID = "submission-e2e"
COURSE_ID = "course-e2e"
TASK_ID = "task-e2e"
STUDENT_ACTOR = "opaque-student-subject"
RAW_ANSWER = "PRIVATE_RAW_ANSWER_SENTINEL_student@example.test"
RAW_SOURCE_CHUNK = "PRIVATE_RETRIEVED_CHUNK_SENTINEL"
RAW_SIMULATION_ERROR = "PRIVATE_SIMULATION_ERROR_SENTINEL"


class FeedbackPolicy:
    async def can_access_submission(
        self,
        actor: AuthenticatedActor,
        submission_id: str,
    ) -> bool:
        return actor.actor_reference == STUDENT_ACTOR and submission_id == SUBMISSION_ID


class LearningPolicy:
    async def resolve_task_scope(
        self,
        actor: AuthenticatedActor,
        task_id: str,
    ) -> LearningEventScope | None:
        if actor.actor_reference != STUDENT_ACTOR or task_id != TASK_ID:
            return None
        return LearningEventScope(course_id=COURSE_ID, task_id=TASK_ID)


class AnalyticsPolicy:
    async def authorized_course_ids(self, actor_reference: str) -> set[str]:
        return {COURSE_ID} if actor_reference == "opaque-educator-subject" else set()


class ExportPolicy:
    async def authorized_course_ids(
        self,
        actor: AuthenticatedActor,
    ) -> set[str]:
        return {COURSE_ID} if actor.actor_reference == "opaque-researcher-subject" else set()


class Roster:
    async def learner_references(self, course_ids: set[str]) -> list[str]:
        assert course_ids == {COURSE_ID}
        return [STUDENT_ACTOR, "opaque-never-active-subject"]


class EligibleResearch:
    async def is_eligible(self, context: FeedbackContext) -> bool:
        return context.task.course_id == COURSE_ID


class MemoryContinuationRepository:
    def __init__(self) -> None:
        self.records: dict[str, ContinuationRecord] = {}
        self.tokens: dict[str, str] = {}
        self.leases: dict[str, datetime] = {}

    def ensure_pending(self, notice: TerminalFeedbackNotice) -> ContinuationRecord:
        existing = self.records.get(notice.workflow_run_id)
        if existing is not None:
            replay = (
                notice.pseudonymous_actor_reference,
                notice.course_reference,
                notice.completed_task_reference,
                notice.correlation_id,
            )
            stored = (
                existing.pseudonymous_actor_reference,
                existing.course_reference,
                existing.completed_task_reference,
                existing.correlation_id,
            )
            if replay != stored:
                raise RuntimeError("continuation notice conflict")
            return existing
        record = ContinuationRecord(
            workflow_run_id=notice.workflow_run_id,
            pseudonymous_actor_reference=notice.pseudonymous_actor_reference,
            course_reference=notice.course_reference,
            completed_task_reference=notice.completed_task_reference,
            correlation_id=notice.correlation_id,
            state=ContinuationState.PENDING,
        )
        self.records[notice.workflow_run_id] = record
        return record

    def claim_next(
        self,
        *,
        now: datetime,
        lease_expires_at: datetime,
        execution_token: str,
        maximum_attempts: int,
    ) -> ContinuationClaim | None:
        for workflow_id, record in self.records.items():
            lease = self.leases.get(workflow_id)
            expired = (
                record.state is ContinuationState.RUNNING and lease is not None and lease <= now
            )
            retry_due = record.state is ContinuationState.RETRY_SCHEDULED and (
                record.next_retry_at is None or record.next_retry_at <= now
            )
            if not (record.state is ContinuationState.PENDING or retry_due or expired):
                continue
            if record.processing_attempts >= maximum_attempts:
                continue
            running = replace(
                record,
                state=ContinuationState.RUNNING,
                processing_attempts=record.processing_attempts + 1,
                next_retry_at=None,
                retryable=False,
                failure_category=None,
            )
            self.records[workflow_id] = running
            self.tokens[workflow_id] = execution_token
            self.leases[workflow_id] = lease_expires_at
            return ContinuationClaim(
                workflow_run_id=workflow_id,
                execution_token=execution_token,
                pseudonymous_actor_reference=running.pseudonymous_actor_reference,
                course_reference=running.course_reference,
                completed_task_reference=running.completed_task_reference,
                correlation_id=running.correlation_id,
                progress_recorded=running.progress_recorded,
                processing_attempts=running.processing_attempts,
                lease_expires_at=lease_expires_at,
            )
        return None

    def finalize_next_exhausted(
        self,
        *,
        observed_at: datetime,
        maximum_attempts: int,
    ) -> str | None:
        for workflow_id, record in self.records.items():
            lease = self.leases.get(workflow_id)
            if (
                record.state is ContinuationState.RUNNING
                and record.processing_attempts >= maximum_attempts
                and lease is not None
                and lease <= observed_at
            ):
                self.records[workflow_id] = replace(
                    record,
                    state=ContinuationState.FAILED,
                    retryable=False,
                    next_retry_at=None,
                    failure_category=ContinuationFailureCategory.PERSISTENCE_UNAVAILABLE,
                )
                self.tokens.pop(workflow_id, None)
                self.leases.pop(workflow_id, None)
                return workflow_id
        return None

    def mark_progress_recorded(self, claim: ContinuationClaim) -> bool:
        if self.tokens.get(claim.workflow_run_id) != claim.execution_token:
            return False
        self.records[claim.workflow_run_id] = replace(
            self.records[claim.workflow_run_id],
            progress_recorded=True,
        )
        return True

    def complete(
        self,
        claim: ContinuationClaim,
        next_task_reference: str,
        *,
        completed_at: datetime,
    ) -> bool:
        del completed_at
        if self.tokens.get(claim.workflow_run_id) != claim.execution_token:
            return False
        self.records[claim.workflow_run_id] = replace(
            self.records[claim.workflow_run_id],
            state=ContinuationState.COMPLETED,
            next_task_reference=next_task_reference,
        )
        return True

    def fail(
        self,
        claim: ContinuationClaim,
        category: ContinuationFailureCategory,
        *,
        failed_at: datetime,
        retryable: bool,
        next_retry_at: datetime | None,
    ) -> bool:
        del failed_at
        if self.tokens.get(claim.workflow_run_id) != claim.execution_token:
            return False
        self.records[claim.workflow_run_id] = replace(
            self.records[claim.workflow_run_id],
            state=(ContinuationState.RETRY_SCHEDULED if retryable else ContinuationState.FAILED),
            failure_category=category,
            retryable=retryable,
            next_retry_at=next_retry_at,
        )
        return True

    def get(self, workflow_run_id: str) -> ContinuationRecord | None:
        return self.records.get(workflow_run_id)


class ProgressAdapter:
    def __init__(self) -> None:
        self.idempotency_keys: set[str] = set()
        self.calls: list[ProgressUpdate] = []

    async def record_terminal_feedback(self, update: ProgressUpdate) -> None:
        if update.idempotency_key in self.idempotency_keys:
            return
        self.idempotency_keys.add(update.idempotency_key)
        self.calls.append(update)


class Recommender:
    def __init__(self) -> None:
        self.calls: list[NextTaskRequest] = []

    async def recommend_next_task(self, request: NextTaskRequest) -> str:
        self.calls.append(request)
        return "team-recommender:next-task-opaque"


class ResearchObserver:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        pseudonymizer: HmacSha256Pseudonymizer,
        dispatcher: DatabaseResearchJobDispatcher,
        continuation: TerminalContinuationService,
        *,
        fast_path: bool = True,
    ) -> None:
        self._session_factory = session_factory
        self._pseudonymizer = pseudonymizer
        self._dispatcher = dispatcher
        self._continuation = continuation
        self._fast_path = fast_path
        self.contexts: dict[str, FeedbackContext] = {}
        self.notices: dict[str, TerminalFeedbackNotice] = {}

    async def after_terminal_feedback(
        self,
        context: FeedbackContext,
        result: object,
        attempts: object,
    ) -> None:
        from app.schemas.feedback import FeedbackPipelineResult
        from app.services.feedback.contracts import FeedbackAttemptPersistence

        pipeline_result = FeedbackPipelineResult.model_validate(result)
        typed_attempts = tuple(
            FeedbackAttemptPersistence(
                feedback_id=item.feedback_id,
                generation_attempt=item.generation_attempt,
                generated_feedback=item.generated_feedback,
                judge_evaluation=item.judge_evaluation,
            )
            for item in attempts
        )
        if self._fast_path:
            with self._session_factory() as session:
                factory = ResearchCaseFactory(
                    EligibleResearch(),
                    SqlAlchemyResearchJobRepository(session),
                    self._dispatcher,
                    self._pseudonymizer,
                    fallback_provider="deterministic-provider",
                    fallback_model="deterministic-model",
                )
                await factory.create_after_feedback(
                    context,
                    pipeline_result,
                    typed_attempts,
                )
        self.contexts[pipeline_result.workflow_run_id] = context
        notice = TerminalFeedbackNotice(
            workflow_run_id=pipeline_result.workflow_run_id,
            pseudonymous_actor_reference=self._pseudonymizer.pseudonymize(
                "continuation-actor",
                context.submission.student_id,
            ),
            course_reference=context.task.course_id,
            completed_task_reference=context.task.task_id,
            correlation_id=context.correlation_id,
        )
        self.notices[pipeline_result.workflow_run_id] = notice
        if self._fast_path:
            self._continuation.after_terminal_feedback(notice)


class BaselineContextProvider:
    def __init__(self, contexts: dict[str, FeedbackContext]) -> None:
        self._contexts = contexts

    async def get_context(self, workflow_run_id: str) -> FeedbackContext | None:
        return self._contexts.get(workflow_run_id)


class DeterministicBaselineGenerator:
    def __init__(self) -> None:
        self.contexts: list[FeedbackContext] = []

    async def generate(
        self,
        context: FeedbackContext,
        *,
        expected_provider: str,
        expected_model: str,
    ) -> GeneratedFeedback:
        self.contexts.append(context)
        assert context.retrieval_context == []
        assert context.simulation_context is None
        return GeneratedFeedback(
            feedback_content={
                "response_classification": (FeedbackResponseClassification.PARTIALLY_CORRECT.value),
                "summary": "The baseline identifies the main idea.",
                "identified_error": None,
                "explanation": "The measurement step needs more detail.",
                "improvement_actions": ["Describe the measurement outcome."],
                "recommended_next_step": "Review measurement.",
                "source_references": [],
                "simulation_references": [],
            },
            provider=expected_provider,
            model=expected_model,
            prompt_version=BASELINE_PROMPT_VERSION,
            source_references=[],
            simulation_references=[],
            token_usage=TokenUsage(
                input_tokens=12,
                output_tokens=8,
                total_tokens=20,
            ),
            estimated_cost=Decimal("0.002000"),
        )


class DeterministicBaselineJudge:
    def __init__(self) -> None:
        self.calls = 0

    async def evaluate(
        self,
        context: FeedbackContext,
        feedback: GeneratedFeedback,
    ) -> JudgeEvaluationOutcome:
        del context, feedback
        self.calls += 1
        return _judge_outcome("pass")


@dataclass(slots=True)
class E2EHarness:
    client: TestClient
    session_factory: sessionmaker[Session]
    database_path: Path
    observer: ResearchObserver
    continuation_repository: MemoryContinuationRepository
    progress: ProgressAdapter
    recommender: Recommender
    pseudonymizer: HmacSha256Pseudonymizer
    trusted_events: TrustedLearningEventHooks


def _migration_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _generated_feedback(summary: str) -> GeneratedFeedback:
    return GeneratedFeedback(
        feedback_content={
            "response_classification": (FeedbackResponseClassification.PARTIALLY_CORRECT.value),
            "summary": summary,
            "identified_error": "The measurement step is incomplete.",
            "explanation": "Connect superposition to the measurement probabilities.",
            "improvement_actions": ["Explain both possible measurement outcomes."],
            "recommended_next_step": "Review the measurement postulate.",
            "source_references": ["source-safe-1"],
            "simulation_references": ["simulation-safe-1"],
        },
        provider="deterministic-provider",
        model="deterministic-model",
        prompt_version="feedback-v2",
        source_references=["source-safe-1"],
        source_attributions=[
            FeedbackSourceAttribution(
                source_id="source-safe-1",
                label="Week 2 course notes",
            )
        ],
        simulation_references=["simulation-safe-1"],
        token_usage=TokenUsage(
            input_tokens=20,
            output_tokens=10,
            total_tokens=30,
        ),
        estimated_cost=Decimal("0.003000"),
    )


def _judge_outcome(decision: str) -> JudgeEvaluationOutcome:
    from app.models import JudgeDecision, JudgeEvaluationStatus

    typed_decision = JudgeDecision(decision)
    result = JudgeResult(
        decision=typed_decision,
        correctness_score=90,
        relevance_score=91,
        grounding_score=92,
        actionability_score=93,
        safety_score=100,
        reason="The output is grounded and actionable.",
        unsupported_claims=[],
        regeneration_instructions=([] if decision == "pass" else ["Clarify the measurement step."]),
    )
    return JudgeEvaluationOutcome(
        evaluation_status=JudgeEvaluationStatus.VALID,
        reported_decision=typed_decision,
        judge_result=result,
        reason=result.reason,
        provider="deterministic-provider",
        model="deterministic-judge",
        prompt_version="quality-judge-v1",
        quality_policy_version="quality-policy-v1",
        token_usage=TokenUsage(input_tokens=6, output_tokens=4, total_tokens=10),
        estimated_cost=Decimal("0.001000"),
    )


@pytest.fixture
def e2e_harness(tmp_path: Path) -> Generator[E2EHarness, None, None]:
    database_path = tmp_path / "person4-e2e.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    command.upgrade(_migration_config(database_url), "head")
    engine = create_db_engine(database_url)
    session_factory = create_session_factory(engine)
    pseudonymizer = HmacSha256Pseudonymizer(PSEUDONYM_SECRET)
    learning_recorder = LearningEventRecorder(
        session_factory,
        pseudonymizer,
        now=lambda: NOW,
    )
    trusted_events = TrustedLearningEventHooks(BestEffortLearningEventSink(learning_recorder))
    feedback_view_tracker = BestEffortFeedbackViewTracker(trusted_events)
    audit_sink = BestEffortAuditSink(
        lambda: IndependentAuditRecorder(session_factory)  # type: ignore[arg-type]
    )
    audit_events = FeedbackAuditEvents(audit_sink, now=lambda: NOW)
    student_audit = StudentAuditTracker(audit_events, pseudonymizer)

    continuation_repository = MemoryContinuationRepository()
    continuation = TerminalContinuationService(continuation_repository)
    dispatcher_calls: list[str] = []
    dispatcher = DatabaseResearchJobDispatcher(dispatcher_calls.append)
    observer = ResearchObserver(
        session_factory,
        pseudonymizer,
        dispatcher,
        continuation,
        fast_path=False,
    )
    terminal_integration_planner = DurableTerminalIntegrationPlanner(
        pseudonymizer,
        research_eligibility=EligibleResearch(),
        fallback_provider="deterministic-provider",
        fallback_model="deterministic-model",
    )

    task = TaskContext(
        task_id=TASK_ID,
        course_id=COURSE_ID,
        task_type="short_answer",
        prompt="Explain measurement of a qubit in superposition.",
        difficulty="introductory",
        marking_criteria="Describe the possible outcomes and probabilities.",
        learning_outcome_id="outcome-e2e",
        source_references=["source-safe-1"],
    )
    submission = SubmissionContext(
        submission_id=SUBMISSION_ID,
        task_id=TASK_ID,
        course_id=COURSE_ID,
        student_id="opaque-team-student-reference",
        attempt_number=1,
        submitted_answer=RAW_ANSWER,
        score=78,
        submitted_at=NOW,
    )
    retrieval = RetrievalContext(
        retrieval_request_id="retrieval-safe-1",
        task_id=TASK_ID,
        course_id=COURSE_ID,
        source_id="source-safe-1",
        document_id="document-safe-1",
        chunk_id="chunk-safe-1",
        chunk_text=RAW_SOURCE_CHUNK,
        relevance_score=0.95,
        source_label="Week 2 course notes",
    )
    simulation = SimulationContext(
        simulation_id="simulation-safe-1",
        task_id=TASK_ID,
        course_id=COURSE_ID,
        status="completed",
        circuit_summary="Hadamard then measurement.",
        measurement_counts={"0": 50, "1": 50},
        probability_distribution={"0": 0.5, "1": 0.5},
        error_details=RAW_SIMULATION_ERROR,
    )
    collector = DefaultFeedbackContextCollector(
        InMemoryTaskProvider({TASK_ID: task}),
        StaticRetrievalProvider({TASK_ID: [retrieval]}),
        StaticSimulationProvider({TASK_ID: simulation}),
    )
    submission_provider = InMemorySubmissionProvider({SUBMISSION_ID: submission})

    def pipeline_factory(
        repository: SqlAlchemyFeedbackWorkflowRepository,
    ) -> FeedbackPipeline:
        clock = iter([10.0, 10.2])
        return FeedbackPipeline(
            submission_provider,
            collector,
            FakeFeedbackGenerator(
                [
                    _generated_feedback("The first candidate needs revision."),
                    _generated_feedback("The revised feedback is ready."),
                ]
            ),
            FakeFeedbackJudge([_judge_outcome("fail"), _judge_outcome("pass")]),
            repository,
            clock=lambda: next(clock),
            now=lambda: NOW,
            terminal_observer=observer,
            terminal_integration_planner=terminal_integration_planner,
            audit_events=audit_events,
        )

    executor = InProcessFeedbackExecutor(
        session_factory,
        pipeline_factory,
        now=lambda: NOW,
        audit_events=audit_events,
    )
    app = create_app()
    request_sessions: list[Session] = []

    def request_session() -> Session:
        session = session_factory()
        request_sessions.append(session)
        return session

    async def actor_dependency(request: Request) -> AuthenticatedActor | None:
        role = request.headers.get("x-e2e-role", "student")
        actor_reference = {
            "student": STUDENT_ACTOR,
            "denied": "opaque-denied-subject",
            "educator": "opaque-educator-subject",
            "researcher": "opaque-researcher-subject",
            "anonymous": "",
        }[role]
        if not actor_reference:
            return None
        return AuthenticatedActor(actor_reference=actor_reference, role=role)

    def feedback_application_dependency() -> FeedbackWorkflowApplication:
        return FeedbackWorkflowApplication(
            SqlAlchemyFeedbackWorkflowRepository(request_session()),
            now=lambda: NOW,
        )

    def analytics_application_dependency() -> AnalyticsApplication:
        return AnalyticsApplication(
            SqlAlchemyAnalyticsRepository(request_session()),
            Roster(),
            pseudonymizer,
            now=lambda: NOW + timedelta(hours=1),
        )

    def export_service_dependency() -> ResearchExportService:
        return ResearchExportService(
            SqlAlchemyResearchExportRepository(request_session()),
            IndependentAuditRecorder(session_factory),  # type: ignore[arg-type]
            batch_size=1,
        )

    readiness_settings = Settings(
        database_url=database_url,
        learning_event_pseudonym_secret=SecretStr(PSEUDONYM_SECRET),
        rate_limit_enabled=False,
        csrf_enabled=False,
    )
    harness_worker_health = WorkerHealthRegistry(
        now=lambda: NOW + timedelta(hours=1),
        repository=SqlAlchemyWorkerHeartbeatRepository(engine),
    )
    assert harness_worker_health.heartbeat() is True
    readiness = ReadinessProbe(engine, readiness_settings, harness_worker_health)
    app.dependency_overrides[get_authenticated_actor] = actor_dependency
    app.dependency_overrides[get_feedback_access_policy] = FeedbackPolicy
    app.dependency_overrides[get_feedback_application] = feedback_application_dependency
    app.dependency_overrides[get_feedback_executor] = lambda: executor
    app.dependency_overrides[get_learning_event_access_policy] = LearningPolicy
    app.dependency_overrides[get_learning_event_recorder] = lambda: learning_recorder
    app.dependency_overrides[get_feedback_view_tracker] = lambda: feedback_view_tracker
    app.dependency_overrides[get_student_audit_tracker] = lambda: student_audit
    app.dependency_overrides[get_analytics_access_policy] = AnalyticsPolicy
    app.dependency_overrides[get_analytics_application] = analytics_application_dependency
    app.dependency_overrides[get_analytics_pseudonymizer] = lambda: pseudonymizer
    app.dependency_overrides[get_research_export_access_policy] = ExportPolicy
    app.dependency_overrides[get_research_export_service] = export_service_dependency
    app.dependency_overrides[get_readiness_probe] = lambda: readiness
    progress = ProgressAdapter()
    recommender = Recommender()

    with TestClient(app) as client:
        yield E2EHarness(
            client=client,
            session_factory=session_factory,
            database_path=database_path,
            observer=observer,
            continuation_repository=continuation_repository,
            progress=progress,
            recommender=recommender,
            pseudonymizer=pseudonymizer,
            trusted_events=trusted_events,
        )

    app.dependency_overrides.clear()
    for request_session_instance in request_sessions:
        request_session_instance.close()
    engine.dispose()


def test_person4_deterministic_end_to_end(
    e2e_harness: E2EHarness,
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = e2e_harness.client
    event_correlation = str(uuid4())
    view_event_id = str(uuid4())
    draft_event_id = str(uuid4())
    response_texts: list[str] = []

    denied = client.post(
        f"/api/v1/submissions/{SUBMISSION_ID}/feedback",
        headers={"x-e2e-role": "denied"},
    )
    assert denied.status_code == 404
    assert SUBMISSION_ID not in denied.text
    response_texts.append(denied.text)

    for payload in (
        {
            "event_id": view_event_id,
            "event_type": "task_view",
            "task_id": TASK_ID,
            "metadata": {"source": "canonical-task-page"},
        },
        {
            "event_id": draft_event_id,
            "event_type": "draft_save",
            "task_id": TASK_ID,
            "metadata": {"duration_ms": 1500},
        },
    ):
        event_response = client.post(
            "/api/v1/learning-events",
            json=payload,
            headers={
                "x-e2e-role": "student",
                "x-correlation-id": event_correlation,
            },
        )
        assert event_response.status_code == 201
        response_texts.append(event_response.text)

    replay = client.post(
        "/api/v1/learning-events",
        json={
            "event_id": view_event_id,
            "event_type": "task_view",
            "task_id": TASK_ID,
            "metadata": {"source": "canonical-task-page"},
        },
        headers={
            "x-e2e-role": "student",
            "x-correlation-id": event_correlation,
        },
    )
    assert replay.status_code == 200

    submission_event_id = str(uuid4())
    completion_event_id = str(uuid4())
    assert (
        e2e_harness.trusted_events.record_submission(
            actor_reference=STUDENT_ACTOR,
            course_id=COURSE_ID,
            task_id=TASK_ID,
            source_event_id=submission_event_id,
            correlation_id=event_correlation,
            attempt_number=1,
            score=78,
        )
        is not None
    )

    start_correlation = str(uuid4())
    start = client.post(
        f"/api/v1/submissions/{SUBMISSION_ID}/feedback",
        headers={
            "x-e2e-role": "student",
            "x-correlation-id": start_correlation,
        },
    )
    assert start.status_code == 202
    assert start.headers["x-correlation-id"] == start_correlation
    assert start.json()["status"] == "processing"
    workflow_id = start.json()["workflow_run_id"]
    response_texts.append(start.text)

    view_correlation = str(uuid4())
    first_view = client.get(
        f"/api/v1/submissions/{SUBMISSION_ID}/feedback",
        headers={
            "x-e2e-role": "student",
            "x-correlation-id": view_correlation,
        },
    )
    second_view = client.get(
        f"/api/v1/submissions/{SUBMISSION_ID}/feedback",
        headers={
            "x-e2e-role": "student",
            "x-correlation-id": view_correlation,
        },
    )
    assert first_view.status_code == second_view.status_code == 200
    assert first_view.json()["status"] == "validated"
    assert first_view.json()["feedback"]["summary"] == ("The revised feedback is ready.")
    assert first_view.json() == second_view.json()
    feedback_id = first_view.json()["feedback"]["feedback_id"]
    response_texts.extend([first_view.text, second_view.text])

    with e2e_harness.session_factory() as session:
        reconciliation = TerminalIntegrationWorker(
            session,
            now=lambda: NOW + timedelta(seconds=1),
        )
        assert asyncio.run(reconciliation.run_once()).processed is True
        assert asyncio.run(reconciliation.run_once()).processed is True
        assert set(session.scalars(select(TerminalIntegrationOutbox.state))) == {
            TerminalIntegrationState.COMPLETED
        }
        assert session.scalar(select(func.count()).select_from(ResearchEvaluation)) == 2
        assert session.scalar(select(func.count()).select_from(ContinuationJob)) == 1

    report_correlation = str(uuid4())
    report_payload = {
        "category": "citation_issue",
        "note": "Please review the source label.",
    }
    first_report = client.post(
        f"/api/v1/feedback/{feedback_id}/report",
        json=report_payload,
        headers={
            "x-e2e-role": "student",
            "x-correlation-id": report_correlation,
        },
    )
    second_report = client.post(
        f"/api/v1/feedback/{feedback_id}/report",
        json=report_payload,
        headers={
            "x-e2e-role": "student",
            "x-correlation-id": report_correlation,
        },
    )
    assert first_report.status_code == 201
    assert second_report.status_code == 200
    assert first_report.json() == second_report.json()
    response_texts.extend([first_report.text, second_report.text])

    assert (
        e2e_harness.trusted_events.record_completion(
            actor_reference=STUDENT_ACTOR,
            course_id=COURSE_ID,
            task_id=TASK_ID,
            source_event_id=completion_event_id,
            correlation_id=event_correlation,
            completion_status="passed",
            score=78,
        )
        is not None
    )

    with e2e_harness.session_factory() as session:
        research_repository = SqlAlchemyResearchJobRepository(session)
        original_claim = research_repository.claim_next(now=NOW)
    assert original_claim is not None
    with e2e_harness.session_factory() as session:
        research_repository = SqlAlchemyResearchJobRepository(session)
        restarted_claim = research_repository.claim_next(now=NOW + timedelta(minutes=6))
    assert restarted_claim is not None
    assert restarted_claim.execution_token != original_claim.execution_token
    with e2e_harness.session_factory() as session:
        research_repository = SqlAlchemyResearchJobRepository(session)
        assert (
            research_repository.fail(
                original_claim,
                "stale-worker-private-error",
                completed_at=NOW + timedelta(minutes=6),
            )
            is False
        )

    baseline_generator = DeterministicBaselineGenerator()
    baseline_judge = DeterministicBaselineJudge()
    clock = iter([1.0, 1.15, 2.0, 2.025])
    with e2e_harness.session_factory() as session:
        baseline_worker = BaselineJobExecutor(
            SqlAlchemyResearchJobRepository(session),
            BaselineContextProvider(e2e_harness.observer.contexts),
            baseline_generator,
            baseline_judge,
            now=lambda: NOW + timedelta(minutes=12),
            clock=lambda: next(clock),
        )
        assert asyncio.run(baseline_worker.run_once()) is True
    assert baseline_judge.calls == 1
    assert len(baseline_generator.contexts) == 1
    assert baseline_generator.contexts[0].retrieval_context == []
    assert baseline_generator.contexts[0].simulation_context is None

    notice = e2e_harness.observer.notices[workflow_id]
    replay_receipt = TerminalContinuationService(
        e2e_harness.continuation_repository
    ).after_terminal_feedback(notice)
    assert replay_receipt.accepted is True
    continuation_outcome = asyncio.run(
        ContinuationWorker(
            e2e_harness.continuation_repository,
            e2e_harness.progress,
            e2e_harness.recommender,
            now=lambda: NOW,
        ).run_once()
    )
    assert continuation_outcome.state is ContinuationState.COMPLETED
    continuation = ContinuationQueryService(e2e_harness.continuation_repository).get(workflow_id)
    assert continuation.status is ContinuationAvailability.READY
    assert continuation.next_task_reference == "team-recommender:next-task-opaque"
    assert e2e_harness.progress.idempotency_keys == {workflow_id}
    assert len(e2e_harness.progress.calls) == 1
    assert len(e2e_harness.recommender.calls) == 1

    with e2e_harness.session_factory() as session:
        feedback_repository = SqlAlchemyFeedbackWorkflowRepository(session)
        first_claim = feedback_repository.claim_workflow(
            "submission-restart-e2e",
            str(uuid4()),
            started_at=NOW,
            lease_expires_at=NOW + timedelta(minutes=5),
        )
        assert first_claim.execution_token is not None
        feedback_repository.record_stage(
            first_claim.workflow_run_id,
            WorkflowStage.GENERATING,
            execution_token=first_claim.execution_token,
            lease_expires_at=NOW + timedelta(minutes=5),
        )
        recovered_claim = feedback_repository.claim_workflow(
            "submission-restart-e2e",
            str(uuid4()),
            started_at=NOW + timedelta(minutes=6),
            lease_expires_at=NOW + timedelta(minutes=11),
        )
        assert recovered_claim.should_start is True
        assert recovered_claim.execution_token != first_claim.execution_token
        with pytest.raises(LostWorkflowLeaseError):
            feedback_repository.record_stage(
                first_claim.workflow_run_id,
                WorkflowStage.JUDGING,
                execution_token=first_claim.execution_token,
                lease_expires_at=NOW + timedelta(minutes=12),
            )

    range_parameters = {
        "course_id": COURSE_ID,
        "date_from": (NOW - timedelta(days=1)).isoformat(),
        "date_to": (NOW + timedelta(days=1)).isoformat(),
    }
    learning = client.get(
        "/api/v1/analytics/learning",
        params=range_parameters,
        headers={"x-e2e-role": "educator"},
    )
    research = client.get(
        "/api/v1/analytics/research",
        params=range_parameters,
        headers={"x-e2e-role": "educator"},
    )
    filters = client.get(
        "/api/v1/analytics/filter-options",
        headers={"x-e2e-role": "educator"},
    )
    inactive = client.get(
        "/api/v1/analytics/inactive-learners",
        params={**range_parameters, "page": 1, "page_size": 100},
        headers={"x-e2e-role": "educator"},
    )
    assert learning.status_code == research.status_code == 200
    assert filters.status_code == inactive.status_code == 200
    assert learning.json()["schema_version"] == "learning-metrics-v1"
    assert learning.json()["completion_rate"]["value"] == 1
    assert learning.json()["feedback_view_rate"]["value"] == 1
    assert [stage["count"] for stage in learning.json()["funnel"]] == [
        1,
        1,
        1,
        1,
        1,
    ]
    assert research.json()["schema_version"] == "research-metrics-v1"
    assert research.json()["regeneration_success_rate"]["value"] == 1
    assert research.json()["paired_agentic_minus_baseline"]["pass_rate"]["sample_size"] == 1
    assert filters.json()["courses"] == [COURSE_ID]
    inactive_ids = {item["pseudonymous_user_id"] for item in inactive.json()["items"]}
    assert (
        e2e_harness.pseudonymizer.pseudonymize(
            "learning-actor",
            "opaque-never-active-subject",
        )
        in inactive_ids
    )
    response_texts.extend([learning.text, research.text, filters.text, inactive.text])

    cross_course = client.get(
        "/api/v1/analytics/research",
        params={"course_id": "course-private-sentinel"},
        headers={"x-e2e-role": "educator"},
    )
    assert cross_course.status_code == 403
    assert "course-private-sentinel" not in cross_course.text

    json_export = client.get(
        "/api/v1/research/exports",
        params={"format": "json", **range_parameters},
        headers={"x-e2e-role": "researcher"},
    )
    csv_export = client.get(
        "/api/v1/research/exports",
        params={"format": "csv", **range_parameters},
        headers={"x-e2e-role": "researcher"},
    )
    assert json_export.status_code == csv_export.status_code == 200
    assert json_export.headers["cache-control"] == "no-store"
    json_body = json_export.json()
    assert json_body["schema_version"] == "quantumlearn.research-export.v1"
    assert json_body["record_count"] == 2
    assert {row["experimental_condition"] for row in json_body["records"]} == {
        condition.value for condition in ExperimentalCondition
    }
    csv_rows = list(csv.DictReader(io.StringIO(csv_export.content.decode("utf-8-sig"))))
    assert len(csv_rows) == 2
    assert {row["experimental_condition"] for row in csv_rows} == {
        condition.value for condition in ExperimentalCondition
    }
    response_texts.extend([json_export.text, csv_export.text])

    health = client.get("/api/v1/health")
    readiness = client.get("/api/v1/ready")
    assert health.json() == {"status": "ok"}
    assert readiness.status_code == 200
    assert readiness.json()["status"] == "ready"

    with e2e_harness.session_factory() as session:
        research_rows = list(
            session.scalars(
                select(ResearchEvaluation)
                .where(ResearchEvaluation.case_id == workflow_id)
                .order_by(ResearchEvaluation.experimental_condition)
            )
        )
        assert len(research_rows) == 2
        baseline = next(
            row
            for row in research_rows
            if row.experimental_condition is ExperimentalCondition.SINGLE_STEP_BASELINE
        )
        agentic = next(
            row
            for row in research_rows
            if row.experimental_condition is ExperimentalCondition.AGENTIC_RAG
        )
        assert baseline.provider == agentic.provider
        assert baseline.model == agentic.model
        assert baseline.input_references == []
        assert baseline.retrieved_sources == []
        assert baseline.simulation_reference is None
        assert baseline.prompt_version == BASELINE_PROMPT_VERSION
        assert baseline.evaluation_total_tokens == 10
        assert agentic.regeneration_count == 1
        assert agentic.retrieval_hit_count == 1

        feedback_views = session.scalar(
            select(func.count())
            .select_from(LearningEvent)
            .where(LearningEvent.event_type == LearningEventType.FEEDBACK_VIEW)
        )
        assert feedback_views == 1
        action_counts = dict(
            session.execute(
                select(AuditEvent.action, func.count()).group_by(AuditEvent.action)
            ).all()
        )
        assert action_counts[AuditAction.FEEDBACK_GENERATION_STARTED] == 1
        assert action_counts[AuditAction.FEEDBACK_GENERATION_COMPLETED] == 2
        assert action_counts[AuditAction.FEEDBACK_JUDGED] == 2
        assert action_counts[AuditAction.FEEDBACK_REGENERATED] == 1
        assert action_counts[AuditAction.FEEDBACK_VIEWED] == 1
        assert action_counts[AuditAction.FEEDBACK_REPORTED] == 1
        assert action_counts[AuditAction.WORKFLOW_COMPLETED] == 1
        assert action_counts[AuditAction.RESEARCH_EXPORT_CREATED] == 2
        audit_resources = session.execute(
            select(
                AuditEvent.actor_reference,
                AuditEvent.resource_type,
                AuditEvent.resource_id,
                AuditEvent.failure_category,
            )
        ).all()
        assert all(SUBMISSION_ID not in repr(row) for row in audit_resources)
        assert session.get(WorkflowRun, workflow_id) is not None

    privacy_surfaces = "\n".join(response_texts) + "\n" + caplog.text
    database_bytes = e2e_harness.database_path.read_bytes()
    for forbidden in (
        RAW_ANSWER,
        RAW_SOURCE_CHUNK,
        RAW_SIMULATION_ERROR,
        STUDENT_ACTOR,
    ):
        assert forbidden not in privacy_surfaces
        assert forbidden.encode() not in database_bytes

    serialized_exports = json.dumps(json_body, sort_keys=True) + csv_export.text
    assert RAW_ANSWER not in serialized_exports
    assert RAW_SOURCE_CHUNK not in serialized_exports
    assert RAW_SIMULATION_ERROR not in serialized_exports
