"""Public LMS reads must preserve unscored formal submissions."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from support.assessment import build_assessment_blueprint

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
from app.services.lms import DEMO_PASSWORD, LmsService, bootstrap_demo


def prepare_reads(session: Session, legacy_score: int | None):
    users, _ = bootstrap_demo(session)
    student = next(user for user in users if user.role is UserRole.STUDENT)
    definition, _, _, _, form, owner = build_assessment_blueprint(session)
    course = session.get(Course, definition.course_id)
    task = session.get(LearningTask, form.learning_task_id)
    assert course is not None and task is not None
    course.state = CourseState.PUBLISHED
    session.add(Enrollment(course_id=course.id, student_id=student.id))
    if legacy_score is not None:
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
                score=25,
                feedback="Recorded.",
            )
        )
        practice = LearningTask(
            slug="read-practice",
            title="Practice evidence",
            module=task.module,
            description="Practice",
            instructions="Practice",
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
                score=legacy_score,
                feedback="Recorded.",
            )
        )
    definition.formal_result_eligible = True
    definition.result_eligibility_declared_at = datetime(2026, 8, 16, tzinfo=UTC)
    session.commit()
    definition.approval_state = AssessmentApprovalState.APPROVED
    definition.approved_at = datetime(2026, 8, 16, tzinfo=UTC)
    definition.approved_by_user_id = owner.id
    session.add(
        TaskApproval(
            course_id=course.id,
            assessment_definition_version_id=definition.id,
            task_form_version_id=form.id,
            actor_user_id=owner.id,
            approval_reason="Approved test form.",
            approval_state=AssessmentApprovalState.APPROVED,
            approved_at=definition.approved_at,
            approved_by_user_id=owner.id,
        )
    )
    session.commit()
    attempt = LmsService(session).submit(
        student,
        task.id,
        SubmissionCreate(
            answer="Formal evidence",
            idempotency_key="assessed-read-test",
        ),
    )
    assert attempt.score is None
    return student, owner, course, task


@pytest.mark.parametrize("legacy_score", (None, 0, 80))
@pytest.mark.parametrize(
    "path", ("task", "student_dashboard", "educator_students", "educator_dashboard", "history")
)
def test_reads_after_formal_submission(
    db_session: Session, legacy_score: int | None, path: str
) -> None:
    student, owner, course, task = prepare_reads(db_session, legacy_score)
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
        assert data["latest_score"] is None
        assert data["latest_attempt"]["score"] is None
        assert data["latest_attempt"]["formal_assessment"] == {
            "result": None,
            "visibility": "withheld",
        }
        assert data["assessment"]["criteria"][0]["mandatory"] is True
    elif path == "student_dashboard":
        assert data["summary"]["average_score"] == legacy_score
        assert data["recommendations"]
        if legacy_score is None:
            assert all("%" not in item["reason"] for item in data["recommendations"])
    elif path == "educator_students":
        assert data[0]["average_score"] == legacy_score
        if legacy_score is None:
            assert data[0]["at_risk"] is False
    elif path == "educator_dashboard":
        assert any(item["score"] is None for item in data["recent_activity"])
        formal = next(item for item in data["recent_activity"] if item["formal_assessment"])
        assert formal["formal_assessment"] == {"result": None, "visibility": "withheld"}
        if legacy_score is None:
            assert data["task_type_performance"] == []
            assert data["concept_mastery"] == []
    else:
        assert data[0]["score"] is None
        assert data[0]["formal_assessment"] == {"result": None, "visibility": "withheld"}
        assert len(data) == (1 if legacy_score is None else 2)
        if legacy_score is not None:
            assert data[1]["score"] == 25
            assert data[1]["formal_assessment"] is None
    stored = db_session.scalars(
        select(SubmissionAttempt).where(SubmissionAttempt.task_id == task.id)
    ).all()
    assert sorted(item.attempt_number for item in stored) == list(range(1, len(stored) + 1))
