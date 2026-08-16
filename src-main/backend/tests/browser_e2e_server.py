from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import uvicorn
from alembic import command
from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_assessor_review_api import _assign_assessor, _decision_context
from test_person4_e2e import (
    COURSE_ID,
    NOW,
    PSEUDONYM_SECRET,
    STUDENT_ACTOR,
    SUBMISSION_ID,
    TASK_ID,
    BaselineContextProvider,
    DeterministicBaselineGenerator,
    DeterministicBaselineJudge,
    EligibleResearch,
    MemoryContinuationRepository,
    ResearchObserver,
    _generated_feedback,
    _judge_outcome,
    _migration_config,
)

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
from app.api.security_dependencies import get_request_security_guard
from app.db.session import create_db_engine, create_session_factory, get_db
from app.main import create_app
from app.models import (
    ContinuationJob,
    LearningEventType,
    ResearchEvaluation,
    TerminalIntegrationOutbox,
    TerminalIntegrationState,
)
from app.schemas.feedback import (
    RetrievalContext,
    SimulationContext,
    SubmissionContext,
    TaskContext,
)
from app.schemas.feedback_api import AuthenticatedActor
from app.services.analytics import AnalyticsApplication, SqlAlchemyAnalyticsRepository
from app.services.audit import BestEffortAuditSink, IndependentAuditRecorder
from app.services.audit_events import FeedbackAuditEvents, StudentAuditTracker
from app.services.continuation import TerminalContinuationService
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
from app.services.learning_events import (
    BestEffortFeedbackViewTracker,
    BestEffortLearningEventSink,
    HmacSha256Pseudonymizer,
    LearningEventCommand,
    LearningEventRecorder,
    LearningEventScope,
    TrustedLearningEventHooks,
)
from app.services.lms import bootstrap_demo
from app.services.research import (
    BaselineJobExecutor,
    DatabaseResearchJobDispatcher,
    SqlAlchemyResearchJobRepository,
)
from app.services.research_export import ResearchExportService
from app.services.research_export_repository import SqlAlchemyResearchExportRepository
from app.services.terminal_integrations.planner import (
    DurableTerminalIntegrationPlanner,
)
from app.services.terminal_integrations.worker import TerminalIntegrationWorker

API_HOST = "127.0.0.1"
API_PORT = int(os.environ.get("QUANTUMLEARN_E2E_API_PORT", "4180"))
CORRELATION_ID = "2db966be-63ed-43cf-b783-04f8ad027b47"


class BrowserFeedbackPolicy:
    async def can_access_submission(
        self,
        actor: AuthenticatedActor,
        submission_id: str,
    ) -> bool:
        return actor.actor_reference == STUDENT_ACTOR and submission_id == SUBMISSION_ID


class BrowserLearningPolicy:
    async def resolve_task_scope(
        self,
        actor: AuthenticatedActor,
        task_id: str,
    ) -> LearningEventScope | None:
        if actor.actor_reference != STUDENT_ACTOR or task_id != TASK_ID:
            return None
        return LearningEventScope(course_id=COURSE_ID, task_id=TASK_ID)


class BrowserAnalyticsPolicy:
    async def authorized_course_ids(self, actor_reference: str) -> set[str]:
        return {COURSE_ID} if actor_reference == STUDENT_ACTOR else set()


class BrowserExportPolicy:
    async def authorized_course_ids(
        self,
        actor: AuthenticatedActor,
    ) -> set[str]:
        return {COURSE_ID} if actor.actor_reference == STUDENT_ACTOR else set()


class BrowserRoster:
    async def learner_references(self, course_ids: set[str]) -> list[str]:
        assert course_ids == {COURSE_ID}
        return [STUDENT_ACTOR, "opaque-never-active-browser-subject"]


class BrowserSecurityGuard:
    async def enforce(
        self,
        request: Request,
        actor: AuthenticatedActor,
        bucket: str,
        *,
        mutating: bool,
    ) -> None:
        del request, actor, bucket, mutating


def _pipeline_factory(
    submission_provider: InMemorySubmissionProvider,
    collector: DefaultFeedbackContextCollector,
    observer: ResearchObserver,
    terminal_integration_planner: DurableTerminalIntegrationPlanner,
    audit_events: FeedbackAuditEvents,
):
    def create(repository: SqlAlchemyFeedbackWorkflowRepository) -> FeedbackPipeline:
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

    return create


def _seed_learning_events(
    recorder: LearningEventRecorder,
    hooks: TrustedLearningEventHooks,
    workflow_run_id: str,
) -> None:
    for event_type, metadata in (
        (LearningEventType.TASK_VIEW, {"source": "browser-e2e"}),
        (LearningEventType.DRAFT_SAVE, {"duration_ms": 1500}),
    ):
        recorder.record(
            LearningEventCommand(
                actor_reference=STUDENT_ACTOR,
                course_id=COURSE_ID,
                task_id=TASK_ID,
                event_type=event_type,
                client_event_id=str(uuid4()),
                correlation_id=CORRELATION_ID,
                metadata=metadata,
            )
        )
    hooks.record_submission(
        actor_reference=STUDENT_ACTOR,
        course_id=COURSE_ID,
        task_id=TASK_ID,
        source_event_id=str(uuid4()),
        correlation_id=CORRELATION_ID,
        attempt_number=1,
        score=78,
    )
    hooks.record_feedback_view(
        actor_reference=STUDENT_ACTOR,
        course_id=COURSE_ID,
        task_id=TASK_ID,
        workflow_run_id=workflow_run_id,
        correlation_id=CORRELATION_ID,
        feedback_status="validated",
    )
    hooks.record_completion(
        actor_reference=STUDENT_ACTOR,
        course_id=COURSE_ID,
        task_id=TASK_ID,
        source_event_id=str(uuid4()),
        correlation_id=CORRELATION_ID,
        completion_status="passed",
        score=78,
    )


def _build_app(database_url: str):
    command.upgrade(_migration_config(database_url), "head")
    engine = create_db_engine(database_url)
    session_factory = create_session_factory(engine)
    with session_factory() as demo_session:
        demo_users, _ = bootstrap_demo(demo_session)
        demo_educator = next(
            user for user in demo_users if user.email == "educator@quantumlearn.demo"
        )
        assessment_attempt, _, _, assessment_owner = _decision_context(demo_session)
        _assign_assessor(
            demo_session,
            demo_educator,
            assessment_attempt.course_id,
            assessment_owner,
        )
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
    observer = ResearchObserver(
        session_factory,
        pseudonymizer,
        DatabaseResearchJobDispatcher(lambda _: None),
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
        submitted_answer="browser-e2e-transient-answer",
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
        chunk_text="Transient browser E2E retrieval context.",
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
    )
    collector = DefaultFeedbackContextCollector(
        InMemoryTaskProvider({TASK_ID: task}),
        StaticRetrievalProvider({TASK_ID: [retrieval]}),
        StaticSimulationProvider({TASK_ID: simulation}),
    )
    submission_provider = InMemorySubmissionProvider({SUBMISSION_ID: submission})
    executor = InProcessFeedbackExecutor(
        session_factory,
        _pipeline_factory(
            submission_provider,
            collector,
            observer,
            terminal_integration_planner,
            audit_events,
        ),
        now=lambda: NOW,
        audit_events=audit_events,
    )

    with session_factory() as session:
        claim = FeedbackWorkflowApplication(
            SqlAlchemyFeedbackWorkflowRepository(session),
            now=lambda: NOW,
        ).start(SUBMISSION_ID)
    if claim.execution_token is None:
        raise RuntimeError("browser E2E workflow did not acquire an execution token")
    asyncio.run(
        executor.execute(
            claim.workflow_run_id,
            SUBMISSION_ID,
            claim.execution_token,
            CORRELATION_ID,
        )
    )
    with session_factory() as session:
        reconciliation = TerminalIntegrationWorker(
            session,
            now=lambda: NOW + timedelta(seconds=1),
        )
        if not asyncio.run(reconciliation.run_once()).processed:
            raise RuntimeError("browser E2E terminal integration was not reconciled")
        if not asyncio.run(reconciliation.run_once()).processed:
            raise RuntimeError("browser E2E terminal integration was not reconciled")
        outbox_states = set(session.scalars(select(TerminalIntegrationOutbox.state)))
        research_count = session.scalar(select(func.count()).select_from(ResearchEvaluation))
        continuation_count = session.scalar(select(func.count()).select_from(ContinuationJob))
    if outbox_states != {TerminalIntegrationState.COMPLETED}:
        raise RuntimeError("browser E2E terminal outbox did not complete")
    if research_count != 2 or continuation_count != 1:
        raise RuntimeError("browser E2E terminal integrations were incomplete")

    baseline_generator = DeterministicBaselineGenerator()
    baseline_judge = DeterministicBaselineJudge()
    baseline_clock = iter([1.0, 1.15, 2.0, 2.025])
    with session_factory() as session:
        completed = asyncio.run(
            BaselineJobExecutor(
                SqlAlchemyResearchJobRepository(session),
                BaselineContextProvider(observer.contexts),
                baseline_generator,
                baseline_judge,
                now=lambda: NOW + timedelta(minutes=1),
                clock=lambda: next(baseline_clock),
            ).run_once()
        )
    if not completed or baseline_judge.calls != 1:
        raise RuntimeError("browser E2E baseline case was not completed")
    _seed_learning_events(learning_recorder, trusted_events, claim.workflow_run_id)

    app = create_app()

    def request_database_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    async def actor_dependency() -> AuthenticatedActor:
        return AuthenticatedActor(
            actor_reference=STUDENT_ACTOR,
            role="browser-e2e",
        )

    def feedback_application_dependency() -> Generator[FeedbackWorkflowApplication, None, None]:
        with session_factory() as session:
            yield FeedbackWorkflowApplication(
                SqlAlchemyFeedbackWorkflowRepository(session),
                now=lambda: NOW + timedelta(minutes=2),
            )

    def analytics_application_dependency() -> Generator[AnalyticsApplication, None, None]:
        with session_factory() as session:
            yield AnalyticsApplication(
                SqlAlchemyAnalyticsRepository(session),
                BrowserRoster(),
                pseudonymizer,
                now=lambda: NOW + timedelta(hours=1),
            )

    def export_service_dependency() -> Generator[ResearchExportService, None, None]:
        with session_factory() as session:
            yield ResearchExportService(
                SqlAlchemyResearchExportRepository(session),
                IndependentAuditRecorder(session_factory),  # type: ignore[arg-type]
                batch_size=1,
            )

    app.dependency_overrides[get_authenticated_actor] = actor_dependency
    app.dependency_overrides[get_db] = request_database_session
    app.dependency_overrides[get_feedback_access_policy] = BrowserFeedbackPolicy
    app.dependency_overrides[get_feedback_application] = feedback_application_dependency
    app.dependency_overrides[get_feedback_executor] = lambda: executor
    app.dependency_overrides[get_learning_event_access_policy] = BrowserLearningPolicy
    app.dependency_overrides[get_learning_event_recorder] = lambda: learning_recorder
    app.dependency_overrides[get_feedback_view_tracker] = lambda: feedback_view_tracker
    app.dependency_overrides[get_student_audit_tracker] = lambda: student_audit
    app.dependency_overrides[get_analytics_access_policy] = BrowserAnalyticsPolicy
    app.dependency_overrides[get_analytics_application] = analytics_application_dependency
    app.dependency_overrides[get_analytics_pseudonymizer] = lambda: pseudonymizer
    app.dependency_overrides[get_research_export_access_policy] = BrowserExportPolicy
    app.dependency_overrides[get_research_export_service] = export_service_dependency
    app.dependency_overrides[get_request_security_guard] = BrowserSecurityGuard

    def close_resources() -> None:
        engine.dispose()

    app.state.browser_e2e_cleanup = close_resources
    return app


def main() -> None:
    temporary = TemporaryDirectory(prefix="quantumlearn-browser-e2e-")
    database_path = Path(temporary.name) / "browser-e2e.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    app = None
    try:
        app = _build_app(database_url)
        uvicorn.run(
            app,
            host=API_HOST,
            port=API_PORT,
            log_level="warning",
            access_log=False,
        )
    finally:
        cleanup = getattr(getattr(app, "state", None), "browser_e2e_cleanup", None)
        if callable(cleanup):
            cleanup()
        temporary.cleanup()


if __name__ == "__main__":
    main()
