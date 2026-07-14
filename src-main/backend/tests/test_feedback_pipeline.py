import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import (
    FeedbackRecord,
    FeedbackStatus,
    JudgeDecision,
    JudgeEvaluation,
    WorkflowOutcome,
    WorkflowRun,
    WorkflowStage,
)
from app.schemas.feedback import (
    FeedbackPipelineResult,
    FeedbackPipelineStatus,
    GeneratedFeedback,
    JudgeResult,
    RetrievalContext,
    SimulationContext,
    SubmissionContext,
    TaskContext,
    TokenUsage,
)
from app.services.feedback import (
    ContextCollectionError,
    DefaultFeedbackContextCollector,
    FakeFeedbackGenerator,
    FakeFeedbackJudge,
    FeedbackGenerationError,
    FeedbackJudgementError,
    FeedbackPipeline,
    InMemorySubmissionProvider,
    InMemoryTaskProvider,
    PipelinePersistenceError,
    PipelinePersistenceRequest,
    SqlAlchemyFeedbackWorkflowRepository,
    StaticRetrievalProvider,
    StaticSimulationProvider,
    SubmissionNotFoundError,
    TaskNotFoundError,
)


STARTED_AT = datetime(2026, 7, 13, 10, 0, tzinfo=timezone.utc)
COMPLETED_AT = STARTED_AT + timedelta(milliseconds=125)


def submission() -> SubmissionContext:
    return SubmissionContext(
        submission_id="submission-1",
        task_id="task-1",
        student_id="student-pseudonym",
        attempt_number=1,
        submitted_answer="A qubit can be in a combination of zero and one.",
        score=0.8,
        submitted_at=STARTED_AT,
    )


def task() -> TaskContext:
    return TaskContext(
        task_id="task-1",
        course_id="course-1",
        task_type="short_answer",
        prompt="Explain a qubit.",
        difficulty="introductory",
        marking_criteria="Describe a two-state quantum system and superposition.",
        learning_outcome_id="outcome-1",
        source_references=["source-1"],
    )


def generated_feedback() -> GeneratedFeedback:
    return GeneratedFeedback(
        feedback_content={
            "summary": "The response correctly identifies superposition.",
            "recommended_next_step": "Explain how measurement changes the state.",
        },
        model="fake-feedback-model",
        source_references=["source-1"],
        simulation_references=["simulation-1"],
        token_usage=TokenUsage(input_tokens=20, output_tokens=10, total_tokens=30),
        estimated_cost=Decimal("0.001500"),
    )


def judge_result(decision: JudgeDecision = JudgeDecision.PASS) -> JudgeResult:
    return JudgeResult(
        decision=decision,
        correctness_score=90,
        relevance_score=91,
        grounding_score=92,
        actionability_score=93,
        safety_score=100,
        reason="The feedback is grounded and actionable.",
        unsupported_claims=[],
        regeneration_instructions=[] if decision is JudgeDecision.PASS else ["Be more precise."],
    )


def retrieval_context() -> RetrievalContext:
    return RetrievalContext(
        retrieval_request_id="retrieval-1",
        source_id="source-1",
        document_id="document-1",
        chunk_id="chunk-1",
        chunk_text="A qubit is a two-state quantum system.",
        relevance_score=0.95,
        source_label="Course notes",
    )


def simulation_context() -> SimulationContext:
    return SimulationContext(
        simulation_id="simulation-1",
        status="completed",
        circuit_summary="One Hadamard gate followed by measurement.",
        measurement_counts={"0": 50, "1": 50},
        probability_distribution={"0": 0.5, "1": 0.5},
    )


def run(coroutine: object) -> FeedbackPipelineResult:
    return asyncio.run(coroutine)  # type: ignore[arg-type,return-value]


def table_count(db_session: Session, model: type[object]) -> int:
    return db_session.scalar(select(func.count()).select_from(model)) or 0


def build_pipeline(
    db_session: Session,
    *,
    submissions: dict[str, SubmissionContext] | None = None,
    tasks: dict[str, TaskContext] | None = None,
    generator_error: Exception | None = None,
    judge_error: Exception | None = None,
    decision: JudgeDecision = JudgeDecision.PASS,
    repository: SqlAlchemyFeedbackWorkflowRepository | None = None,
) -> tuple[
    FeedbackPipeline,
    InMemorySubmissionProvider,
    InMemoryTaskProvider,
    FakeFeedbackGenerator,
    FakeFeedbackJudge,
]:
    submission_provider = InMemorySubmissionProvider(
        submissions if submissions is not None else {"submission-1": submission()}
    )
    task_provider = InMemoryTaskProvider(tasks if tasks is not None else {"task-1": task()})
    retrieval_provider = StaticRetrievalProvider({"task-1": [retrieval_context()]})
    simulation_provider = StaticSimulationProvider({"task-1": simulation_context()})
    collector = DefaultFeedbackContextCollector(
        task_provider,
        retrieval_provider,
        simulation_provider,
    )
    generator = FakeFeedbackGenerator(generated_feedback(), generator_error)
    judge = FakeFeedbackJudge(judge_result(decision), judge_error)
    clock_values = iter([10.0, 10.125])
    now_values = iter([STARTED_AT, COMPLETED_AT])
    pipeline = FeedbackPipeline(
        submission_provider,
        collector,
        generator,
        judge,
        repository or SqlAlchemyFeedbackWorkflowRepository(db_session),
        clock=lambda: next(clock_values),
        now=lambda: next(now_values),
    )
    return pipeline, submission_provider, task_provider, generator, judge


def test_successful_pipeline_persists_and_returns_validated_feedback(db_session: Session) -> None:
    pipeline, _, _, generator, judge = build_pipeline(db_session)

    result = run(pipeline.run("submission-1"))

    assert result.status is FeedbackPipelineStatus.VALIDATED
    assert result.validated_feedback == generated_feedback()
    assert result.latency_ms == 125
    assert result.token_usage.total_tokens == 30
    assert result.estimated_cost == Decimal("0.001500")
    assert result.source_references == ["source-1"]
    assert result.idempotent_replay is False
    assert generator.call_count == 1
    assert judge.call_count == 1
    assert generator.contexts[0].correlation_id == result.workflow_run_id
    assert generator.contexts[0].retrieval_context == [retrieval_context()]
    assert generator.contexts[0].simulation_context == simulation_context()

    workflow = db_session.get(WorkflowRun, result.workflow_run_id)
    feedback = db_session.get(FeedbackRecord, result.feedback_id)
    assert workflow is not None
    assert workflow.current_stage is WorkflowStage.COMPLETED
    assert workflow.final_outcome is WorkflowOutcome.FIRST_PASS
    assert feedback is not None
    assert feedback.workflow_run_id == result.workflow_run_id
    assert feedback.status is FeedbackStatus.ACCEPTED
    assert feedback.generation_attempt == 1
    assert feedback.judge_evaluation is not None
    assert feedback.judge_evaluation.decision is JudgeDecision.PASS


def test_duplicate_request_returns_stored_result_without_provider_calls(
    db_session: Session,
) -> None:
    pipeline, submission_provider, task_provider, generator, judge = build_pipeline(db_session)
    first = run(pipeline.run("submission-1"))
    second = run(pipeline.run("submission-1"))

    assert second.workflow_run_id == first.workflow_run_id
    assert second.feedback_id == first.feedback_id
    assert second.idempotent_replay is True
    assert submission_provider.call_count == 1
    assert task_provider.call_count == 1
    assert generator.call_count == 1
    assert judge.call_count == 1
    assert table_count(db_session, WorkflowRun) == 1
    assert table_count(db_session, FeedbackRecord) == 1
    assert table_count(db_session, JudgeEvaluation) == 1


def test_missing_submission_stores_nothing(db_session: Session) -> None:
    pipeline, _, _, generator, judge = build_pipeline(db_session, submissions={})

    with pytest.raises(SubmissionNotFoundError):
        run(pipeline.run("missing-submission"))

    assert generator.call_count == 0
    assert judge.call_count == 0
    assert table_count(db_session, WorkflowRun) == 0


def test_missing_task_stores_nothing(db_session: Session) -> None:
    pipeline, _, _, generator, judge = build_pipeline(db_session, tasks={})

    with pytest.raises(TaskNotFoundError):
        run(pipeline.run("submission-1"))

    assert generator.call_count == 0
    assert judge.call_count == 0
    assert table_count(db_session, WorkflowRun) == 0


def test_empty_optional_context_is_valid(db_session: Session) -> None:
    submission_provider = InMemorySubmissionProvider({"submission-1": submission()})
    task_provider = InMemoryTaskProvider({"task-1": task()})
    collector = DefaultFeedbackContextCollector(task_provider)
    generator = FakeFeedbackGenerator(generated_feedback())
    judge = FakeFeedbackJudge(judge_result())
    clock_values = iter([1.0, 1.0])
    now_values = iter([STARTED_AT, STARTED_AT])
    pipeline = FeedbackPipeline(
        submission_provider,
        collector,
        generator,
        judge,
        SqlAlchemyFeedbackWorkflowRepository(db_session),
        clock=lambda: next(clock_values),
        now=lambda: next(now_values),
    )

    run(pipeline.run("submission-1"))

    assert generator.contexts[0].retrieval_context == []
    assert generator.contexts[0].simulation_context is None


def test_context_provider_failure_is_controlled_and_private(db_session: Session) -> None:
    class FailingTaskProvider:
        async def get_task(self, task_id: str) -> TaskContext | None:
            raise RuntimeError(submission().submitted_answer)

    submission_provider = InMemorySubmissionProvider({"submission-1": submission()})
    collector = DefaultFeedbackContextCollector(FailingTaskProvider())
    generator = FakeFeedbackGenerator(generated_feedback())
    judge = FakeFeedbackJudge(judge_result())
    pipeline = FeedbackPipeline(
        submission_provider,
        collector,
        generator,
        judge,
        SqlAlchemyFeedbackWorkflowRepository(db_session),
    )

    with pytest.raises(ContextCollectionError) as caught:
        run(pipeline.run("submission-1"))

    assert submission().submitted_answer not in str(caught.value)
    assert caught.value.__cause__ is None
    assert table_count(db_session, WorkflowRun) == 0


@pytest.mark.parametrize(
    ("generator_error", "judge_error", "expected_error"),
    [
        (RuntimeError("generator unavailable"), None, FeedbackGenerationError),
        (None, RuntimeError("judge unavailable"), FeedbackJudgementError),
    ],
)
def test_provider_failures_are_controlled_and_store_nothing(
    db_session: Session,
    generator_error: Exception | None,
    judge_error: Exception | None,
    expected_error: type[Exception],
) -> None:
    pipeline, _, _, _, _ = build_pipeline(
        db_session,
        generator_error=generator_error,
        judge_error=judge_error,
    )

    with pytest.raises(expected_error):
        run(pipeline.run("submission-1"))

    assert table_count(db_session, WorkflowRun) == 0
    assert table_count(db_session, FeedbackRecord) == 0
    assert table_count(db_session, JudgeEvaluation) == 0


def test_judge_rejection_is_persisted_but_not_released(db_session: Session) -> None:
    pipeline, _, _, _, _ = build_pipeline(db_session, decision=JudgeDecision.FAIL)

    result = run(pipeline.run("submission-1"))

    assert result.status is FeedbackPipelineStatus.REJECTED
    assert result.validated_feedback is None
    workflow = db_session.get(WorkflowRun, result.workflow_run_id)
    feedback = db_session.get(FeedbackRecord, result.feedback_id)
    assert workflow is not None
    assert workflow.current_stage is WorkflowStage.FAILED
    assert workflow.final_outcome is WorkflowOutcome.WORKFLOW_FAILED
    assert feedback is not None
    assert feedback.status is FeedbackStatus.REJECTED
    assert feedback.feedback_content == generated_feedback().feedback_content


def test_database_failure_rolls_back_the_complete_aggregate(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_commit() -> None:
        raise OperationalError("commit", {}, RuntimeError("database unavailable"))

    monkeypatch.setattr(db_session, "commit", fail_commit)
    pipeline, _, _, _, _ = build_pipeline(db_session)

    with pytest.raises(PipelinePersistenceError):
        run(pipeline.run("submission-1"))

    assert table_count(db_session, WorkflowRun) == 0
    assert table_count(db_session, FeedbackRecord) == 0
    assert table_count(db_session, JudgeEvaluation) == 0


def test_duplicate_save_race_returns_the_winning_result(db_session: Session) -> None:
    class RacingRepository(SqlAlchemyFeedbackWorkflowRepository):
        def __init__(self, session: Session) -> None:
            super().__init__(session)
            self._raced = False

        def save_result(self, request: PipelinePersistenceRequest) -> FeedbackPipelineResult:
            if not self._raced:
                self._raced = True
                winner = request.result.model_copy(
                    update={
                        "workflow_run_id": str(uuid4()),
                        "feedback_id": str(uuid4()),
                    }
                )
                super().save_result(
                    PipelinePersistenceRequest(
                        result=winner,
                        generated_feedback=request.generated_feedback,
                        started_at=request.started_at,
                        completed_at=request.completed_at,
                    )
                )
            return super().save_result(request)

    repository = RacingRepository(db_session)
    pipeline, _, _, _, _ = build_pipeline(db_session, repository=repository)

    result = run(pipeline.run("submission-1"))

    assert result.idempotent_replay is True
    assert table_count(db_session, WorkflowRun) == 1
    assert table_count(db_session, FeedbackRecord) == 1
    assert table_count(db_session, JudgeEvaluation) == 1
