"""Synthetic workflow tests; no institutional or participant approval evidence."""

import json
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from test_research_governance import governed as governed
from test_research_instruments import instruments as instruments

from app.models.research_study import ResearchStudyEvent
from app.models.user import RoleAssignment, ScopedRole, User, UserRole
from app.schemas.research_governance import PROCESSING_FIELDS, STUDY_FIELDS
from app.schemas.research_study import StudyCommand, StudyExportRequest, StudySelfResponse
from app.services.research import governance
from app.services.research.governance import GovernanceConflict, GovernanceDenied
from app.services.research.study import ResearchStudyService


@pytest.fixture
def study(instruments, request):
    g = instruments
    if getattr(request, "param", None) == "operational":
        from app.schemas.research_governance import OPERATIONAL_FIELDS

        g.scope = g.scope.model_copy(
            update={
                "fields": sorted(
                    set(g.scope.fields)
                    | OPERATIONAL_FIELDS
                    | {"operational.collect", "operational.read", "operational.export"}
                ),
                "purposes": [*g.scope.purposes, "study_operational_evidence"],
                "retention": [
                    *g.scope.retention,
                    g.scope.retention[0].model_copy(
                        update={"record_class": "study_operational_manifests"}
                    ),
                ],
            }
        )
    g.scope = g.scope.model_copy(
        update={
            "fields": sorted(set(g.scope.fields) | STUDY_FIELDS),
            "retention": [
                *g.scope.retention,
                *[
                    g.scope.retention[0].model_copy(update={"record_class": c})
                    for c in ("study_workflows", "study_reviewer_packets")
                ],
            ],
        }
    )
    g.scope_event = g.record(g.scope)
    g.approval = g.approval.model_copy(update={"scope_id": g.scope_event.id})
    g.record(g.approval)
    g.consent = g.consent.model_copy(
        update={
            "scope_id": g.scope_event.id,
            "fields": g.scope.fields,
            "purposes": g.scope.purposes,
        }
    )
    g.record(g.consent, g.student.id)
    g.eligibility = g.eligibility.model_copy(update={"scope_id": g.scope_event.id})
    g.record(g.eligibility)
    g.grant = g.grant.model_copy(update={"scope_id": g.scope_event.id, "fields": g.scope.fields})
    g.record(g.grant)
    g.form = g.instruments.save_form(
        g.educator.id,
        g.study,
        g.course.id,
        "synthetic_form",
        g.form_command.model_copy(update={"request_key": "study-form", "expected_version": 1}),
    )
    g.instruments.freeze_form(
        g.educator.id,
        g.study,
        g.course.id,
        g.form.id,
        g.freeze.model_copy(
            update={"request_key": "study-freeze", "content_digest": g.form.content_digest}
        ),
    )
    g.command = g.command.model_copy(update={"form_version_id": g.form.id})
    g.reviewer = User(
        email="reviewer@example.invalid",
        full_name="Synthetic reviewer",
        password_hash="unused",
        role=UserRole.EDUCATOR,
        is_active=True,
    )
    g.session.add(g.reviewer)
    g.session.flush()
    g.session.add(
        RoleAssignment(
            subject_user_id=g.reviewer.id,
            course_id=g.course.id,
            role=ScopedRole.RESEARCH,
            version=1,
            assigned_by_user_id=g.admin.id,
            reason="Synthetic only",
            assigned_at=g.now,
            valid_from=g.scope.valid_from,
        )
    )
    g.session.commit()
    g.record(g.grant.model_copy(update={"subject_user_id": g.reviewer.id}))
    g.workflow = ResearchStudyService(g.session, now=lambda: g.now)

    def record(kind, actor=None, key=None, **data):
        return g.workflow.record(
            actor or g.educator.id,
            g.study,
            g.course.id,
            StudyCommand(request_key=key or str(uuid4()), decision={"kind": kind, **data}),
        )

    g.write = record
    g.plan_data = dict(
        expected_revision=0,
        authority_reference="synthetic-not-approval",
        evidence_reference="synthetic-not-approval",
        allocation_rule_reference="synthetic-rule",
        redaction_rule_reference="synthetic-rule",
        conditions=["condition_a", "condition_b"],
        stages=[
            {"stage": "T0_BASELINE", "form_id": g.form.id},
            {"stage": "T2_TRANSFER", "form_id": g.form.id},
        ],
        rubrics=[
            {
                "code": "synthetic_rubric",
                "wording": "Synthetic review only",
                "values": ["observed", "not_observed"],
            }
        ],
    )
    g.plan = g.write("plan", **g.plan_data)
    g.allocation = g.write(
        "allocation",
        subject_user_id=g.student.id,
        plan_id=g.plan.id,
        sequence_key="synthetic-sequence",
        condition="condition_a",
        allocation_evidence_reference="synthetic-only",
    )
    return g


def pipeline(g):
    response = g.workflow.submit_self(
        g.student.id,
        g.study,
        g.course.id,
        StudySelfResponse(allocation_id=g.allocation.id, record=g.command),
    )
    packet = g.write(
        "packet",
        allocation_id=g.allocation.id,
        instrument_record_id=response.id,
        reviewer_user_id=g.reviewer.id,
        rubric_code="synthetic_rubric",
        redacted_evidence="Synthetic redacted evidence",
        redaction_evidence_reference="synthetic-only",
    )
    rating = g.write("rating", actor=g.reviewer.id, packet_id=packet.id, value_code="observed")
    outcome = g.write(
        "outcome",
        packet_id=packet.id,
        rating_id=rating.id,
        value_code="observed",
        interpretation_reference="synthetic-only",
    )
    return response, packet, rating, outcome


def test_self_collection_blinded_packet_and_stage_linked_outcome(study):
    g = study
    forms = g.workflow.participant_forms(g.student.id, g.study, g.course.id)
    assert forms[0]["allocation_id"] == g.allocation.id
    assert "condition" not in json.dumps(forms)
    response, packet, rating, outcome = pipeline(g)
    blinded = g.workflow.packet(g.reviewer.id, g.study, g.course.id, packet.id).model_dump()
    assert set(blinded) == {"id", "stage", "rubric", "redacted_evidence", "production_active"}
    assert blinded["stage"] == "T0_BASELINE"
    row = g.session.get(ResearchStudyEvent, outcome.id)
    assert row.data["instrument_record_id"] == response.id
    assert row.data["rating_id"] == rating.id
    assert not (STUDY_FIELDS & PROCESSING_FIELDS)


@pytest.mark.parametrize("change", ["actor", "subject", "stage", "form"])
def test_self_assignment_denial(study, change):
    g = study
    actor = g.admin.id if change == "actor" else g.student.id
    record = g.command.model_copy(
        update={"subject_user_id": g.admin.id}
        if change == "subject"
        else {"stage": "T2_CONCEPTUAL"}
        if change == "stage"
        else {"form_version_id": "unknown"}
        if change == "form"
        else {}
    )
    with pytest.raises(GovernanceDenied):
        g.workflow.submit_self(
            actor,
            g.study,
            g.course.id,
            StudySelfResponse(allocation_id=g.allocation.id, record=record),
        )


def test_reviewer_assignment_and_rating_code_denied(study):
    g = study
    _, packet, _, _ = pipeline(g)
    with pytest.raises(GovernanceDenied, match="assignment"):
        g.workflow.packet(g.educator.id, g.study, g.course.id, packet.id)
    with pytest.raises(GovernanceDenied, match="assignment"):
        g.write("rating", packet_id=packet.id, value_code="observed")
    with pytest.raises(GovernanceDenied, match="rating_code"):
        g.write("rating", actor=g.reviewer.id, packet_id=packet.id, value_code="invented")


def test_packet_rejects_other_sequence(study):
    g = study
    response = g.instruments.collect(
        g.educator.id,
        g.study,
        g.course.id,
        g.command.model_copy(update={"sequence_key": "different"}),
    )
    with pytest.raises(GovernanceDenied, match="stage_link"):
        g.write(
            "packet",
            allocation_id=g.allocation.id,
            instrument_record_id=response.id,
            reviewer_user_id=g.reviewer.id,
            rubric_code="synthetic_rubric",
            redacted_evidence="Synthetic",
            redaction_evidence_reference="synthetic-only",
        )


@pytest.mark.parametrize("format", ["json", "csv"])
def test_full_export_projects_approved_fields_and_excludes_raw(study, format):
    g = study
    pipeline(g)
    prepared = g.workflow.export(
        g.educator.id,
        g.study,
        g.course.id,
        StudyExportRequest(
            format=format,
            fields=["study.record_kind", "study.value_code", "instrument.choice_code"],
            stages=["T0_BASELINE"],
        ),
    )
    body = b"".join(prepared.body).decode()
    assert "example.invalid" not in body and "redacted evidence" not in body
    assert "condition_a" not in body and "subject_user_id" not in body
    assert "observed" in body and "high" in body
    if format == "json":
        assert json.loads(body)["schema_version"] == "learnlens.full-study-export.v1"


@pytest.mark.parametrize("when", ["before", "stream", "reconsent"])
def test_withdrawal_excludes_or_interrupts_all_study_records(study, when):
    g = study
    _, packet, _, _ = pipeline(g)
    command = StudyExportRequest(
        format="json",
        fields=["study.record_kind", "instrument.choice_code"],
        stages=["T0_BASELINE"],
    )
    if when == "stream":
        prepared = g.workflow.export(g.educator.id, g.study, g.course.id, command)
        next(prepared.body)
    g.record(g.consent.model_copy(update={"decision": "withdrawn"}), g.student.id)
    if when == "reconsent":
        g.record(g.consent, g.student.id)
    with pytest.raises(GovernanceDenied):
        g.workflow.packet(g.reviewer.id, g.study, g.course.id, packet.id)
    if when == "stream":
        with pytest.raises(GovernanceDenied):
            next(prepared.body)
    else:
        body = b"".join(g.workflow.export(g.educator.id, g.study, g.course.id, command).body)
        assert json.loads(body)["records"] == []


def test_gate_and_research_grant_are_independent_of_admin(study, monkeypatch):
    g = study
    with pytest.raises(GovernanceDenied, match="grant"):
        g.workflow.read_plan(g.admin.id, g.study, g.course.id)
    monkeypatch.setattr(governance, "research_processing_approved", lambda: False)
    assert g.workflow.read_plan(g.educator.id, g.study, g.course.id)["production_active"] is False
    with pytest.raises(GovernanceDenied, match="pending"):
        g.workflow.participant_forms(g.student.id, g.study, g.course.id)


def test_plan_replacement_and_idempotency(study):
    g = study
    a = g.write("plan", key="replacement", **{**g.plan_data, "expected_revision": 1})
    assert g.write("plan", key="replacement", **{**g.plan_data, "expected_revision": 1}).id == a.id
    with pytest.raises(GovernanceConflict):
        g.write("plan", **g.plan_data)
    assert g.workflow.participant_forms(g.student.id, g.study, g.course.id) == []


def test_missing_outcomes_are_explicit_and_history_immutable(study):
    g = study
    _, packet, _, _ = pipeline(g)
    with pytest.raises(Exception, match="immutable"):
        g.session.execute(text("UPDATE research_study_events SET kind='rating'"))
        g.session.commit()
    g.session.rollback()
    assert (
        g.session.scalar(select(ResearchStudyEvent).where(ResearchStudyEvent.id == packet.id)).kind
        == "packet"
    )


def test_mounted_study_routes_auth_csrf_self_and_export_fields(study):
    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.core.security import hash_password
    from app.db.session import create_session_factory, get_db_session
    from app.main import create_app

    g = study
    for user in (g.student, g.educator):
        user.email = f"study-api-{user.id}@example.com"
        user.password_hash = hash_password("synthetic-password")
    g.session.commit()
    factory = create_session_factory(g.session.get_bind())

    def database():
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = database
    base = f"/api/v1/research/instruments/{g.study}/{g.course.id}/study"
    with TestClient(app) as client:
        assert client.get(base + "/my-forms").status_code == 401
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": g.student.email, "password": "synthetic-password"},
            ).status_code
            == 200
        )
        forms = client.get(base + "/my-forms")
        assert forms.status_code == 200, forms.text
        assert forms.headers["cache-control"] == "no-store"
        assert client.get(base + "/plan").status_code == 403
        assert client.get(base + "/reconciliation").status_code == 403
        body = {"allocation_id": g.allocation.id, "record": g.command.model_dump(mode="json")}
        assert client.post(base + "/my-responses", json=body).status_code == 403
        headers = {
            settings.csrf_header_name: client.cookies.get(settings.csrf_cookie_name),
            "Origin": settings.frontend_origin,
        }
        saved = client.post(base + "/my-responses", json=body, headers=headers)
        assert saved.status_code == 201, saved.text
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": g.educator.email, "password": "synthetic-password"},
            ).status_code
            == 200
        )
        headers[settings.csrf_header_name] = client.cookies.get(settings.csrf_cookie_name)
        assert client.get(base + "/plan").status_code == 200
        reconciled = client.get(base + "/reconciliation")
        assert reconciled.status_code == 200, reconciled.text
        assert reconciled.headers["cache-control"] == "no-store"
        assert reconciled.json()["rows"][0]["status"] == "response"
        payload = {
            "fields": ["study.condition", "instrument.stage"],
            "stages": ["T0_BASELINE"],
            "format": "json",
        }
        exported = client.post(base + "/exports", json=payload, headers=headers)
        assert exported.status_code == 200, exported.text
        assert exported.json()["schema_version"] == "learnlens.full-study-export.v1"
        for field in [
            "study.redacted_evidence",
            "instrument.response_text",
            "subject_user_id",
            "*",
        ]:
            assert (
                client.post(
                    base + "/exports", json={**payload, "fields": [field]}, headers=headers
                ).status_code
                == 422
            )
        assert (
            client.get("/api/v1/research/exports", params={"fields": "study.condition"}).status_code
            == 422
        )


def test_field_revocation_and_wrong_course_deny_export(study):
    g = study
    pipeline(g)
    command = StudyExportRequest(format="json", fields=["study.condition"], stages=["T0_BASELINE"])
    prepared = g.workflow.export(g.educator.id, g.study, g.course.id, command)
    next(prepared.body)
    g.record(
        g.grant.model_copy(update={"fields": [f for f in g.grant.fields if f != "study.condition"]})
    )
    with pytest.raises(GovernanceDenied, match="field_denied"):
        next(prepared.body)
    with pytest.raises(GovernanceDenied):
        g.workflow.export(g.educator.id, g.study, "wrong-course", command)


def test_corrected_instrument_invalidates_old_packet(study):
    g = study
    response, packet, _, _ = pipeline(g)
    g.workflow.submit_self(
        g.student.id,
        g.study,
        g.course.id,
        StudySelfResponse(
            allocation_id=g.allocation.id,
            record=g.command.model_copy(
                update={
                    "request_key": "correction",
                    "supersedes_id": response.id,
                    "correction_reason_code": "synthetic_correction",
                }
            ),
        ),
    )
    with pytest.raises(GovernanceDenied, match="superseded"):
        g.workflow.packet(g.reviewer.id, g.study, g.course.id, packet.id)


def test_study_migration_replay_and_populated_guard(study):
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = Path(__file__).parents[1] / "migrations/versions/20260911_0048_study_workflows.py"
    spec = importlib.util.spec_from_file_location("study_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with study.session.get_bind().begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            module.upgrade()
            with pytest.raises(RuntimeError, match="populated"):
                module.downgrade()


def test_researcher_status_uses_allocation_sequence_and_denies_student(study):
    g = study
    command = StudySelfResponse(
        allocation_id=g.allocation.id,
        record=g.command.model_copy(
            update={
                "kind": "missingness",
                "answers": [],
                "reason_code": "synthetic_fault",
                "missing_reason": "not_collected",
                "stage": "T2_TRANSFER",
            }
        ),
    )
    with pytest.raises(GovernanceDenied):
        g.workflow.submit_researcher(g.student.id, g.study, g.course.id, command)
    receipt = g.workflow.submit_researcher(g.educator.id, g.study, g.course.id, command)
    from app.models.research_instruments import ResearchInstrumentRecord

    row = g.session.get(ResearchInstrumentRecord, receipt.id)
    allocation = g.session.get(ResearchStudyEvent, g.allocation.id)
    assert row.sequence_id == allocation.data["sequence_id"]
    assert row.data["missing_reason"] == "not_collected"
