"""Learners see confirmed evidence and can obtain a scoped, durable review notice."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from test_assessor_review_api import _assign_assessor, _decision_context, _request, _review_service

from app.domain.assessment import AssessorReviewAction, ResultState
from app.models.appeal_resolution import AppealResolution
from app.models.assessment import AppealOrCorrection
from app.models.lms import Course, CourseState, Enrollment, PlatformAuditEvent
from app.models.user import User
from app.schemas.learner_results import AppealResolutionWrite, LearnerAppealWrite
from app.services.assessment.learner_results import LearnerResultService
from app.services.lms import LmsServiceError


def context(session):
    attempt, response, decision, owner = _decision_context(session)
    student = session.get(User, attempt.student_id)
    session.get(Course, attempt.course_id).state = CourseState.PUBLISHED
    session.add(Enrollment(course_id=attempt.course_id, student_id=student.id))
    session.commit()
    _assign_assessor(session, owner, attempt.course_id, owner)
    reviews = _review_service(session, owner)
    return (
        LearnerResultService(session, assignments=reviews.assignments),
        reviews,
        student,
        owner,
        response,
        decision,
    )


def test_pending_result_hides_verdict_criteria_and_private_reasons(db_session):
    results, reviews, student, owner, response, decision = context(db_session)
    pending = results.read(student, response.id)
    assert pending.result is None
    assert all(criterion.decision is None for criterion in pending.criteria)
    assert "approved_anchors" not in pending.model_dump_json()
    assert "model.v1" not in pending.model_dump_json()
    reviews.act(owner, decision_id=decision.id, request=_request(AssessorReviewAction.CONFIRM))
    confirmed = results.read(student, response.id)
    assert confirmed.result.value == "PASS"
    assert confirmed.criteria[0].decision.value == "MET"
    assert confirmed.bloom_process
    reviews.act(
        owner,
        decision_id=decision.id,
        request=_request(
            AssessorReviewAction.VOID,
            expected_state=ResultState.CONFIRMED,
            expected_revision=1,
        ),
    )
    void = results.read(student, response.id)
    assert void.result is None
    assert all(criterion.decision is None for criterion in void.criteria)
    assert void.status == "Attempt voided"
    assert all(set(item.model_dump()) == {"action", "at"} for item in void.history)


@pytest.mark.parametrize(
    "action, status",
    [
        (AssessorReviewAction.RETURN, "Returned for further work"),
        (AssessorReviewAction.WITHHOLD, "Result withheld pending review"),
    ],
)
def test_pending_actions_never_release_verdict_or_private_note(db_session, action, status):
    results, reviews, student, owner, response, decision = context(db_session)
    reviews.act(
        owner, decision_id=decision.id, request=_request(action, reason="PRIVATE assessor note")
    )
    result = results.read(student, response.id)
    assert result.status == status
    assert result.result is None
    assert "PRIVATE" not in result.model_dump_json()


def test_request_resolution_replay_stale_review_and_notice(db_session):
    results, reviews, student, owner, response, decision = context(db_session)
    request = LearnerAppealWrite(
        reason="Please explain which evidence is missing.", idempotency_key="request-1"
    )
    appeal = results.request_review(student, response.id, request)
    assert results.request_review(student, response.id, request).id == appeal.id
    assert len(results.queue(owner, decision.assessment_attempt.course_id)) == 1
    with pytest.raises(LmsServiceError, match="different details"):
        results.request_review(
            student, response.id, request.model_copy(update={"reason": "Changed request"})
        )
    db_session.rollback()
    reviews.act(owner, decision_id=decision.id, request=_request(AssessorReviewAction.CONFIRM))
    resolution = AppealResolutionWrite(
        expected_decision_revision=0,
        reason="Private resolution explanation",
        learner_notice="Your explanation meets the approved criterion.",
    )
    with pytest.raises(LmsServiceError, match="decision changed"):
        results.resolve(owner, appeal.id, resolution)
    db_session.rollback()
    resolution = resolution.model_copy(update={"expected_decision_revision": 1})
    resolved = results.resolve(owner, appeal.id, resolution)
    assert resolved.state == "RESOLVED"
    assert results.resolve(owner, appeal.id, resolution).id == appeal.id
    result = results.read(student, response.id)
    assert result.requests[0].learner_notice == resolution.learner_notice
    assert resolution.reason not in result.model_dump_json()
    assert results.queue(owner, decision.assessment_attempt.course_id) == []
    assert len(list(db_session.scalars(select(AppealOrCorrection)))) == 1
    assert len(list(db_session.scalars(select(AppealResolution)))) == 1
    audit = list(
        db_session.scalars(
            select(PlatformAuditEvent).where(PlatformAuditEvent.resource_id == appeal.id)
        )
    )
    assert len(audit) == 2
    assert all("Please explain" not in str(row.details) for row in audit)
    with pytest.raises(IntegrityError, match="immutable"):
        db_session.execute(text("DELETE FROM appeal_resolutions"))
    db_session.rollback()


def test_ownership_and_revoked_course_access(db_session):
    results, _, student, owner, response, _ = context(db_session)
    with pytest.raises(LmsServiceError) as error:
        results.read(owner, response.id)
    assert error.value.status_code == 404
    enrolment = db_session.scalar(select(Enrollment).where(Enrollment.student_id == student.id))
    db_session.delete(enrolment)
    db_session.commit()
    with pytest.raises(LmsServiceError):
        results.read(student, response.id)


def test_resolution_notice_is_withheld_until_confirmation_and_hidden_after_void(db_session):
    results, reviews, student, owner, response, decision = context(db_session)
    appeal = results.request_review(
        student,
        response.id,
        LearnerAppealWrite(
            reason="Please review my result",
            idempotency_key="pending-notice",
        ),
    )
    results.resolve(
        owner,
        appeal.id,
        AppealResolutionWrite(
            expected_decision_revision=0,
            reason="Private review rationale",
            learner_notice="Your result is PASS.",
        ),
    )
    assert "Your result is PASS" not in results.read(student, response.id).model_dump_json()
    stored = db_session.scalar(select(AppealResolution))
    assert stored.learner_notice == "Your result is PASS."
    reviews.act(owner, decision_id=decision.id, request=_request(AssessorReviewAction.CONFIRM))
    assert results.read(student, response.id).requests[0].learner_notice == stored.learner_notice
    reviews.act(
        owner,
        decision_id=decision.id,
        request=_request(
            AssessorReviewAction.VOID,
            expected_state=ResultState.CONFIRMED,
            expected_revision=1,
        ),
    )
    assert "Your result is PASS" not in results.read(student, response.id).model_dump_json()


def test_override_reason_preserves_criterion_detail_without_claiming_all_met(db_session):
    from app.domain.assessment import AssessmentResult

    results, reviews, student, owner, response, decision = context(db_session)
    reviews.act(
        owner,
        decision_id=decision.id,
        request=_request(
            AssessorReviewAction.OVERRIDE,
            new_result=AssessmentResult.INCOMPLETE,
        ),
    )
    result = results.read(student, response.id)
    assert "override to INCOMPLETE" in result.reason
    assert result.criteria[0].description in result.reason
    assert "Evidence shown" in result.reason


def test_result_routes_reject_foreign_learner_and_missing_csrf(db_session, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api.dependencies.authentication import get_current_user
    from app.core.config import settings
    from app.db.session import get_db
    from app.main import create_app

    _, _, student, _, response, _ = context(db_session)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: student
    client = TestClient(app)
    path = f"/api/v1/students/me/responses/{response.id}"
    assert client.get(f"{path}/result").headers["Cache-Control"] == "no-store"
    monkeypatch.setattr(settings, "csrf_enabled", True)
    client.cookies.set(settings.csrf_cookie_name, "test-csrf-token")
    denied = client.post(
        f"{path}/review-requests", json={"reason": "Review", "idempotency_key": "csrf"}
    )
    assert denied.status_code == 403
    assert db_session.scalar(select(AppealOrCorrection)) is None
    app.dependency_overrides.pop(get_current_user)
    assert client.get(f"{path}/result").status_code == 401
