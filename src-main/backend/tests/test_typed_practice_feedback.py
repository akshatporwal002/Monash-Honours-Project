"""Real typed practice submissions must not masquerade as formal assessment."""

import asyncio
import hashlib
import json
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
from app.schemas.feedback import AssessmentContextStatus, FeedbackContext, RetrievalContext
from app.schemas.lms import SubmissionCreate
from app.services.assessment.feedback_context import SqlAlchemyAssessmentFeedbackContextProvider
from app.services.episode_evidence import canonical_response_digest, response_digest_matches
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
    with pytest.raises(ValueError):
        response_digest_matches("sha256:" + "0" * 64, **{**values, **invalid})


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


@pytest.mark.parametrize("version", ["assessment.response.v2", "practice.response.v1"])
def test_application_content_changes_digest_without_rehashing_absent_defaults(version):
    def digest(application):
        return canonical_response_digest(
            content=ResponseContent(answer="same top-level answer"),
            episode=EpisodePayloadV1(supported={"application": application}),
            schema_version=version,
        )

    assert len({digest(None), digest({"answer": "first"}), digest({"answer": "changed"})}) == 3


def intermediate_digest(**values):
    """Independent fixture for the complete serialization written after ba01754."""
    content = values.pop("content")
    episode = values.pop("episode")
    raw = {
        **content.model_dump(mode="json"),
        "episode": episode.model_dump(mode="json"),
        "assessment_work_start_id": None,
        "task_form_version_id": None,
        "declared_conditions": None,
        **values,
    }
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
    )


def test_original_transfer_process_digest_golden():
    # Computed with both schema and digest implementation loaded from 0eaf467.
    episode = EpisodePayloadV1(
        supported={"explanation": "  supported\n"},
        transfer={
            "stage_start_id": "stage",
            "part_id": "transfer",
            "content": {"answer": " fresh\n", "code": "h(0)"},
            "process": {"reasoning": "  reason\n", "reflection": " reflection\n"},
        },
    )
    assert (
        canonical_response_digest(
            content=ResponseContent(answer=" original\n"),
            episode=episode,
            schema_version="assessment.response.v2",
            assessment_work_start_id="work",
            task_form_version_id="form",
            declared_conditions={"transfer": True},
        )
        == "sha256:6781a7f008c15eba14abb45c7f4418d37b96fa71dc136e7c862ba6d16395ea96"
    )


def retain_intermediate_record(session, response):
    digest = intermediate_digest(
        content=ResponseContent(
            answer=response.answer, code=response.code, circuit=response.circuit
        ),
        episode=EpisodePayloadV1.model_validate(response.episode),
        schema_version=response.response_schema_version,
        assessment_work_start_id=response.assessment_work_start_id,
        task_form_version_id=response.task_form_version_id,
        declared_conditions=response.declared_conditions,
    )
    # Seed an exact record from the intermediate writer; runtime must never rewrite it.
    session.execute(
        update(SubmissionAttempt)
        .where(SubmissionAttempt.id == response.id)
        .values(content_digest=digest)
    )
    session.commit()
    session.expire_all()
    return digest


@pytest.mark.parametrize("stage", ["supported", "transfer"])
@pytest.mark.parametrize("intermediate", [False, True])
def test_historical_verification_binds_application_content_and_conditions(stage, intermediate):
    raw = {
        "supported": {},
        "transfer": {
            "stage_start_id": "stage",
            "part_id": "transfer",
            "content": {},
            "process": {},
        },
    }
    target = raw["supported"] if stage == "supported" else raw["transfer"]["process"]
    target["application"] = {"answer": "original", "code": "h(0)", "circuit": {"gate": "h"}}
    episode = EpisodePayloadV1.model_validate(raw)
    values = dict(
        content=ResponseContent(answer="unchanged"),
        episode=episode,
        schema_version="assessment.response.v2",
    )
    digest = intermediate_digest(**values) if intermediate else canonical_response_digest(**values)
    assert response_digest_matches(digest, **values)
    for field, changed in (("answer", "changed"), ("code", "x(0)"), ("circuit", {"gate": "x"})):
        changed_raw = episode.model_dump(mode="json")
        changed_target = (
            changed_raw["supported"] if stage == "supported" else changed_raw["transfer"]["process"]
        )
        changed_target["application"][field] = changed
        assert not response_digest_matches(
            digest, **{**values, "episode": EpisodePayloadV1.model_validate(changed_raw)}
        )
    for key, value in (
        ("assessment_work_start_id", "changed"),
        ("task_form_version_id", "changed"),
        ("declared_conditions", {"changed": True}),
    ):
        assert not response_digest_matches(digest, **{**values, key: value})


def test_intermediate_practice_record_replays_and_releases_feedback_without_rewrite(
    db_session, monkeypatch
):
    lms, student, task, payload = practice(db_session)
    submitted = lms.submit(student, task.id, payload)
    response = db_session.get(SubmissionAttempt, submitted.id)
    retained = retain_intermediate_record(db_session, response)
    assert retained != canonical_response_digest(
        content=ResponseContent(answer=payload.answer),
        episode=payload.episode,
        schema_version="practice.response.v1",
    )
    assert lms.submit(student, task.id, payload).id == submitted.id
    assert resolution(db_session, submitted.id).status == AssessmentContextStatus.NOT_ASSESSED
    run_worker(db_session, monkeypatch)
    workflow = db_session.scalar(
        select(WorkflowRun).where(WorkflowRun.submission_id == submitted.id)
    )
    assert workflow.current_stage == WorkflowStage.COMPLETED, workflow.failure_category
    assert (
        db_session.scalar(
            select(FeedbackRecord).where(FeedbackRecord.workflow_run_id == workflow.id)
        ).status
        == FeedbackStatus.ACCEPTED
    )
    assert db_session.get(SubmissionAttempt, submitted.id).content_digest == retained
    changed = payload.episode.model_dump(mode="json")
    changed["supported"]["application"] = {"answer": "injected"}
    with pytest.raises(LmsServiceError) as error:
        lms.submit(
            student,
            task.id,
            payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(changed)}),
        )
    assert error.value.status_code == 409
    db_session.rollback()
    db_session.execute(
        update(SubmissionAttempt)
        .where(SubmissionAttempt.id == submitted.id)
        .values(episode=changed)
    )
    db_session.commit()
    assert resolution(db_session, submitted.id).reason_code == "PRACTICE_RESPONSE_INVALID"


def test_intermediate_formal_record_replays_reads_and_releases_exact_feedback(db_session):
    from test_task14_lifecycle import complete, setup_episode
    from test_task16_grounding import candidate, decision

    from app.models.enums import JudgeDecision

    lms, student, task, started = setup_episode(db_session)
    draft = complete(lms, student, task, started)
    payload = SubmissionCreate(**draft.model_dump(), idempotency_key="intermediate-formal")
    submitted = lms.submit(student, task.id, payload)
    response = db_session.get(SubmissionAttempt, submitted.id)
    retained = retain_intermediate_record(db_session, response)
    assert lms.submit(student, task.id, payload).id == submitted.id
    resolved = resolution(db_session, submitted.id)
    assert resolved.context is not None, resolved.reason_code
    assessed = resolved.context.model_copy(
        update={"feedback_release_allowed": True, "active_transfer": False, "context_warnings": []}
    )
    assert assessed.frozen_response.reference.content_digest == retained
    assert assessed.response_content_digest == retained
    passage = "A Hadamard operation changes the amplitudes of the input state."
    context = FeedbackContext(
        correlation_id="11111111-1111-4111-8111-111111111111",
        task=assessed.task,
        submission=asyncio.run(LmsSubmissionProvider(db_session).get_submission(submitted.id)),
        assessment_context=assessed,
        retrieval_context=[
            RetrievalContext(
                source_id="source",
                document_id="document",
                chunk_id="chunk",
                source_revision_id="revision",
                source_digest="synthetic-source-digest",
                passage_digest=hashlib.sha256(passage.encode()).hexdigest(),
                approval_id="approval",
                retrieval_request_id="retrieval",
                retrieval_version="v1",
                task_id=task.id,
                course_id=task.course_id,
                chunk_text=passage,
                relevance_score=0.9,
                source_label="Approved source",
            )
        ],
    )
    generated = candidate(context)
    assert generated.feedback_content["assessed"]["content_digest"] == retained
    assert decision(context, generated) == JudgeDecision.PASS
    assert db_session.get(SubmissionAttempt, submitted.id).content_digest == retained
    changed = response.episode.copy()
    changed["transfer"] = {
        **changed["transfer"],
        "process": {**changed["transfer"]["process"], "application": {"answer": "injected"}},
    }
    changed_episode = EpisodePayloadV1.model_validate(changed)
    frozen = assessed.frozen_response.model_copy(update={"episode": changed_episode})
    altered = context.model_copy(
        update={"assessment_context": assessed.model_copy(update={"frozen_response": frozen})}
    )
    assert candidate(altered).feedback_content.get("assessed") is None
    with pytest.raises(LmsServiceError) as error:
        lms.submit(student, task.id, payload.model_copy(update={"episode": changed_episode}))
    assert error.value.status_code == 409
    db_session.rollback()
    db_session.execute(
        update(SubmissionAttempt)
        .where(SubmissionAttempt.id == submitted.id)
        .values(episode=changed)
    )
    db_session.commit()
    assert resolution(db_session, submitted.id).reason_code == "FROZEN_RESPONSE_INVALID"
