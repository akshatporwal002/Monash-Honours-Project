"""Grounded task generation orchestration with strict source validation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Course, CourseModule, LearningOutcome, LearningTask, TaskType
from app.services.rag.contracts import (
    RetrievalPurpose,
    RetrievalQuery,
    TaskGenerationClient,
    TaskGenerationRequest,
)
from app.services.rag.errors import RagError
from app.services.rag.retrieval import RetrievalService
from app.services.task_types import DEFAULT_TASK_TYPE_REGISTRY


class NoRelevantCourseContentError(RagError):
    def __init__(self) -> None:
        super().__init__("no_relevant_course_content", "No relevant course content was found.", 422)


class TaskGenerationProviderUnavailableError(RagError):
    def __init__(self) -> None:
        super().__init__(
            "task_generation_provider_unavailable",
            "Task generation provider is not configured.",
            503,
        )


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

    def __init__(
        self, session: Session, retrieval: RetrievalService, client: TaskGenerationClient | None
    ) -> None:
        self.session, self.retrieval, self.client = session, retrieval, client

    async def generate(
        self,
        request: GenerateTasksInput,
        *,
        commit: bool = True,
    ) -> list[LearningTask]:
        if self.client is None:
            raise TaskGenerationProviderUnavailableError()
        module_id, module_title = self._validated_scope(request)
        result = self.retrieval.search(
            RetrievalQuery(
                course_id=request.course_id,
                text=request.learning_outcome_text,
                purpose=RetrievalPurpose.TASK_GENERATION,
                module_id=module_id,
                top_k=min(10, max(1, request.task_count * 2)),
            )
        )
        if not result.hits and module_id is not None:
            result = self.retrieval.search(
                RetrievalQuery(
                    course_id=request.course_id,
                    text=request.learning_outcome_text,
                    purpose=RetrievalPurpose.TASK_GENERATION,
                    module_id=None,
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
                    "sources": [
                        {"chunk_id": hit.chunk_id, "text": hit.chunk_text} for hit in result.hits
                    ],
                },
            )
        )
        if len(response.tasks) != request.task_count:
            raise ValueError("task generation response returned an unexpected task count")
        allowed_sources = {hit.chunk_id for hit in result.hits}
        allowed_task_types = {item.value for item in request.allowed_task_types}
        start_position = (
            self.session.scalar(
                select(func.max(LearningTask.position)).where(
                    LearningTask.course_id == request.course_id
                )
            )
            or 0
        )
        tasks: list[LearningTask] = []
        seen_prompts: set[str] = set()
        previous_id: str | None = None
        for index, output in enumerate(response.tasks):
            source_ids = output.get("source_references", [])
            task_type = output.get("task_type")
            difficulty = output.get("difficulty")
            if (
                not isinstance(source_ids, list)
                or not source_ids
                or not set(source_ids) <= allowed_sources
                or output.get("learning_outcome_id") != request.learning_outcome_id
                or task_type not in allowed_task_types
                or difficulty not in request.difficulty_levels
                or not output.get("title")
                or not output.get("prompt")
                or not output.get("instructions")
                or output["prompt"] in seen_prompts
            ):
                raise ValueError("task generation response failed grounding validation")
            seen_prompts.add(output["prompt"])
            scaffold = DEFAULT_TASK_TYPE_REGISTRY.scaffold(
                str(task_type),
                request.learning_outcome_text,
            )
            expected_answer = output.get("expected_answer") or scaffold.expected_answer
            criteria = output.get("marking_criteria")
            if not isinstance(criteria, dict):
                criteria = scaffold.marking_criteria
            starter_code = output.get("starter_code")
            if not isinstance(starter_code, str) or not starter_code.strip():
                starter_code = scaffold.starter_code
            if not expected_answer and not criteria:
                raise ValueError("task generation response failed marking validation")
            task_id = str(uuid4())
            task = LearningTask(
                id=task_id,
                slug=f"generated-{request.learning_outcome_id[:8]}-{task_id[:12]}",
                title=output["title"],
                module=module_title,
                description=output["prompt"],
                instructions=output["instructions"],
                task_type=TaskType(task_type),
                difficulty=difficulty,
                points=100 + index * 50,
                position=start_position + index + 1,
                starter_code=starter_code,
                course_id=request.course_id,
                module_id=module_id,
                learning_outcome_id=request.learning_outcome_id,
                expected_answer=expected_answer,
                marking_criteria=criteria,
                source_references=source_ids,
                prerequisite_task_ids=[previous_id] if previous_id else [],
                generation_provider=response.provider,
                generation_model=response.model,
                generation_prompt_version=self.prompt_version,
                generation_input_tokens=response.input_tokens,
                generation_output_tokens=response.output_tokens,
                generation_total_tokens=response.input_tokens + response.output_tokens,
                generation_estimated_cost=Decimal(str(response.estimated_cost)),
            )
            tasks.append(task)
            previous_id = task.id
        self.session.add_all(tasks)
        if commit:
            self.session.commit()
        else:
            self.session.flush()
        return tasks

    def _validated_scope(self, request: GenerateTasksInput) -> tuple[str, str]:
        course = self.session.get(Course, request.course_id)
        outcome = self.session.get(LearningOutcome, request.learning_outcome_id)
        if course is None or outcome is None:
            raise ValueError("task generation requires an existing course and learning outcome")
        module = self.session.get(CourseModule, outcome.module_id)
        if (
            module is None
            or module.course_id != course.id
            or (request.module_id is not None and request.module_id != module.id)
        ):
            raise ValueError("the learning outcome must belong to the selected course module")
        return module.id, module.title
