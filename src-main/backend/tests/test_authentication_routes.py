from collections.abc import Generator

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
from app.models.user import User, UserRole


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


def test_login_sets_http_only_session_cookie(
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
    }
    assert client.cookies.get(settings.session_cookie_name) is not None
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]


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


def test_logout_clears_session_cookie(client: TestClient, session: Session) -> None:
    add_user(session)
    client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.edu", "password": "correct-password"},
    )

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    assert client.cookies.get(settings.session_cookie_name) is None
    assert client.get("/api/v1/auth/me").status_code == 401


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
