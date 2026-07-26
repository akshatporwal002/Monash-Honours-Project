import asyncio
import io
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import (
    LearningMaterial,
    LearningTask,
    MaterialIndexStatus,
    StudentProfile,
    StudentSubmission,
    SubmissionStatus,
    TaskType,
)
from app.schemas.feedback import SubmissionContext
from app.services.feedback.composition import build_grounded_feedback_context_collector
from app.services.feedback.providers import SqlAlchemySubmissionProvider
from app.services.rag.contracts import ExtractedBlock, ExtractedDocument
from app.services.rag.fakes import InMemoryVectorStore, StaticDocumentExtractor
from app.services.rag.ingestion import MaterialProcessor
from app.services.rag.retrieval import RetrievalService
from app.services.rag.storage import LocalFileStorage


class FlatEmbeddingProvider:
    model_id = "flat-test-v1"
    dimension = 1

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0]


def _session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{(tmp_path / 'feedback-rag.db').as_posix()}")
    Base.metadata.create_all(engine)
    return Session(engine)


def _material(session: Session, storage: LocalFileStorage, course_id: str) -> LearningMaterial:
    staged = storage.stage_upload("notes.pdf", io.BytesIO(b"%PDF-1.4\nnotes"))
    material = LearningMaterial(
        course_id=course_id,
        original_filename="notes.pdf",
        mime_type="application/pdf",
        content_hash=f"sha256:{course_id}",
        indexing_status=MaterialIndexStatus.PENDING,
        file_size_bytes=staged.file_size_bytes,
    )
    session.add(material)
    session.flush()
    material.storage_key = storage.commit(staged, material.id)
    session.commit()
    return material


def _indexed_material(
    session: Session, storage: LocalFileStorage, course_id: str, vectors: InMemoryVectorStore
) -> LearningMaterial:
    material = _material(session, storage, course_id)
    document = ExtractedDocument(
        (
            ExtractedBlock(
                0, "Hadamard creates a quantum superposition state.", "Gates", "Page 1", "paragraph"
            ),
        ),
        None,
        50,
    )
    MaterialProcessor(
        session,
        storage,
        {"application/pdf": StaticDocumentExtractor(document)},
        FlatEmbeddingProvider(),
        vectors,
    ).process(material)
    return material


def _task_and_submission(session: Session, material: LearningMaterial) -> SubmissionContext:
    student = StudentProfile(display_name="Student")
    session.add(student)
    session.flush()
    task = LearningTask(
        slug=f"task-{material.course_id}",
        title="Hadamard",
        module="Foundations",
        description="Explain H",
        instructions="Explain the Hadamard gate.",
        task_type=TaskType.QUIZ,
        difficulty="beginner",
        points=10,
        position=1,
        course_id=material.course_id,
        learning_outcome_id="outcome-1",
        expected_answer="A superposition.",
        source_references=[material.chunks[0].id],
    )
    session.add(task)
    session.flush()
    submission = StudentSubmission(
        student_id=student.id,
        task_id=task.id,
        answer="It makes superposition.",
        status=SubmissionStatus.SUBMITTED,
        attempts=1,
        score=0,
        submitted_at=datetime.now(UTC),
    )
    session.add(submission)
    session.commit()
    return asyncio.run(SqlAlchemySubmissionProvider(session).get_submission(submission.id))


def test_feedback_composition_returns_only_task_grounded_course_hits(tmp_path: Path) -> None:
    session, storage, vectors = (
        _session(tmp_path),
        LocalFileStorage(tmp_path / "uploads", 1024 * 1024),
        InMemoryVectorStore(),
    )
    course_one = _indexed_material(session, storage, "course-1", vectors)
    _indexed_material(session, storage, "course-2", vectors)
    submission = _task_and_submission(session, course_one)
    collector = build_grounded_feedback_context_collector(
        session, RetrievalService(session, FlatEmbeddingProvider(), vectors)
    )

    context = asyncio.run(collector.collect(submission, "00000000-0000-4000-8000-000000000001"))

    assert len(context.retrieval_context) == 1
    assert context.retrieval_context[0].chunk_id == course_one.chunks[0].id
    assert context.retrieval_context[0].source_id == course_one.id


def test_feedback_composition_handles_no_retrieval_hits(tmp_path: Path) -> None:
    session, storage, vectors = (
        _session(tmp_path),
        LocalFileStorage(tmp_path / "uploads", 1024 * 1024),
        InMemoryVectorStore(),
    )
    material = _indexed_material(session, storage, "course-1", vectors)
    submission = _task_and_submission(session, material)
    vectors.delete_material(material.id)
    collector = build_grounded_feedback_context_collector(
        session, RetrievalService(session, FlatEmbeddingProvider(), vectors)
    )

    context = asyncio.run(collector.collect(submission, "00000000-0000-4000-8000-000000000001"))

    assert context.retrieval_context == []
