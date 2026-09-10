"""Real cookie-authenticated governance writes retain CSRF, roles and rate limits."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.security_dependencies import get_request_security_guard
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import create_session_factory, get_db_session
from app.main import create_app
from app.models.lms import Course, Enrollment
from app.models.research_governance import ResearchGovernanceEvent
from app.models.user import User, UserRole
from app.schemas.research_governance import ApprovalDecision, ConsentDecision, StudyScope
from app.services.research.governance import research_processing_approved

PASSWORD = "synthetic-governance-fixture-only"
URL = "/api/v1/research/governance/synthetic-security-study/decisions"


@pytest.fixture
def governance_api(db_session, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "csrf_enabled", True)
    get_request_security_guard.cache_clear()
    password_hash = hash_password(PASSWORD)
    users = {
        role: User(
            email=f"synthetic-governance-{role.value}@example.com",
            full_name="Synthetic governance fixture",
            role=role,
            password_hash=password_hash,
        )
        for role in UserRole
    }
    db_session.add_all(users.values())
    db_session.flush()
    course = Course(
        code="GOVERNANCE-SECURITY",
        title="Synthetic only",
        educator_id=users[UserRole.EDUCATOR].id,
    )
    db_session.add(course)
    db_session.flush()
    db_session.add(Enrollment(course_id=course.id, student_id=users[UserRole.STUDENT].id))
    db_session.commit()
    now = datetime.now(UTC)
    scope = StudyScope(
        protocol_version="synthetic-v1",
        data_plan_version="synthetic-v1",
        consent_version="synthetic-v1",
        eligibility_rule_version="synthetic-v1",
        withdrawal_rule_reference="synthetic-only",
        processing_researcher_id=users[UserRole.EDUCATOR].id,
        course_ids=[course.id],
        fields=["case_id"],
        purposes=["technical_pair"],
        valid_from=now - timedelta(minutes=1),
        valid_until=now + timedelta(days=1),
        retention=[
            {
                "record_class": record_class,
                "authority_reference": "synthetic-only",
                "authority_version": "synthetic-v1",
                "owner_reference": "synthetic-owner",
                "trigger": "synthetic-closure",
                "retention_rule": "review-only-no-deletion",
                "review_at": now + timedelta(days=2),
            }
            for record_class in (
                "governance",
                "identity_mapping",
                "technical_pairs",
                "export_audit",
            )
        ],
    )
    factory = create_session_factory(db_session.get_bind())

    def database():
        with factory() as session:
            yield session

    app = create_app()
    # Only storage is isolated. Authentication, CSRF and the configured rate limiter are real.
    app.dependency_overrides[get_db_session] = database
    assert research_processing_approved() is False
    try:
        yield SimpleNamespace(app=app, users=users, scope=scope, course=course, session=db_session)
    finally:
        app.dependency_overrides.clear()
        get_request_security_guard.cache_clear()
        assert research_processing_approved() is False


def login(client, user):
    response = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    csrf = client.cookies.get(settings.csrf_cookie_name)
    assert csrf
    assert client.get("/api/v1/auth/me").json()["id"] == user.id
    return {settings.csrf_header_name: csrf, "Origin": settings.allowed_cors_origins[0]}


def command(decision, revision):
    return {
        "request_key": str(uuid4()),
        "expected_revision": revision,
        "reason": "synthetic-security-regression",
        "decision": decision.model_dump(mode="json"),
    }


def test_governance_writes_use_real_auth_csrf_and_role_boundaries(governance_api):
    g = governance_api
    scope_command = command(g.scope, 0)
    with TestClient(g.app) as admin, TestClient(g.app) as learner:
        anonymous = admin.post(URL, json=scope_command)
        assert anonymous.status_code == 401
        admin_headers = login(admin, g.users[UserRole.ADMINISTRATOR])
        missing_csrf = admin.post(
            URL, json=scope_command, headers={"Origin": admin_headers["Origin"]}
        )
        assert missing_csrf.status_code == 403
        assert missing_csrf.json()["error"]["code"] == "csrf_validation_failed"
        created = admin.post(URL, json=scope_command, headers=admin_headers)
        assert created.status_code == 201, created.text
        assert created.json()["production_active"] is False
        assert created.headers["cache-control"] == "no-store"
        scope_id = created.json()["id"]
        approval = ApprovalDecision(
            scope_id=scope_id,
            state="approved",
            authority_reference="synthetic-only",
            evidence_reference="synthetic-only",
            valid_from=g.scope.valid_from,
            valid_until=g.scope.valid_until,
        )
        learner_headers = login(learner, g.users[UserRole.STUDENT])
        forbidden = learner.post(URL, json=command(approval, 1), headers=learner_headers)
        assert forbidden.status_code == 403
        assert forbidden.json()["detail"] == "governance_custodian_required"
        approved = admin.post(URL, json=command(approval, 1), headers=admin_headers)
        assert approved.status_code == 201, approved.text
        consent = ConsentDecision(
            scope_id=scope_id,
            course_id=g.course.id,
            subject_user_id=g.users[UserRole.STUDENT].id,
            decision="consented",
            consent_version=g.scope.consent_version,
            fields=g.scope.fields,
            purposes=g.scope.purposes,
        )
        impersonated = admin.post(URL, json=command(consent, 2), headers=admin_headers)
        assert impersonated.status_code == 403
        assert impersonated.json()["detail"] == "consent_owner_required"
        saved = learner.post(URL, json=command(consent, 2), headers=learner_headers)
        assert saved.status_code == 201, saved.text
        withdrawn = learner.post(
            URL,
            json=command(consent.model_copy(update={"decision": "withdrawn"}), 3),
            headers=learner_headers,
        )
        assert withdrawn.status_code == 201, withdrawn.text
        assert withdrawn.json()["production_active"] is False
    assert g.session.scalar(select(func.count()).select_from(ResearchGovernanceEvent)) == 4


def test_governance_rate_limit_allows_sixty_writes_then_denies_only_that_actor(governance_api):
    g = governance_api
    request = command(g.scope, 0)
    with TestClient(g.app) as admin, TestClient(g.app) as learner:
        headers = login(admin, g.users[UserRole.ADMINISTRATOR])
        scope_id = None
        # Exact retries exercise the real write route without manufacturing sixty scope versions.
        for _ in range(60):
            response = admin.post(URL, json=request, headers=headers)
            assert response.status_code == 201, response.text
            scope_id = scope_id or response.json()["id"]
            assert response.json()["id"] == scope_id
        denied = admin.post(URL, json=command(g.scope, 1), headers=headers)
        assert denied.status_code == 429
        assert denied.json()["error"]["code"] == "rate_limit_exceeded"
        assert 1 <= int(denied.headers["retry-after"]) <= 60
        assert denied.headers["cache-control"] == "no-store"
        learner_headers = login(learner, g.users[UserRole.STUDENT])
        decline = ConsentDecision(
            scope_id=scope_id,
            course_id=g.course.id,
            subject_user_id=g.users[UserRole.STUDENT].id,
            decision="declined",
            consent_version=g.scope.consent_version,
        )
        separate_actor = learner.post(URL, json=command(decline, 1), headers=learner_headers)
        assert separate_actor.status_code == 201, separate_actor.text
        assert separate_actor.json()["production_active"] is False
    assert g.session.scalar(select(func.count()).select_from(ResearchGovernanceEvent)) == 2
