import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.user import User, UserRole


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


def test_user_is_persisted_with_role_and_active_status(session: Session) -> None:
    user = User(
        email="student@example.edu",
        password_hash="not-a-plain-text-password",
        full_name="Example Student",
        role=UserRole.STUDENT,
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    assert user.id is not None
    assert user.role is UserRole.STUDENT
    assert user.is_active is True
    assert user.created_at is not None
    assert user.updated_at is not None


def test_user_email_must_be_unique(session: Session) -> None:
    session.add_all(
        [
            User(
                email="educator@example.edu",
                password_hash="first-hash",
                full_name="First Educator",
                role=UserRole.EDUCATOR,
            ),
            User(
                email="educator@example.edu",
                password_hash="second-hash",
                full_name="Second Educator",
                role=UserRole.EDUCATOR,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        session.commit()
