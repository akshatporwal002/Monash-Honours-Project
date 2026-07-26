import hashlib
from secrets import token_urlsafe
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.authentication import get_current_user
from app.core.config import settings
from app.core.session import create_session_token
from app.db.session import get_db
from app.models.lms import PlatformAuditEvent
from app.models.user import User
from app.schemas.authentication import AuthenticatedUserResponse, LoginRequest
from app.services.authentication import authenticate_user, normalize_email

router = APIRouter(prefix="/auth")


@router.post("/login", response_model=AuthenticatedUserResponse)
def login(
    credentials: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_db)],
) -> User:
    user = authenticate_user(session, str(credentials.email), credentials.password)
    if user is None:
        _record_login(
            session,
            request,
            actor=None,
            email=str(credentials.email),
            outcome="failure",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    _record_login(
        session,
        request,
        actor=user,
        email=user.email,
        outcome="success",
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
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token_urlsafe(32),
        max_age=settings.session_ttl_minutes * 60,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    session.add(
        PlatformAuditEvent(
            actor_id=user.id,
            action="authentication.logout",
            resource_type="user",
            resource_id=str(user.id),
            outcome="success",
            correlation_id=_correlation_id(request),
        )
    )
    session.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/me", response_model=AuthenticatedUserResponse)
def current_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


def _record_login(
    session: Session,
    request: Request,
    *,
    actor: User | None,
    email: str,
    outcome: str,
) -> None:
    subject_hash = hashlib.sha256(normalize_email(email).encode()).hexdigest()[:16]
    session.add(
        PlatformAuditEvent(
            actor_id=actor.id if actor is not None else None,
            action="authentication.login",
            resource_type="user",
            resource_id=str(actor.id) if actor is not None else f"unknown:{subject_hash}",
            outcome=outcome,
            correlation_id=_correlation_id(request),
        )
    )
    session.commit()


def _correlation_id(request: Request) -> str:
    contextual = getattr(request.state, "correlation_id", None)
    return contextual if isinstance(contextual, str) else str(uuid4())
