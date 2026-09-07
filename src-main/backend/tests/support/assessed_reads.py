"""Independent browser accounts and assessment records for read-path checks."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.assessment import AssessmentApprovalState, CriterionEvaluatorType, TaskApproval
from app.models.lms import Course, CourseState, Enrollment
from app.models.persistence import StudentProfile
from app.models.user import User, UserRole
from support.assessment import build_assessment_blueprint
from support.task_review import bind_reviewed_fixture_form


def seed_assessed_reads(session: Session) -> dict[str, str]:
    suffix = uuid4().hex[:12]
    definition, _, criterion, _, form, owner = build_assessment_blueprint(session, suffix=suffix)
    password = "browser-read-test-password"
    student = User(
        email=f"read-{suffix}@example.edu",
        full_name="Read Test Student",
        password_hash=hash_password(password),
        role=UserRole.STUDENT,
    )
    session.add(student)
    session.flush()
    session.add(StudentProfile(user_id=student.id, display_name=student.full_name))
    session.add(Enrollment(course_id=definition.course_id, student_id=student.id))
    course = session.get(Course, definition.course_id)
    assert course is not None
    course.state = CourseState.PUBLISHED
    criterion.evaluator_type = CriterionEvaluatorType.HUMAN
    definition.formal_result_eligible = True
    definition.result_eligibility_declared_at = datetime(2026, 8, 16, tzinfo=UTC)
    session.commit()
    review_event = bind_reviewed_fixture_form(session, form)
    form.approval_state = AssessmentApprovalState.APPROVED
    form.approved_at = datetime(2026, 8, 16, tzinfo=UTC)
    form.approved_by_user_id = owner.id
    definition.approval_state = AssessmentApprovalState.APPROVED
    definition.approved_at = datetime(2026, 8, 16, tzinfo=UTC)
    definition.approved_by_user_id = owner.id
    session.add(
        TaskApproval(
            course_id=definition.course_id,
            assessment_definition_version_id=definition.id,
            task_form_version_id=form.id,
            task_review_event_id=review_event.id,
            actor_user_id=owner.id,
            approval_reason="Approved read test form.",
            approval_state=AssessmentApprovalState.APPROVED,
            approved_at=definition.approved_at,
            approved_by_user_id=owner.id,
        )
    )
    session.commit()
    return {
        "student_email": student.email,
        "password": password,
        "task_id": form.learning_task_id,
        "educator_email": owner.email,
        "educator_password": "assessment-model-test-password",
    }
