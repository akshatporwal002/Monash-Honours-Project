import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.schemas.feedback import (
    FeedbackContext,
    FeedbackResponseClassification,
    RetrievalContext,
    SimulationContext,
    SubmissionContext,
    TaskContext,
    TokenUsage,
)
from app.services.feedback import RecordingStructuredLlmClient, StructuredLlmResponse
from app.services.research import (
    BASELINE_PROMPT_VERSION,
    BaselineGenerator,
    BaselineModelMismatchError,
    BaselineOutputError,
    BaselinePromptBuilder,
    DisabledResearchEligibilityPolicy,
)


def context() -> FeedbackContext:
    return FeedbackContext(
        correlation_id=str(uuid4()),
        task=TaskContext(
            task_id="task-private",
            course_id="course-private",
            task_type="short_answer",
            prompt="Explain measurement.",
            difficulty="introductory",
            marking_criteria={"required": "collapse"},
            learning_outcome_id="outcome-private",
            source_references=["source-private"],
        ),
        submission=SubmissionContext(
            submission_id="submission-private",
            task_id="task-private",
            course_id="course-private",
            student_id="student-private",
            attempt_number=1,
            submitted_answer="Measurement reads the qubit.",
            submitted_at=datetime(2026, 7, 25, tzinfo=UTC),
        ),
        retrieval_context=[
            RetrievalContext(
                retrieval_request_id="request-private",
                task_id="task-private",
                course_id="course-private",
                source_id="source-private",
                document_id="document-private",
                chunk_id="chunk-private",
                chunk_text="private retrieved material",
                relevance_score=0.9,
                source_label="Private notes",
            )
        ],
        simulation_context=SimulationContext(
            simulation_id="simulation-private",
            task_id="task-private",
            course_id="course-private",
            status="completed",
            circuit_summary="private circuit",
        ),
    )


def output(**updates: object) -> dict[str, object]:
    values: dict[str, object] = {
        "response_classification": FeedbackResponseClassification.PARTIALLY_CORRECT,
        "summary": "A useful start.",
        "identified_error": None,
        "explanation": "Add what measurement changes.",
        "improvement_actions": ["Explain collapse."],
        "recommended_next_step": "Review measurement.",
        "source_references": [],
        "simulation_references": [],
    }
    values.update(updates)
    return values


def response(**updates: object) -> StructuredLlmResponse:
    values: dict[str, object] = {
        "output": output(),
        "provider": "provider-a",
        "model": "model-a",
        "token_usage": TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        "estimated_cost": Decimal("0.01"),
        "usage_complete": True,
    }
    values.update(updates)
    return StructuredLlmResponse(**values)  # type: ignore[arg-type]


def test_baseline_prompt_contains_only_task_and_submission_content() -> None:
    request = BaselinePromptBuilder().build(context())
    payload = json.loads(request.user_prompt)
    serialized = request.user_prompt

    assert request.prompt_version == BASELINE_PROMPT_VERSION
    assert set(payload) == {"task", "submission"}
    assert set(payload["submission"]) == {"submitted_answer"}
    assert payload["submission"]["submitted_answer"] == "Measurement reads the qubit."
    for forbidden in (
        "course-private",
        "student-private",
        "submission-private",
        "source-private",
        "private retrieved material",
        "simulation-private",
        "private circuit",
        "regeneration",
    ):
        assert forbidden not in serialized


def test_baseline_generation_enforces_same_model_and_empty_references() -> None:
    client = RecordingStructuredLlmClient(response())
    generated = asyncio.run(
        BaselineGenerator(client).generate(
            context(),
            expected_provider="provider-a",
            expected_model="model-a",
        )
    )

    assert generated.source_references == []
    assert generated.simulation_references == []
    assert generated.model == "model-a"
    assert generated.usage_complete is True
    assert len(client.requests) == 1

    with pytest.raises(BaselineModelMismatchError):
        asyncio.run(
            BaselineGenerator(RecordingStructuredLlmClient(response())).generate(
                context(),
                expected_provider="provider-a",
                expected_model="other-model",
            )
        )


def test_baseline_preserves_missing_usage_measurement() -> None:
    generated = asyncio.run(
        BaselineGenerator(RecordingStructuredLlmClient(response(usage_complete=False))).generate(
            context(),
            expected_provider="provider-a",
            expected_model="model-a",
        )
    )

    assert generated.usage_complete is False


def test_baseline_rejects_provider_authored_references() -> None:
    client = RecordingStructuredLlmClient(
        response(output=output(source_references=["source-private"]))
    )

    with pytest.raises(BaselineOutputError):
        asyncio.run(
            BaselineGenerator(client).generate(
                context(),
                expected_provider="provider-a",
                expected_model="model-a",
            )
        )


def test_research_is_disabled_without_an_explicit_policy() -> None:
    assert asyncio.run(DisabledResearchEligibilityPolicy().is_eligible(context())) is False
