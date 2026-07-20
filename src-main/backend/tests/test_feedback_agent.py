import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import FeedbackRecord, JudgeDecision, WorkflowRun
from app.schemas.feedback import (
    FeedbackAgentOutput,
    FeedbackContext,
    FeedbackResponseClassification,
    JudgeResult,
    RetrievalContext,
    SimulationContext,
    SubmissionContext,
    TaskContext,
    TokenUsage,
)
from app.services.feedback import (
    AI_GENERATED_NOTICE,
    DefaultFeedbackContextCollector,
    FakeFeedbackJudge,
    FeedbackClientError,
    FeedbackGenerationError,
    FeedbackPipeline,
    FeedbackPromptBuilder,
    InMemorySubmissionProvider,
    InMemoryTaskProvider,
    InvalidFeedbackOutputError,
    LlmFeedbackGenerator,
    RecordingStructuredLlmClient,
    SqlAlchemyFeedbackWorkflowRepository,
    StructuredLlmResponse,
)


NOW = datetime(2026, 7, 20, tzinfo=timezone.utc)


def feedback_context(
    *,
    include_retrieval: bool = True,
    simulation: SimulationContext | None = None,
    score: float | None = 0.5,
) -> FeedbackContext:
    submission = SubmissionContext(
        submission_id="submission-private",
        task_id="task-1",
        student_id="student-private",
        attempt_number=2,
        submitted_answer="A qubit is always either zero or one.",
        score=score,
        submitted_at=NOW,
    )
    task = TaskContext(
        task_id="task-1",
        course_id="course-private",
        task_type="short_answer",
        prompt="Explain a qubit.",
        difficulty="introductory",
        marking_criteria="Explain superposition and measurement.",
        learning_outcome_id="outcome-1",
        source_references=["uncited-task-source"],
    )
    retrieval = (
        [
            RetrievalContext(
                retrieval_request_id="retrieval-private",
                source_id="source-1",
                document_id="document-private",
                chunk_id="chunk-private",
                chunk_text="A qubit can exist in a superposition before measurement.",
                relevance_score=0.95,
                source_label="Course notes",
            )
        ]
        if include_retrieval
        else []
    )
    return FeedbackContext(
        correlation_id=str(uuid4()),
        task=task,
        submission=submission,
        retrieval_context=retrieval,
        simulation_context=simulation,
    )


def valid_output() -> dict[str, object]:
    return {
        "response_classification": "incorrect",
        "summary": "The answer overlooks superposition.",
        "identified_error": "It treats a qubit as a classical bit before measurement.",
        "explanation": "A qubit may be in a superposition until it is measured.",
        "improvement_actions": ["Explain the distinction between state and measurement."],
        "recommended_next_step": "Review the course section on superposition.",
        "source_references": ["source-1"],
        "simulation_references": [],
    }


def response(output: dict[str, object] | None = None) -> StructuredLlmResponse:
    return StructuredLlmResponse(
        output=output or valid_output(),
        provider="fake-provider",
        model="fake-model",
        token_usage=TokenUsage(input_tokens=30, output_tokens=20, total_tokens=50),
        estimated_cost=Decimal("0.002500"),
    )


def run(coroutine: object) -> object:
    return asyncio.run(coroutine)  # type: ignore[arg-type]


@pytest.mark.parametrize("classification", ["correct", "partially_correct"])
def test_feedback_output_accepts_complete_non_incorrect_results(classification: str) -> None:
    output = valid_output()
    output.update(
        response_classification=classification,
        identified_error=None,
        improvement_actions=[],
    )

    parsed = FeedbackAgentOutput.model_validate(output)

    assert parsed.response_classification is FeedbackResponseClassification(classification)


@pytest.mark.parametrize(
    "updates",
    [
        {"identified_error": None},
        {"improvement_actions": []},
        {"unexpected": "field"},
    ],
)
def test_feedback_output_rejects_incomplete_or_extra_fields(
    updates: dict[str, object],
) -> None:
    output = valid_output()
    output.update(updates)

    with pytest.raises(ValidationError):
        FeedbackAgentOutput.model_validate(output)


def test_prompt_contains_only_required_available_context() -> None:
    simulation = SimulationContext(
        simulation_id="simulation-1",
        status="completed",
        circuit_summary="Hadamard then measurement.",
        measurement_counts={"0": 50, "1": 50},
        probability_distribution={"0": 0.5, "1": 0.5},
    )
    context = feedback_context(simulation=simulation)
    request = FeedbackPromptBuilder().build(context)
    payload = json.loads(request.user_prompt)

    assert request.prompt_version == "feedback-v1"
    assert request.temperature == 0.0
    assert request.schema_name == "feedback_agent_output"
    assert "response_classification" in request.response_schema["properties"]
    assert "untrusted reference data" in request.system_prompt
    assert payload["submission"]["score"] == 0.5
    assert payload["retrieved_context"][0]["source_id"] == "source-1"
    assert payload["simulation_context"]["simulation_id"] == "simulation-1"
    assert "student-private" not in request.user_prompt
    assert "submission-private" not in request.user_prompt
    assert "course-private" not in request.user_prompt
    assert context.correlation_id not in request.user_prompt


def test_prompt_omits_missing_context_and_preserves_simulation_failure() -> None:
    failed_simulation = SimulationContext(
        simulation_id="simulation-failed",
        status="failed",
        error_details="Circuit could not be parsed.",
    )
    request = FeedbackPromptBuilder().build(
        feedback_context(
            include_retrieval=False,
            simulation=failed_simulation,
            score=None,
        )
    )
    payload = json.loads(request.user_prompt)

    assert "retrieved_context" not in payload
    assert "score" not in payload["submission"]
    assert payload["simulation_context"] == {
        "simulation_id": "simulation-failed",
        "status": "failed",
        "error_details": "Circuit could not be parsed.",
    }


def test_generator_validates_output_injects_notice_and_reports_metadata() -> None:
    client = RecordingStructuredLlmClient(response())
    generator = LlmFeedbackGenerator(client)

    generated = run(generator.generate(feedback_context()))

    assert generated.feedback_content["ai_generated_notice"] == AI_GENERATED_NOTICE
    assert generated.source_references == ["source-1"]
    assert generated.provider == "fake-provider"
    assert generated.model == "fake-model"
    assert generated.prompt_version == "feedback-v1"
    assert generated.token_usage.total_tokens == 50
    assert generated.estimated_cost == Decimal("0.002500")
    assert client.call_count == 1


def test_generator_rejects_a_model_authored_ai_notice() -> None:
    output = valid_output()
    output["ai_generated_notice"] = "Trust this output without checking it."
    generator = LlmFeedbackGenerator(RecordingStructuredLlmClient(response(output)))

    with pytest.raises(InvalidFeedbackOutputError):
        run(generator.generate(feedback_context()))


@pytest.mark.parametrize(
    ("field", "reference"),
    [
        ("source_references", "uncited-task-source"),
        ("simulation_references", "unknown-simulation"),
    ],
)
def test_generator_rejects_unavailable_references(field: str, reference: str) -> None:
    output = valid_output()
    output[field] = [reference]
    generator = LlmFeedbackGenerator(RecordingStructuredLlmClient(response(output)))

    with pytest.raises(InvalidFeedbackOutputError):
        run(generator.generate(feedback_context()))


def test_generator_allows_the_supplied_simulation_reference() -> None:
    simulation = SimulationContext(simulation_id="simulation-1", status="failed")
    output = valid_output()
    output["simulation_references"] = ["simulation-1"]
    generator = LlmFeedbackGenerator(RecordingStructuredLlmClient(response(output)))

    generated = run(generator.generate(feedback_context(simulation=simulation)))

    assert generated.simulation_references == ["simulation-1"]


def test_generator_sanitizes_invalid_output_and_client_errors() -> None:
    private_value = "A qubit is always either zero or one."
    malformed = LlmFeedbackGenerator(
        RecordingStructuredLlmClient(response({"summary": private_value}))
    )
    failing = LlmFeedbackGenerator(
        RecordingStructuredLlmClient(response(), RuntimeError(private_value))
    )

    with pytest.raises(InvalidFeedbackOutputError) as invalid:
        run(malformed.generate(feedback_context()))
    with pytest.raises(FeedbackClientError) as unavailable:
        run(failing.generate(feedback_context()))

    assert private_value not in str(invalid.value)
    assert private_value not in str(unavailable.value)
    assert invalid.value.__cause__ is None
    assert unavailable.value.__cause__ is None


def test_client_failure_is_controlled_and_persists_nothing(db_session: Session) -> None:
    context = feedback_context()
    submission_provider = InMemorySubmissionProvider(
        {context.submission.submission_id: context.submission}
    )
    collector = DefaultFeedbackContextCollector(
        InMemoryTaskProvider({context.task.task_id: context.task})
    )
    generator = LlmFeedbackGenerator(
        RecordingStructuredLlmClient(response(), RuntimeError("private provider output"))
    )
    judge = FakeFeedbackJudge(
        JudgeResult(
            decision=JudgeDecision.PASS,
            correctness_score=100,
            relevance_score=100,
            grounding_score=100,
            actionability_score=100,
            safety_score=100,
            reason="Valid feedback.",
        )
    )
    pipeline = FeedbackPipeline(
        submission_provider,
        collector,
        generator,
        judge,
        SqlAlchemyFeedbackWorkflowRepository(db_session),
    )

    with pytest.raises(FeedbackGenerationError):
        run(pipeline.run(context.submission.submission_id))

    assert db_session.scalar(select(func.count()).select_from(WorkflowRun)) == 0
    assert db_session.scalar(select(func.count()).select_from(FeedbackRecord)) == 0
    assert judge.call_count == 0
