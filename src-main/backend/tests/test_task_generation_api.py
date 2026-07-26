import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.models import TaskType
from app.services.rag.contracts import RetrievalHit, RetrievalResult, TaskGenerationResponse
from app.services.rag.task_generation import (
    GenerateTasksInput,
    GroundedTaskGenerationService,
    NoRelevantCourseContentError,
)


class StaticRetrieval:
    def __init__(self, hits: tuple[RetrievalHit, ...]) -> None:
        self.hits = hits

    def search(self, query):
        return RetrievalResult("request-1", bool(self.hits), self.hits, None, 0, "test-embedding")


class RecordingGenerator:
    def __init__(self, tasks: tuple[dict, ...]) -> None:
        self.tasks = tasks

    async def generate_structured(self, request):
        return TaskGenerationResponse(self.tasks, "fake", "fake-model", 1, 2, 0.0)


def _request() -> GenerateTasksInput:
    return GenerateTasksInput("course-1", None, "outcome-1", "Explain superposition", 1, (TaskType.QUIZ,), ("beginner",))


def _hit() -> RetrievalHit:
    return RetrievalHit("chunk-1", "material-1", "course-1", "Grounded material", "Notes — Page 1", 0.9, 0)


def test_task_generation_is_disabled_by_default() -> None:
    response = TestClient(app).post(
        "/api/v1/courses/course-1/tasks/generate",
        json={"learning_outcome_id": "outcome-1", "learning_outcome_text": "Explain", "allowed_task_types": ["quiz"], "difficulty_levels": ["beginner"]},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "task_generation_provider_unavailable"


def test_task_generation_rejects_invented_citations_and_no_retrieval_hits() -> None:
    invented = RecordingGenerator(({
        "title": "Task", "prompt": "Explain", "instructions": "Respond", "task_type": "quiz",
        "difficulty": "beginner", "learning_outcome_id": "outcome-1", "expected_answer": "Answer",
        "source_references": ["invented"],
    },))
    service = GroundedTaskGenerationService(None, StaticRetrieval((_hit(),)), invented)  # type: ignore[arg-type]
    try:
        asyncio.run(service.generate(_request()))
    except ValueError as error:
        assert "grounding" in str(error)
    else:
        raise AssertionError("invented citations must be rejected")

    empty = GroundedTaskGenerationService(None, StaticRetrieval(()), invented)  # type: ignore[arg-type]
    try:
        asyncio.run(empty.generate(_request()))
    except NoRelevantCourseContentError:
        pass
    else:
        raise AssertionError("generation must not run without retrieval hits")
