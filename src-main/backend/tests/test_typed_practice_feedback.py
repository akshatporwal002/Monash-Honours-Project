"""Real typed practice submissions must not masquerade as formal assessment."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select, update
from support.curriculum import setup_curriculum
from support.task_review import approve_sourced_fixture_task, bootstrap_reviewed_demo

from app.api.feedback_dependencies import get_feedback_executor
from app.core.config import Settings, settings
from app.db.session import create_session_factory, get_db_session
from app.domain.platform_enums import EvidenceType
from app.main import create_app
from app.models.activity_continuation import ActivityProgress, ActivitySuggestion
from app.models.assessment import AssessmentAttempt, AssessmentDecision
from app.models.continuation import ContinuationJob
from app.models.enums import ContinuationState, FeedbackStatus, TaskType, WorkflowStage
from app.models.learning_evidence import LearningEvidence
from app.models.lms import SubmissionAttempt
from app.models.persistence import FeedbackRecord, LearningTask, WorkflowRun
from app.models.user import UserRole
from app.schemas.episode import EpisodePayloadV1, ResponseContent
from app.schemas.feedback import AssessmentContextStatus
from app.schemas.lms import SubmissionCreate
from app.services.assessment.feedback_context import SqlAlchemyAssessmentFeedbackContextProvider
from app.services.episode_evidence import canonical_response_digest
from app.services.feedback.runtime import LmsSubmissionProvider
from app.services.lms import DEMO_PASSWORD, LmsService, LmsServiceError
from app.worker import build_database_worker, build_offline_worker_adapters

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def practice(session):
    users, _ = bootstrap_reviewed_demo(session)
    student = next(user for user in users if user.role == UserRole.STUDENT)
    task = session.scalar(select(LearningTask).order_by(LearningTask.position))
    task.task_type = TaskType.EXPLANATION
    task.expected_answer = "A qubit can be in a superposition of zero and one."
    task.marking_criteria = {"keywords": ["qubit", "superposition"]}
    session.commit()
    approve_sourced_fixture_task(session, task, source_text=task.expected_answer)
    payload = SubmissionCreate(
        answer=task.expected_answer,
        idempotency_key="synthetic-typed-practice",
        episode=EpisodePayloadV1(
            supported={
                "explanation": task.expected_answer,
                "reasoning": "The amplitudes specify the state.",
            }
        ),
    )
    return LmsService(session), student, task, payload


def run_worker(session, monkeypatch, *, worker=None):
    monkeypatch.setattr(settings, "llm_api_key", None)
    monkeypatch.setattr(settings, "research_enabled", False)
    monkeypatch.setattr(
        settings, "learning_event_pseudonym_secret", SecretStr("synthetic-practice-key-" * 3)
    )
    configured = Settings(_env_file=None, research_enabled=False)
    worker = worker or build_database_worker(
        build_offline_worker_adapters(configured),
        configured_settings=configured,
        engine=session.get_bind(),
        session_factory=create_session_factory(session.get_bind()),
        now=lambda: datetime.now(UTC) + timedelta(minutes=5),
    )
    for _ in range(3):
        asyncio.run(worker.run_once())
    session.expire_all()
    return worker


def test_typed_practice_worker_produces_feedback_without_formal_grade(db_session, monkeypatch):
    lms, student, task, payload = practice(db_session)
    response = lms.submit(student, task.id, payload)
    run_worker(db_session, monkeypatch)
    workflow = db_session.scalar(
        select(WorkflowRun).where(WorkflowRun.submission_id == response.id)
    )
    assert workflow.failure_category != "context_integrity_error"
    assert workflow.current_stage == WorkflowStage.COMPLETED, workflow.failure_category
    feedback = db_session.scalar(
        select(FeedbackRecord).where(FeedbackRecord.workflow_run_id == workflow.id)
    )
    assert feedback is not None and feedback.status == FeedbackStatus.ACCEPTED
    assert db_session.scalar(select(AssessmentAttempt)) is None
    assert db_session.scalar(select(AssessmentDecision)) is None


class DeferredExecutor:
    """Leave API-accepted work for the actual database worker to recover."""

    async def execute(self, *args, **kwargs):
        pass


@pytest.mark.parametrize("episode_only", [False, True])
def test_api_typed_practice_feedback_continuation_and_retry(db_session, monkeypatch, episode_only):
    _, student, task, payload = practice(db_session)
    _, _, _, _, tasks, _, _ = setup_curriculum(db_session)
    if episode_only:
        payload = payload.model_copy(update={"answer": "", "idempotency_key": None})
    factory = create_session_factory(db_session.get_bind())

    def database():
        with factory() as session:
            yield session

    monkeypatch.setattr(settings, "llm_api_key", None)
    monkeypatch.setattr(settings, "research_enabled", False)
    app = create_app()
    app.dependency_overrides[get_db_session] = database
    app.dependency_overrides[get_feedback_executor] = DeferredExecutor
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": student.email, "password": DEMO_PASSWORD},
        )
        assert login.status_code == 200, login.text
        headers = {
            settings.csrf_header_name: client.cookies.get(settings.csrf_cookie_name),
            "Origin": settings.frontend_origin,
        }
        url = f"/api/v1/students/me/tasks/{task.id}/submissions"
        accepted = client.post(url, json=payload.model_dump(mode="json"), headers=headers)
        assert accepted.status_code == 201, accepted.text
        identity = accepted.json()["id"]
        assert accepted.json()["formal_assessment"] is None
        worker = run_worker(db_session, monkeypatch)
        workflow = db_session.scalar(
            select(WorkflowRun).where(WorkflowRun.submission_id == identity)
        )
        assert workflow.current_stage == WorkflowStage.COMPLETED, workflow.failure_category
        feedback = db_session.scalar(
            select(FeedbackRecord).where(FeedbackRecord.workflow_run_id == workflow.id)
        )
        assert feedback.status == FeedbackStatus.ACCEPTED
        continuation = db_session.get(ContinuationJob, workflow.id)
        assert continuation.state == ContinuationState.COMPLETED, continuation.failure_category
        progress = db_session.get(ActivityProgress, workflow.id)
        suggestion = db_session.get(ActivitySuggestion, workflow.id)
        assert progress.snapshot_id and suggestion.task_id == tasks[1].id
        explanation = db_session.scalar(
            select(LearningEvidence).where(
                LearningEvidence.response_version_id == identity,
                LearningEvidence.evidence_type == EvidenceType.EXPLANATION,
            )
        )
        assert explanation is not None and explanation.id in progress.evidence_ids
        stored = db_session.get(SubmissionAttempt, identity)
        assert stored.episode == payload.episode.model_dump(mode="json")
        assert stored.response_schema_version == "practice.response.v1"
        assert stored.content_digest and stored.content_digest.startswith("sha256:")
        assert stored.assessment_work_start_id is None and stored.task_form_version_id is None
        if payload.idempotency_key:
            original_digest = stored.content_digest
            retry = client.post(url, json=payload.model_dump(mode="json"), headers=headers)
            assert retry.status_code == 201 and retry.json()["id"] == identity
            changed = payload.model_dump(mode="json")
            changed["episode"] = None
            conflict = client.post(url, json=changed, headers=headers)
            assert conflict.status_code == 409, conflict.text
            run_worker(db_session, monkeypatch, worker=worker)
            assert db_session.get(SubmissionAttempt, identity).content_digest == original_digest
            for model in (
                SubmissionAttempt,
                WorkflowRun,
                FeedbackRecord,
                ActivityProgress,
                ActivitySuggestion,
            ):
                assert db_session.scalar(select(func.count()).select_from(model)) == 1
        assert db_session.scalar(select(AssessmentAttempt)) is None
        assert db_session.scalar(select(AssessmentDecision)) is None


def resolution(session, identity):
    submission = asyncio.run(LmsSubmissionProvider(session).get_submission(identity))
    assert submission is not None
    return asyncio.run(SqlAlchemyAssessmentFeedbackContextProvider(session).resolve(submission))


@pytest.mark.parametrize("legacy", [False, True])
def test_typed_retry_preserves_stored_version_digest_and_exact_content(db_session, legacy):
    lms, student, task, payload = practice(db_session)
    submitted = lms.submit(student, task.id, payload)
    response = db_session.get(SubmissionAttempt, submitted.id)
    if legacy:
        # Seed the historical bug's exact stored shape; production never rewrites history.
        legacy_digest = canonical_response_digest(
            content=ResponseContent(answer=payload.answer),
            episode=payload.episode,
            schema_version="assessment.response.v2",
        )
        db_session.execute(
            update(SubmissionAttempt)
            .where(SubmissionAttempt.id == response.id)
            .values(
                response_schema_version="assessment.response.v2",
                content_digest=legacy_digest,
            )
        )
        db_session.commit()
        db_session.expire_all()
    before = (
        response.id,
        response.response_schema_version,
        response.content_digest,
        response.episode,
    )
    task.instructions += " A later edit requiring a new review."
    db_session.commit()
    assert lms.submit(student, task.id, payload).id == response.id
    changed_episode = payload.episode.model_copy(
        update={
            "supported": payload.episode.supported.model_copy(
                update={"explanation": payload.episode.supported.explanation + " "}
            )
        }
    )
    for changed in (
        payload.model_copy(update={"episode": changed_episode}),
        payload.model_copy(update={"episode": None}),
        payload.model_copy(update={"answer": payload.answer + " "}),
        payload.model_copy(update={"assessment_work_start_id": "foreign-work"}),
    ):
        with pytest.raises(LmsServiceError) as error:
            lms.submit(student, task.id, changed)
        assert error.value.status_code == 409
        db_session.rollback()
    assert (
        response.id,
        response.response_schema_version,
        response.content_digest,
        response.episode,
    ) == before
    resolved = resolution(db_session, response.id)
    if legacy:
        assert resolved.reason_code == "ASSESSMENT_ATTEMPT_MISSING"
    else:
        # Retry identity is stable, but unreviewed task edits cannot release model feedback.
        assert resolved.reason_code == "PRACTICE_RESPONSE_INVALID"
    assert db_session.scalar(select(func.count()).select_from(SubmissionAttempt)) == 1


@pytest.mark.parametrize("corruption", ["digest", "schema", "missing"])
def test_typed_formal_context_still_fails_closed(db_session, monkeypatch, corruption):
    from test_task14_lifecycle import complete, setup_episode

    lms, student, task, started = setup_episode(db_session)
    draft = complete(lms, student, task, started)
    submitted = lms.submit(
        student, task.id, SubmissionCreate(**draft.model_dump(), idempotency_key="formal")
    )
    response = db_session.get(SubmissionAttempt, submitted.id)
    if corruption == "missing":
        # A preserved response with no assessment attempt is not practice.
        orphan = SubmissionAttempt(
            **{
                column.name: getattr(response, column.name)
                for column in SubmissionAttempt.__table__.columns
                if column.name not in {"id", "attempt_number", "idempotency_key"}
            },
            attempt_number=2,
            idempotency_key="orphan",
        )
        db_session.add(orphan)
        db_session.flush()
        db_session.add(
            WorkflowRun(
                submission_id=orphan.id,
                current_stage=WorkflowStage.PENDING,
                course_id=task.course_id,
                task_id=task.id,
            )
        )
        identity = orphan.id
    else:
        # Simulate damaged storage through SQL, bypassing the ORM immutability guard in this fixture.
        changes = (
            {"content_digest": "sha256:" + "0" * 64}
            if corruption == "digest"
            else {"response_schema_version": "practice.response.v1"}
        )
        db_session.execute(
            update(SubmissionAttempt).where(SubmissionAttempt.id == response.id).values(**changes)
        )
        identity = response.id
    db_session.commit()
    resolved = resolution(db_session, identity)
    assert resolved.status in {AssessmentContextStatus.MISSING, AssessmentContextStatus.INVALID}
    assert resolved.reason_code == (
        "ASSESSMENT_ATTEMPT_MISSING" if corruption == "missing" else "FROZEN_RESPONSE_INVALID"
    )
    run_worker(db_session, monkeypatch)
    workflow = db_session.scalar(select(WorkflowRun).where(WorkflowRun.submission_id == identity))
    assert workflow.failure_category == "context_integrity_error"
    assert (
        db_session.scalar(
            select(FeedbackRecord).where(FeedbackRecord.workflow_run_id == workflow.id)
        )
        is None
    )


@pytest.mark.parametrize(
    "invalid",
    [
        {"episode": None},
        {"assessment_work_start_id": "work"},
        {"task_form_version_id": "form"},
        {"declared_conditions": {}},
        {"schema_version": "practice.response.v99"},
    ],
)
def test_practice_digest_rejects_missing_episode_unknown_version_and_formal_bindings(invalid):
    values = dict(
        content=ResponseContent(),
        episode=EpisodePayloadV1(supported={}),
        schema_version="practice.response.v1",
    )
    with pytest.raises(ValueError):
        canonical_response_digest(**{**values, **invalid})


@pytest.mark.parametrize(
    "version,expected",
    [
        (
            "assessment.response.v1",
            "sha256:c7d6c8bde364a79792b8081796be167a1479a0052a3becc140aba9de0f3e81bd",
        ),
        (
            "assessment.response.v2",
            "sha256:3e2b0e886f7144086a57652626fb4b973dbc419d147064fad805dd3fd746f0ea",
        ),
    ],
)
def test_historical_digest_vectors_are_unchanged(version, expected):
    # Recorded using the original hash implementation at coordinator commit 0eaf467.
    assert (
        canonical_response_digest(
            content=ResponseContent(answer="  supported\n", code="h(0)\n"),
            episode=EpisodePayloadV1(supported={"explanation": "  exact explanation\n"})
            if version.endswith("v2")
            else None,
            schema_version=version,
            assessment_work_start_id="work",
            task_form_version_id="form",
            declared_conditions={"transfer": True},
        )
        == expected
    )
