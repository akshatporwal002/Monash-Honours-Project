from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.session import decode_session_token
from app.db.session import get_db
from app.models.user import User


def get_current_user(
    session: Annotated[Session, Depends(get_db)],
    session_token: Annotated[
        str | None,
        Cookie(alias=settings.session_cookie_name),
    ] = None,
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )
    if session_token is None:
        raise credentials_error

    user_id = decode_session_token(session_token)
    if user_id is None:
        raise credentials_error

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_error

    return user
