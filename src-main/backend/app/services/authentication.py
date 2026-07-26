from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User

# Verifying a fallback hash ensures unknown accounts follow the same expensive
# password-verification path as known accounts.
_UNKNOWN_USER_PASSWORD_HASH = hash_password("quantumlearn-unknown-user")


def normalize_email(email: str) -> str:
    """Return the canonical form used to store and look up an email address."""
    return email.strip().casefold()


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    """Authenticate an active user without revealing why authentication failed."""
    normalized_email = normalize_email(email)
    user = session.scalar(select(User).where(User.email == normalized_email))
    password_hash = user.password_hash if user is not None else _UNKNOWN_USER_PASSWORD_HASH
    password_is_valid = verify_password(password, password_hash)

    if user is None or not user.is_active or not password_is_valid:
        return None

    return user
