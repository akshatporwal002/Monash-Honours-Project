from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import LearningTask, TaskType
from app.schemas import LearningMaterialCreate, MaterialChunkCreate, TaskGenerationMetadata
from app.services.task_context import to_feedback_task_context


def test_material_and_chunk_schemas_validate() -> None:
    material = LearningMaterialCreate(
        course_id="course-1",
        original_filename="slides.pdf",
        mime_type="application/pdf",
        content_hash="sha256:abc",
    )
    chunk = MaterialChunkCreate(
        material_id="material-1",
        chunk_index=0,
        chunk_text="Hadamard creates a superposition.",
        location_label="Slide 4",
    )

    assert material.indexing_status.value == "pending"
    assert chunk.location_label == "Slide 4"


@pytest.mark.parametrize(
    "payload",
    [
        {"course_id": "course-1", "mime_type": "application/pdf", "content_hash": "hash"},
        {"course_id": "course-1", "original_filename": "slides.pdf", "source_url": "https://example.edu/slides.pdf", "mime_type": "application/pdf", "content_hash": "hash"},
        {"course_id": "course-1", "source_url": "http://example.edu/slides.pdf", "mime_type": "application/pdf", "content_hash": "hash"},
    ],
)
def test_material_schema_rejects_invalid_source_identity(payload: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        LearningMaterialCreate(**payload)


def test_generation_metadata_requires_consistent_tokens() -> None:
    with pytest.raises(ValidationError):
        TaskGenerationMetadata(
            provider="provider", model="model", prompt_version="v1",
            input_tokens=2, output_tokens=3, total_tokens=4, estimated_cost=Decimal(0),
        )


def test_task_context_mapper_converts_grounded_task() -> None:
    task = LearningTask(
        id="task-1",
        slug="grounded-task",
        title="Grounded task",
        module="Foundations",
        description="Explain superposition.",
        instructions="Explain what a Hadamard gate does to |0>.",
        task_type=TaskType.QUIZ,
        difficulty="Beginner",
        points=10,
        position=1,
        course_id="course-1",
        learning_outcome_id="outcome-1",
        expected_answer="It creates an equal superposition.",
        source_references=["chunk-1"],
    )

    context = to_feedback_task_context(task)
    assert context.course_id == "course-1"
    assert context.expected_answer == "It creates an equal superposition."
    assert context.source_references == ["chunk-1"]


@pytest.mark.parametrize(
    "changes",
    [
        {"course_id": None},
        {"learning_outcome_id": None},
        {"source_references": []},
        {"expected_answer": None, "marking_criteria": None},
    ],
)
def test_task_context_mapper_rejects_incomplete_generated_task(changes: dict[str, object]) -> None:
    values: dict[str, object] = {
        "id": "task-1", "slug": "task", "title": "Task", "module": "Foundations",
        "description": "Description", "instructions": "Instructions", "task_type": TaskType.QUIZ,
        "difficulty": "Beginner", "points": 10, "position": 1, "course_id": "course-1",
        "learning_outcome_id": "outcome-1", "expected_answer": "Expected", "source_references": ["chunk-1"],
    }
    values.update(changes)
    with pytest.raises(ValueError):
        to_feedback_task_context(LearningTask(**values))
