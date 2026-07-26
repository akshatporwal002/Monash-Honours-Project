from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import LearningMaterial, LearningTask, MaterialChunk, TaskType


def make_material(**overrides: object) -> LearningMaterial:
    values: dict[str, object] = {
        "course_id": "course-quantum-101",
        "original_filename": "week-1.pdf",
        "mime_type": "application/pdf",
        "content_hash": "hash-week-1",
    }
    values.update(overrides)
    return LearningMaterial(**values)


def test_material_and_ordered_chunks_persist(db_session) -> None:
    material = make_material()
    db_session.add(material)
    db_session.flush()
    db_session.add_all(
        [
            MaterialChunk(material_id=material.id, chunk_index=0, chunk_text="Qubits have two basis states.", token_count=6),
            MaterialChunk(material_id=material.id, chunk_index=1, chunk_text="Measurement produces classical output.", token_count=5),
        ]
    )
    db_session.commit()

    assert [chunk.chunk_index for chunk in material.chunks] == [0, 1]


@pytest.mark.parametrize(
    "material",
    [
        make_material(original_filename=None, source_url=None),
        make_material(original_filename="week-1.pdf", source_url="https://example.edu/week-1.pdf"),
        make_material(original_filename=None, source_url="http://example.edu/week-1.pdf"),
    ],
)
def test_material_source_constraints(db_session, material: LearningMaterial) -> None:
    db_session.add(material)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_material_hash_and_chunk_index_are_unique(db_session) -> None:
    material = make_material()
    db_session.add(material)
    db_session.commit()

    db_session.add(make_material(original_filename="duplicate.pdf"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.add(MaterialChunk(material_id=material.id, chunk_index=0, chunk_text="First"))
    db_session.commit()
    db_session.add(MaterialChunk(material_id=material.id, chunk_index=0, chunk_text="Duplicate"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_chunks_cascade_when_material_is_deleted(db_session) -> None:
    material = make_material()
    db_session.add(material)
    db_session.flush()
    chunk = MaterialChunk(material_id=material.id, chunk_index=0, chunk_text="Delete with material")
    db_session.add(chunk)
    db_session.commit()
    chunk_id = chunk.id

    db_session.delete(material)
    db_session.commit()
    db_session.expire_all()
    assert db_session.get(MaterialChunk, chunk_id) is None


def test_task_generation_metadata_constraints_and_legacy_defaults(db_session) -> None:
    legacy_task = LearningTask(
        slug="legacy-task",
        title="Legacy task",
        module="Foundations",
        description="Existing dashboard task",
        instructions="Answer the question.",
        task_type=TaskType.QUIZ,
        difficulty="Beginner",
        points=10,
        position=1,
    )
    db_session.add(legacy_task)
    db_session.commit()
    assert legacy_task.generation_total_tokens == 0
    assert legacy_task.source_references == []

    invalid_task = LearningTask(
        slug="bad-generation-task",
        title="Bad generation task",
        module="Foundations",
        description="Invalid token metadata",
        instructions="Answer the question.",
        task_type=TaskType.QUIZ,
        difficulty="Beginner",
        points=10,
        position=2,
        generation_provider="provider",
        generation_model="model",
        generation_prompt_version="v1",
        generation_input_tokens=1,
        generation_output_tokens=2,
        generation_total_tokens=2,
        generation_estimated_cost=Decimal("0.1"),
    )
    db_session.add(invalid_task)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
