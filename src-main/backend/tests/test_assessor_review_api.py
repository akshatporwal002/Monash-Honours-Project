"""Focused tests for course-scoped assessor review actions."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_assessment_attempt_models import _attempt_context, _provisional_decision

from app.core.security import hash_password
from app.domain.assessment import (
    AssessmentAttemptState,
    AssessmentResult,
    AssessorReviewAction,
    CriterionDecision,
    ResultState,
)
from app.main import create_app
from app.models.assessment import (
    AssessmentAttempt,
    AssessmentDecision,
    AssessorReview,
    CriterionEvaluation,
)
from app.models.lms import Course, PlatformAuditEvent
from app.models.user import RoleAssignment, ScopedRole, User, UserRole
from app.services.assessment.access import RoleAssignmentService, ScopedRoleAccessDeniedError
from app.services.assessment.review import (
    AssessmentReviewActionRequest,
    AssessmentReviewConflictError,
    AssessmentReviewFilters,
    AssessmentReviewService,
    AssessmentReviewValidationError,
)

NOW = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)


def _review_service(session: Session, assessor: User) -> AssessmentReviewService:
    return AssessmentReviewService(
        session,
        assignments=RoleAssignmentService(session, now=lambda: NOW),
        correlation_id="00000000-0000-4000-8000-000000000013",
        now=lambda: NOW,
    )


def _assign_assessor(session: Session, assessor: User, course_id: str, assigned_by: User) -> None:
    session.add(
        RoleAssignment(
            subject_user_id=assessor.id,
            course_id=course_id,
            role=ScopedRole.ASSESSOR,
            version=1,
            assigned_by_user_id=assigned_by.id,
            reason="The assessor is assigned to review formal assessment decisions.",
            assigned_at=NOW,
            valid_from=NOW,
        )
    )
    session.commit()


def _request(
    action: AssessorReviewAction,
    *,
    expected_state: ResultState = ResultState.PROVISIONAL,
    expected_revision: int = 0,
    new_result: AssessmentResult | None = None,
    reason: str = "The assessor recorded this review action from the frozen evidence.",
) -> AssessmentReviewActionRequest:
    return AssessmentReviewActionRequest(
        action=action,
        reason=reason,
        expected_result_state=expected_state,
        expected_review_revision=expected_revision,
        new_result=new_result,
    )


def _decision_context(session: Session):
    attempt, response, criterion, _, owner = _attempt_context(session)
    decision = _provisional_decision(session, attempt)
    session.add(
        CriterionEvaluation(
            assessment_attempt_id=attempt.id,
            criterion_version_id=criterion.id,
            decision=CriterionDecision.MET,
            evidence_references={"evidence": ["frozen-evidence-1"]},
            evaluator_reference="rules.v1",
            model_version="model.v1",
            prompt_version="prompt.v1",
            retrieval_version="retrieval.v1",
            reason="The exact response contains the required explanation.",
        )
    )
    session.add(
        PlatformAuditEvent(
            actor_id=None,
            action="assessment_evaluation.provisional",
            resource_type="assessment_attempt",
            resource_id=attempt.id,
            correlation_id="00000000-0000-4000-8000-000000000012",
            details={"quality_review_status": "REJECTED"},
        )
    )
    session.commit()
    return attempt, response, decision, owner


def test_formal_result_requires_authorised_assessor_confirmation(db_session: Session) -> None:
    attempt, _, decision, owner = _decision_context(db_session)
    service = _review_service(db_session, owner)

    with pytest.raises(ScopedRoleAccessDeniedError):
        service.act(owner, decision_id=decision.id, request=_request(AssessorReviewAction.CONFIRM))

    _assign_assessor(db_session, owner, attempt.course_id, owner)
    result = service.act(
        owner, decision_id=decision.id, request=_request(AssessorReviewAction.CONFIRM)
    )

    assert result.result is AssessmentResult.PASS
    assert result.result_state is ResultState.CONFIRMED
    assert result.review_revision == 1
    assert db_session.get(AssessmentDecision, decision.id).assessor_user_id == owner.id


def test_override_keeps_old_new_reason_assessor_and_time(db_session: Session) -> None:
    attempt, _, decision, owner = _decision_context(db_session)
    _assign_assessor(db_session, owner, attempt.course_id, owner)
    service = _review_service(db_session, owner)
    service.act(owner, decision_id=decision.id, request=_request(AssessorReviewAction.CONFIRM))

    result = service.act(
        owner,
        decision_id=decision.id,
        request=_request(
            AssessorReviewAction.OVERRIDE,
            expected_state=ResultState.CONFIRMED,
            expected_revision=1,
            new_result=AssessmentResult.INCOMPLETE,
            reason="A required criterion remains unresolved after evidence review.",
        ),
    )

    history = db_session.scalars(
        select(AssessorReview)
        .where(AssessorReview.assessment_decision_id == decision.id)
        .order_by(AssessorReview.review_revision)
    ).all()
    assert result.result_state is ResultState.OVERRIDDEN
    assert [(review.prior_result, review.new_result) for review in history] == [
        (None, AssessmentResult.PASS),
        (AssessmentResult.PASS, AssessmentResult.INCOMPLETE),
    ]
    assert history[-1].reason == "A required criterion remains unresolved after evidence review."
    assert history[-1].assessor_user_id == owner.id
    assert history[-1].reviewed_at.replace(tzinfo=UTC) == NOW


def test_override_can_change_a_provisional_result(db_session: Session) -> None:
    attempt, _, decision, owner = _decision_context(db_session)
    _assign_assessor(db_session, owner, attempt.course_id, owner)

    result = _review_service(db_session, owner).act(
        owner,
        decision_id=decision.id,
        request=_request(
            AssessorReviewAction.OVERRIDE,
            new_result=AssessmentResult.INCOMPLETE,
            reason="The frozen response does not meet the required evidence standard.",
        ),
    )

    assert result.result is AssessmentResult.INCOMPLETE
    assert result.result_state is ResultState.OVERRIDDEN
    assert result.review_revision == 1


def test_withhold_void_and_return_require_reason(db_session: Session) -> None:
    attempt, _, decision, owner = _decision_context(db_session)
    _assign_assessor(db_session, owner, attempt.course_id, owner)
    service = _review_service(db_session, owner)

    with pytest.raises(AssessmentReviewValidationError, match="reason"):
        service.act(
            owner,
            decision_id=decision.id,
            request=_request(AssessorReviewAction.WITHHOLD, reason=" "),
        )
    withhold = service.act(
        owner, decision_id=decision.id, request=_request(AssessorReviewAction.WITHHOLD)
    )
    returned = service.act(
        owner,
        decision_id=decision.id,
        request=_request(
            AssessorReviewAction.RETURN,
            expected_revision=1,
            reason="Return the attempt with the published next assessment action.",
        ),
    )
    voided = service.act(
        owner,
        decision_id=decision.id,
        request=_request(
            AssessorReviewAction.VOID,
            expected_revision=2,
            reason="The published task form has an assessment validity fault.",
        ),
    )

    assert withhold.result_state is ResultState.PROVISIONAL
    assert returned.result_state is ResultState.PROVISIONAL
    assert voided.result is None and voided.result_state is ResultState.VOID
    assert db_session.get(AssessmentAttempt, attempt.id).state is AssessmentAttemptState.VOID


def test_duplicate_review_action_is_idempotent(db_session: Session) -> None:
    attempt, _, decision, owner = _decision_context(db_session)
    _assign_assessor(db_session, owner, attempt.course_id, owner)
    service = _review_service(db_session, owner)
    request = _request(AssessorReviewAction.CONFIRM)

    first = service.act(owner, decision_id=decision.id, request=request)
    replay = service.act(owner, decision_id=decision.id, request=request)

    assert replay.replayed is True
    assert replay.review_id == first.review_id
    assert len(db_session.scalars(select(AssessorReview)).all()) == 1


def test_stale_and_cross_course_review_actions_are_denied(db_session: Session) -> None:
    attempt, _, decision, owner = _decision_context(db_session)
    _assign_assessor(db_session, owner, attempt.course_id, owner)
    service = _review_service(db_session, owner)
    service.act(owner, decision_id=decision.id, request=_request(AssessorReviewAction.WITHHOLD))

    with pytest.raises(AssessmentReviewConflictError, match="changed"):
        service.act(owner, decision_id=decision.id, request=_request(AssessorReviewAction.CONFIRM))

    outsider = User(
        email="out-of-course-assessor@example.edu",
        password_hash=hash_password("out-of-course-assessor-password"),
        full_name="Out of Course Assessor",
        role=UserRole.EDUCATOR,
    )
    db_session.add(outsider)
    db_session.commit()
    with pytest.raises(ScopedRoleAccessDeniedError):
        _review_service(db_session, outsider).act(
            outsider,
            decision_id=decision.id,
            request=_request(AssessorReviewAction.CONFIRM, expected_revision=1),
        )


def test_review_queue_filters_without_leaking_other_courses(db_session: Session) -> None:
    attempt, response, decision, owner = _decision_context(db_session)
    _assign_assessor(db_session, owner, attempt.course_id, owner)
    service = _review_service(db_session, owner)

    records = service.list_queue(
        owner,
        filters=AssessmentReviewFilters(
            course_id=attempt.course_id,
            result=AssessmentResult.PASS,
            result_state=ResultState.PROVISIONAL,
            review_flag="QUALITY_REJECTED",
        ),
    )
    assert len(records) == 1
    assert records[0].decision_id == decision.id
    assert records[0].response_text == response.answer
    assert records[0].criteria[0].evidence_references == {"evidence": ["frozen-evidence-1"]}
    assert records[0].quality_review_status == "REJECTED"

    other_course = Course(
        educator_id=owner.id,
        code="OTHER-REVIEW",
        title="Other review course",
        description="A course outside this assessor assignment.",
    )
    db_session.add(other_course)
    db_session.commit()
    with pytest.raises(ScopedRoleAccessDeniedError):
        service.list_queue(owner, filters=AssessmentReviewFilters(course_id=other_course.id))


def test_review_api_exposes_actions_without_numeric_grade_fields() -> None:
    schema = create_app().openapi()
    operation = schema["paths"]["/api/v1/assessment/decisions/{decision_id}/review"]["post"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "AssessmentReviewActionRead"
    )
    assert "score" not in str(operation).casefold()
