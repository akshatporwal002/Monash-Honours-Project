"""Synthetic restricted-text disposal; no real participant data is deleted."""

from datetime import timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, select, text
from test_research_governance import governed as governed
from test_research_instruments import instruments as instruments
from test_research_study import pipeline
from test_research_study import study as study

from app.models.research_governance import ResearchGovernanceEvent
from app.models.research_instruments import ResearchInstrumentRecord, RestrictedInstrumentEvidence
from app.schemas.research_governance import (
    DisposalAuthorization,
    DisposalExecute,
    DisposalExecution,
    RetentionHold,
)
from app.services.research.disposal import custodian, execute, inventory
from app.services.research.governance import GovernanceConflict, GovernanceDenied
from app.services.research.instruments import BASE_FIELDS


def prepare(g, **changes):
    response, packet, _, _ = pipeline(g)
    manifest = inventory(g.service, g.study, [response.id])
    decision = DisposalAuthorization(
        scope_id=g.scope_event.id,
        record_class="restricted_instrument_evidence",
        record_ids=[response.id],
        manifest_digest=manifest["manifest_digest"],
        executor_user_id=g.admin.id,
        state="authorized",
        method="delete_restricted_text",
        authority_reference="synthetic-only",
        evidence_reference="synthetic-only",
        not_before=g.now - timedelta(hours=1),
        valid_until=g.now + timedelta(hours=1),
    ).model_copy(update=changes)
    authorization = g.record(decision)
    return response, packet, manifest, authorization


def test_exact_authorized_disposal_is_audited_idempotent_and_preserves_history(study):
    g = study
    response, packet, manifest, authorization = prepare(g)
    assert not manifest["disposal_permitted"] and "response_text" not in str(manifest)
    assert g.session.scalar(select(func.count()).select_from(RestrictedInstrumentEvidence)) == 1
    command = DisposalExecute(authorization_id=authorization.id, request_key="synthetic-disposal")
    receipt = execute(g.service, g.admin.id, g.study, command)
    assert receipt["disposed_count"] == 1
    assert execute(g.service, g.admin.id, g.study, command) == receipt
    assert g.session.scalar(select(func.count()).select_from(RestrictedInstrumentEvidence)) == 0
    assert g.session.get(ResearchInstrumentRecord, response.id) is not None
    event = g.session.get(ResearchGovernanceEvent, receipt["id"])
    assert event.kind == "disposal_execution"
    assert "Synthetic private answer" not in str(event.command)
    assert any(row.kind == "consent" for row in g.service.events(g.study))
    with pytest.raises(GovernanceDenied, match="disposed"):
        g.instruments.read(g.educator.id, g.study, g.course.id, response.id, BASE_FIELDS)
    with pytest.raises(GovernanceDenied, match="disposed"):
        g.workflow.packet(g.reviewer.id, g.study, g.course.id, packet.id)
    with pytest.raises(Exception, match="immutable"):
        g.session.execute(text("DELETE FROM research_instrument_records"))
    g.session.rollback()


@pytest.mark.parametrize("block", ["hold", "window", "executor", "revoked", "scope"])
def test_disposal_rechecks_hold_scope_window_executor_and_revocation(study, block):
    g = study
    response, _, _, authorization = prepare(
        g, **({"not_before": g.now + timedelta(minutes=1)} if block == "window" else {})
    )
    if block == "hold":
        g.record(
            RetentionHold(
                scope_id=g.scope_event.id,
                record_class="restricted_instrument_evidence",
                hold_reference="synthetic-hold",
                authority_reference="synthetic-only",
                active=True,
            )
        )
    elif block == "revoked":
        g.record(g.service.decision(authorization).model_copy(update={"state": "revoked"}))
    elif block == "scope":
        g.record(g.scope)
    actor = g.educator.id if block == "executor" else g.admin.id
    with pytest.raises((GovernanceDenied, GovernanceConflict)):
        execute(
            g.service,
            actor,
            g.study,
            DisposalExecute(authorization_id=authorization.id, request_key="blocked"),
        )
    assert g.session.scalar(
        select(RestrictedInstrumentEvidence.id).where(
            RestrictedInstrumentEvidence.record_id == response.id
        )
    )
    assert not any(row.kind == "disposal_execution" for row in g.service.events(g.study))


def test_disposal_rejects_forged_receipt_and_unscoped_inventory(study):
    g = study
    _, _, manifest, authorization = prepare(g)
    with pytest.raises(GovernanceDenied, match="route_required"):
        g.record(
            DisposalExecution(
                scope_id=g.scope_event.id,
                authorization_id=authorization.id,
                manifest_digest=manifest["manifest_digest"],
                records=manifest["records"],
            )
        )
    with pytest.raises(GovernanceDenied, match="scope"):
        inventory(g.service, g.study, ["unknown-record"])
    with pytest.raises(GovernanceDenied, match="custodian"):
        custodian(g.service, g.educator.id)
    with pytest.raises(Exception, match="immutable"):
        g.session.execute(text("DELETE FROM restricted_instrument_evidence"))
    g.session.rollback()


@pytest.mark.parametrize("study", ["operational"], indirect=True)
def test_migration_guard_allows_only_exact_audit_and_restore_stays_ineligible(study):
    g = study
    response, _, _, authorization = prepare(g)
    original = g.session.scalar(select(RestrictedInstrumentEvidence))
    restored = dict(
        id=original.id,
        record_id=original.record_id,
        response_text=original.response_text,
        content_digest=original.content_digest,
    )
    path = Path(__file__).parents[1] / "migrations/versions/20260911_0053_research_disposal.py"
    spec = spec_from_file_location("research_disposal_migration", path)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    with Operations.context(MigrationContext.configure(g.session.connection())):
        migration.downgrade()
        migration.upgrade()
    g.session.commit()
    execute(
        g.service,
        g.admin.id,
        g.study,
        DisposalExecute(authorization_id=authorization.id, request_key="migration-disposal"),
    )
    g.session.add(RestrictedInstrumentEvidence(**restored))
    g.session.commit()
    with pytest.raises(GovernanceDenied, match="disposed"):
        g.instruments.read(g.educator.id, g.study, g.course.id, response.id, BASE_FIELDS)
    from app.schemas.research_operational import OperationalSelection
    from app.services.research.operational import OperationalCollector

    with pytest.raises(GovernanceDenied, match="disposed"):
        OperationalCollector(g.workflow).preview(
            g.educator.id,
            g.study,
            g.course.id,
            OperationalSelection(
                allocation_id=g.allocation.id,
                instrument_record_id=response.id,
                fields=["operational.latency_ms"],
            ),
        )


def test_disposal_routes_require_admin_csrf_and_separate_authorization(study):
    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.core.security import hash_password
    from app.db.session import create_session_factory, get_db_session
    from app.main import create_app

    g = study
    response, _, _, authorization = prepare(g)
    for user in (g.educator, g.admin):
        user.email = f"disposal-{user.id}@example.com"
        user.password_hash = hash_password("synthetic-password")
    g.session.commit()
    factory = create_session_factory(g.session.get_bind())

    def database():
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = database
    base = f"/api/v1/research/governance/{g.study}/disposal"
    with TestClient(app) as client:
        assert client.post(base + "/preview", json={"record_ids": [response.id]}).status_code == 401
        for user in (g.educator, g.admin):
            assert (
                client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": user.email,
                        "password": "synthetic-password",
                    },
                ).status_code
                == 200
            )
            headers = {
                settings.csrf_header_name: client.cookies.get(settings.csrf_cookie_name),
                "Origin": settings.frontend_origin,
            }
            preview = client.post(
                base + "/preview", json={"record_ids": [response.id]}, headers=headers
            )
            if user == g.educator:
                assert preview.status_code == 403
                continue
            assert preview.status_code == 200, preview.text
            assert preview.headers["cache-control"] == "no-store"
            command = {"authorization_id": authorization.id, "request_key": "api-disposal"}
            assert client.post(base + "/execute", json=command).status_code == 403
            result = client.post(base + "/execute", json=command, headers=headers)
            assert result.status_code == 200, result.text
            assert result.headers["cache-control"] == "no-store"
            assert result.json()["disposed_count"] == 1
