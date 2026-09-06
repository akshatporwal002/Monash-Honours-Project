from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_lms_core_api import lms_context as lms_context
from test_lms_core_api import login

from app.models import Course, PlatformAuditEvent, ScopedRole, User, UserRole
from app.models.assessor_eligibility import AssessorEligibilityApproval
from app.services.assessment.access import (
    RoleAssignmentConflictError,
    RoleAssignmentService,
    RoleAssignmentValidationError,
    ScopedRoleAccessDeniedError,
)
from app.services.assessment.eligibility import AssessorEligibilityService


@pytest.fixture
def eligibility_context(db_session):
    actors = {}
    for name, role in (
        ("lead", UserRole.EDUCATOR),
        ("staff", UserRole.EDUCATOR),
        ("outsider", UserRole.EDUCATOR),
        ("admin", UserRole.ADMINISTRATOR),
        ("student", UserRole.STUDENT),
    ):
        actors[name] = User(
            email=f"{name}@eligibility.test", password_hash="unused", full_name=name, role=role
        )
    db_session.add_all(actors.values())
    db_session.flush()
    course = Course(educator_id=actors["lead"].id, code="ELIG-1", title="Eligibility course")
    db_session.add(course)
    db_session.commit()
    clock = [datetime(2026, 9, 7, 4, tzinfo=UTC)]
    service = AssessorEligibilityService(db_session, now=lambda: clock[0])
    return service, actors, course, clock


def _approve(context, **overrides):
    service, actors, course, _ = context
    payload = dict(
        course_id=course.id,
        subject_user_id=actors["staff"].id,
        expected_version=0,
        state="APPROVED",
        reason="Teaching eligibility confirmed",
    )
    return service.record(actors["lead"], **{**payload, **overrides})


def test_course_lead_approval_is_versioned_and_does_not_itself_grant_access(
    db_session, eligibility_context
):
    service, actors, course, clock = eligibility_context
    approved = _approve(eligibility_context, valid_until=clock[0] + timedelta(days=30))
    assert approved.version == 1
    assert approved.policy_version == "assessor-access-v1-selection"
    assert approved.actor_user_id == actors["lead"].id
    assert service.current(course.id, actors["staff"].id).id == approved.id
    with pytest.raises(ScopedRoleAccessDeniedError):
        RoleAssignmentService(db_session, now=lambda: clock[0]).require_assessor_access(
            actors["staff"], course.id
        )
    withdrawn = service.record(
        actors["lead"],
        course_id=course.id,
        subject_user_id=actors["staff"].id,
        expected_version=1,
        state="WITHDRAWN",
        reason="Teaching duties ended",
    )
    assert withdrawn.version == 2
    assert service.current(course.id, actors["staff"].id) is None
    assert len(service.history(actors["admin"], course.id)) == 2
    assert db_session.scalar(select(func.count()).select_from(PlatformAuditEvent)) == 2


@pytest.mark.parametrize("actor", ["outsider", "admin", "student"])
def test_only_course_lead_can_record_eligibility(eligibility_context, actor):
    service, actors, course, _ = eligibility_context
    with pytest.raises(ScopedRoleAccessDeniedError):
        service.record(
            actors[actor],
            course_id=course.id,
            subject_user_id=actors["staff"].id,
            expected_version=0,
            state="APPROVED",
            reason="Not authorised",
        )
    assert service.latest(course.id, actors["staff"].id) is None


def test_stale_replay_cannot_duplicate_approval(eligibility_context):
    _approve(eligibility_context)
    with pytest.raises(RoleAssignmentConflictError):
        _approve(eligibility_context)


def test_expiry_and_deactivation_remove_current_eligibility(db_session, eligibility_context):
    service, actors, course, clock = eligibility_context
    _approve(eligibility_context, valid_until=clock[0] + timedelta(hours=1))
    actors["staff"].is_active = False
    db_session.commit()
    assert service.current(course.id, actors["staff"].id) is None
    actors["staff"].is_active = True
    db_session.commit()
    clock[0] += timedelta(hours=1)
    assert service.current(course.id, actors["staff"].id) is None


@pytest.mark.parametrize(
    "change", ["student", "admin", "inactive", "expired", "blank", "withdraw", "unknown_state"]
)
def test_invalid_eligibility_is_rejected(db_session, eligibility_context, change):
    _, actors, _, clock = eligibility_context
    payload = {}
    if change in {"student", "admin"}:
        payload["subject_user_id"] = actors[change].id
    elif change == "inactive":
        actors["staff"].is_active = False
        db_session.commit()
    elif change == "expired":
        payload["valid_until"] = clock[0]
    elif change == "blank":
        payload["reason"] = " "
    elif change == "withdraw":
        payload["state"] = "WITHDRAWN"
    else:
        payload["state"] = "OTHER"
    with pytest.raises(RoleAssignmentValidationError):
        _approve(eligibility_context, **payload)
    assert db_session.scalar(select(func.count()).select_from(AssessorEligibilityApproval)) == 0


def test_history_is_private_and_paginated(eligibility_context):
    service, actors, course, clock = eligibility_context
    first = _approve(eligibility_context)
    clock[0] += timedelta(seconds=1)
    second = _approve(eligibility_context, expected_version=1, reason="Reviewed again")
    assert service.history(actors["lead"], course.id, limit=1)[0].id == second.id
    assert service.history(actors["admin"], course.id, limit=1, offset=1)[0].id == first.id
    for actor in ("staff", "outsider", "student"):
        with pytest.raises(ScopedRoleAccessDeniedError):
            service.history(actors[actor], course.id)


def test_approval_history_cannot_be_changed_or_replaced(db_session, eligibility_context):
    _approve(eligibility_context)
    for statement in (
        "UPDATE assessor_eligibility_approvals SET reason = 'changed'",
        "DELETE FROM assessor_eligibility_approvals",
        "INSERT OR REPLACE INTO assessor_eligibility_approvals SELECT * FROM assessor_eligibility_approvals",
    ):
        with pytest.raises(IntegrityError, match="append-only"):
            db_session.execute(text(statement))
        db_session.rollback()


def test_concurrent_changes_cannot_overwrite_each_other(db_session, eligibility_context):
    _, actors, course, clock = eligibility_context
    _approve(eligibility_context)
    barrier = Barrier(2)
    lead_id, staff_id, course_id = actors["lead"].id, actors["staff"].id, course.id

    def change(state):
        with Session(db_session.get_bind()) as session:
            lead = session.get(User, lead_id)
            service = AssessorEligibilityService(session, now=lambda: clock[0])
            barrier.wait()
            try:
                return service.record(
                    lead,
                    course_id=course_id,
                    subject_user_id=staff_id,
                    expected_version=1,
                    state=state,
                    reason="Concurrent review",
                ).version
            except RoleAssignmentConflictError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(change, ["APPROVED", "WITHDRAWN"]))
    assert set(results) == {2, "conflict"}
    assert db_session.scalar(select(func.count()).select_from(AssessorEligibilityApproval)) == 2


def test_http_course_lead_approval_path_has_no_policy_override(lms_context):
    client, session = lms_context
    course = session.scalar(select(Course))
    path = f"/api/v1/assessment/courses/{course.id}/assessor-eligibility"
    assert client.get(path).status_code == 401
    grant_path = f"/api/v1/assessment/admin/courses/{course.id}/assignments"
    grant_payload = {
        "subject_user_id": course.educator_id,
        "role": "assessor",
        "reason": "Named course assessor",
    }
    login(client, "admin")
    assert client.post(grant_path, json=grant_payload).status_code == 422
    client.post("/api/v1/auth/logout")
    login(client, "educator")
    payload = {
        "subject_user_id": course.educator_id,
        "expected_version": 0,
        "state": "APPROVED",
        "reason": "Course lead confirms teaching eligibility",
    }
    approved = client.post(path, json=payload)
    assert approved.status_code == 201, approved.text
    assert approved.json()["created_at"].endswith("Z")
    assert client.get(path).json()[0]["id"] == approved.json()["id"]
    assert client.post(path, json=payload).status_code == 409
    client.post("/api/v1/auth/logout")
    login(client, "admin")
    assert client.get(path).status_code == 200
    assert client.post(path, json=payload).status_code == 403
    grant = client.post(grant_path, json=grant_payload)
    assert grant.status_code == 201, grant.text
    assert grant.json()["eligibility_approval_id"] == approved.json()["id"]
    client.post("/api/v1/auth/logout")
    login(client, "educator")
    assert len(client.get("/api/v1/auth/me").json()["scoped_assignments"]) == 1
    assert (
        client.post(path, json={**payload, "expected_version": 1, "state": "WITHDRAWN"}).status_code
        == 201
    )
    assert client.get("/api/v1/auth/me").json()["scoped_assignments"] == []
    client.post("/api/v1/auth/logout")
    login(client, "student")
    assert client.get(path).status_code == 403


def test_reapproval_needs_a_new_admin_grant_and_retains_old_history(
    db_session, eligibility_context
):
    from app.api.assessment_dependencies import get_scoped_role_eligibility

    service, actors, course, clock = eligibility_context
    first = _approve(eligibility_context, valid_until=clock[0] + timedelta(days=3))
    assignments = RoleAssignmentService(
        db_session, now=lambda: clock[0], assignment_eligibility=get_scoped_role_eligibility()
    )
    grant = assignments.assign(
        actors["admin"],
        subject_user_id=actors["staff"].id,
        course_id=course.id,
        role=ScopedRole.ASSESSOR,
        reason="Approved teaching appointment",
    )
    assert grant.eligibility_approval_id == first.id
    assert grant.valid_until == first.valid_until
    service.record(
        actors["lead"],
        course_id=course.id,
        subject_user_id=actors["staff"].id,
        expected_version=1,
        state="WITHDRAWN",
        reason="Appointment paused",
    )
    second = _approve(eligibility_context, expected_version=2)
    with pytest.raises(ScopedRoleAccessDeniedError):
        assignments.require_assessor_access(actors["staff"], course.id)
    new_grant = assignments.assign(
        actors["admin"],
        subject_user_id=actors["staff"].id,
        course_id=course.id,
        role=ScopedRole.ASSESSOR,
        reason="New appointment recorded",
    )
    assert new_grant.eligibility_approval_id == second.id
    assert assignments.require_assessor_access(actors["staff"], course.id).id == new_grant.id
    assert grant.eligibility_approval_id == first.id


def test_grant_cannot_outlive_course_approval(db_session, eligibility_context):
    from app.api.assessment_dependencies import get_scoped_role_eligibility

    _, actors, course, clock = eligibility_context
    _approve(eligibility_context, valid_until=clock[0] + timedelta(days=1))
    assignments = RoleAssignmentService(
        db_session, now=lambda: clock[0], assignment_eligibility=get_scoped_role_eligibility()
    )
    with pytest.raises(RoleAssignmentValidationError, match="cannot extend"):
        assignments.assign(
            actors["admin"],
            subject_user_id=actors["staff"].id,
            course_id=course.id,
            role=ScopedRole.ASSESSOR,
            reason="Longer appointment",
            valid_until=clock[0] + timedelta(days=2),
        )


def test_future_grant_can_replace_an_appointment_with_withdrawn_approval(
    db_session, eligibility_context
):
    from app.api.assessment_dependencies import get_scoped_role_eligibility

    service, actors, course, clock = eligibility_context
    _approve(eligibility_context)
    assignments = RoleAssignmentService(
        db_session, now=lambda: clock[0], assignment_eligibility=get_scoped_role_eligibility()
    )
    assignments.assign(
        actors["admin"],
        subject_user_id=actors["staff"].id,
        course_id=course.id,
        role=ScopedRole.ASSESSOR,
        reason="Initial appointment",
    )
    service.record(
        actors["lead"],
        course_id=course.id,
        subject_user_id=actors["staff"].id,
        expected_version=1,
        state="WITHDRAWN",
        reason="Appointment paused",
    )
    _approve(eligibility_context, expected_version=2)
    upcoming = assignments.assign(
        actors["admin"],
        subject_user_id=actors["staff"].id,
        course_id=course.id,
        role=ScopedRole.ASSESSOR,
        reason="Appointment resumes tomorrow",
        valid_from=clock[0] + timedelta(days=1),
    )
    assert assignments.list_active_assignments(actors["staff"].id) == []
    clock[0] += timedelta(days=1)
    assert assignments.require_assessor_access(actors["staff"], course.id).id == upcoming.id
