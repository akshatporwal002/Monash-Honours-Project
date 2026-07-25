from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a non-empty password using Argon2id."""
    if not password:
        raise ValueError("Password must not be empty")

    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return whether a password matches an encoded Argon2 hash."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False
