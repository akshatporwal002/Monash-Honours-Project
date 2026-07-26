"""Grounded task-generation API; disabled until a provider is configured."""
# ruff: noqa: B008

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.materials import _require_manage, get_actor_id, get_course_access_policy
from app.api.routes.retrieval import get_retrieval_service
from app.db.session import get_db_session
from app.schemas.content import GeneratedTaskRead, GenerateTasksRequest
from app.services.rag.contracts import CourseAccessPolicy, TaskGenerationClient
from app.services.rag.task_generation import (
    GenerateTasksInput,
    GroundedTaskGenerationService,
    TaskGenerationProviderUnavailableError,
)

router = APIRouter(prefix="/courses/{course_id}/tasks")


def get_task_generation_client() -> TaskGenerationClient | None:
    return None


def get_task_generation_service(
    db: Session = Depends(get_db_session),
    client: TaskGenerationClient | None = Depends(get_task_generation_client),
) -> GroundedTaskGenerationService:
    if client is None:
        # A placeholder retrieval object is never used because the service fails before retrieval.
        return GroundedTaskGenerationService(db, None, None)  # type: ignore[arg-type]
    return GroundedTaskGenerationService(db, get_retrieval_service(db), client)


@router.post("/generate", response_model=list[GeneratedTaskRead])
async def generate_tasks(
    course_id: str,
    payload: GenerateTasksRequest,
    actor_id: str = Depends(get_actor_id),
    policy: CourseAccessPolicy = Depends(get_course_access_policy),
    service: GroundedTaskGenerationService = Depends(get_task_generation_service),
) -> list[GeneratedTaskRead]:
    _require_manage(policy, actor_id, course_id)
    try:
        tasks = await service.generate(
            GenerateTasksInput(
                course_id=course_id, module_id=payload.module_id,
                learning_outcome_id=payload.learning_outcome_id,
                learning_outcome_text=payload.learning_outcome_text,
                task_count=payload.task_count, allowed_task_types=tuple(payload.allowed_task_types),
                difficulty_levels=tuple(payload.difficulty_levels),
            )
        )
    except TaskGenerationProviderUnavailableError as error:
        raise HTTPException(status_code=error.http_status, detail={"code": error.code, "message": error.safe_message}) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail={"code": "invalid_generation_output", "message": str(error)}) from error
    return [GeneratedTaskRead(id=task.id, title=task.title, prompt=task.description, instructions=task.instructions, task_type=task.task_type, difficulty=task.difficulty, learning_outcome_id=task.learning_outcome_id, source_references=task.source_references) for task in tasks]
