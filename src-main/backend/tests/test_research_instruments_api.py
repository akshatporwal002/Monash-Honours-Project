"""Mounted authentication, CSRF, typed field and closed research boundaries."""

from fastapi.testclient import TestClient
from test_research_governance import governed as governed
from test_research_instruments import instruments as instruments

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import create_session_factory, get_db_session
from app.main import create_app
from app.services.research import governance


def test_instrument_api_authentication_fields_and_closed_gate(instruments, monkeypatch):
    g = instruments
    g.educator.email = "synthetic-instrument-educator@example.com"
    g.educator.password_hash = hash_password("synthetic-fixture-passphrase")
    g.admin.email = "synthetic-instrument-admin@example.com"
    g.admin.password_hash = hash_password("synthetic-fixture-passphrase")
    g.session.commit()
    factory = create_session_factory(g.session.get_bind())

    def database():
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = database
    base = f"/api/v1/research/instruments/{g.study}/{g.course.id}"
    with TestClient(app) as client:
        assert client.get(f"{base}/forms/{g.form.id}").status_code == 401
        login = client.post(
            "/api/v1/auth/login",
            json={"email": g.educator.email, "password": "synthetic-fixture-passphrase"},
        )
        assert login.status_code == 200, login.text
        headers = {
            settings.csrf_header_name: client.cookies.get(settings.csrf_cookie_name),
            "Origin": settings.frontend_origin,
        }
        read = client.get(f"{base}/forms/{g.form.id}")
        assert read.status_code == 200 and read.json()["production_active"] is False
        assert read.headers["cache-control"] == "no-store"
        assert (
            client.post(f"{base}/records", json=g.command.model_dump(mode="json")).status_code
            == 403
        )
        accepted = client.post(
            f"{base}/records", json=g.command.model_dump(mode="json"), headers=headers
        )
        assert accepted.status_code == 201, accepted.text
        identity = accepted.json()["id"]
        rows = client.get(
            f"{base}/records/{identity}", params={"fields": "instrument.integer_value"}
        )
        assert rows.status_code == 200 and all(
            set(row) == {"instrument.integer_value"} for row in rows.json()
        )
        for field in ("instrument.response_text", "subject_user_id", "*"):
            denied = client.get(f"{base}/records/{identity}", params={"fields": field})
            assert denied.status_code == 422
        assert (
            client.get(
                "/api/v1/research/exports", params={"fields": "instrument.stage"}
            ).status_code
            == 422
        )
        export_payload = {
            "fields": ["instrument.integer_value"],
            "stages": ["T0_BASELINE"],
            "format": "json",
        }
        for format in ("csv", "json"):
            exported = client.post(
                f"{base}/exports",
                json={**export_payload, "format": format},
                headers=headers,
            )
            assert exported.status_code == 200, exported.text
            assert exported.headers["cache-control"] == "no-store"
            assert exported.headers["x-research-export-id"]
            assert "example.invalid" not in exported.text and "HYPERLINK" not in exported.text
            if format == "json":
                assert exported.json()["records"] == rows.json()
            else:
                assert exported.text.splitlines()[0] == '"instrument.integer_value"'
        monkeypatch.setattr(governance, "research_processing_approved", lambda: False)
        assert (
            client.post(f"{base}/exports", json=export_payload, headers=headers).status_code == 403
        )
        assert (
            client.post(
                f"{base}/records", json=g.command.model_dump(mode="json"), headers=headers
            ).status_code
            == 403
        )
        assert (
            client.get(
                f"{base}/records/{identity}", params={"fields": "instrument.stage"}
            ).status_code
            == 403
        )
        login = client.post(
            "/api/v1/auth/login",
            json={"email": g.admin.email, "password": "synthetic-fixture-passphrase"},
        )
        assert login.status_code == 200
        headers = {
            settings.csrf_header_name: client.cookies.get(settings.csrf_cookie_name),
            "Origin": settings.frontend_origin,
        }
        prepared = client.post(
            f"/api/v1/research/governance/{g.study}/decisions",
            headers=headers,
            json={
                "request_key": "synthetic-api-governance",
                "expected_revision": g.service.events(g.study)[-1].revision,
                "reason": "synthetic-only",
                "decision": g.grant.model_dump(mode="json"),
            },
        )
        assert prepared.status_code == 201, prepared.text
        assert prepared.json()["production_active"] is False
