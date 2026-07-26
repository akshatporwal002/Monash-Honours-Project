import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.models.enums import JudgeDecision
from app.schemas.feedback import (
    FeedbackContext,
    FeedbackPipelineResult,
    GeneratedFeedback,
    JudgeResult,
    SubmissionContext,
    TaskContext,
    TokenUsage,
)
from app.services.continuation import (
    ContinuationScheduleReceipt,
    ContinuationState,
    ContinuationTerminalFeedbackObserver,
    TerminalFeedbackNotice,
    compose_research_and_continuation,
)
from app.services.feedback import (
    FakeFeedbackGenerator,
    FakeFeedbackJudge,
    FeedbackPipeline,
)
from app.services.feedback.contracts import (
    FeedbackAttemptPersistence,
    PipelinePersistenceRequest,
)

NOW = datetime(2026, 7, 26, 10, 0, tzinfo=UTC)
PRIVATE_ANSWER = "PRIVATE ANSWER: amplitudes supplied by learner@example.test"
PRIVATE_FEEDBACK = "PRIVATE FEEDBACK: correct the relative phase"


def feedback_context() -> FeedbackContext:
    return FeedbackContext(
        correlation_id=str(uuid4()),
        task=TaskContext(
            task_id="task-bell-state",
            course_id="course-quantum-1",
            task_type="short-answer",
            prompt="PRIVATE TASK PROMPT",
            difficulty="introductory",
            expected_answer="PRIVATE EXPECTED ANSWER",
            learning_outcome_id="outcome-entanglement",
        ),
        submission=SubmissionContext(
            submission_id="submission-direct-identifier",
            task_id="task-bell-state",
            course_id="course-quantum-1",
            student_id="learner@example.test",
            attempt_number=1,
            submitted_answer=PRIVATE_ANSWER,
            submitted_at=NOW,
        ),
    )


def generated_feedback() -> GeneratedFeedback:
    return GeneratedFeedback(
        feedback_content={"summary": PRIVATE_FEEDBACK},
        provider="deterministic-provider",
        model="feedback-model",
        prompt_version="feedback-v1",
        token_usage=TokenUsage(input_tokens=2, output_tokens=3, total_tokens=5),
        estimated_cost=Decimal("0.001"),
    )


def passing_judge() -> JudgeResult:
    return JudgeResult(
        decision=JudgeDecision.PASS,
        correctness_score=90,
        relevance_score=90,
        grounding_score=90,
        actionability_score=90,
        safety_score=100,
        reason="All policy thresholds passed",
    )


class SubmissionProvider:
    def __init__(self, context: FeedbackContext) -> None:
        self._submission = context.submission

    async def get_submission(self, submission_id: str) -> SubmissionContext | None:
        if submission_id != self._submission.submission_id:
            return None
        return self._submission


class ContextCollector:
    def __init__(self, context: FeedbackContext) -> None:
        self._context = context

    async def collect(
        self,
        submission: SubmissionContext,
        correlation_id: str,
    ) -> FeedbackContext:
        assert submission is self._context.submission
        return self._context.model_copy(update={"correlation_id": correlation_id})


class DurableRepository:
    def __init__(self) -> None:
        self.durable = False
        self.saved_result: FeedbackPipelineResult | None = None

    def get_by_submission(self, submission_id: str) -> None:
        del submission_id
        return None

    def save_result(
        self,
        request: PipelinePersistenceRequest,
    ) -> FeedbackPipelineResult:
        self.durable = True
        self.saved_result = request.result
        return request.result


class ResearchCaseCreator:
    def __init__(
        self,
        repository: DurableRepository,
        *,
        failure: Exception | None = None,
    ) -> None:
        self._repository = repository
        self._failure = failure
        self.case_ids: list[str] = []

    async def after_terminal_feedback(
        self,
        context: FeedbackContext,
        result: FeedbackPipelineResult,
        attempts: tuple[FeedbackAttemptPersistence, ...],
    ) -> None:
        del context, attempts
        assert self._repository.durable is True
        self.case_ids.append(result.workflow_run_id)
        if self._failure is not None:
            raise self._failure


class ContinuationScheduler:
    def __init__(
        self,
        repository: DurableRepository,
        *,
        failure: Exception | None = None,
    ) -> None:
        self._repository = repository
        self._failure = failure
        self.notices: list[TerminalFeedbackNotice] = []

    def after_terminal_feedback(
        self,
        notice: TerminalFeedbackNotice,
    ) -> ContinuationScheduleReceipt:
        assert self._repository.durable is True
        self.notices.append(notice)
        if self._failure is not None:
            raise self._failure
        return ContinuationScheduleReceipt(
            workflow_run_id=notice.workflow_run_id,
            accepted=True,
            state=ContinuationState.PENDING,
        )


class Pseudonymizer:
    def pseudonymize(self, namespace: str, reference: str) -> str:
        assert namespace == "continuation-actor"
        assert reference == "learner@example.test"
        return f"v1_{'a' * 64}"


def build_pipeline(
    repository: DurableRepository,
    observer: object,
) -> FeedbackPipeline:
    context = feedback_context()
    clock = iter([1.0, 1.025])
    return FeedbackPipeline(
        SubmissionProvider(context),
        ContextCollector(context),
        FakeFeedbackGenerator(generated_feedback()),
        FakeFeedbackJudge(passing_judge()),
        repository,  # type: ignore[arg-type]
        clock=lambda: next(clock),
        now=lambda: NOW,
        uuid_factory=lambda: "10000000-0000-4000-8000-000000000001",
        terminal_observer=observer,  # type: ignore[arg-type]
    )


def test_research_failure_does_not_block_continuation_or_released_feedback(
    caplog: object,
) -> None:
    repository = DurableRepository()
    raw_failure = RuntimeError(f"research failed with {PRIVATE_ANSWER}")
    research = ResearchCaseCreator(repository, failure=raw_failure)
    continuation = ContinuationScheduler(repository)
    observer = compose_research_and_continuation(
        research,  # type: ignore[arg-type]
        continuation,
        Pseudonymizer(),
        logger=logging.getLogger("test.terminal-observers.research"),
    )
    pipeline = build_pipeline(repository, observer)

    with caplog.at_level(logging.WARNING):  # type: ignore[union-attr]
        result = asyncio.run(pipeline.run("submission-direct-identifier"))

    assert result is repository.saved_result
    assert result.validated_feedback is not None
    assert result.validated_feedback.feedback_content["summary"] == PRIVATE_FEEDBACK
    assert research.case_ids == [result.workflow_run_id]
    assert len(continuation.notices) == 1
    notice = continuation.notices[0]
    assert notice.workflow_run_id == result.workflow_run_id
    assert notice.pseudonymous_actor_reference.startswith("v1_")
    assert notice.course_reference == "course-quantum-1"
    assert notice.completed_task_reference == "task-bell-state"
    serialized_notice = repr(notice)
    for forbidden in (
        PRIVATE_ANSWER,
        PRIVATE_FEEDBACK,
        "learner@example.test",
        "submission-direct-identifier",
    ):
        assert forbidden not in serialized_notice
        assert forbidden not in caplog.text  # type: ignore[union-attr]


def test_continuation_failure_does_not_block_research_or_released_feedback(
    caplog: object,
) -> None:
    repository = DurableRepository()
    research = ResearchCaseCreator(repository)
    continuation = ContinuationScheduler(
        repository,
        failure=RuntimeError(f"continuation failed with {PRIVATE_FEEDBACK}"),
    )
    observer = compose_research_and_continuation(
        research,  # type: ignore[arg-type]
        continuation,
        Pseudonymizer(),
        logger=logging.getLogger("test.terminal-observers.continuation"),
    )
    pipeline = build_pipeline(repository, observer)

    with caplog.at_level(logging.WARNING):  # type: ignore[union-attr]
        result = asyncio.run(pipeline.run("submission-direct-identifier"))

    assert repository.durable is True
    assert result is repository.saved_result
    assert research.case_ids == [result.workflow_run_id]
    assert len(continuation.notices) == 1
    assert PRIVATE_FEEDBACK not in caplog.text  # type: ignore[union-attr]
    assert "terminal_feedback_observer_failed" in caplog.text  # type: ignore[union-attr]


def test_missing_pseudonymizer_and_scope_mismatch_fail_closed() -> None:
    repository = DurableRepository()
    scheduler = ContinuationScheduler(repository)
    context = feedback_context()
    result = asyncio.run(
        build_pipeline(repository, ResearchCaseCreator(repository)).run(
            "submission-direct-identifier"
        )
    )
    assert repository.durable is True

    without_pseudonymizer = ContinuationTerminalFeedbackObserver(scheduler, None)
    asyncio.run(without_pseudonymizer.after_terminal_feedback(context, result, ()))
    mismatched = result.model_copy(update={"submission_id": "different-submission"})
    with_pseudonymizer = ContinuationTerminalFeedbackObserver(
        scheduler,
        Pseudonymizer(),
    )
    asyncio.run(with_pseudonymizer.after_terminal_feedback(context, mismatched, ()))

    assert scheduler.notices == []
