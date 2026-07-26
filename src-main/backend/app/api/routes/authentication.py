from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.authentication import get_current_user
from app.core.config import settings
from app.core.session import create_session_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.authentication import AuthenticatedUserResponse, LoginRequest
from app.services.authentication import authenticate_user

router = APIRouter(prefix="/auth")


@router.post("/login", response_model=AuthenticatedUserResponse)
def login(
    credentials: LoginRequest,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
) -> User:
    user = authenticate_user(session, str(credentials.email), credentials.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    response.set_cookie(
        key=settings.session_cookie_name,
        value=create_session_token(user.id),
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/me", response_model=AuthenticatedUserResponse)
def current_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
