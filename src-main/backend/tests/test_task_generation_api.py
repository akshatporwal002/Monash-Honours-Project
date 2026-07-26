import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.routes.task_generation import (
    get_actor_id,
    get_course_access_policy,
    get_task_generation_service,
)
from app.core.security import hash_password
from app.db.session import get_db_session
from app.main import create_app
from app.models import (
    Course,
    CourseModule,
    LearningMaterial,
    LearningOutcome,
    LearningTask,
    MaterialChunk,
    MaterialIndexStatus,
    OutcomeKind,
    TaskType,
    User,
    UserRole,
)
from app.services.local_ai import LocalTaskGenerationClient
from app.services.rag.contracts import RetrievalHit, RetrievalResult, TaskGenerationResponse
from app.services.rag.fakes import AllowAllCourseAccessPolicy
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
    return GenerateTasksInput(
        "course-1", None, "outcome-1", "Explain superposition", 1, (TaskType.QUIZ,), ("beginner",)
    )


def _hit() -> RetrievalHit:
    return RetrievalHit(
        "chunk-1", "material-1", "course-1", "Grounded material", "Notes — Page 1", 0.9, 0
    )


def _seed_course_scope(db_session: Session) -> None:
    educator = User(
        email="generator@example.edu",
        full_name="Task Generator",
        password_hash=hash_password("test-password"),
        role=UserRole.EDUCATOR,
    )
    db_session.add(educator)
    db_session.flush()
    db_session.add(
        Course(
            id="course-1",
            educator_id=educator.id,
            code="GEN-1",
            title="Generation",
            description="",
        )
    )
    db_session.add(
        CourseModule(
            id="module-1",
            course_id="course-1",
            title="Superposition",
            description="",
            position=1,
        )
    )
    db_session.add(
        LearningOutcome(
            id="outcome-1",
            module_id="module-1",
            title="Explain superposition",
            statement="Explain qubit superposition",
            kind=OutcomeKind.TOPIC,
            position=1,
        )
    )
    db_session.commit()


def test_task_generation_uses_offline_local_scaffold_by_default(
    db_session: Session,
) -> None:
    _seed_course_scope(db_session)
    material = LearningMaterial(
        id="material-1",
        course_id="course-1",
        module_id="module-1",
        original_filename="superposition-notes.pdf",
        mime_type="application/pdf",
        content_hash="sha256:superposition",
        indexing_status=MaterialIndexStatus.INDEXED,
    )
    material.chunks.append(
        MaterialChunk(
            id="chunk-1",
            chunk_index=0,
            chunk_text="A Hadamard gate creates a qubit superposition.",
            location_label="Page 1",
            token_count=8,
            chunk_hash="sha256:chunk-1",
        )
    )
    db_session.add(material)
    db_session.commit()

    application = create_app()
    application.dependency_overrides[get_db_session] = lambda: db_session
    application.dependency_overrides[get_actor_id] = lambda: "educator-1"
    application.dependency_overrides[get_course_access_policy] = AllowAllCourseAccessPolicy
    response = TestClient(application).post(
        "/api/v1/courses/course-1/tasks/generate",
        json={
            "learning_outcome_id": "outcome-1",
            "learning_outcome_text": "Explain qubit superposition",
            "task_count": 1,
            "allowed_task_types": ["short_answer"],
            "difficulty_levels": ["beginner"],
        },
    )

    assert response.status_code == 200
    assert response.json()[0]["source_references"] == ["chunk-1"]
    assert response.json()[0]["task_type"] == "short_answer"
    generated = db_session.query(LearningTask).one()
    assert generated.generation_provider == "local-deterministic"
    assert generated.generation_model == "quantumlearn-task-scaffold-v1"
    assert "Hadamard gate creates a qubit superposition" in generated.description
    assert generated.position == 1
    assert generated.module_id == "module-1"


def test_default_service_does_not_construct_embedding_retrieval(
    db_session: Session,
    monkeypatch,
) -> None:
    def fail_if_called(_db: Session):
        raise AssertionError("local generation must not initialize model retrieval")

    monkeypatch.setattr(
        "app.api.routes.task_generation.get_retrieval_service",
        fail_if_called,
    )

    service = get_task_generation_service(db_session, LocalTaskGenerationClient())

    assert service.client is not None


def test_default_generation_without_content_returns_controlled_422(
    db_session: Session,
) -> None:
    _seed_course_scope(db_session)
    application = create_app()
    application.dependency_overrides[get_db_session] = lambda: db_session
    application.dependency_overrides[get_actor_id] = lambda: "educator-1"
    application.dependency_overrides[get_course_access_policy] = AllowAllCourseAccessPolicy

    response = TestClient(application).post(
        "/api/v1/courses/course-1/tasks/generate",
        json={
            "learning_outcome_id": "outcome-1",
            "learning_outcome_text": "Explain qubit superposition",
            "task_count": 1,
            "allowed_task_types": ["short_answer"],
            "difficulty_levels": ["beginner"],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "no_relevant_course_content"


def test_task_generation_rejects_invented_citations_and_no_retrieval_hits(
    db_session: Session,
) -> None:
    _seed_course_scope(db_session)
    invented = RecordingGenerator(
        (
            {
                "title": "Task",
                "prompt": "Explain",
                "instructions": "Respond",
                "task_type": "quiz",
                "difficulty": "beginner",
                "learning_outcome_id": "outcome-1",
                "expected_answer": "Answer",
                "source_references": ["invented"],
            },
        )
    )
    service = GroundedTaskGenerationService(
        db_session,
        StaticRetrieval((_hit(),)),
        invented,
    )
    try:
        asyncio.run(service.generate(_request()))
    except ValueError as error:
        assert "grounding" in str(error)
    else:
        raise AssertionError("invented citations must be rejected")

    empty = GroundedTaskGenerationService(db_session, StaticRetrieval(()), invented)
    try:
        asyncio.run(empty.generate(_request()))
    except NoRelevantCourseContentError:
        pass
    else:
        raise AssertionError("generation must not run without retrieval hits")
