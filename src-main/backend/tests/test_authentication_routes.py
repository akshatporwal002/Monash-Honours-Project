from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.lms import Course, PlatformAuditEvent
from app.models.user import ScopedRole, User, UserRole
from app.services.assessment.access import RoleAssignmentService


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as database_session:
        yield database_session

    Base.metadata.drop_all(engine)


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def add_user(session: Session, *, is_active: bool = True) -> User:
    user = User(
        email="student@example.edu",
        password_hash=hash_password("correct-password"),
        full_name="Example Student",
        role=UserRole.STUDENT,
        is_active=is_active,
    )
    session.add(user)
    session.commit()
    return user


def test_login_sets_session_and_csrf_cookies(
    client: TestClient,
    session: Session,
) -> None:
    user = add_user(session)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "STUDENT@example.edu", "password": "correct-password"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": user.id,
        "email": "student@example.edu",
        "full_name": "Example Student",
        "role": "student",
        "scoped_assignments": [],
    }
    assert client.cookies.get(settings.session_cookie_name) is not None
    assert client.cookies.get(settings.csrf_cookie_name) is not None
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    audit = session.query(PlatformAuditEvent).one()
    assert audit.actor_id == user.id
    assert audit.action == "authentication.login"
    assert audit.outcome == "success"
    assert len(audit.correlation_id) == 36


def test_current_user_restores_authenticated_session(
    client: TestClient,
    session: Session,
) -> None:
    add_user(session)
    client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.edu", "password": "correct-password"},
    )

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "student@example.edu"


def test_login_returns_active_assignments_without_changing_primary_role(
    client: TestClient,
    session: Session,
) -> None:
    educator = User(
        email="owner@example.edu",
        password_hash=hash_password("owner-password"),
        full_name="Course Owner",
        role=UserRole.EDUCATOR,
        is_active=True,
    )
    administrator = User(
        email="admin@example.edu",
        password_hash=hash_password("admin-password"),
        full_name="Administrator",
        role=UserRole.ADMINISTRATOR,
        is_active=True,
    )
    session.add_all([educator, administrator])
    session.flush()
    course = Course(
        educator_id=educator.id,
        code="QNT201",
        title="Assessment Foundations",
    )
    session.add(course)
    session.commit()
    assignment = RoleAssignmentService(
        session,
        assignment_eligibility=lambda _subject, _role: True,
    ).assign(
        administrator,
        subject_user_id=educator.id,
        course_id=course.id,
        role=ScopedRole.ASSESSOR,
        reason="Approved course assessor.",
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": educator.email, "password": "owner-password"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "educator"
    assert response.json()["scoped_assignments"] == [
        {
            "id": assignment.id,
            "course_id": course.id,
            "role": "assessor",
            "version": 1,
            "valid_from": assignment.valid_from.isoformat(),
            "valid_until": None,
        }
    ]
    assert (
        client.get("/api/v1/auth/me").json()["scoped_assignments"]
        == response.json()["scoped_assignments"]
    )
    assignment_service = RoleAssignmentService(
        session,
        assignment_eligibility=lambda _subject, _role: True,
    )
    assignment_service.revoke(
        administrator,
        assignment.id,
        reason="Assessor access withdrawn.",
    )
    now = datetime.now(UTC)
    assignment_service.assign(
        administrator,
        subject_user_id=educator.id,
        course_id=course.id,
        role=ScopedRole.RESEARCH,
        reason="Research access starts next week.",
        valid_from=now + timedelta(days=7),
    )
    assignment_service.assign(
        administrator,
        subject_user_id=educator.id,
        course_id=course.id,
        role=ScopedRole.ASSESSOR,
        reason="Expired assessor access.",
        valid_from=now - timedelta(days=14),
        valid_until=now - timedelta(days=7),
    )
    assert client.get("/api/v1/auth/me").json()["scoped_assignments"] == []


def test_logout_clears_session_cookie(client: TestClient, session: Session) -> None:
    add_user(session)
    client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.edu", "password": "correct-password"},
    )

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    assert client.cookies.get(settings.session_cookie_name) is None
    assert client.cookies.get(settings.csrf_cookie_name) is None
    assert client.get("/api/v1/auth/me").status_code == 401
    assert {event.action for event in session.query(PlatformAuditEvent).all()} == {
        "authentication.login",
        "authentication.logout",
    }


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("student@example.edu", "wrong-password"),
        ("unknown@example.edu", "correct-password"),
    ],
)
def test_login_rejects_invalid_credentials(
    client: TestClient,
    session: Session,
    email: str,
    password: str,
) -> None:
    add_user(session)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}
    assert client.cookies.get(settings.session_cookie_name) is None
    audit = session.query(PlatformAuditEvent).one()
    assert audit.actor_id is None
    assert audit.outcome == "failure"
    assert "student@example.edu" not in audit.resource_id


def test_login_rejects_inactive_account(client: TestClient, session: Session) -> None:
    add_user(session, is_active=False)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.edu", "password": "correct-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_current_user_rejects_tampered_session_cookie(client: TestClient) -> None:
    client.cookies.set(settings.session_cookie_name, "not-a-valid-token")

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
