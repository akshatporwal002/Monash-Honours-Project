from sqlalchemy import select
from test_lms_core_api import lms_context as lms_context
from test_lms_core_api import login
from test_task_review import _source

from app.api.assessment_dependencies import get_scoped_role_eligibility
from app.core.security import hash_password
from app.models import Course, LearningTask, ScopedRole, User, UserRole
from app.services.assessment.access import RoleAssignmentService
from app.services.assessment.eligibility import AssessorEligibilityService
from app.services.lms import DEMO_PASSWORD


def test_source_review_rejects_stale_actions_and_limits_assessors_to_current_read_access(
    lms_context,
):
    client, session = lms_context
    task = session.scalar(select(LearningTask))
    material, revision = _source(session, task)
    base = f"/api/v1/courses/{task.course_id}/materials"
    history_url = f"{base}/{material.id}/revisions"
    approval_url = f"{history_url}/{revision.id}/approvals"
    login(client, "educator")
    approved = client.post(
        approval_url,
        json={"state": "APPROVED", "expected_sequence": 0, "reason": "Read the saved passages"},
    )
    assert approved.status_code == 201, approved.text
    assert approved.json()["created_at"].endswith("Z")
    stale = client.post(
        approval_url,
        json={"state": "REVOKED", "expected_sequence": 0, "reason": "Outdated browser tab"},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "source_approval_conflict"
    assert len(client.get(history_url).json()[0]["approvals"]) == 1

    lead = session.get(User, session.get(Course, task.course_id).educator_id)
    admin = session.scalar(select(User).where(User.role == UserRole.ADMINISTRATOR))
    assessor = User(
        email="source-assessor@example.edu",
        full_name="Source assessor",
        password_hash=hash_password(DEMO_PASSWORD),
        role=UserRole.EDUCATOR,
    )
    session.add(assessor)
    session.commit()
    eligibility = AssessorEligibilityService(session)
    eligibility.record(
        lead,
        course_id=task.course_id,
        subject_user_id=assessor.id,
        state="APPROVED",
        expected_version=0,
        reason="Course lead verified teaching eligibility",
    )
    RoleAssignmentService(session, assignment_eligibility=get_scoped_role_eligibility()).assign(
        admin,
        subject_user_id=assessor.id,
        course_id=task.course_id,
        role=ScopedRole.ASSESSOR,
        reason="Course assessor appointment",
    )
    response = client.post(
        "/api/v1/auth/login", json={"email": assessor.email, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200, response.text
    reads = [
        history_url,
        f"{history_url}/{revision.id}",
        f"{base}/passages/review-passage",
        f"{base}/citations/task/{task.id}",
    ]
    for url in reads:
        assert client.get(url).status_code == 200
    assert (
        client.post(
            approval_url,
            json={
                "state": "REVOKED",
                "expected_sequence": 1,
                "reason": "Assessor cannot change teaching sources",
            },
        ).status_code
        == 403
    )
    assert client.get(history_url).json()[0]["approval_state"] == "APPROVED"
    eligibility.record(
        lead,
        course_id=task.course_id,
        subject_user_id=assessor.id,
        state="WITHDRAWN",
        expected_version=1,
        reason="Appointment ended",
    )
    for url in reads:
        assert client.get(url).status_code == 403
    login(client, "student")
    for url in reads:
        assert client.get(url).status_code == 403
