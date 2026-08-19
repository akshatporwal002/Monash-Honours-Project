from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from support.assessment import build_assessment_blueprint as _blueprint

from app.core.security import hash_password
from app.domain.assessment import (
    AppealOrCorrectionState,
    AssessmentAttemptState,
    AssessmentResult,
    AssessorReviewAction,
    CriterionDecision,
    ResultState,
)
from app.models.assessment import (
    AppealOrCorrection,
    AssessmentAttempt,
    AssessmentDecision,
    AssessorReview,
    Criterion,
    CriterionEvaluation,
    CriterionEvaluatorType,
    CriterionVersion,
    ImmutableAssessmentVersionError,
)
from app.models.audit import AuditAction, AuditAppendOnlyError, AuditEvent, AuditOutcome
from app.models.lms import AttemptStatus, SubmissionAttempt, SubmissionDraft
from app.models.user import User, UserRole

NOW = datetime(2026, 8, 15, 5, 0, tzinfo=UTC)
DIGEST = "sha256:" + "a" * 64


def _attempt_context(
    session: Session,
) -> tuple[AssessmentAttempt, SubmissionAttempt, object, object, User]:
    definition_version, bloom_version, criterion_version, rule_version, form_version, owner = (
        _blueprint(session)
    )
    student = User(
        email="attempt-student@example.edu",
        password_hash=hash_password("attempt-model-test-password"),
        full_name="Attempt Student",
        role=UserRole.STUDENT,
    )
    session.add(student)
    session.flush()
    draft = SubmissionDraft(student_id=student.id, task_id=form_version.learning_task_id)
    session.add(draft)
    session.flush()
    response = SubmissionAttempt(
        draft_id=draft.id,
        student_id=student.id,
        task_id=form_version.learning_task_id,
        attempt_number=1,
        status=AttemptStatus.SUBMITTED,
        answer="The response links the observation to the claim.",
        score=None,
        feedback="Response recorded.",
        task_form_version_id=form_version.id,
        response_schema_version="assessment.response.v1",
        content_digest=DIGEST,
        idempotency_key="response-key-1",
        declared_conditions={"tools": ["notes"]},
    )
    session.add(response)
    session.flush()
    attempt = AssessmentAttempt(
        course_id=definition_version.course_id,
        student_id=student.id,
        task_id=form_version.learning_task_id,
        response_version_id=response.id,
        assessment_definition_version_id=definition_version.id,
        task_form_version_id=form_version.id,
        bloom_target_version_id=bloom_version.id,
        pass_rule_version_id=rule_version.id,
        state=AssessmentAttemptState.PENDING,
    )
    session.add(attempt)
    session.commit()
    return attempt, response, criterion_version, rule_version, owner


def _provisional_decision(session: Session, attempt: AssessmentAttempt) -> AssessmentDecision:
    decision = AssessmentDecision(
        assessment_attempt_id=attempt.id,
        bloom_target_version_id=attempt.bloom_target_version_id,
        pass_rule_version_id=attempt.pass_rule_version_id,
        evaluation_idempotency_key="evaluation-key-1",
        result=AssessmentResult.PASS,
        result_state=ResultState.PROVISIONAL,
        evidence_references={"criterion_evaluations": []},
        system_reason="TARGET_EVIDENCE_MET",
    )
    session.add(decision)
    session.commit()
    return decision


def _criterion_outside_frozen_rule(
    session: Session,
    attempt: AssessmentAttempt,
    frozen_criterion: CriterionVersion,
    owner: User,
) -> CriterionVersion:
    criterion = Criterion(
        assessment_definition_id=frozen_criterion.criterion.assessment_definition_id,
        stable_key="later-criterion",
    )
    session.add(criterion)
    session.flush()
    version = CriterionVersion(
        course_id=attempt.course_id,
        criterion_id=criterion.id,
        assessment_definition_version_id=attempt.assessment_definition_version_id,
        version=1,
        owner_user_id=owner.id,
        created_by_user_id=owner.id,
        learner_description="A later criterion that the frozen rule does not include.",
        evidence_description="Evidence for a later criterion.",
        mandatory=True,
        evidence_source_types=["learner_response"],
        met_rule="The response satisfies the later criterion.",
        not_met_rule="The response does not satisfy the later criterion.",
        not_evaluable_rule="The response cannot be evaluated for the later criterion.",
        approved_anchors={"met": ["later evidence"]},
        critical_error_rules={"errors": []},
        evaluator_type=CriterionEvaluatorType.RULES,
    )
    session.add(version)
    session.commit()
    return version


def test_submission_attempt_is_the_immutable_response_version(db_session: Session) -> None:
    _, response, _, _, _ = _attempt_context(db_session)

    assert response.id
    assert response.score is None
    assert response.response_schema_version == "assessment.response.v1"
    response.answer = "Changed response"
    with pytest.raises(RuntimeError, match="immutable"):
        db_session.commit()


def test_response_version_idempotency_allows_one_record_per_request_key(
    db_session: Session,
) -> None:
    _, response, _, _, _ = _attempt_context(db_session)
    duplicate = SubmissionAttempt(
        draft_id=response.draft_id,
        student_id=response.student_id,
        task_id=response.task_id,
        attempt_number=2,
        status=AttemptStatus.SUBMITTED,
        answer="Different content must not create a second response version.",
        score=None,
        feedback="Response recorded.",
        task_form_version_id=response.task_form_version_id,
        response_schema_version="assessment.response.v1",
        content_digest="sha256:" + "b" * 64,
        idempotency_key=response.idempotency_key,
        declared_conditions={},
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError, match="idempotency"):
        db_session.commit()


def test_assessment_attempt_and_appeal_history_cannot_be_deleted(db_session: Session) -> None:
    attempt, _, _, _, owner = _attempt_context(db_session)
    db_session.delete(attempt)
    with pytest.raises(ImmutableAssessmentVersionError, match="append-only"):
        db_session.commit()
    db_session.rollback()

    decision = _provisional_decision(db_session, attempt)
    appeal = AppealOrCorrection(
        assessment_attempt_id=attempt.id,
        assessment_decision_id=decision.id,
        requested_by_user_id=owner.id,
        request_kind="appeal",
        request_reason="The learner requested a review.",
        state=AppealOrCorrectionState.PENDING,
    )
    db_session.add(appeal)
    db_session.commit()
    db_session.delete(appeal)
    with pytest.raises(ImmutableAssessmentVersionError, match="append-only"):
        db_session.commit()


def test_assessment_decision_idempotency_allows_one_record_per_evaluation(
    db_session: Session,
) -> None:
    attempt, _, _, _, _ = _attempt_context(db_session)
    _provisional_decision(db_session, attempt)
    duplicate = AssessmentDecision(
        assessment_attempt_id=attempt.id,
        bloom_target_version_id=attempt.bloom_target_version_id,
        pass_rule_version_id=attempt.pass_rule_version_id,
        evaluation_idempotency_key="evaluation-key-1",
        result=AssessmentResult.PASS,
        result_state=ResultState.PROVISIONAL,
        evidence_references={"criterion_evaluations": []},
        system_reason="TARGET_EVIDENCE_MET",
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError, match="assessment_decisions"):
        db_session.commit()


def test_assessment_decision_reason_code_is_database_constrained(db_session: Session) -> None:
    attempt, _, _, _, _ = _attempt_context(db_session)

    with pytest.raises(IntegrityError, match="assessment_reason_code"):
        db_session.execute(
            text(
                "INSERT INTO assessment_decisions ("
                "id, assessment_attempt_id, bloom_target_version_id, pass_rule_version_id, "
                "evaluation_idempotency_key, result, result_state, evidence_references, "
                "system_reason, assessor_user_id, reviewed_at, prior_result, override_reason, "
                "created_at) VALUES ("
                ":id, :attempt_id, :bloom_id, :rule_id, :key, 'PASS', 'PROVISIONAL', '{}', "
                "'UNKNOWN_REASON', NULL, NULL, NULL, NULL, :created_at)"
            ),
            {
                "id": "invalid-reason-decision",
                "attempt_id": attempt.id,
                "bloom_id": attempt.bloom_target_version_id,
                "rule_id": attempt.pass_rule_version_id,
                "key": "invalid-reason-key",
                "created_at": NOW,
            },
        )
        db_session.commit()
    db_session.rollback()


def test_decision_references_exact_response_and_rule_versions(db_session: Session) -> None:
    attempt, _, criterion_version, _, owner = _attempt_context(db_session)
    invalid_decision = AssessmentDecision(
        assessment_attempt_id=attempt.id,
        bloom_target_version_id="different-bloom-version",
        pass_rule_version_id=attempt.pass_rule_version_id,
        evaluation_idempotency_key="invalid-evaluation-key",
        result=AssessmentResult.PASS,
        result_state=ResultState.PROVISIONAL,
        evidence_references={"criterion_evaluations": []},
        system_reason="TARGET_EVIDENCE_MET",
    )
    db_session.add(invalid_decision)
    with pytest.raises(ValueError, match="assessment attempt version bundle"):
        db_session.commit()
    db_session.rollback()

    invalid_evaluation = CriterionEvaluation(
        assessment_attempt_id=attempt.id,
        criterion_version_id=_criterion_outside_frozen_rule(
            db_session, attempt, criterion_version, owner
        ).id,
        decision=CriterionDecision.MET,
        evidence_references={"response_version_id": attempt.response_version_id},
        evaluator_reference="rules.v1",
        reason="The criterion version must be part of the frozen pass rule.",
    )
    db_session.add(invalid_evaluation)
    with pytest.raises(ValueError, match="assessment attempt frozen pass rule"):
        db_session.commit()
    db_session.rollback()

    evaluation = CriterionEvaluation(
        assessment_attempt_id=attempt.id,
        criterion_version_id=criterion_version.id,
        decision=CriterionDecision.MET,
        evidence_references={"response_version_id": attempt.response_version_id},
        evaluator_reference="rules.v1",
        reason="The response states the required relationship.",
    )
    db_session.add(evaluation)
    decision = _provisional_decision(db_session, attempt)

    assert decision.assessment_attempt.response_version_id == attempt.response_version_id
    assert decision.pass_rule_version_id == attempt.pass_rule_version_id
    assert evaluation.criterion_version_id == criterion_version.id


def test_assessment_attempt_rejects_a_cross_course_version_bundle(db_session: Session) -> None:
    attempt, _, _, _, _ = _attempt_context(db_session)

    attempt.course_id = "another-course"
    with pytest.raises(ValueError, match="exact course-scoped version bundle"):
        db_session.commit()


def test_invalid_result_lifecycle_writes_fail(db_session: Session) -> None:
    attempt, response, _, _, _ = _attempt_context(db_session)
    decision = _provisional_decision(db_session, attempt)
    decision.result_state = ResultState.NOT_ASSESSED
    with pytest.raises(ImmutableAssessmentVersionError, match="lifecycle"):
        db_session.commit()
    db_session.rollback()

    decision.result_state = ResultState.CONFIRMED
    with pytest.raises(ValueError, match="matching assessor review"):
        db_session.commit()
    db_session.rollback()

    decision.result_state = ResultState.CONFIRMED
    decision.assessor_user_id = 1
    decision.reviewed_at = NOW
    with pytest.raises(ValueError, match="matching assessor review"):
        db_session.commit()
    db_session.rollback()

    attempt.state = AssessmentAttemptState.FAULTED
    attempt.fault_reason = "The required simulation evidence was unavailable."
    with pytest.raises(ImmutableAssessmentVersionError, match="decided assessment attempts"):
        db_session.commit()
    db_session.rollback()
    db_session.refresh(attempt)

    faulted_response = SubmissionAttempt(
        draft_id=response.draft_id,
        student_id=response.student_id,
        task_id=response.task_id,
        attempt_number=2,
        status=AttemptStatus.SUBMITTED,
        answer="A later response that encountered a system fault.",
        score=None,
        feedback="Response recorded.",
        task_form_version_id=response.task_form_version_id,
        response_schema_version="assessment.response.v1",
        content_digest="sha256:" + "c" * 64,
        idempotency_key="response-key-2",
        declared_conditions={},
    )
    db_session.add(faulted_response)
    db_session.flush()
    faulted_attempt = AssessmentAttempt(
        course_id=attempt.course_id,
        student_id=attempt.student_id,
        task_id=attempt.task_id,
        response_version_id=faulted_response.id,
        assessment_definition_version_id=attempt.assessment_definition_version_id,
        task_form_version_id=attempt.task_form_version_id,
        bloom_target_version_id=attempt.bloom_target_version_id,
        pass_rule_version_id=attempt.pass_rule_version_id,
        state=AssessmentAttemptState.FAULTED,
        fault_reason="The required simulation evidence was unavailable.",
    )
    db_session.add(faulted_attempt)
    db_session.commit()
    attempt.response_version_id = faulted_response.id
    with pytest.raises(ImmutableAssessmentVersionError, match="version anchors are immutable"):
        db_session.commit()
    db_session.rollback()
    with pytest.raises(ImmutableAssessmentVersionError, match="faulted assessment attempts"):
        _provisional_decision(db_session, faulted_attempt)
    db_session.rollback()
    faulted_attempt.state = AssessmentAttemptState.PENDING
    faulted_attempt.fault_reason = None
    db_session.commit()
    assert faulted_attempt.state is AssessmentAttemptState.PENDING


def test_confirm_override_void_and_return_require_actor_reason_and_time(
    db_session: Session,
) -> None:
    attempt, _, _, _, owner = _attempt_context(db_session)
    decision = _provisional_decision(db_session, attempt)
    confirmation = AssessorReview(
        assessment_decision_id=decision.id,
        assessor_user_id=owner.id,
        action=AssessorReviewAction.CONFIRM,
        prior_result=None,
        new_result=AssessmentResult.PASS,
        reason="The evidence supports the provisional result.",
        reviewed_at=NOW,
    )
    db_session.add(confirmation)
    decision.result_state = ResultState.CONFIRMED
    decision.assessor_user_id = owner.id
    decision.reviewed_at = NOW
    decision.evidence_references = {"rewritten": True}
    with pytest.raises(ImmutableAssessmentVersionError, match="evidence and anchors are immutable"):
        db_session.commit()
    db_session.rollback()

    confirmation = AssessorReview(
        assessment_decision_id=decision.id,
        assessor_user_id=owner.id,
        action=AssessorReviewAction.CONFIRM,
        prior_result=None,
        new_result=AssessmentResult.PASS,
        reason="The evidence supports the provisional result.",
        reviewed_at=NOW,
    )
    db_session.add(confirmation)
    decision.result_state = ResultState.CONFIRMED
    decision.assessor_user_id = owner.id
    decision.reviewed_at = NOW
    db_session.commit()

    invalid_review = AssessorReview(
        assessment_decision_id=decision.id,
        assessor_user_id=owner.id,
        action=AssessorReviewAction.OVERRIDE,
        prior_result=AssessmentResult.INCOMPLETE,
        new_result=AssessmentResult.PASS,
        reason="The review record conflicts with the decision reason.",
        reviewed_at=NOW,
    )
    db_session.add(invalid_review)
    decision.result_state = ResultState.OVERRIDDEN
    decision.prior_result = AssessmentResult.INCOMPLETE
    decision.result = AssessmentResult.PASS
    decision.override_reason = "A different conflicting reason."
    with pytest.raises(ValueError, match="matching assessor review"):
        db_session.commit()
    db_session.rollback()

    review = AssessorReview(
        assessment_decision_id=decision.id,
        assessor_user_id=owner.id,
        action=AssessorReviewAction.OVERRIDE,
        prior_result=AssessmentResult.PASS,
        new_result=AssessmentResult.INCOMPLETE,
        reason="A required criterion was not evaluable.",
        reviewed_at=NOW,
    )
    db_session.add(review)
    decision.result_state = ResultState.OVERRIDDEN
    decision.prior_result = AssessmentResult.PASS
    decision.result = AssessmentResult.INCOMPLETE
    decision.override_reason = review.reason
    decision.assessor_user_id = owner.id
    decision.reviewed_at = NOW
    db_session.commit()

    void_review = AssessorReview(
        assessment_decision_id=decision.id,
        assessor_user_id=owner.id,
        action=AssessorReviewAction.VOID,
        prior_result=AssessmentResult.INCOMPLETE,
        new_result=None,
        reason="The task form had a validity fault.",
        reviewed_at=NOW,
    )
    db_session.add(void_review)
    decision.result_state = ResultState.VOID
    decision.result = None
    db_session.commit()

    attempt.state = AssessmentAttemptState.VOID
    attempt.fault_reason = "The task form had a validity fault."
    db_session.commit()

    invalid_review = AssessorReview(
        assessment_decision_id=decision.id,
        assessor_user_id=owner.id,
        action=AssessorReviewAction.OVERRIDE,
        prior_result=AssessmentResult.PASS,
        new_result=AssessmentResult.PASS,
        reason="An override must change the result.",
        reviewed_at=NOW,
    )
    db_session.add(invalid_review)
    with pytest.raises(IntegrityError, match="assessor_review_action_shape"):
        db_session.commit()
    db_session.rollback()

    db_session.delete(decision)
    with pytest.raises(ImmutableAssessmentVersionError, match="append-only"):
        db_session.commit()


def test_assessment_audit_events_are_append_only_and_content_free(db_session: Session) -> None:
    event = AuditEvent(
        actor_reference="user:assessor-1",
        action=AuditAction.ASSESSMENT_DECISION_CREATED,
        outcome=AuditOutcome.SUCCESS,
        correlation_id="assessment-correlation",
        resource_type="assessment_decision",
        resource_id="decision-1",
        deduplication_key="assessment-decision-1",
    )
    db_session.add(event)
    db_session.commit()

    assert "answer" not in event.resource_type
    event.resource_id = "changed"
    with pytest.raises(AuditAppendOnlyError, match="append-only"):
        db_session.commit()
