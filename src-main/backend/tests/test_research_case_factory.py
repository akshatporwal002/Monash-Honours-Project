import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.models.enums import JudgeDecision, JudgeEvaluationStatus
from app.schemas.feedback import (
    ContextProviderStatus,
    FeedbackContext,
    FeedbackPipelineResult,
    FeedbackPipelineStatus,
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
from app.services.feedback.contracts import FeedbackAttemptPersistence
from app.services.research import ResearchCaseFactory
from app.services.research.cases import ResearchCaseSeed

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


def generated(summary: str) -> GeneratedFeedback:
    return GeneratedFeedback(
        feedback_content={
            "response_classification": FeedbackResponseClassification.PARTIALLY_CORRECT.value,
            "summary": summary,
            "identified_error": None,
            "explanation": "Explain",
            "improvement_actions": ["Improve"],
            "recommended_next_step": "Retry",
            "source_references": ["source-1"],
            "simulation_references": ["simulation-1"],
        },
        provider="provider",
        model="model",
        prompt_version="feedback-v1",
        source_references=["source-1"],
        source_attributions=[FeedbackSourceAttribution(source_id="source-1", label="Source label")],
        simulation_references=["simulation-1"],
        token_usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        estimated_cost=Decimal("0.01"),
    )


def judged(decision: JudgeDecision) -> JudgeEvaluationOutcome:
    return JudgeEvaluationOutcome(
        evaluation_status=JudgeEvaluationStatus.VALID,
        reported_decision=decision,
        judge_result=JudgeResult(
            decision=decision,
            correctness_score=90,
            relevance_score=90,
            grounding_score=90,
            actionability_score=90,
            safety_score=100,
            reason="Measured",
        ),
        reason="Measured",
        provider="provider",
        model="judge",
        prompt_version="judge-v1",
        token_usage=TokenUsage(input_tokens=3, output_tokens=2, total_tokens=5),
    )


def research_context() -> FeedbackContext:
    return FeedbackContext(
        correlation_id=str(uuid4()),
        task=TaskContext(
            task_id="task-1",
            course_id="course-1",
            task_type="short_answer",
            prompt="PRIVATE TASK PROMPT",
            difficulty="intro",
            expected_answer="PRIVATE EXPECTED ANSWER",
            learning_outcome_id="lo-1",
            source_references=["source-1"],
        ),
        submission=SubmissionContext(
            submission_id="submission-private",
            task_id="task-1",
            course_id="course-1",
            student_id="student-private",
            attempt_number=1,
            submitted_answer="PRIVATE STUDENT ANSWER",
            submitted_at=NOW,
        ),
        retrieval_status=ContextProviderStatus.COMPLETED,
        retrieval_request_ids=["request-1"],
        retrieval_context=[
            RetrievalContext(
                retrieval_request_id="request-1",
                task_id="task-1",
                course_id="course-1",
                source_id="source-1",
                document_id="document-private",
                chunk_id="chunk-private",
                chunk_text="PRIVATE SOURCE CHUNK",
                relevance_score=0.9,
                source_label="Source label",
            )
        ],
        simulation_status=ContextProviderStatus.COMPLETED,
        simulation_context=SimulationContext(
            simulation_id="simulation-1",
            task_id="task-1",
            course_id="course-1",
            status="completed",
            error_details="PRIVATE RAW ERROR",
        ),
    )


def attempts() -> tuple[FeedbackAttemptPersistence, ...]:
    return (
        FeedbackAttemptPersistence(
            feedback_id=str(uuid4()),
            generation_attempt=1,
            generated_feedback=generated("candidate one"),
            judge_evaluation=judged(JudgeDecision.FAIL),
        ),
        FeedbackAttemptPersistence(
            feedback_id=str(uuid4()),
            generation_attempt=2,
            generated_feedback=generated("candidate two"),
            judge_evaluation=judged(JudgeDecision.PASS),
        ),
    )


def result() -> FeedbackPipelineResult:
    final = generated("candidate two")
    return FeedbackPipelineResult(
        workflow_run_id=str(uuid4()),
        feedback_id=str(uuid4()),
        submission_id="submission-private",
        status=FeedbackPipelineStatus.VALIDATED,
        validated_feedback=final,
        judge_result=judged(JudgeDecision.PASS).judge_result,
        judge_evaluations=[
            judged(JudgeDecision.FAIL),
            judged(JudgeDecision.PASS),
        ],
        regeneration_count=1,
        latency_ms=120,
        token_usage=TokenUsage(input_tokens=26, output_tokens=14, total_tokens=40),
        estimated_cost=Decimal("0.02"),
        source_references=["source-1"],
    )


class Eligibility:
    def __init__(self, eligible: bool) -> None:
        self.eligible = eligible

    async def is_eligible(self, _: FeedbackContext) -> bool:
        return self.eligible


class Repository:
    def __init__(self) -> None:
        self.seed: ResearchCaseSeed | None = None

    def create_pair(self, seed: ResearchCaseSeed) -> None:
        self.seed = seed


class Dispatcher:
    def __init__(self) -> None:
        self.case_ids: list[str] = []

    def schedule_baseline(self, case_id: str) -> None:
        self.case_ids.append(case_id)


class Pseudonymizer:
    def pseudonymize(self, namespace: str, reference: str) -> str:
        return f"v1_{namespace}_{len(reference)}"


def test_eligible_terminal_feedback_creates_one_private_pair_then_dispatches() -> None:
    repository = Repository()
    dispatcher = Dispatcher()
    factory = ResearchCaseFactory(
        Eligibility(True),
        repository,
        dispatcher,
        Pseudonymizer(),
        fallback_provider="provider",
        fallback_model="model",
    )
    pipeline_result = result()

    seed = asyncio.run(
        factory.create_after_feedback(
            research_context(),
            pipeline_result,
            attempts(),
        )
    )

    assert seed is repository.seed
    assert seed is not None
    assert seed.case_id == pipeline_result.workflow_run_id
    assert dispatcher.case_ids == [pipeline_result.workflow_run_id]
    assert seed.generated_output["summary"] == "candidate two"
    assert seed.retrieval_hit_count == 1
    serialized = repr(seed)
    for forbidden in (
        "PRIVATE STUDENT ANSWER",
        "PRIVATE SOURCE CHUNK",
        "PRIVATE RAW ERROR",
        "PRIVATE TASK PROMPT",
    ):
        assert forbidden not in serialized


def test_research_is_disabled_without_positive_eligibility() -> None:
    repository = Repository()
    dispatcher = Dispatcher()
    factory = ResearchCaseFactory(
        Eligibility(False),
        repository,
        dispatcher,
        Pseudonymizer(),
        fallback_provider="provider",
        fallback_model="model",
    )

    seed = asyncio.run(factory.create_after_feedback(research_context(), result(), attempts()))

    assert seed is None
    assert repository.seed is None
    assert dispatcher.case_ids == []
