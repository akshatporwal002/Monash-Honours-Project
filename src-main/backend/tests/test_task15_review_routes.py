"""Task 15 new routes enforce current scoped access with the real frozen reader."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from support.assessment import _lms_scope
from test_task15_migrated_review import request, setup_human

from app.api.dependencies.authentication import get_current_user
from app.api.routes.assessment import router
from app.db.session import get_db
from app.models.user import RoleAssignment, UserRole

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def client_for(session, actor):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[get_db] = lambda: session
    return TestClient(app)


def payload(value):
    from dataclasses import asdict

    return asdict(value)


def test_real_new_routes_expose_complete_criteria_and_confirm(db_session):
    service, actor, attempt, _ = setup_human(
        db_session, revision=True, simulation_status="completed"
    )
    client = client_for(db_session, actor)
    queue = client.get(f"/api/v1/assessment/courses/{attempt.course_id}/unresolved-attempts")
    assert queue.status_code == 200
    detail = client.get(f"/api/v1/assessment/attempts/{attempt.id}/human-review")
    assert detail.status_code == 200
    assert (
        detail.json()["frozen_context"]["transfer_prompt"]
        == "SYNTHETIC PRIVATE fresh Hadamard application"
    )
    assert detail.json()["historical_evidence"][0]["simulations"][0]["status"] == "completed"
    assert detail.json()["criteria"] and detail.json()["criteria"][0]["decision"] is None
    assert detail.json()["response"]["episode"]["transfer"]["content"]["code"] == "  h(0)\n"
    response = client.post(
        f"/api/v1/assessment/attempts/{attempt.id}/human-review",
        json=payload(request(service, actor, attempt.id)),
    )
    assert response.status_code == 200
    assert response.json()["result_state"] == "CONFIRMED"
    reviewed = client.get(f"/api/v1/assessment/decisions/{response.json()['decision_id']}/review")
    assert reviewed.status_code == 200
    assert reviewed.json()["frozen_context"] == detail.json()["frozen_context"]
    assert reviewed.json()["historical_evidence"] == detail.json()["historical_evidence"]
    assert reviewed.json()["criteria"][0]["evaluator_reference"].startswith(f"human:{actor.id}:")
    assert reviewed.json()["response"]["episode"]["transfer"]["content"]["code"] == "  h(0)\n"


@pytest.mark.parametrize(
    "denial", ["revoked", "expired", "inactive", "foreign_educator", "general_admin", "learner"]
)
def test_all_new_routes_recheck_course_scope_and_active_access(db_session, denial):
    service, actor, attempt, _ = setup_human(db_session)
    body = payload(request(service, actor, attempt.id))
    assignment = db_session.scalar(
        select(RoleAssignment).where(
            RoleAssignment.subject_user_id == actor.id,
            RoleAssignment.course_id == attempt.course_id,
        )
    )
    if denial == "revoked":
        assignment.revoked_at = datetime.now(UTC)
        assignment.revoked_by_user_id = actor.id
        assignment.revocation_reason = "The teaching assignment ended"
    elif denial == "expired":
        from app.models.user import ScopedRole, User
        from app.services.assessment.access import RoleAssignmentService

        admin = User(
            email="expiry-admin@example.edu",
            full_name="Grant administrator",
            password_hash=actor.password_hash,
            role=UserRole.ADMINISTRATOR,
        )
        db_session.add(admin)
        db_session.commit()
        RoleAssignmentService(db_session, assignment_eligibility=lambda subject, role: True).assign(
            admin,
            subject_user_id=actor.id,
            course_id=attempt.course_id,
            role=ScopedRole.ASSESSOR,
            reason="A bounded teaching period",
            valid_until=datetime.now(UTC) + timedelta(minutes=1),
        )
    elif denial == "learner":
        from app.models.user import User

        actor = db_session.get(User, attempt.student_id)
    elif denial == "inactive":
        actor.is_active = False
    else:
        actor, *_ = _lms_scope(db_session, suffix="foreign-review")
        if denial == "general_admin":
            actor.role = UserRole.ADMINISTRATOR
    db_session.commit()
    client = client_for(db_session, actor)
    if denial == "expired":
        from app.api.assessment_dependencies import get_role_assignment_service
        from app.services.assessment.access import RoleAssignmentService

        client.app.dependency_overrides[get_role_assignment_service] = lambda: (
            RoleAssignmentService(db_session, now=lambda: datetime.now(UTC) + timedelta(minutes=2))
        )
    responses = [
        client.get(f"/api/v1/assessment/courses/{attempt.course_id}/unresolved-attempts"),
        client.get(f"/api/v1/assessment/attempts/{attempt.id}/human-review"),
        client.post(f"/api/v1/assessment/attempts/{attempt.id}/human-review", json=body),
    ]
    assert [response.status_code for response in responses] == [404, 404, 404]
    assert all(
        "Fresh application" not in response.text and "SYNTHETIC PRIVATE" not in response.text
        for response in responses
    )
