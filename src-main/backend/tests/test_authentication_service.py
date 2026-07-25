import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.models.user import User, UserRole
from app.services.authentication import authenticate_user, normalize_email


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as database_session:
        yield database_session

    Base.metadata.drop_all(engine)


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


def test_normalize_email_strips_whitespace_and_ignores_case() -> None:
    assert normalize_email("  Student@Example.EDU ") == "student@example.edu"


def test_authenticate_user_returns_active_user_for_valid_credentials(session: Session) -> None:
    user = add_user(session)

    authenticated_user = authenticate_user(
        session,
        email="  STUDENT@example.edu ",
        password="correct-password",
    )

    assert authenticated_user is user


def test_authenticate_user_rejects_wrong_password(session: Session) -> None:
    add_user(session)

    assert authenticate_user(session, "student@example.edu", "wrong-password") is None


def test_authenticate_user_rejects_unknown_email(session: Session) -> None:
    assert authenticate_user(session, "unknown@example.edu", "any-password") is None


def test_authenticate_user_rejects_inactive_account(session: Session) -> None:
    add_user(session, is_active=False)

    assert authenticate_user(session, "student@example.edu", "correct-password") is None
