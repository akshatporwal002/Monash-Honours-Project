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
    JudgeEvaluationStatus,
    WorkflowOutcome,
    WorkflowRun,
    WorkflowStage,
)
from app.models.audit import AuditAction, AuditOutcome
from app.schemas.audit import AuditEventCommand
from app.schemas.feedback import (
    FeedbackPipelineResult,
    FeedbackPipelineStatus,
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
from app.services.audit_events import FeedbackAuditEvents
from app.services.feedback import (
    ContextCollectionError,
    ContextIntegrityError,
    DefaultFeedbackContextCollector,
    FakeFeedbackGenerator,
    FakeFeedbackJudge,
    FeedbackAttemptPersistence,
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
        course_id="course-1",
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
        provider="fake-provider",
        model="fake-feedback-model",
        prompt_version="feedback-v2",
        source_references=["source-1"],
        source_attributions=[FeedbackSourceAttribution(source_id="source-1", label="Course notes")],
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


def judge_outcome(
    decision: JudgeDecision,
    *,
    input_tokens: int,
    output_tokens: int,
    cost: str,
) -> JudgeEvaluationOutcome:
    result = judge_result(decision)
    return JudgeEvaluationOutcome(
        evaluation_status=JudgeEvaluationStatus.VALID,
        reported_decision=decision,
        judge_result=result,
        reason=result.reason,
        provider="fake-judge-provider",
        model="fake-judge-model",
        prompt_version="quality-judge-v1",
        token_usage=TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        ),
        estimated_cost=Decimal(cost),
    )


def retrieval_context() -> RetrievalContext:
    return RetrievalContext(
        retrieval_request_id="retrieval-1",
        task_id="task-1",
        course_id="course-1",
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
        task_id="task-1",
        course_id="course-1",
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
    generator_results: list[GeneratedFeedback] | None = None,
    judge_results: list[JudgeResult | JudgeEvaluationOutcome] | None = None,
    generator_error_on_calls: dict[int, Exception] | None = None,
    judge_error_on_calls: dict[int, Exception] | None = None,
    decision: JudgeDecision = JudgeDecision.PASS,
    repository: SqlAlchemyFeedbackWorkflowRepository | None = None,
    terminal_observer: object | None = None,
    audit_events: FeedbackAuditEvents | None = None,
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
    generator = FakeFeedbackGenerator(
        generator_results or generated_feedback(),
        generator_error,
        generator_error_on_calls,
    )
    judge = FakeFeedbackJudge(
        judge_results or judge_result(decision),
        judge_error,
        judge_error_on_calls,
    )
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
        terminal_observer=terminal_observer,  # type: ignore[arg-type]
        audit_events=audit_events,
    )
    return pipeline, submission_provider, task_provider, generator, judge


def test_terminal_observer_runs_after_commit_and_audit_maps_real_calls(
    db_session: Session,
) -> None:
    class Sink:
        def __init__(self) -> None:
            self.commands: list[AuditEventCommand] = []

        def record(self, command: AuditEventCommand) -> None:
            self.commands.append(command)

    class Observer:
        def __init__(self) -> None:
            self.calls: list[tuple[object, object, object]] = []

        async def after_terminal_feedback(
            self,
            context: object,
            result: FeedbackPipelineResult,
            attempts: object,
        ) -> None:
            workflow = db_session.get(WorkflowRun, result.workflow_run_id)
            assert workflow is not None
            assert workflow.current_stage is WorkflowStage.COMPLETED
            self.calls.append((context, result, attempts))

    sink = Sink()
    observer = Observer()
    pipeline, _, _, _, _ = build_pipeline(
        db_session,
        terminal_observer=observer,
        audit_events=FeedbackAuditEvents(sink),  # type: ignore[arg-type]
    )
    correlation_id = str(uuid4())

    result = run(pipeline.run("submission-1", correlation_id=correlation_id))

    assert len(observer.calls) == 1
    assert observer.calls[0][1] is result
    assert {command.action for command in sink.commands} == {
        AuditAction.FEEDBACK_GENERATION_STARTED,
        AuditAction.FEEDBACK_GENERATION_COMPLETED,
        AuditAction.FEEDBACK_JUDGED,
        AuditAction.WORKFLOW_COMPLETED,
    }
    assert all(command.outcome is AuditOutcome.SUCCESS for command in sink.commands)
    assert all(command.correlation_id == correlation_id for command in sink.commands)


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
    assert workflow.course_id == "course-1"
    assert workflow.task_id == "task-1"
    assert workflow.latency_ms == 125
    assert feedback is not None
    assert feedback.workflow_run_id == result.workflow_run_id
    assert feedback.status is FeedbackStatus.ACCEPTED
    assert feedback.generation_attempt == 1
    assert feedback.provider == "fake-provider"
    assert feedback.prompt_version == "feedback-v2"
    assert feedback.simulation_references == ["simulation-1"]
    assert feedback.total_tokens == 30
    assert feedback.estimated_cost == Decimal("0.001500")
    assert feedback.judge_evaluation is not None
    assert feedback.judge_evaluation.decision is JudgeDecision.PASS
    assert feedback.judge_evaluation.quality_policy_version == "quality-policy-v1"


def test_duplicate_request_returns_stored_result_without_provider_calls(
    db_session: Session,
) -> None:
    pipeline, submission_provider, task_provider, generator, judge = build_pipeline(db_session)
    first = run(pipeline.run("submission-1"))
    second = run(pipeline.run("submission-1"))

    assert second.workflow_run_id == first.workflow_run_id
    assert second.feedback_id == first.feedback_id
    assert second.idempotent_replay is True
    assert second.validated_feedback == first.validated_feedback
    assert second.token_usage == first.token_usage
    assert second.estimated_cost == first.estimated_cost
    assert second.source_references == first.source_references
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


def test_submission_provider_must_return_the_requested_submission(
    db_session: Session,
) -> None:
    mismatched = submission().model_copy(update={"submission_id": "submission-other"})
    pipeline, _, _, generator, judge = build_pipeline(
        db_session,
        submissions={"submission-1": mismatched},
    )

    with pytest.raises(ContextIntegrityError):
        run(pipeline.run("submission-1"))

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


def test_initial_generation_failure_releases_safe_fallback(db_session: Session) -> None:
    pipeline, _, _, generator, judge = build_pipeline(
        db_session,
        generator_error=RuntimeError("generator unavailable"),
    )

    result = run(pipeline.run("submission-1"))

    assert result.status is FeedbackPipelineStatus.FALLBACK
    assert result.safe_fallback is not None
    assert result.regeneration_count == 0
    assert generator.call_count == 1
    assert judge.call_count == 0
    assert table_count(db_session, WorkflowRun) == 1
    assert table_count(db_session, FeedbackRecord) == 1
    assert table_count(db_session, JudgeEvaluation) == 0


def test_first_judge_failure_regenerates_and_second_passes(db_session: Session) -> None:
    pipeline, _, _, generator, judge = build_pipeline(
        db_session,
        judge_error=RuntimeError("judge unavailable"),
    )

    result = run(pipeline.run("submission-1"))

    assert result.status is FeedbackPipelineStatus.VALIDATED
    assert result.regeneration_count == 1
    assert generator.call_count == 2
    assert generator.regenerations[1] is not None
    assert judge.call_count == 2
    assert result.judge_evaluations[0].evaluation_status is JudgeEvaluationStatus.PROVIDER_ERROR
    assert table_count(db_session, FeedbackRecord) == 2
    assert table_count(db_session, JudgeEvaluation) == 2


def test_pipeline_revalidates_a_constructed_judge_outcome_before_release(
    db_session: Session,
) -> None:
    hostile_result = JudgeResult.model_construct(
        decision=JudgeDecision.PASS,
        correctness_score=79,
        relevance_score=100,
        grounding_score=100,
        actionability_score=100,
        safety_score=100,
        reason="PRIVATE INVALID PASS",
        unsupported_claims=[],
        regeneration_instructions=[],
    )
    hostile_outcome = JudgeEvaluationOutcome.model_construct(
        evaluation_status=JudgeEvaluationStatus.VALID,
        reported_decision=JudgeDecision.PASS,
        judge_result=hostile_result,
        reason="PRIVATE INVALID PASS",
        provider="hostile-provider",
        model="hostile-model",
        prompt_version="quality-judge-v1",
        quality_policy_version="quality-policy-v1",
        token_usage=TokenUsage(),
        estimated_cost=Decimal("0"),
        usage_complete=False,
    )
    pipeline, _, _, generator, judge = build_pipeline(
        db_session,
        judge_results=[hostile_outcome, hostile_outcome],
    )

    result = run(pipeline.run("submission-1"))

    assert result.status is FeedbackPipelineStatus.FALLBACK
    assert result.fallback_used is True
    assert generator.call_count == 2
    assert judge.call_count == 2
    assert all(
        evaluation.evaluation_status is JudgeEvaluationStatus.PROVIDER_ERROR
        for evaluation in result.judge_evaluations
    )


def test_failed_first_attempt_releases_only_judge_approved_regeneration(
    db_session: Session,
) -> None:
    revised_feedback = generated_feedback().model_copy(
        update={
            "feedback_content": {
                "summary": "The revised response is conservative and grounded.",
                "recommended_next_step": "Review measurement after superposition.",
            },
            "token_usage": TokenUsage(
                input_tokens=25,
                output_tokens=15,
                total_tokens=40,
            ),
            "estimated_cost": Decimal("0.002000"),
        }
    )
    first_judge = judge_outcome(
        JudgeDecision.FAIL,
        input_tokens=7,
        output_tokens=3,
        cost="0.000500",
    )
    second_judge = judge_outcome(
        JudgeDecision.PASS,
        input_tokens=8,
        output_tokens=4,
        cost="0.000600",
    )
    pipeline, _, _, generator, judge = build_pipeline(
        db_session,
        generator_results=[generated_feedback(), revised_feedback],
        judge_results=[first_judge, second_judge],
    )

    result = run(pipeline.run("submission-1"))

    assert result.status is FeedbackPipelineStatus.VALIDATED
    assert result.validated_feedback == revised_feedback
    assert result.regeneration_count == 1
    assert result.token_usage == TokenUsage(
        input_tokens=60,
        output_tokens=32,
        total_tokens=92,
    )
    assert result.estimated_cost == Decimal("0.004600")
    assert generator.call_count == 2
    assert judge.call_count == 2
    regeneration = generator.regenerations[1]
    assert regeneration is not None
    assert regeneration.previous_feedback == generated_feedback()
    assert regeneration.judge_evaluation == first_judge

    records = db_session.scalars(
        select(FeedbackRecord).order_by(FeedbackRecord.generation_attempt)
    ).all()
    assert [record.status for record in records] == [
        FeedbackStatus.REJECTED,
        FeedbackStatus.ACCEPTED,
    ]
    assert records[0].feedback_content != result.validated_feedback.feedback_content
    workflow = db_session.get(WorkflowRun, result.workflow_run_id)
    assert workflow is not None
    assert workflow.final_outcome is WorkflowOutcome.SECOND_PASS

    replay = run(pipeline.run("submission-1"))
    assert replay == result.model_copy(update={"idempotent_replay": True})


def test_malformed_first_judgement_uses_generic_guidance_then_passes(
    db_session: Session,
) -> None:
    malformed = JudgeEvaluationOutcome(
        evaluation_status=JudgeEvaluationStatus.MALFORMED,
        reason="The quality judge returned invalid structured output.",
        error_category="invalid_structured_output",
        provider="fake-judge-provider",
        model="fake-judge-model",
        prompt_version="quality-judge-v1",
        token_usage=TokenUsage(input_tokens=5, output_tokens=2, total_tokens=7),
        estimated_cost=Decimal("0.000300"),
    )
    pipeline, _, _, generator, _ = build_pipeline(
        db_session,
        judge_results=[
            malformed,
            judge_outcome(JudgeDecision.PASS, input_tokens=1, output_tokens=1, cost="0"),
        ],
    )

    result = run(pipeline.run("submission-1"))

    assert result.status is FeedbackPipelineStatus.VALIDATED
    assert result.regeneration_count == 1
    assert generator.regenerations[1] is not None
    assert generator.regenerations[1].judge_evaluation == malformed


def test_regeneration_failure_falls_back_and_retains_first_evaluation(
    db_session: Session,
) -> None:
    pipeline, _, _, generator, judge = build_pipeline(
        db_session,
        decision=JudgeDecision.FAIL,
        generator_error_on_calls={2: TimeoutError("feedback timeout")},
    )

    result = run(pipeline.run("submission-1"))

    assert result.status is FeedbackPipelineStatus.FALLBACK
    assert result.regeneration_count == 1
    assert generator.call_count == 2
    assert judge.call_count == 1
    assert len(result.judge_evaluations) == 1
    assert table_count(db_session, FeedbackRecord) == 2
    assert table_count(db_session, JudgeEvaluation) == 1


def test_second_judge_provider_failure_produces_exact_replayable_fallback(
    db_session: Session,
) -> None:
    pipeline, _, _, generator, judge = build_pipeline(
        db_session,
        decision=JudgeDecision.FAIL,
        judge_error_on_calls={2: TimeoutError("judge timeout")},
    )

    result = run(pipeline.run("submission-1"))

    assert result.status is FeedbackPipelineStatus.FALLBACK
    assert result.safe_fallback is not None
    assert result.safe_fallback.source_references == []
    assert result.safe_fallback.simulation_references == []
    fallback_text = " ".join(str(value) for value in result.safe_fallback.feedback_content.values())
    assert "Personalized feedback is temporarily unavailable" in fallback_text
    assert "course material" in fallback_text
    assert "educator" in fallback_text
    assert "correct" not in fallback_text.lower()
    assert generator.call_count == 2
    assert judge.call_count == 2
    assert result.judge_evaluations[-1].evaluation_status is (JudgeEvaluationStatus.PROVIDER_ERROR)
    assert table_count(db_session, FeedbackRecord) == 3
    assert table_count(db_session, JudgeEvaluation) == 2

    replay = run(pipeline.run("submission-1"))
    assert replay == result.model_copy(update={"idempotent_replay": True})


def test_judge_rejection_is_persisted_but_not_released(db_session: Session) -> None:
    pipeline, _, _, _, _ = build_pipeline(db_session, decision=JudgeDecision.FAIL)

    result = run(pipeline.run("submission-1"))

    assert result.status is FeedbackPipelineStatus.FALLBACK
    assert result.validated_feedback is None
    assert result.safe_fallback is not None
    assert result.regeneration_count == 1
    workflow = db_session.get(WorkflowRun, result.workflow_run_id)
    feedback = db_session.get(FeedbackRecord, result.feedback_id)
    assert workflow is not None
    assert workflow.current_stage is WorkflowStage.COMPLETED
    assert workflow.final_outcome is WorkflowOutcome.SAFE_FALLBACK
    assert feedback is not None
    assert feedback.status is FeedbackStatus.SAFE_FALLBACK
    assert table_count(db_session, FeedbackRecord) == 3
    assert table_count(db_session, JudgeEvaluation) == 2


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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("correctness_score", 79),
        ("safety_score", 99),
        ("unsupported_claims", ["PRIVATE UNSUPPORTED CLAIM"]),
        ("quality_policy_version", "quality-policy-v0"),
    ],
)
def test_corrupted_passing_judge_aggregate_raises_sanitized_persistence_error(
    db_session: Session,
    field: str,
    value: object,
) -> None:
    pipeline, _, _, _, _ = build_pipeline(db_session)
    result = run(pipeline.run("submission-1"))
    evaluation = db_session.scalar(select(JudgeEvaluation))
    assert evaluation is not None
    setattr(evaluation, field, value)
    db_session.commit()
    db_session.expire_all()

    with pytest.raises(PipelinePersistenceError) as exc_info:
        SqlAlchemyFeedbackWorkflowRepository(db_session).get_by_submission(
            result.submission_id,
        )

    assert "PRIVATE UNSUPPORTED CLAIM" not in str(exc_info.value)


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
                    }
                )
                super().save_result(
                    PipelinePersistenceRequest(
                        result=winner,
                        attempts=request.attempts,
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


def test_persistence_rejects_regeneration_and_usage_aggregate_mismatches(
    db_session: Session,
) -> None:
    generated = generated_feedback()
    evaluation = judge_outcome(
        JudgeDecision.PASS,
        input_tokens=5,
        output_tokens=3,
        cost="0.000500",
    )
    attempt = FeedbackAttemptPersistence(
        feedback_id=str(uuid4()),
        generation_attempt=1,
        generated_feedback=generated,
        judge_evaluation=evaluation,
    )
    result = FeedbackPipelineResult(
        workflow_run_id=str(uuid4()),
        feedback_id=attempt.feedback_id,
        submission_id="submission-invalid-aggregate",
        status=FeedbackPipelineStatus.VALIDATED,
        validated_feedback=generated,
        judge_result=evaluation.judge_result,
        judge_evaluations=[evaluation],
        regeneration_count=0,
        latency_ms=1,
        token_usage=TokenUsage(input_tokens=25, output_tokens=13, total_tokens=38),
        estimated_cost=Decimal("0.002000"),
        source_references=generated.source_references,
    )
    repository = SqlAlchemyFeedbackWorkflowRepository(db_session)

    for invalid in (
        result.model_copy(update={"regeneration_count": 1}),
        result.model_copy(update={"token_usage": TokenUsage()}),
    ):
        with pytest.raises(PipelinePersistenceError):
            repository.save_result(
                PipelinePersistenceRequest(
                    result=invalid,
                    attempts=(attempt,),
                    started_at=STARTED_AT,
                    completed_at=COMPLETED_AT,
                )
            )

    assert table_count(db_session, WorkflowRun) == 0


def test_persistence_rejects_a_passing_first_attempt_before_regeneration(
    db_session: Session,
) -> None:
    first_feedback = generated_feedback()
    second_feedback = generated_feedback().model_copy(
        update={"feedback_content": {"summary": "Second candidate"}}
    )
    first_evaluation = judge_outcome(
        JudgeDecision.PASS,
        input_tokens=2,
        output_tokens=1,
        cost="0.000200",
    )
    second_evaluation = judge_outcome(
        JudgeDecision.PASS,
        input_tokens=2,
        output_tokens=1,
        cost="0.000200",
    )
    attempts = (
        FeedbackAttemptPersistence(
            feedback_id=str(uuid4()),
            generation_attempt=1,
            generated_feedback=first_feedback,
            judge_evaluation=first_evaluation,
        ),
        FeedbackAttemptPersistence(
            feedback_id=str(uuid4()),
            generation_attempt=2,
            generated_feedback=second_feedback,
            judge_evaluation=second_evaluation,
        ),
    )
    result = FeedbackPipelineResult(
        workflow_run_id=str(uuid4()),
        feedback_id=attempts[1].feedback_id,
        submission_id="submission-invalid-regeneration",
        status=FeedbackPipelineStatus.VALIDATED,
        validated_feedback=second_feedback,
        judge_result=second_evaluation.judge_result,
        judge_evaluations=[first_evaluation, second_evaluation],
        regeneration_count=1,
        latency_ms=1,
        token_usage=TokenUsage(input_tokens=44, output_tokens=22, total_tokens=66),
        estimated_cost=Decimal("0.003400"),
        source_references=second_feedback.source_references,
    )

    with pytest.raises(PipelinePersistenceError):
        SqlAlchemyFeedbackWorkflowRepository(db_session).save_result(
            PipelinePersistenceRequest(
                result=result,
                attempts=attempts,
                started_at=STARTED_AT,
                completed_at=COMPLETED_AT,
            )
        )
