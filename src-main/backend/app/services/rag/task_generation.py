"""Grounded task generation orchestration with strict source validation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import LearningTask, TaskType
from app.services.rag.contracts import (
    RetrievalPurpose,
    RetrievalQuery,
    TaskGenerationClient,
    TaskGenerationRequest,
)
from app.services.rag.errors import RagError
from app.services.rag.retrieval import RetrievalService


class NoRelevantCourseContentError(RagError):
    def __init__(self) -> None:
        super().__init__("no_relevant_course_content", "No relevant course content was found.", 422)


class TaskGenerationProviderUnavailableError(RagError):
    def __init__(self) -> None:
        super().__init__("task_generation_provider_unavailable", "Task generation provider is not configured.", 503)


@dataclass(frozen=True, slots=True)
class GenerateTasksInput:
    course_id: str
    module_id: str | None
    learning_outcome_id: str
    learning_outcome_text: str
    task_count: int
    allowed_task_types: tuple[TaskType, ...]
    difficulty_levels: tuple[str, ...]


class GroundedTaskGenerationService:
    prompt_version = "task-generation-v1"

    def __init__(self, session: Session, retrieval: RetrievalService, client: TaskGenerationClient | None) -> None:
        self.session, self.retrieval, self.client = session, retrieval, client

    async def generate(self, request: GenerateTasksInput) -> list[LearningTask]:
        if self.client is None:
            raise TaskGenerationProviderUnavailableError()
        result = self.retrieval.search(
            RetrievalQuery(
                course_id=request.course_id,
                text=request.learning_outcome_text,
                purpose=RetrievalPurpose.TASK_GENERATION,
                module_id=request.module_id,
                top_k=min(10, max(1, request.task_count * 2)),
            )
        )
        if not result.hits:
            raise NoRelevantCourseContentError()
        response = await self.client.generate_structured(
            TaskGenerationRequest(
                self.prompt_version,
                {
                    "learning_outcome_id": request.learning_outcome_id,
                    "learning_outcome_text": request.learning_outcome_text,
                    "task_count": request.task_count,
                    "allowed_task_types": [item.value for item in request.allowed_task_types],
                    "difficulty_levels": list(request.difficulty_levels),
                    "sources": [{"chunk_id": hit.chunk_id, "text": hit.chunk_text} for hit in result.hits],
                },
            )
        )
        allowed_sources = {hit.chunk_id for hit in result.hits}
        tasks: list[LearningTask] = []
        seen_prompts: set[str] = set()
        for index, output in enumerate(response.tasks):
            source_ids = output.get("source_references", [])
            task_type = output.get("task_type")
            difficulty = output.get("difficulty")
            if (
                not isinstance(source_ids, list)
                or not source_ids
                or not set(source_ids) <= allowed_sources
                or output.get("learning_outcome_id") != request.learning_outcome_id
                or task_type not in {item.value for item in request.allowed_task_types}
                or difficulty not in request.difficulty_levels
                or not output.get("title")
                or not output.get("prompt")
                or not output.get("instructions")
                or (not output.get("expected_answer") and not output.get("marking_criteria"))
                or output["prompt"] in seen_prompts
            ):
                raise ValueError("task generation response failed grounding validation")
            seen_prompts.add(output["prompt"])
            task = LearningTask(
                slug=f"generated-{request.learning_outcome_id}-{index}",
                title=output["title"], module=request.module_id or "Generated",
                description=output["prompt"], instructions=output["instructions"],
                task_type=TaskType(task_type), difficulty=difficulty, points=10, position=index,
                course_id=request.course_id, module_id=request.module_id,
                learning_outcome_id=request.learning_outcome_id,
                expected_answer=output.get("expected_answer"), marking_criteria=output.get("marking_criteria"),
                source_references=source_ids, generation_provider=response.provider,
                generation_model=response.model, generation_prompt_version=self.prompt_version,
                generation_input_tokens=response.input_tokens, generation_output_tokens=response.output_tokens,
                generation_total_tokens=response.input_tokens + response.output_tokens,
                generation_estimated_cost=Decimal(str(response.estimated_cost)),
            )
            tasks.append(task)
        self.session.add_all(tasks)
        self.session.commit()
        return tasks
