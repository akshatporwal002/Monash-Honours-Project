"""Public LMS reads must preserve unscored formal submissions."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from support.assessment import build_assessment_blueprint
from support.task_review import (
    approve_fixture_task,
    bind_reviewed_fixture_form,
    bootstrap_reviewed_demo,
)

from app.db.session import get_db
from app.main import create_app
from app.models.assessment import AssessmentApprovalState, TaskApproval
from app.models.lms import (
    AttemptStatus,
    Course,
    CourseState,
    Enrollment,
    SubmissionAttempt,
    SubmissionDraft,
)
from app.models.persistence import LearningTask
from app.models.user import UserRole
from app.schemas.lms import SubmissionCreate
from app.services.lms import DEMO_PASSWORD, LmsService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def prepare_reads(session: Session, with_practice: bool):
    users, _ = bootstrap_reviewed_demo(session)
    student = next(user for user in users if user.role is UserRole.STUDENT)
    definition, _, _, _, form, owner = build_assessment_blueprint(session)
    course = session.get(Course, definition.course_id)
    task = session.get(LearningTask, form.learning_task_id)
    assert course is not None and task is not None
    course.state = CourseState.PUBLISHED
    session.add(Enrollment(course_id=course.id, student_id=student.id))
    if with_practice:
        draft = SubmissionDraft(student_id=student.id, task_id=task.id)
        session.add(draft)
        session.flush()
        session.add(
            SubmissionAttempt(
                draft_id=draft.id,
                student_id=student.id,
                task_id=task.id,
                attempt_number=1,
                status=AttemptStatus.SUBMITTED,
                answer="Earlier practice",
                feedback="Recorded.",
            )
        )
        practice = LearningTask(
            slug="read-practice",
            title="Practice evidence",
            module=task.module,
            description="Practice",
            instructions="Practice",
            expected_answer="Practice",
            task_type=task.task_type,
            difficulty="beginner",
            points=0,
            position=2,
            course_id=course.id,
            module_id=task.module_id,
            learning_outcome_id=task.learning_outcome_id,
        )
        session.add(practice)
        session.flush()
        approve_fixture_task(session, practice)
        practice_draft = SubmissionDraft(student_id=student.id, task_id=practice.id)
        session.add(practice_draft)
        session.flush()
        session.add(
            SubmissionAttempt(
                draft_id=practice_draft.id,
                student_id=student.id,
                task_id=practice.id,
                attempt_number=1,
                status=AttemptStatus.SUBMITTED,
                answer="Practice",
                feedback="Recorded.",
            )
        )
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
            course_id=course.id,
            assessment_definition_version_id=definition.id,
            task_form_version_id=form.id,
            task_review_event_id=review_event.id,
            actor_user_id=owner.id,
            approval_reason="Approved test form.",
            approval_state=AssessmentApprovalState.APPROVED,
            approved_at=definition.approved_at,
            approved_by_user_id=owner.id,
        )
    )
    session.commit()
    approve_fixture_task(session, task)
    attempt = LmsService(session).submit(
        student,
        task.id,
        SubmissionCreate(
            answer="Formal evidence",
            idempotency_key="assessed-read-test",
        ),
    )
    assert not hasattr(attempt, "score")
    return student, owner, course, task


@pytest.mark.parametrize("with_practice", (False, True))
@pytest.mark.parametrize(
    "path", ("task", "student_dashboard", "educator_students", "educator_dashboard", "history")
)
def test_reads_after_formal_submission(db_session: Session, with_practice: bool, path: str) -> None:
    student, owner, course, task = prepare_reads(db_session, with_practice)
    actor = owner if path.startswith("educator") else student
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    endpoints = {
        "task": f"/api/v1/students/me/tasks/{task.id}",
        "student_dashboard": "/api/v1/students/me/dashboard",
        "educator_students": f"/api/v1/educator/students?course_id={course.id}",
        "educator_dashboard": "/api/v1/educator/dashboard",
        "history": f"/api/v1/students/me/tasks/{task.id}/submissions",
    }
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": actor.email,
                "password": "assessment-model-test-password" if actor is owner else DEMO_PASSWORD,
            },
        )
        assert login.status_code == 200
        response = client.get(endpoints[path])
        assert response.status_code == 200, response.text
        data = response.json()
    if path == "task":
        assert "latest_score" not in data
        assert "score" not in data["latest_attempt"]
        assert data["latest_attempt"]["formal_assessment"] == {
            "result": None,
            "visibility": "withheld",
        }
        assert data["assessment"]["criteria"][0]["mandatory"] is True
    elif path == "student_dashboard":
        assert "average_score" not in data["summary"]
        assert data["recommendations"]
        if not with_practice:
            assert all("%" not in item["reason"] for item in data["recommendations"])
    elif path == "educator_students":
        assert "average_score" not in data[0]
        if not with_practice:
            assert data[0]["at_risk"] is False
    elif path == "educator_dashboard":
        assert all("score" not in item for item in data["recent_activity"])
        formal = next(item for item in data["recent_activity"] if item["formal_assessment"])
        assert formal["formal_assessment"] == {"result": None, "visibility": "withheld"}
        if not with_practice:
            assert "task_type_performance" not in data
            assert "concept_mastery" not in data
    else:
        assert "score" not in data[0]
        assert data[0]["formal_assessment"] == {"result": None, "visibility": "withheld"}
        assert len(data) == (1 if not with_practice else 2)
        if with_practice:
            assert "score" not in data[1]
            assert data[1]["formal_assessment"] is None
    stored = db_session.scalars(
        select(SubmissionAttempt).where(SubmissionAttempt.task_id == task.id)
    ).all()
    assert sorted(item.attempt_number for item in stored) == list(range(1, len(stored) + 1))
