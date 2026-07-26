from datetime import UTC, datetime, timedelta

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings

_SESSION_ALGORITHM = "HS256"
_SESSION_TOKEN_TYPE = "session"


def create_session_token(
    user_id: int,
    *,
    expires_in: timedelta | None = None,
) -> str:
    """Create a signed, time-limited session token for a user."""
    issued_at = datetime.now(UTC)
    lifetime = expires_in or timedelta(minutes=settings.session_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "type": _SESSION_TOKEN_TYPE,
        "iat": issued_at,
        "exp": issued_at + lifetime,
    }
    return jwt.encode(
        payload,
        settings.session_secret_key.get_secret_value(),
        algorithm=_SESSION_ALGORITHM,
    )


def decode_session_token(token: str) -> int | None:
    """Return the authenticated user ID, or None for any invalid session token."""
    try:
        payload = jwt.decode(
            token,
            settings.session_secret_key.get_secret_value(),
            algorithms=[_SESSION_ALGORITHM],
            options={"require": ["sub", "type", "iat", "exp"]},
        )
        if payload["type"] != _SESSION_TOKEN_TYPE:
            return None

        user_id = int(payload["sub"])
        return user_id if user_id > 0 else None
    except (InvalidTokenError, KeyError, TypeError, ValueError):
        return None
