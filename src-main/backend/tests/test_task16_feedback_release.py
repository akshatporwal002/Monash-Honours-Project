"""Read-time release and access checks preserve accepted assessed work."""

import asyncio

import pytest
from sqlalchemy import select, update
from support.assessment import assign_assessor
from support.task16 import setup_task16_episode
from test_task14_lifecycle import complete
from test_task15_migrated_review import make_service, request
from test_task16_feedback_workflow import run_pipeline

from app.api.feedback_dependencies import DatabaseFeedbackAccessPolicy
from app.models.assessment import AssessmentAttempt, AssessmentDefinitionVersion
from app.models.lms import Course, CourseState, Enrollment, EnrollmentStatus, SubmissionAttempt
from app.models.user import User
from app.schemas.feedback import FeedbackPipelineStatus
from app.schemas.feedback_api import AuthenticatedActor, FeedbackWorkflowStatus
from app.schemas.lms import SubmissionCreate
from app.services.feedback.application import FeedbackWorkflowApplication
from app.services.feedback.errors import ContextIntegrityError
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository
from app.services.feedback.runtime import build_feedback_pipeline


def setup_human(session):
    lms, student, task, started = setup_task16_episode(session)
    payload = complete(lms, student, task, started)
    submitted = lms.submit(
        student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="task16-release")
    )
    actor = session.get(User, session.get(Course, task.course_id).educator_id)
    from app.services.assessment.access import RoleAssignmentService

    if not RoleAssignmentService(session).list_active_assignments(actor.id):
        assign_assessor(session, actor, task.course_id, actor)
    session.commit()
    attempt = session.scalar(
        select(AssessmentAttempt).where(AssessmentAttempt.response_version_id == submitted.id)
    )
    return make_service(session), actor, attempt, submitted.id


def collected(session, attempt):
    pipeline = build_feedback_pipeline(session, SqlAlchemyFeedbackWorkflowRepository(session))
    submission = asyncio.run(
        pipeline._submission_provider.get_submission(attempt.response_version_id)
    )
    return asyncio.run(
        pipeline._context_collector.collect(submission, "22222222-2222-4222-8222-222222222222")
    )


def test_cached_pending_feedback_withheld_after_human_confirmation(db_session):
    service, actor, attempt, _ = setup_human(db_session)
    context = collected(db_session, attempt)
    result, repository = run_pipeline(db_session, context)
    assert result.status is FeedbackPipelineStatus.VALIDATED
    app = FeedbackWorkflowApplication(repository)
    before = asyncio.run(app.response(app.get(attempt.response_version_id)))
    assert before.status is FeedbackWorkflowStatus.VALIDATED
    service.finalise(
        actor, assessment_attempt_id=attempt.id, request=request(service, actor, attempt.id)
    )
    after = asyncio.run(app.response(app.get(attempt.response_version_id)))
    assert after.status is FeedbackWorkflowStatus.FALLBACK
    assert not getattr(after.feedback, "assessed", None)
    assert (
        db_session.get(SubmissionAttempt, attempt.response_version_id).content_digest
        == context.assessment_context.response_content_digest
    )


def test_corrupt_frozen_context_never_uses_cached_practice_feedback(db_session):
    _, _, attempt, _ = setup_human(db_session)
    context = collected(db_session, attempt)
    result, repository = run_pipeline(db_session, context)
    assert result.status is FeedbackPipelineStatus.VALIDATED
    db_session.execute(
        update(AssessmentDefinitionVersion)
        .where(AssessmentDefinitionVersion.id == attempt.assessment_definition_version_id)
        .values(formal_result_eligible=False)
    )
    db_session.commit()
    app = FeedbackWorkflowApplication(repository)
    response = asyncio.run(app.response(app.get(attempt.response_version_id)))
    assert response.status is FeedbackWorkflowStatus.FALLBACK
    with pytest.raises(ContextIntegrityError):
        collected(db_session, attempt)
    assert db_session.get(SubmissionAttempt, attempt.response_version_id).score is None


@pytest.mark.parametrize(
    "change", ["enrollment", "archived", "foreign_student", "foreign_educator"]
)
def test_feedback_access_rechecks_current_course_and_owner(db_session, change):
    _, owner, attempt, _ = setup_human(db_session)
    response = db_session.get(SubmissionAttempt, attempt.response_version_id)
    original = (response.answer, response.content_digest)
    policy = DatabaseFeedbackAccessPolicy(db_session)
    actor = AuthenticatedActor(actor_reference=str(attempt.student_id), role="student")
    assert asyncio.run(policy.can_access_submission(actor, response.id))
    if change == "enrollment":
        enrollment = db_session.scalar(
            select(Enrollment).where(
                Enrollment.course_id == attempt.course_id,
                Enrollment.student_id == attempt.student_id,
            )
        )
        enrollment.status = EnrollmentStatus.WITHDRAWN
    elif change == "archived":
        db_session.get(Course, attempt.course_id).state = CourseState.ARCHIVED
    elif change == "foreign_student":
        actor = AuthenticatedActor(actor_reference=str(owner.id), role="student")
    else:
        actor = AuthenticatedActor(actor_reference=str(attempt.student_id), role="educator")
    db_session.commit()
    assert not asyncio.run(policy.can_access_submission(actor, response.id))
    assert (response.answer, response.content_digest) == original


def test_cached_feedback_rechecks_active_transfer_at_read_time(db_session, monkeypatch):
    from app.services.assessment import feedback_context

    _, _, attempt, _ = setup_human(db_session)
    context = collected(db_session, attempt)
    result, repository = run_pipeline(db_session, context)
    assert result.status is FeedbackPipelineStatus.VALIDATED
    app = FeedbackWorkflowApplication(repository)
    assert (
        asyncio.run(app.response(app.get(attempt.response_version_id))).status
        is FeedbackWorkflowStatus.VALIDATED
    )
    calls = []

    def active_transfer(*args, **kwargs):
        calls.append(True)
        return False, True

    # The SQL helper has a separate persisted-stage test. This isolates the read gate.
    monkeypatch.setattr(feedback_context, "feedback_release_state", active_transfer)
    response = asyncio.run(app.response(app.get(attempt.response_version_id)))
    assert calls
    assert response.status is FeedbackWorkflowStatus.FALLBACK
    assert not getattr(response.feedback, "assessed", None)
    assert (
        db_session.get(SubmissionAttempt, attempt.response_version_id).content_digest
        == context.assessment_context.response_content_digest
    )


@pytest.mark.parametrize("change", ["revoked", "retired", "reapproved", "indexing_failed"])
def test_cached_source_changes_withhold_feedback_without_rewriting_history(db_session, change):
    from datetime import UTC, datetime

    from sqlalchemy import event

    from app.models import LearningMaterial, MaterialIndexStatus
    from app.models.source_history import SourceRevision
    from app.services.rag.source_history import latest_approval, record_approval

    _, actor, attempt, _ = setup_human(db_session)
    context = collected(db_session, attempt)
    result, repository = run_pipeline(db_session, context)
    assert result.status is FeedbackPipelineStatus.VALIDATED
    app = FeedbackWorkflowApplication(repository)
    assert (
        asyncio.run(app.response(app.get(attempt.response_version_id))).status
        is FeedbackWorkflowStatus.VALIDATED
    )
    claim = result.validated_feedback.feedback_content["assessed"]["source_claims"][0]
    revision = db_session.get(SourceRevision, claim["source_revision_id"])
    material = db_session.get(LearningMaterial, revision.material_id)
    if change in {"revoked", "reapproved"}:
        record_approval(
            db_session,
            course_id=attempt.course_id,
            material_id=material.id,
            revision_id=revision.id,
            actor_id=str(actor.id),
            state="REVOKED",
            reason="Synthetic source withdrawn after feedback release.",
            expected_sequence=latest_approval(db_session, revision.id).sequence,
        )
        if change == "reapproved":
            renewed = record_approval(
                db_session,
                course_id=attempt.course_id,
                material_id=material.id,
                revision_id=revision.id,
                actor_id=str(actor.id),
                state="APPROVED",
                reason="Synthetic source reviewed again under a new approval.",
                expected_sequence=latest_approval(db_session, revision.id).sequence,
            )
            assert renewed.id != claim["approval_id"]
    elif change == "retired":
        material.retired_at = datetime.now(UTC)
    else:
        material.indexing_status = MaterialIndexStatus.FAILED
    db_session.commit()
    statements = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(db_session.bind, "before_cursor_execute", observe)
    try:
        response = asyncio.run(app.response(app.get(attempt.response_version_id)))
    finally:
        event.remove(db_session.bind, "before_cursor_execute", observe)
    assert response.status is FeedbackWorkflowStatus.FALLBACK
    assert not getattr(response.feedback, "assessed", None)
    assert not {"INSERT", "UPDATE", "DELETE", "REPLACE"} & set(statements)
    saved = repository.get_by_submission(attempt.response_version_id)
    assert saved.validated_feedback == result.validated_feedback
    assert saved.feedback_id == result.feedback_id
    assert (
        db_session.get(SubmissionAttempt, attempt.response_version_id).content_digest
        == context.assessment_context.response_content_digest
    )


def test_first_feedback_after_source_reapproval_requires_original_task_review_binding(db_session):
    from app.models.source_history import SourcePassage, SourceRevision
    from app.services.rag.source_history import latest_approval, record_approval

    _, actor, attempt, response_id = setup_human(db_session)
    original = collected(db_session, attempt)
    passage = db_session.get(SourcePassage, original.task.source_references[0])
    revision = db_session.get(SourceRevision, passage.revision_id)
    original_binding = original.task.source_approvals[passage.id]
    original_digest = db_session.get(SubmissionAttempt, response_id).content_digest
    for state in ("REVOKED", "APPROVED"):
        record_approval(
            db_session,
            course_id=attempt.course_id,
            material_id=revision.material_id,
            revision_id=revision.id,
            actor_id=str(actor.id),
            state=state,
            reason="Synthetic source review changed before first feedback.",
            expected_sequence=latest_approval(db_session, revision.id).sequence,
        )
    db_session.commit()
    context = collected(db_session, attempt)
    assert context.task.source_approvals[passage.id] == original_binding
    assert latest_approval(db_session, revision.id).id != original_binding
    assert not context.retrieval_context
    result, _ = run_pipeline(db_session, context)
    assert result.status is FeedbackPipelineStatus.FALLBACK
    assert db_session.get(SubmissionAttempt, response_id).content_digest == original_digest
    assert db_session.get(SourcePassage, passage.id).chunk_text == passage.chunk_text
