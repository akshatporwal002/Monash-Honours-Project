from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.lms import Course, CourseState, PlatformAuditEvent
from app.models.user import RoleAssignment, ScopedRole, User, UserRole
from app.services.assessment.access import (
    RoleAssignmentConflictError,
    RoleAssignmentPolicyRequiredError,
    RoleAssignmentService,
    RoleAssignmentValidationError,
    ScopedRoleAccessDeniedError,
)

NOW = datetime(2026, 8, 15, 2, 0, tzinfo=UTC)


def _user(
    session: Session,
    email: str,
    role: UserRole,
    *,
    is_active: bool = True,
) -> User:
    user = User(
        email=email,
        password_hash=hash_password("permission-test-password"),
        full_name=email.split("@", maxsplit=1)[0].title(),
        role=role,
        is_active=is_active,
    )
    session.add(user)
    session.flush()
    return user


def _course(session: Session, educator: User, code: str) -> Course:
    course = Course(
        educator_id=educator.id,
        code=code,
        title=f"Course {code}",
    )
    session.add(course)
    session.flush()
    return course


def _actors(session: Session) -> tuple[User, User, Course, Course]:
    administrator = _user(session, "admin@example.edu", UserRole.ADMINISTRATOR)
    educator = _user(session, "educator@example.edu", UserRole.EDUCATOR)
    first_course = _course(session, educator, "QNT101")
    second_course = _course(session, educator, "QNT102")
    session.commit()
    return administrator, educator, first_course, second_course


def _service(session: Session) -> RoleAssignmentService:
    return RoleAssignmentService(
        session,
        correlation_id="00000000-0000-4000-8000-000000000201",
        now=lambda: NOW,
        assignment_eligibility=lambda _subject, _role: True,
    )


def test_assessor_and_research_assignments_are_explicit_and_course_scoped(
    db_session: Session,
) -> None:
    administrator, educator, first_course, second_course = _actors(db_session)
    service = _service(db_session)

    assessor = service.assign(
        administrator,
        subject_user_id=educator.id,
        course_id=first_course.id,
        role=ScopedRole.ASSESSOR,
        reason="Approved to assess QNT101.",
    )
    researcher = service.assign(
        administrator,
        subject_user_id=educator.id,
        course_id=second_course.id,
        role=ScopedRole.RESEARCH,
        reason="Approved for the QNT102 research dataset.",
    )

    assert educator.role is UserRole.EDUCATOR
    assert service.require_assessor_access(educator, first_course.id).id == assessor.id
    assert service.require_research_access(educator, second_course.id).id == researcher.id
    assert {
        (assignment.course_id, assignment.role)
        for assignment in service.list_active_assignments(educator.id)
    } == {
        (first_course.id, ScopedRole.ASSESSOR),
        (second_course.id, ScopedRole.RESEARCH),
    }
    with pytest.raises(ScopedRoleAccessDeniedError):
        service.require_assessor_access(administrator, first_course.id)


def test_educator_without_assessor_assignment_is_denied(db_session: Session) -> None:
    _, educator, first_course, _ = _actors(db_session)

    with pytest.raises(ScopedRoleAccessDeniedError):
        _service(db_session).require_assessor_access(educator, first_course.id)


def test_assignment_requires_explicit_eligibility_policy(db_session: Session) -> None:
    administrator, educator, first_course, _ = _actors(db_session)

    with pytest.raises(RoleAssignmentPolicyRequiredError):
        RoleAssignmentService(db_session).assign(
            administrator,
            subject_user_id=educator.id,
            course_id=first_course.id,
            role=ScopedRole.ASSESSOR,
            reason="This must not bypass the unresolved policy.",
        )


def test_future_replacement_cannot_interrupt_active_assignment(
    db_session: Session,
) -> None:
    administrator, educator, first_course, _ = _actors(db_session)
    service = _service(db_session)
    active = service.assign(
        administrator,
        subject_user_id=educator.id,
        course_id=first_course.id,
        role=ScopedRole.ASSESSOR,
        reason="Current assessment authority.",
    )

    with pytest.raises(
        RoleAssignmentValidationError,
        match="future assignment cannot replace",
    ):
        service.assign(
            administrator,
            subject_user_id=educator.id,
            course_id=first_course.id,
            role=ScopedRole.ASSESSOR,
            reason="Future replacement.",
            valid_from=NOW + timedelta(days=7),
        )

    db_session.refresh(active)
    assert active.revoked_at is None
    assert service.require_assessor_access(educator, first_course.id).id == active.id
    assert [event.action for event in db_session.scalars(select(PlatformAuditEvent)).all()] == [
        "role_assignment.assigned"
    ]


def test_revoked_and_inactive_assignments_are_denied(db_session: Session) -> None:
    administrator, educator, first_course, second_course = _actors(db_session)
    service = _service(db_session)
    revoked = service.assign(
        administrator,
        subject_user_id=educator.id,
        course_id=first_course.id,
        role=ScopedRole.ASSESSOR,
        reason="Temporary assessor assignment.",
    )
    service.revoke(
        administrator,
        revoked.id,
        reason="Assessment period ended.",
    )

    with pytest.raises(ScopedRoleAccessDeniedError):
        service.require_assessor_access(educator, first_course.id)

    service.assign(
        administrator,
        subject_user_id=educator.id,
        course_id=second_course.id,
        role=ScopedRole.ASSESSOR,
        reason="Assessor access starts next week.",
        valid_from=NOW + timedelta(days=7),
    )
    service.assign(
        administrator,
        subject_user_id=educator.id,
        course_id=first_course.id,
        role=ScopedRole.RESEARCH,
        reason="Past research access window.",
        valid_from=NOW - timedelta(days=14),
        valid_until=NOW - timedelta(days=7),
    )
    with pytest.raises(ScopedRoleAccessDeniedError):
        service.require_assessor_access(educator, second_course.id)
    with pytest.raises(ScopedRoleAccessDeniedError):
        service.require_research_access(educator, first_course.id)
    assert service.list_active_assignments(educator.id) == []

    service.assign(
        administrator,
        subject_user_id=educator.id,
        course_id=second_course.id,
        role=ScopedRole.RESEARCH,
        reason="Research access approved.",
    )
    educator.is_active = False
    db_session.commit()

    with pytest.raises(ScopedRoleAccessDeniedError):
        service.require_research_access(educator, second_course.id)
    assert service.list_active_assignments(educator.id) == []


def test_cross_course_assessor_and_research_access_are_denied(
    db_session: Session,
) -> None:
    administrator, educator, first_course, second_course = _actors(db_session)
    service = _service(db_session)
    for role in ScopedRole:
        service.assign(
            administrator,
            subject_user_id=educator.id,
            course_id=first_course.id,
            role=role,
            reason=f"Approved {role.value} access for QNT101.",
        )

    with pytest.raises(ScopedRoleAccessDeniedError):
        service.require_assessor_access(educator, second_course.id)
    with pytest.raises(ScopedRoleAccessDeniedError):
        service.require_research_access(educator, second_course.id)


def test_assignment_changes_are_versioned_and_audited(db_session: Session) -> None:
    administrator, educator, first_course, _ = _actors(db_session)
    service = _service(db_session)
    first = service.assign(
        administrator,
        subject_user_id=educator.id,
        course_id=first_course.id,
        role=ScopedRole.ASSESSOR,
        reason="Initial semester assignment.",
        valid_until=NOW + timedelta(days=30),
    )
    second = service.assign(
        administrator,
        subject_user_id=educator.id,
        course_id=first_course.id,
        role=ScopedRole.ASSESSOR,
        reason="Extended through the examination period.",
        valid_until=NOW + timedelta(days=60),
    )

    db_session.refresh(first)
    assert first.version == 1
    assert first.revoked_at == NOW.replace(tzinfo=None)
    assert second.version == 2
    assert second.supersedes_assignment_id == first.id
    assert service.require_assessor_access(educator, first_course.id).id == second.id

    service.revoke(
        administrator,
        second.id,
        reason="Examination period ended.",
    )
    assignments = list(
        db_session.scalars(select(RoleAssignment).order_by(RoleAssignment.version)).all()
    )
    assert [assignment.version for assignment in assignments] == [1, 2]
    assert all(assignment.revoked_at is not None for assignment in assignments)
    audits = list(
        db_session.scalars(
            select(PlatformAuditEvent).order_by(PlatformAuditEvent.occurred_at)
        ).all()
    )
    assert [event.action for event in audits] == [
        "role_assignment.assigned",
        "role_assignment.changed",
        "role_assignment.revoked",
    ]
    assert [event.actor_id for event in audits] == [administrator.id] * 3
    assert [event.resource_id for event in audits] == [first.id, second.id, second.id]
    assert {event.correlation_id for event in audits} == {"00000000-0000-4000-8000-000000000201"}
    assert [event.details["version"] for event in audits] == [1, 2, 2]
    assert all(event.details["course_id"] == first_course.id for event in audits)
    assert all(event.details["role"] == ScopedRole.ASSESSOR.value for event in audits)
    assert audits[1].details["previous_assignment_id"] == first.id
    assert "previous_assignment_id" not in audits[0].details


def test_course_archive_keeps_assignment_history_and_delete_is_restricted(
    db_session: Session,
) -> None:
    administrator, educator, first_course, _ = _actors(db_session)
    service = _service(db_session)
    assignment = service.assign(
        administrator,
        subject_user_id=educator.id,
        course_id=first_course.id,
        role=ScopedRole.ASSESSOR,
        reason="Retain this assessment authority record.",
    )

    first_course.state = CourseState.ARCHIVED
    db_session.commit()
    assert db_session.get(RoleAssignment, assignment.id) is not None
    assert service.require_assessor_access(educator, first_course.id).id == assignment.id

    db_session.delete(first_course)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    assert db_session.get(RoleAssignment, assignment.id) is not None


def test_concurrent_revocation_preserves_the_winning_actor_reason_and_audit(
    db_session: Session,
) -> None:
    administrator, educator, first_course, _ = _actors(db_session)
    second_administrator = _user(
        db_session,
        "second-admin@example.edu",
        UserRole.ADMINISTRATOR,
    )
    db_session.commit()
    service = _service(db_session)
    assignment = service.assign(
        administrator,
        subject_user_id=educator.id,
        course_id=first_course.id,
        role=ScopedRole.ASSESSOR,
        reason="Concurrent revocation test.",
    )

    bind = db_session.get_bind()
    with Session(bind=bind, expire_on_commit=False) as stale_session:
        stale = stale_session.get(RoleAssignment, assignment.id)
        assert stale is not None and stale.revoked_at is None
        stale_session.commit()

        service.revoke(
            administrator,
            assignment.id,
            reason="First administrator revoked access.",
        )
        with pytest.raises(RoleAssignmentConflictError):
            _service(stale_session).revoke(
                second_administrator,
                assignment.id,
                reason="Stale administrator must not overwrite this.",
            )

    db_session.expire_all()
    stored = db_session.get(RoleAssignment, assignment.id)
    assert stored is not None
    assert stored.revoked_by_user_id == administrator.id
    assert stored.revocation_reason == "First administrator revoked access."
    audits = list(
        db_session.scalars(
            select(PlatformAuditEvent).where(PlatformAuditEvent.resource_id == assignment.id)
        ).all()
    )
    assert [event.action for event in audits] == [
        "role_assignment.assigned",
        "role_assignment.revoked",
    ]


def test_assign_revoke_race_does_not_regrant_from_a_stale_version(
    db_session: Session,
) -> None:
    administrator, educator, first_course, _ = _actors(db_session)
    service = _service(db_session)
    assignment = service.assign(
        administrator,
        subject_user_id=educator.id,
        course_id=first_course.id,
        role=ScopedRole.ASSESSOR,
        reason="Initial authority.",
    )

    bind = db_session.get_bind()
    with Session(bind=bind, expire_on_commit=False) as stale_session:
        stale = stale_session.get(RoleAssignment, assignment.id)
        assert stale is not None and stale.revoked_at is None
        stale_session.commit()

        service.revoke(
            administrator,
            assignment.id,
            reason="Authority explicitly withdrawn.",
        )
        with pytest.raises(RoleAssignmentConflictError):
            _service(stale_session).assign(
                administrator,
                subject_user_id=educator.id,
                course_id=first_course.id,
                role=ScopedRole.ASSESSOR,
                reason="Stale change must not recreate authority.",
            )

    db_session.expire_all()
    assignments = list(db_session.scalars(select(RoleAssignment)).all())
    assert [item.id for item in assignments] == [assignment.id]
    assert assignments[0].revocation_reason == "Authority explicitly withdrawn."
