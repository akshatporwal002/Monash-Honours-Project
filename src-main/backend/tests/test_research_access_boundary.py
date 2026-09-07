"""Mounted research access checks using real authentication and scoped grants."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from support.task_review import bootstrap_reviewed_demo

from app.api.research_export_dependencies import get_research_export_service
from app.core.config import settings
from app.db.session import get_db
from app.main import create_app
from app.models.lms import Course
from app.models.user import RoleAssignment, ScopedRole, UserRole
from app.schemas.feedback_api import AuthenticatedActor
from app.services.access import (
    SqlAlchemyAnalyticsAccessPolicy,
    SqlAlchemyResearchExportAccessPolicy,
)
from app.services.feedback.runtime import ConfiguredResearchEligibility
from app.services.lms import DEMO_PASSWORD
from app.services.research_export import PreparedResearchExport


@pytest.mark.parametrize("role", ("educator", "admin"))
def test_ordinary_analytics_access_cannot_export_research(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    bootstrap_reviewed_demo(db_session)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    service = Mock()
    service.prepare.return_value = PreparedResearchExport(
        export_id="00000000-0000-4000-8000-000000000501",
        filename="test-research.csv",
        media_type="text/csv",
        body=[b"test-research-record"],
        record_count=1,
    )
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_research_export_service] = lambda: service
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": f"{role}@quantumlearn.demo", "password": DEMO_PASSWORD},
        )
        assert login.status_code == 200
        response = client.get("/api/v1/research/exports?format=csv")
        assert response.status_code == 403, (response.text, service.prepare.call_count)
        service.prepare.assert_not_called()


@pytest.mark.parametrize("enabled", (False, True))
def test_global_research_flag_cannot_replace_study_and_consent_approval(
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
) -> None:
    monkeypatch.setattr(settings, "research_enabled", enabled)
    assert asyncio.run(ConfiguredResearchEligibility().is_eligible(object())) is False


@pytest.mark.parametrize(
    "grant_state", ("missing", "assessor", "revoked", "expired", "future", "inactive")
)
def test_export_requires_a_current_research_grant(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, grant_state: str
) -> None:
    users, _ = bootstrap_reviewed_demo(db_session)
    educator = next(user for user in users if user.role is UserRole.EDUCATOR)
    admin = next(user for user in users if user.role is UserRole.ADMINISTRATOR)
    course = db_session.scalar(select(Course))
    assert course is not None
    observed = datetime.now(UTC)
    approval_id = None
    if grant_state == "assessor":
        from support.assessment import approve_assessor_eligibility

        approval_id = approve_assessor_eligibility(
            db_session, educator, course.id, at=observed - timedelta(days=2)
        ).id
    if grant_state != "missing":
        assignment = RoleAssignment(
            subject_user_id=educator.id,
            course_id=course.id,
            role=ScopedRole.ASSESSOR if grant_state == "assessor" else ScopedRole.RESEARCH,
            eligibility_approval_id=approval_id,
            version=1,
            assigned_by_user_id=admin.id,
            reason="Explicit test-only permission.",
            assigned_at=observed - timedelta(days=2),
            valid_from=observed - timedelta(days=1),
        )
        if grant_state == "revoked":
            assignment.revoked_at = observed
            assignment.revoked_by_user_id = admin.id
            assignment.revocation_reason = "Test revocation."
        elif grant_state == "expired":
            assignment.valid_until = observed - timedelta(seconds=1)
        elif grant_state == "future":
            assignment.valid_from = observed + timedelta(days=1)
        db_session.add(assignment)
    db_session.commit()
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    service = Mock()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_research_export_service] = lambda: service
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": educator.email, "password": DEMO_PASSWORD}
            ).status_code
            == 200
        )
        if grant_state == "inactive":
            educator.is_active = False
            db_session.commit()
        for params in ({"format": "csv"}, {"format": "json", "course_id": course.id}):
            response = client.get("/api/v1/research/exports", params=params)
            assert response.status_code == (401 if grant_state == "inactive" else 403)
            assert "content-disposition" not in response.headers
        service.prepare.assert_not_called()


def test_research_grants_are_course_scoped_and_revocation_preserves_analytics(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    users, _ = bootstrap_reviewed_demo(db_session)
    educator = next(user for user in users if user.role is UserRole.EDUCATOR)
    admin = next(user for user in users if user.role is UserRole.ADMINISTRATOR)
    owned_course = db_session.scalar(select(Course).where(Course.educator_id == educator.id))
    assert owned_course is not None
    research_course = Course(educator_id=admin.id, code="RESEARCH-ONLY", title="Scoped research")
    db_session.add(research_course)
    db_session.flush()
    now = datetime.now(UTC)
    grant = RoleAssignment(
        subject_user_id=educator.id,
        course_id=research_course.id,
        role=ScopedRole.RESEARCH,
        version=1,
        assigned_by_user_id=admin.id,
        reason="Explicit test-only research scope.",
        assigned_at=now,
        valid_from=now,
    )
    db_session.add(grant)
    db_session.commit()
    actor = AuthenticatedActor(actor_reference=str(educator.id), role="educator")
    policy = SqlAlchemyResearchExportAccessPolicy(db_session)
    assert asyncio.run(policy.authorized_course_ids(actor)) == {research_course.id}
    analytics = SqlAlchemyAnalyticsAccessPolicy(db_session)
    assert asyncio.run(analytics.authorized_course_ids(str(educator.id))) == {owned_course.id}
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(settings, "research_enabled", True)
    service = Mock()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_research_export_service] = lambda: service
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": educator.email, "password": DEMO_PASSWORD}
            ).status_code
            == 200
        )
        for params, expected in (
            ({"format": "csv", "course_id": owned_course.id}, 403),
            ({"format": "json", "course_id": research_course.id}, 503),
            ({"format": "csv"}, 503),
        ):
            response = client.get("/api/v1/research/exports", params=params)
            assert response.status_code == expected
            assert "content-disposition" not in response.headers
            if expected == 503:
                assert response.json()["error"]["code"] == "research_governance_pending"
        service.prepare.assert_not_called()
    grant.revoked_at = datetime.now(UTC)
    grant.revoked_by_user_id = admin.id
    grant.revocation_reason = "Research access revoked in test."
    db_session.commit()
    assert asyncio.run(policy.authorized_course_ids(actor)) == set()
    assert asyncio.run(analytics.authorized_course_ids(str(educator.id))) == {owned_course.id}
