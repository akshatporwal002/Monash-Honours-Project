"""Concurrent mounted login requests retain identity, audit and cookie controls."""

import asyncio

import httpx
import pytest
from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.middleware import Middleware

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import create_session_factory, get_db
from app.main import create_app
from app.models import StudentProfile
from app.models.lms import PlatformAuditEvent
from app.models.user import User, UserRole


def test_async_database_wait_does_not_starve_other_request_completion(db_session, monkeypatch):
    """Minimise real async-route contention without simulation/provider latency."""
    engine = db_session.get_bind()
    # Shorten only the test's pool wait so the old starvation fault fails fast.
    if hasattr(engine.pool, "_timeout"):
        monkeypatch.setattr(engine.pool, "_timeout", 0.1)
    factory = create_session_factory(engine)
    failures = []
    app = create_app()

    def database():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = database

    @app.get("/synthetic-held-read")
    async def held_read(session: Session = Depends(get_db)):
        try:
            session.scalar(select(func.count()).select_from(User))
        except Exception as error:
            failures.append(type(error).__module__ + "." + type(error).__name__)
            raise
        await asyncio.sleep(0.02)
        return {"ready": True}

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await asyncio.gather(*(client.get("/synthetic-held-read") for _ in range(20)))

    responses = asyncio.run(exercise())
    assert all(response.status_code == 200 for response in responses), failures


@pytest.mark.parametrize("follow_dashboard", [False, True])
def test_fifty_concurrent_logins_release_connections_and_preserve_audit(
    db_session, follow_dashboard
):
    password = "synthetic-concurrency-only"
    encoded = hash_password(password)
    users = [
        User(
            email=f"concurrent-{index}@example.com",
            full_name="Synthetic learner",
            role=UserRole.STUDENT,
            password_hash=encoded,
        )
        for index in range(50)
    ]
    db_session.add_all(users)
    db_session.flush()
    db_session.add_all(
        StudentProfile(user_id=user.id, display_name=user.full_name) for user in users
    )
    db_session.commit()
    factory = create_session_factory(db_session.get_bind())
    failures = []

    def database():
        with factory() as session:
            yield session

    class Capture:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            try:
                await self.app(scope, receive, send)
            except Exception as error:
                failures.append(type(error).__module__ + "." + type(error).__name__)
                raise

    app = create_app()
    app.dependency_overrides[get_db] = database
    app.user_middleware.append(Middleware(Capture))

    async def learner(user):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/login", json={"email": user.email, "password": password}
            )
            if follow_dashboard:
                dashboard = await client.get("/api/v1/students/me/dashboard")
                if dashboard.status_code != 200:
                    failures.append(f"dashboard_http_{dashboard.status_code}")
                assert dashboard.status_code == 200, failures
            return response

    async def exercise():
        return await asyncio.gather(*(learner(user) for user in users), return_exceptions=True)

    responses = asyncio.run(exercise())
    assert all(
        isinstance(response, httpx.Response) and response.status_code == 200
        for response in responses
    ), failures
    assert len({response.json()["id"] for response in responses}) == 50
    assert all(settings.csrf_cookie_name in response.cookies for response in responses)
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(PlatformAuditEvent)
            .where(
                PlatformAuditEvent.action == "authentication.login",
                PlatformAuditEvent.outcome == "success",
            )
        )
        == 50
    )
