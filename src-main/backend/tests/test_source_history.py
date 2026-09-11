from __future__ import annotations

import asyncio
import io
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from support.migration_assertions import protected_history_manifest

from app.api.routes.materials import get_actor_id, get_course_access_policy, get_material_storage
from app.db.base import Base
from app.db.session import get_db_session
from app.main import create_app
from app.models import LearningMaterial, MaterialChunk, MaterialIndexStatus
from app.models.source_history import SourceApproval, SourcePassage, SourceRevision, SourceUse
from app.schemas.feedback import SubmissionContext, TaskContext
from app.services.feedback.runtime import TaskSourceRetrievalProvider
from app.services.rag.contracts import (
    ExtractedBlock,
    ExtractedDocument,
    RetrievalPurpose,
    RetrievalQuery,
)
from app.services.rag.errors import CourseAccessDeniedError
from app.services.rag.fakes import (
    AllowAllCourseAccessPolicy,
    DeterministicEmbeddingProvider,
    InMemoryVectorStore,
    StaticDocumentExtractor,
)
from app.services.rag.ingestion import MaterialProcessor
from app.services.rag.local_retrieval import LocalCourseRetrievalService
from app.services.rag.source_history import bind_sources, record_approval
from app.services.rag.storage import LocalFileStorage
from scripts.verify_sqlite_backup import database_manifest


@pytest.fixture
def source_context(tmp_path: Path, monkeypatch):
    from support.material_scanning import enable_synthetic_scanning

    enable_synthetic_scanning(monkeypatch)
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'sources.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session = Session(engine)
    storage = LocalFileStorage(tmp_path / "files", 1_000_000)
    staged = storage.stage_upload("original.pdf", io.BytesIO(b"%PDF-1.4 original"))
    material = LearningMaterial(
        course_id="course-1",
        original_filename="original.pdf",
        content_hash=staged.content_hash,
        mime_type=staged.mime_type,
    )
    session.add(material)
    session.flush()
    material.storage_key = storage.commit(staged, material.id)
    session.commit()
    vectors = InMemoryVectorStore()

    def process(body: str, *, force: bool = False):
        document = ExtractedDocument(
            (ExtractedBlock(0, body, "Quantum gates", "Page 3", "paragraph"),), "Notes", len(body)
        )
        return MaterialProcessor(
            session,
            storage,
            {"application/pdf": StaticDocumentExtractor(document)},
            DeterministicEmbeddingProvider(),
            vectors,
        ).process(material, force=force)

    yield session, storage, material, process
    session.close()
    engine.dispose()


def test_exact_passage_and_approval_survive_reprocessing_and_are_bound_to_outputs(source_context):
    session, _, material, process = source_context
    original = "Hadamard creates superposition. The old approved passage."
    process(original)
    revision_id = material.current_source_revision_id
    passage_id = session.scalar(select(MaterialChunk.id))
    approval = record_approval(
        session,
        course_id=material.course_id,
        material_id=material.id,
        revision_id=revision_id,
        actor_id="educator-1",
        state="APPROVED",
        reason="Reviewed the exact lesson passage",
    )
    for kind in ("task", "feedback", "assessment"):
        assert bind_sources(
            session,
            course_id=material.course_id,
            output_type=kind,
            output_id=f"{kind}-1",
            output_version="v1",
            references=[passage_id],
            strict=True,
        ) == [passage_id]
    session.commit()
    approval_id = approval.id
    process("A different revised passage about measurement.", force=True)
    assert material.current_source_revision_id != revision_id
    assert session.get(MaterialChunk, passage_id) is None
    archived = session.get(SourcePassage, passage_id)
    assert (archived.chunk_text, archived.heading, archived.location_label) == (
        original,
        "Quantum gates",
        "Page 3",
    )
    assert session.get(SourceRevision, revision_id).extracted_blocks[0]["text"] == original
    uses = list(session.scalars(select(SourceUse)))
    assert {item.output_type for item in uses} == {"task", "feedback", "assessment"}
    assert {item.passage_id for item in uses} == {passage_id}
    assert {item.approval_id for item in uses} == {approval_id}
    assert session.scalar(select(func.count()).select_from(SourceApproval)) == 1
    record_approval(
        session,
        course_id=material.course_id,
        material_id=material.id,
        revision_id=revision_id,
        actor_id="educator-1",
        state="REVOKED",
        reason="Retained for history but withdrawn from new use",
    )
    session.commit()
    assert {item.approval_id for item in session.scalars(select(SourceUse))} == {approval_id}
    with pytest.raises(ValueError, match="Retired or revoked"):
        bind_sources(
            session,
            course_id=material.course_id,
            output_type="task",
            output_id="new-task",
            output_version="v1",
            references=[passage_id],
            strict=True,
        )

    frozen = LocalCourseRetrievalService(session).search(
        RetrievalQuery(
            material.course_id,
            "Hadamard superposition",
            RetrievalPurpose.FEEDBACK,
            allowed_chunk_ids=(passage_id,),
        )
    )
    assert frozen.hits[0].chunk_text == original
    assert "original.pdf" in frozen.hits[0].source_label
    current = LocalCourseRetrievalService(session).search(
        RetrievalQuery(material.course_id, "measurement", RetrievalPurpose.SEARCH)
    )
    assert current.hits[0].chunk_id != passage_id


def test_failed_reprocessing_does_not_publish_partial_source_revision(source_context):
    session, storage, material, process = source_context
    process("Original Hadamard evidence about quantum superposition.")
    revision_id = material.current_source_revision_id
    original_ids = list(session.scalars(select(MaterialChunk.id)))

    class BrokenEmbedding(DeterministicEmbeddingProvider):
        def embed_documents(self, texts):
            raise RuntimeError("provider unavailable")

    document = ExtractedDocument(
        (
            ExtractedBlock(
                0, "New content about quantum circuit measurement.", None, "Page 9", "paragraph"
            ),
        ),
        None,
        11,
    )
    with pytest.raises(RuntimeError, match="provider unavailable"):
        MaterialProcessor(
            session,
            storage,
            {"application/pdf": StaticDocumentExtractor(document)},
            BrokenEmbedding(),
            InMemoryVectorStore(),
        ).process(material, force=True)
    assert material.current_source_revision_id == revision_id
    assert list(session.scalars(select(MaterialChunk.id))) == original_ids
    assert session.scalar(select(func.count()).select_from(SourceRevision)) == 1
    assert material.indexing_status == MaterialIndexStatus.FAILED


def test_source_history_blocks_raw_mutation_and_cross_course_citations(source_context):
    session, _, material, process = source_context
    process("Original evidence about Hadamard quantum gates.")
    passage_id = session.scalar(select(SourcePassage.id))
    with pytest.raises(IntegrityError, match="append-only"):
        session.execute(
            text("UPDATE source_passages SET chunk_text='tampered' WHERE id=:id"),
            {"id": passage_id},
        )
    session.rollback()
    with pytest.raises(IntegrityError, match="append-only"):
        session.execute(text("DELETE FROM source_revisions"))
    session.rollback()
    with pytest.raises(IntegrityError, match="append-only"):
        session.execute(
            text(
                "INSERT OR REPLACE INTO source_passages SELECT * FROM source_passages WHERE id=:id"
            ),
            {"id": passage_id},
        )
    session.rollback()
    with pytest.raises(ValueError, match="in this course"):
        bind_sources(
            session,
            course_id="course-2",
            output_type="task",
            output_id="wrong-course",
            output_version="v1",
            references=[passage_id],
            strict=True,
        )
    assert session.scalar(select(func.count()).select_from(SourceUse)) == 0
    bind_sources(
        session,
        course_id=material.course_id,
        output_type="task",
        output_id="task",
        output_version="v1",
        references=[passage_id],
        strict=True,
    )
    session.commit()
    bind_sources(
        session,
        course_id=material.course_id,
        output_type="task",
        output_id="task",
        output_version="v1",
        references=[passage_id],
        strict=True,
    )
    session.commit()
    assert session.scalar(select(func.count()).select_from(SourceUse)) == 1


def test_reviewer_can_recover_passage_and_file_after_replacement_and_retirement(source_context):
    session, storage, material, process = source_context
    process("Original evidence about Hadamard quantum gates.")
    old_revision = material.current_source_revision_id
    old_key = material.storage_key
    old_passage = session.scalar(select(SourcePassage.id))
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_material_storage] = lambda: storage
    app.dependency_overrides[get_actor_id] = lambda: "educator-1"
    app.dependency_overrides[get_course_access_policy] = AllowAllCourseAccessPolicy
    base = f"/api/v1/courses/{material.course_id}/materials"
    with TestClient(app) as client:
        assert (
            client.post(
                f"{base}/{material.id}/revisions/{old_revision}/approvals",
                json={"state": "APPROVED", "reason": "Approved original"},
            ).status_code
            == 201
        )
        bind_sources(
            session,
            course_id=material.course_id,
            output_type="task",
            output_id="review-task",
            output_version="original-v1",
            references=[old_passage],
            strict=True,
        )
        session.commit()
        replaced = client.post(
            f"{base}/{material.id}/replacement",
            files={"file": ("new.pdf", b"%PDF-1.4 replaced", "application/pdf")},
        )
        assert replaced.status_code == 200, replaced.text
        assert replaced.json()["storage_key"] != old_key
        assert (storage.upload_dir / old_key).read_bytes() == b"%PDF-1.4 original"
        process("Replacement evidence about quantum measurement behaviour.")
        history = client.get(f"{base}/{material.id}/revisions").json()
        assert [item["version"] for item in history] == [2, 1]
        assert [item["approval_state"] for item in history] == ["UNREVIEWED", "APPROVED"]
        assert client.delete(f"{base}/{material.id}").status_code == 204
        assert client.get(f"{base}/{material.id}").status_code == 404
        preserved = client.get(f"{base}/{material.id}/revisions/{old_revision}")
        assert preserved.status_code == 200
        assert (
            preserved.json()["passages"][0]["chunk_text"]
            == "Original evidence about Hadamard quantum gates."
        )
        assert (
            client.get(f"{base}/passages/{old_passage}").json()["chunk_text"]
            == "Original evidence about Hadamard quantum gates."
        )
        assert (
            client.get(f"/api/v1/courses/course-2/materials/passages/{old_passage}").status_code
            == 404
        )
        assert client.post(f"{base}/{material.id}/process").status_code == 404
        assert client.get(base).json() == []
        assert (
            client.post(
                f"{base}/{material.id}/revisions/{old_revision}/approvals",
                json={"state": "APPROVED", "reason": "Cannot approve retired"},
            ).status_code
            == 409
        )
        assert (storage.upload_dir / old_key).is_file()
        citations = client.get(f"{base}/citations/task/review-task").json()
        assert len(citations) == 1
        assert citations[0]["passage_id"] == old_passage
        assert citations[0]["revision_id"] == old_revision
        assert citations[0]["material_id"] == material.id
        assert citations[0]["approval_id"] is not None
        assert client.get(f"{base}/citations/task/review-task?output_version=missing").json() == []
        assert (
            client.get("/api/v1/courses/course-2/materials/citations/task/review-task").json() == []
        )

        class Denied(AllowAllCourseAccessPolicy):
            def require_manage(self, actor_id, course_id):
                raise CourseAccessDeniedError()

        app.dependency_overrides[get_course_access_policy] = Denied
        assert client.get(f"{base}/{material.id}/revisions/{old_revision}").status_code == 403
        assert client.get(f"{base}/citations/task/review-task").status_code == 403


def test_current_revision_does_not_change_task_feedback_sources(source_context):
    session, _, material, process = source_context
    process("Hadamard old passage about quantum superposition.")
    old_id = session.scalar(select(SourcePassage.id))
    process("Updated source passage about quantum gates.", force=True)
    task = TaskContext(
        task_id="task-1",
        course_id=material.course_id,
        task_type="quiz",
        prompt="Explain Hadamard",
        difficulty="beginner",
        source_references=[old_id],
        learning_outcome_id="outcome-1",
        expected_answer="A superposition",
    )
    submission = SubmissionContext(
        submission_id="s1",
        student_id="u1",
        task_id="task-1",
        course_id=material.course_id,
        submitted_answer="A superposition",
        attempt_number=1,
        submitted_at=datetime.now(UTC),
    )
    context = asyncio.run(
        TaskSourceRetrievalProvider(session).get_retrieval_context(task, submission)
    )
    assert len(context.items) == 1
    assert context.items[0].chunk_text == "Hadamard old passage about quantum superposition."
    assert context.items[0].source_id == old_id


def test_migration_backfills_without_inventing_approval_and_protects_populated_history(
    tmp_path: Path,
):
    database = tmp_path / "legacy.db"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")
    command.upgrade(config, "20260821_0022")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id,email,password_hash,full_name,role,is_active) VALUES (100,'owner@example.test','unused','Source Owner','educator',1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO courses (id,educator_id,code,title,description,state,enrollment_open,created_at,updated_at) VALUES ('legacy',100,'SRC','Source course','','draft',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO learning_materials (id, course_id, original_filename, mime_type, content_hash, indexing_status, processing_revision, created_at) VALUES ('m','legacy','old.pdf','application/pdf','hash','indexed',0,CURRENT_TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO material_chunks (id, material_id, chunk_index, chunk_text, token_count, chunk_hash, created_at) VALUES ('p','m',0,'Preserved legacy passage',3,'chunk-hash',CURRENT_TIMESTAMP)"
            )
        )
    command.upgrade(config, "head")
    with engine.connect() as conn:
        assert (
            conn.execute(text("SELECT chunk_text FROM source_passages WHERE id='p'")).scalar_one()
            == "Preserved legacy passage"
        )
        assert (
            conn.execute(text("SELECT provenance FROM source_revisions")).scalar_one()
            == "LEGACY_SNAPSHOT"
        )
        assert conn.execute(text("SELECT COUNT(*) FROM source_approvals")).scalar_one() == 0
    before = database_manifest(database)
    protected_before = protected_history_manifest(database)
    command.stamp(config, "20260821_0022")
    command.upgrade(config, "head")
    assert database_manifest(database) == before
    with engine.begin() as conn:
        with pytest.raises(IntegrityError, match="append-only"):
            conn.execute(
                text(
                    "INSERT OR REPLACE INTO source_passages SELECT * FROM source_passages WHERE id='p'"
                )
            )
    with pytest.raises(RuntimeError, match="history is protected"):
        command.downgrade(config, "20260821_0022")
    assert protected_history_manifest(database) == protected_before
    with engine.connect() as conn:
        assert (
            conn.execute(text("SELECT chunk_text FROM source_passages WHERE id='p'")).scalar_one()
            == "Preserved legacy passage"
        )
    engine.dispose()
