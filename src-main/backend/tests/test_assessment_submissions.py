from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_assessment_models import _blueprint

from app.core.security import hash_password
from app.domain.assessment import AssessmentAttemptState, AssessmentPurpose
from app.models.assessment import (
    AssessmentApprovalState,
    AssessmentAttempt,
    AssessmentDecision,
    TaskApproval,
    TaskFormVersion,
)
from app.models.lms import AttemptStatus, SubmissionAttempt, SubmissionDraft
from app.models.persistence import LearningTask
from app.models.user import User, UserRole
from app.services.assessment.submissions import AssessmentSubmissionService


def _approved_bundle(session: Session):
    definition, bloom, _, rule, form, owner = _blueprint(session)
    definition.formal_result_eligible = True
    definition.result_eligibility_declared_at = datetime(2026, 8, 16, tzinfo=UTC)
    session.commit()
    definition.approval_state = AssessmentApprovalState.APPROVED
    definition.approved_at = datetime(2026, 8, 16, tzinfo=UTC)
    definition.approved_by_user_id = owner.id
    session.add(
        TaskApproval(
            course_id=definition.course_id,
            assessment_definition_version_id=definition.id,
            task_form_version_id=form.id,
            actor_user_id=owner.id,
            approval_reason="The form matches the approved definition.",
            approval_state=AssessmentApprovalState.APPROVED,
            approved_at=datetime(2026, 8, 16, tzinfo=UTC),
            approved_by_user_id=owner.id,
        )
    )
    session.commit()
    return definition, bloom, rule, form


def test_assessed_attempt_freezes_versions_before_start(db_session: Session) -> None:
    definition, bloom, rule, form = _approved_bundle(db_session)
    task = db_session.get(LearningTask, form.learning_task_id)
    assert task is not None
    student = User(
        email="submission@example.edu",
        password_hash=hash_password("submission-password"),
        full_name="Student",
        role=UserRole.STUDENT,
    )
    db_session.add(student)
    db_session.flush()
    draft = SubmissionDraft(student_id=student.id, task_id=task.id)
    db_session.add(draft)
    db_session.flush()
    response = SubmissionAttempt(
        draft_id=draft.id,
        student_id=student.id,
        task_id=task.id,
        attempt_number=1,
        status=AttemptStatus.SUBMITTED,
        answer="Evidence",
        score=None,
        feedback="Recorded.",
        task_form_version_id=form.id,
        response_schema_version="assessment.response.v1",
        content_digest="sha256:" + "a" * 64,
        idempotency_key="submission-key",
        declared_conditions={},
    )
    db_session.add(response)
    db_session.flush()

    service = AssessmentSubmissionService(db_session)
    versions = service.frozen_versions_for_task(task)
    assert versions is not None
    assert versions.definition_version_id == definition.id
    assert versions.bloom_target_version_id == bloom.id
    assert versions.pass_rule_version_id == rule.id
    service.create_attempt(task=task, student_id=student.id, response=response, versions=versions)
    db_session.commit()

    attempt = db_session.scalar(select(AssessmentAttempt))
    assert attempt is not None
    assert attempt.response_version_id == response.id
    assert attempt.task_form_version_id == form.id


def test_unassessed_task_cannot_create_formal_result(db_session: Session) -> None:
    _, _, _, _, form, _ = _blueprint(db_session)
    task = db_session.get(LearningTask, form.learning_task_id)
    assert task is not None

    assert AssessmentSubmissionService(db_session).frozen_versions_for_task(task) is None


@pytest.mark.parametrize("purpose", [AssessmentPurpose.DIAGNOSTIC, AssessmentPurpose.FORMATIVE])
def test_formative_and_diagnostic_tasks_cannot_create_formal_result(
    db_session: Session,
    purpose: AssessmentPurpose,
) -> None:
    definition, _, _, rule, form, owner = _blueprint(db_session)
    definition.formal_result_eligible = True
    definition.result_eligibility_declared_at = datetime(2026, 8, 16, tzinfo=UTC)
    definition.purpose = purpose
    db_session.commit()
    definition.approval_state = AssessmentApprovalState.APPROVED
    definition.approved_at = datetime(2026, 8, 16, tzinfo=UTC)
    definition.approved_by_user_id = owner.id
    db_session.add(
        TaskApproval(
            course_id=definition.course_id,
            assessment_definition_version_id=definition.id,
            task_form_version_id=form.id,
            actor_user_id=owner.id,
            approval_reason="The task is approved for non-formal practice.",
            approval_state=AssessmentApprovalState.APPROVED,
            approved_at=datetime(2026, 8, 16, tzinfo=UTC),
            approved_by_user_id=owner.id,
        )
    )
    db_session.commit()
    task = db_session.get(LearningTask, form.learning_task_id)
    assert task is not None
    assert rule.assessment_definition_version_id == definition.id

    assert AssessmentSubmissionService(db_session).frozen_versions_for_task(task) is None


def test_changed_task_form_blocks_finalisation(db_session: Session) -> None:
    definition, _, _, form = _approved_bundle(db_session)
    task = db_session.get(LearningTask, form.learning_task_id)
    assert task is not None
    student = User(
        email="changed-form@example.edu",
        password_hash=hash_password("submission-password"),
        full_name="Student",
        role=UserRole.STUDENT,
    )
    db_session.add(student)
    db_session.flush()
    draft = SubmissionDraft(student_id=student.id, task_id=task.id)
    db_session.add(draft)
    db_session.flush()
    response = SubmissionAttempt(
        draft_id=draft.id,
        student_id=student.id,
        task_id=task.id,
        attempt_number=1,
        status=AttemptStatus.SUBMITTED,
        answer="Evidence",
        score=None,
        feedback="Recorded.",
        task_form_version_id=form.id,
        response_schema_version="assessment.response.v1",
        content_digest="sha256:" + "b" * 64,
        idempotency_key="changed-form-key",
        declared_conditions={},
    )
    db_session.add(response)
    db_session.flush()
    service = AssessmentSubmissionService(db_session)
    versions = service.frozen_versions_for_task(task)
    assert versions is not None
    formal_attempt = service.create_attempt(
        task=task,
        student_id=student.id,
        response=response,
        versions=versions,
    )
    replacement = TaskFormVersion(
        course_id=form.course_id,
        task_form_id=form.task_form_id,
        assessment_definition_version_id=definition.id,
        learning_task_id=task.id,
        version=2,
        owner_user_id=definition.owner_user_id,
        created_by_user_id=definition.created_by_user_id,
        source_version="learning-task.v2",
        source_digest="sha256:replacement-task-form",
        task_family=form.task_family,
        context={"scenario": "replacement interference experiment"},
        constraints={"response_format": "text"},
        created_at=datetime(2026, 8, 17, tzinfo=UTC),
    )
    db_session.add(replacement)
    db_session.flush()
    db_session.add(
        TaskApproval(
            course_id=definition.course_id,
            assessment_definition_version_id=definition.id,
            task_form_version_id=replacement.id,
            actor_user_id=definition.owner_user_id,
            approval_reason="The replacement form is approved before later starts.",
            approval_state=AssessmentApprovalState.APPROVED,
            approved_at=datetime(2026, 8, 17, tzinfo=UTC),
            approved_by_user_id=definition.owner_user_id,
        )
    )
    db_session.commit()

    with pytest.raises(ValueError, match="task form changed"):
        service.assert_current_form_matches(formal_attempt)


def test_system_fault_creates_no_incomplete_result(db_session: Session) -> None:
    _, _, _, form = _approved_bundle(db_session)
    task = db_session.get(LearningTask, form.learning_task_id)
    assert task is not None
    student = User(
        email="faulted-response@example.edu",
        password_hash=hash_password("submission-password"),
        full_name="Student",
        role=UserRole.STUDENT,
    )
    db_session.add(student)
    db_session.flush()
    draft = SubmissionDraft(student_id=student.id, task_id=task.id)
    db_session.add(draft)
    db_session.flush()
    response = SubmissionAttempt(
        draft_id=draft.id,
        student_id=student.id,
        task_id=task.id,
        attempt_number=1,
        status=AttemptStatus.SUBMITTED,
        answer="Evidence",
        score=None,
        feedback="Recorded.",
        task_form_version_id=form.id,
        response_schema_version="assessment.response.v1",
        content_digest="sha256:" + "c" * 64,
        idempotency_key="fault-key",
        declared_conditions={},
    )
    db_session.add(response)
    db_session.flush()
    service = AssessmentSubmissionService(db_session)
    versions = service.frozen_versions_for_task(task)
    assert versions is not None
    formal_attempt = service.create_attempt(
        task=task,
        student_id=student.id,
        response=response,
        versions=versions,
    )
    db_session.flush()

    assert service.mark_fault_for_response(response.id, "Simulation service unavailable") is True
    db_session.commit()

    assert formal_attempt.state is AssessmentAttemptState.FAULTED
    assert formal_attempt.fault_reason == "Simulation service unavailable"
    assert db_session.scalar(select(AssessmentDecision)) is None
