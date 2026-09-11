"""Synthetic-only operational provenance, redaction, missingness and export regressions."""

import json
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update
from test_research_governance import governed as governed
from test_research_instruments import instruments as instruments
from test_research_instruments import linked_operational_response
from test_research_study import study as study

from app.models.enums import FeedbackStatus, WorkflowOutcome, WorkflowStage
from app.models.lms import SubmissionAttempt
from app.models.persistence import FeedbackRecord, WorkflowRun
from app.models.provider_usage import ProviderUsage
from app.models.research_study import ResearchStudyEvent
from app.schemas.research_governance import OPERATIONAL_FIELDS
from app.schemas.research_operational import OperationalCapture, OperationalSelection
from app.schemas.research_study import StudyExportRequest, StudySelfResponse
from app.services.provider_usage import MeteringPolicy, ProviderUsageMeter
from app.services.research.governance import GovernanceDenied
from app.services.research.operational import OperationalCollector

pytestmark = pytest.mark.parametrize("study", ["operational"], indirect=True)


@pytest.fixture
def operational(study, request):
    g = study
    outcome, task, draft, first = linked_operational_response(g)
    form = None
    if getattr(request, "param", None) == "moderation":
        from support.assessment import _assessment_versions, _definition_version

        definition, version = _definition_version(g.session, g.educator, g.course, outcome)
        bloom, _, rule, form = _assessment_versions(
            g.session, g.educator, g.course, task, definition, version
        )
        g.moderation_versions = (version, bloom, rule, form)
    g.response = SubmissionAttempt(
        draft_id=draft.id,
        student_id=g.student.id,
        task_id=task.id,
        attempt_number=2,
        status=first.status,
        answer=f"{g.student.full_name} {g.student.email}\nExplanation remains.",
        code="x = 1\npassword = 'do-not-export'\nprint(x)\n",
        feedback="Recorded",
        submitted_at=g.now,
        task_form_version_id=form.id if form else None,
    )
    g.session.add(g.response)
    g.session.flush()
    g.workflow_row = WorkflowRun(
        submission_id=g.response.id,
        course_id=g.course.id,
        task_id=task.id,
        current_stage=WorkflowStage.COMPLETED,
        final_outcome=WorkflowOutcome.SAFE_FALLBACK,
        completed_at=g.now + timedelta(seconds=1),
        started_at=g.now,
        latency_ms=23,
    )
    g.session.add(g.workflow_row)
    g.session.flush()
    g.feedback_row = FeedbackRecord(
        submission_id=g.response.id,
        workflow_run_id=g.workflow_row.id,
        feedback_content={
            "summary": "Safe feedback student@example.invalid",
            "nested": "https://host.invalid/path?api_key=do-not-export",
        },
        status=FeedbackStatus.SAFE_FALLBACK,
        generation_attempt=None,
        source_references=["https://source.invalid/path?secret=never"],
        simulation_references=[],
        usage_complete=False,
        created_at=g.now,
    )
    g.session.add(g.feedback_row)
    g.session.commit()
    g.instrument = g.workflow.submit_self(
        g.student.id,
        g.study,
        g.course.id,
        StudySelfResponse(
            allocation_id=g.allocation.id,
            record=g.command.model_copy(
                update={
                    "links": g.command.links.model_copy(
                        update={
                            "outcome_id": outcome.id,
                            "task_id": task.id,
                            "response_id": g.response.id,
                        }
                    )
                }
            ),
        ),
    )
    g.collector = OperationalCollector(g.workflow)
    g.selection = OperationalSelection(
        allocation_id=g.allocation.id,
        instrument_record_id=g.instrument.id,
        fields=sorted(OPERATIONAL_FIELDS),
    )
    return g


def capture(g, fields, redactions=None, revision=0, key="capture"):
    return g.collector.capture(
        g.educator.id,
        g.study,
        g.course.id,
        OperationalCapture(
            allocation_id=g.allocation.id,
            instrument_record_id=g.instrument.id,
            fields=fields,
            redactions=redactions or [],
            expected_revision=revision,
            request_key=key,
        ),
    )


def test_preview_exact_lineage_missingness_and_no_raw_prose(operational):
    g = operational
    fields = g.collector.preview(g.educator.id, g.study, g.course.id, g.selection).fields
    assert set(fields) == OPERATIONAL_FIELDS
    assert fields["operational.latency_ms"].value == 23
    assert fields["operational.code"].missing_reason == "redaction_required"
    assert fields["operational.actual_cost"].missing_reason == "not_recorded"
    assert fields["operational.moderation"].missing_reason == "not_recorded"
    assert fields["operational.evidence"].missing_reason == "not_recorded"
    tokens = fields["operational.input_tokens"].value
    assert tokens[0]["value"] is None and tokens[0]["missing_reason"] == "usage_incomplete"
    assert "do-not-export" not in json.dumps({k: v.model_dump() for k, v in fields.items()})
    assert "source.invalid" not in json.dumps(fields["operational.source_references"].value)


def test_raw_fields_require_digest_bound_review_and_preserve_code_lines(operational):
    g = operational
    fields = ["operational.code", "operational.response_text", "operational.ai_output"]
    with pytest.raises(GovernanceDenied, match="redaction_required"):
        capture(g, fields)
    preview = g.collector.preview(g.educator.id, g.study, g.course.id, g.selection).fields
    approvals = [
        {
            "field": f,
            "source_digest": preview[f].source_digest,
            "rule_reference": "synthetic-rule",
            "review_evidence_reference": "synthetic-only-not-human-approval",
            "spans": [],
        }
        for f in fields
    ]
    receipt = capture(g, fields, approvals)
    projected = g.collector.read(g.educator.id, g.study, g.course.id, receipt.id, fields)
    assert projected["operational.code"]["value"] == "x = 1\n[REDACTED]\nprint(x)\n"
    output = json.dumps(projected)
    assert (
        "do-not-export" not in output
        and "example.invalid" not in output
        and "host.invalid" not in output
    )
    row = g.session.get(ResearchStudyEvent, receipt.id)
    assert "print(x)" not in json.dumps(row.data) and "Explanation remains" not in json.dumps(
        row.data
    )
    approvals[0]["source_digest"] = "sha256:" + "0" * 64
    with pytest.raises(GovernanceDenied, match="redaction_stale"):
        capture(g, fields, approvals, revision=1, key="stale")


@pytest.mark.parametrize("change", ["grant", "consent", "withdrawn", "reconsent", "scope"])
def test_materialization_rechecks_all_authority(operational, change):
    g = operational
    fields = ["operational.latency_ms"]
    receipt = capture(g, fields)
    if change == "grant":
        g.record(
            g.grant.model_copy(update={"fields": [f for f in g.grant.fields if f not in fields]})
        )
    elif change == "consent":
        g.record(
            g.consent.model_copy(
                update={"fields": [f for f in g.consent.fields if f not in fields]}
            ),
            g.student.id,
        )
    elif change in {"withdrawn", "reconsent"}:
        g.record(g.consent.model_copy(update={"decision": "withdrawn"}), g.student.id)
        if change == "reconsent":
            g.record(g.consent, g.student.id)
    else:
        g.record(g.scope)
    with pytest.raises(GovernanceDenied):
        g.collector.read(g.educator.id, g.study, g.course.id, receipt.id, fields)


def test_source_changed_after_capture_and_during_stream_denies(operational):
    g = operational
    receipt = capture(g, ["operational.latency_ms"])
    command = StudyExportRequest(
        format="json", fields=["study.stage", "operational.latency_ms"], stages=["T0_BASELINE"]
    )
    exported = g.workflow.export(g.educator.id, g.study, g.course.id, command)
    next(exported.body)
    from sqlalchemy.orm import Session

    with Session(g.session.get_bind()) as other:
        other.execute(
            update(WorkflowRun).where(WorkflowRun.id == g.workflow_row.id).values(latency_ms=99)
        )
        other.commit()
    with pytest.raises(GovernanceDenied, match="source_changed"):
        g.collector.read(
            g.educator.id, g.study, g.course.id, receipt.id, ["operational.latency_ms"]
        )
    with pytest.raises(GovernanceDenied, match="source_changed"):
        b"".join(exported.body)


@pytest.mark.parametrize("format", ["json", "csv"])
def test_full_export_contains_only_selected_operational_cells(operational, format):
    g = operational
    capture(g, ["operational.latency_ms", "operational.evidence"])
    body = b"".join(
        g.workflow.export(
            g.educator.id,
            g.study,
            g.course.id,
            StudyExportRequest(
                format=format,
                fields=[
                    "operational.latency_ms",
                    "operational.evidence",
                    "study.condition",
                    "study.stage",
                ],
                stages=["T0_BASELINE"],
            ),
        ).body
    ).decode()
    assert "23" in body and "not_recorded" in body and "condition_a" in body
    assert "operational.code" not in body and "example.invalid" not in body
    if format == "json":
        snapshot = next(r for r in json.loads(body)["records"] if "operational.latency_ms" in r)
        assert snapshot["study.stage"] == "T0_BASELINE"
        assert snapshot["operational.latency_ms"]["value"] == 23


def test_unselected_field_and_forged_instrument_anchor_denied(operational):
    g = operational
    receipt = capture(g, ["operational.latency_ms"])
    with pytest.raises(GovernanceDenied, match="not_captured"):
        g.collector.read(g.educator.id, g.study, g.course.id, receipt.id, ["operational.code"])
    with pytest.raises(GovernanceDenied, match="anchor"):
        g.collector.preview(
            g.educator.id,
            g.study,
            g.course.id,
            g.selection.model_copy(update={"instrument_record_id": "foreign"}),
        )
    with pytest.raises(GovernanceDenied):
        g.collector.preview(g.admin.id, g.study, g.course.id, g.selection)


def test_optional_provider_adapter_exact_join_null_actual_and_source_drift(operational):
    g = operational
    meter = ProviderUsageMeter(
        g.session.get_bind(),
        MeteringPolicy(
            budget_id="synthetic-research-budget",
            currency="AUD",
            policy_version="synthetic-budget-v1",
            limit=Decimal("1"),
            pricing_version="synthetic-pricing-v1",
            input_rate=Decimal("2"),
            output_rate=Decimal("2"),
            max_input_tokens=2048,
            max_output_tokens=100,
        ),
    )
    exact = {
        "context": {
            "submission_id": g.response.id,
            "course_id": g.course.id,
            "task_id": g.response.task_id,
        },
        "currency": "AUD",
    }
    # The real meter commits independently, just as it does around provider dispatch.
    g.session.commit()
    for key, context in (
        ("correct", exact["context"]),
        ("foreign-response", {**exact["context"], "submission_id": "other"}),
        ("foreign-course", {**exact["context"], "course_id": "other"}),
        ("foreign-task", {**exact["context"], "task_id": "other"}),
    ):
        meter.reserve(key, {"input": "Synthetic request"}, {**exact, "context": context})
        meter.dispatch(key)
        meter.observe(key, input_tokens=7 if key == "correct" else 900, output_tokens=3)
    row = g.session.get(ProviderUsage, "correct")
    assert row.state == "OBSERVED" and row.actual_micros is None
    assert row.estimated_micros == 20
    g.session.commit()
    fields = ["operational.actual_cost", "operational.estimated_cost", "operational.input_tokens"]
    receipt = capture(g, fields)
    projected = g.collector.read(g.educator.id, g.study, g.course.id, receipt.id, fields)
    assert projected[fields[0]]["value"][0]["value"] is None
    assert projected[fields[0]]["value"][0]["missing_reason"] == "not_recorded"
    assert projected[fields[0]]["value"][0]["currency"] == "AUD"
    assert projected[fields[1]]["value"][0]["value"] == 20
    assert projected[fields[2]]["value"][0]["value"] == 7
    assert len(projected[fields[2]]["value"]) == 1
    g.session.commit()
    meter.reconcile(
        "correct",
        actual=Decimal("0.000012"),
        currency="AUD",
        receipt_id="synthetic-billing-receipt",
        actor="synthetic-operator",
    )
    g.session.expire_all()
    assert g.session.get(ProviderUsage, "correct").actual_micros == 12
    with pytest.raises(GovernanceDenied, match="source_changed"):
        g.collector.read(g.educator.id, g.study, g.course.id, receipt.id, fields)


@pytest.mark.parametrize("operational", ["moderation"], indirect=True)
def test_moderation_adapter_exact_response_join_preserves_cycles_and_detects_append(operational):
    from app.models.assessment import AssessmentAttempt
    from app.models.assessment_moderation import (
        ModerationPolicy,
        ModerationReview,
        ModerationSelection,
    )

    g = operational
    version, bloom, rule, form = g.moderation_versions
    foreign = SubmissionAttempt(
        draft_id=g.response.draft_id,
        student_id=g.student.id,
        task_id=g.response.task_id,
        attempt_number=3,
        status=g.response.status,
        answer="Another synthetic response in the same course and task",
        feedback="Recorded",
        task_form_version_id=form.id,
        submitted_at=g.now,
    )
    g.session.add(foreign)
    g.session.flush()
    attempts = [
        AssessmentAttempt(
            course_id=g.course.id,
            student_id=g.student.id,
            task_id=g.response.task_id,
            response_version_id=response.id,
            assessment_definition_version_id=version.id,
            task_form_version_id=form.id,
            bloom_target_version_id=bloom.id,
            pass_rule_version_id=rule.id,
            created_at=g.now,
        )
        for response in (g.response, foreign)
    ]
    policy = ModerationPolicy(
        course_id=g.course.id,
        version=1,
        initial_count=2,
        later_percent=0,
        drift_interval=10,
        approval_reference="synthetic-policy-only",
        training_reference="synthetic-training-only",
        actor_id=g.educator.id,
        expires_at=g.now + timedelta(days=1),
        created_at=g.now,
    )
    g.session.add_all([policy, *attempts])
    g.session.flush()
    g.session.add_all(
        ModerationSelection(
            attempt_id=attempt.id,
            policy_id=policy.id,
            task_family=form.task_family,
            sequence=index + 1,
            selected=True,
            drift_check=False,
            created_at=g.now,
        )
        for index, attempt in enumerate(attempts)
    )
    g.session.flush()

    def review(attempt, cycle, stage, result):
        # Synthetic persisted source records exercise the adapter, not assessor approval.
        return ModerationReview(
            attempt_id=attempt.id,
            cycle=cycle,
            stage=stage,
            actor_id=g.educator.id if stage == "ORIGINAL" else g.reviewer.id,
            result=result,
            reason="Synthetic private judgement student@example.invalid",
            criteria=[{"reason": "do-not-export"}],
            request_key=f"synthetic-{cycle}-{stage}",
            request_digest="a" * 64,
            created_at=g.now,
        )

    g.session.add_all(
        [
            review(attempts[0], 1, "ORIGINAL", "INCOMPLETE"),
            review(attempts[0], 1, "SECOND", "INCOMPLETE"),
            review(attempts[0], 2, "ORIGINAL", "PASS"),
            review(attempts[0], 2, "SECOND", "PASS"),
            review(attempts[1], 9, "ORIGINAL", "PASS"),
        ]
    )
    g.session.commit()
    fields = ["operational.moderation"]
    receipt = capture(g, fields)
    cell = g.collector.read(g.educator.id, g.study, g.course.id, receipt.id, fields)[fields[0]]
    assert cell["adapter_version"] == "learnlens.assessment-moderation.v1"
    assert cell["missing_reason"] is None
    assert {(row["cycle"], row["stage"], row["result"]) for row in cell["value"]} == {
        (1, "ORIGINAL", "INCOMPLETE"),
        (1, "SECOND", "INCOMPLETE"),
        (2, "ORIGINAL", "PASS"),
        (2, "SECOND", "PASS"),
    }
    assert len(cell["value"]) == 4
    assert len({row["attempt_reference"] for row in cell["value"]}) == 1
    encoded = json.dumps(cell)
    assert all(
        value not in encoded
        for value in (attempts[0].id, attempts[1].id, "do-not-export", "example.invalid")
    )
    g.session.add(review(attempts[0], 3, "ORIGINAL", "INCOMPLETE"))
    g.session.commit()
    with pytest.raises(GovernanceDenied, match="source_changed"):
        g.collector.read(g.educator.id, g.study, g.course.id, receipt.id, fields)


def test_evidence_adaptation_and_simulation_are_exact_typed_records(operational):
    from app.domain.platform_enums import (
        AccessSupportState,
        EvidenceProvenance,
        EvidenceType,
        ObservationType,
    )
    from app.models.activity_continuation import (
        ActivityChoice,
        ActivityProgress,
        ActivitySuggestion,
    )
    from app.models.learning_evidence import LearningEvidence
    from app.models.simulation import CircuitVersion, SimulationOutcome, SimulationRun

    g = operational
    task = g.response.task_id
    from app.models.research_instruments import ResearchInstrumentRecord

    instrument = g.session.get(ResearchInstrumentRecord, g.instrument.id)
    evidence = LearningEvidence(
        course_id=g.course.id,
        learner_id=g.student.id,
        outcome_id=instrument.links["outcome_id"],
        activity_id=task,
        task_id=task,
        response_version_id=g.response.id,
        evidence_type=EvidenceType.RESPONSE,
        provenance=EvidenceProvenance.LEARNER,
        observation_type=ObservationType.DIRECT,
        instructional_support_level=4,
        access_support_state=AccessSupportState.NOT_DECLARED,
        content_digest="sha256:" + "a" * 64,
        actor_reference=str(g.student.id),
        correlation_id="synthetic",
        schema_version="evidence-v1",
        record_version=1,
        idempotency_key="synthetic",
        occurred_at=g.now,
    )
    g.session.add(evidence)
    g.session.flush()
    g.session.add(
        ActivityProgress(
            workflow_id=g.workflow_row.id,
            learner_id=g.student.id,
            course_id=g.course.id,
            outcome_id=instrument.links["outcome_id"],
            state="observations_recorded",
            evidence_ids=[evidence.id],
        )
    )
    g.session.flush()
    g.session.add(
        ActivitySuggestion(
            workflow_id=g.workflow_row.id,
            task_id=task,
            decision={
                "state": "suggested",
                "rule_version": "rule-v1",
                "reason": "Synthetic reasoning",
            },
        )
    )
    g.session.flush()
    g.session.add(
        ActivityChoice(
            workflow_id=g.workflow_row.id,
            actor_id=g.student.id,
            version=1,
            request_key="choice",
            payload={"action": "defer", "selected_task_id": None},
        )
    )
    g.session.add(
        CircuitVersion(
            id="synthetic-circuit",
            owner_id=g.student.id,
            task_id=task,
            course_id=g.course.id,
            content_digest="a" * 64,
            circuit={"qubits": 1, "gates": []},
        )
    )
    g.session.flush()
    g.session.add(
        SimulationRun(
            id="synthetic-run",
            owner_id=g.student.id,
            request_key="run",
            circuit_version_id="synthetic-circuit",
            submission_id=g.response.id,
            purpose="feedback",
            shots=10,
            seed=1,
            policy_version="sim-v1",
            engine_versions={"aer": "1.0"},
            deadline_at=g.now + timedelta(seconds=30),
        )
    )
    g.session.flush()
    g.session.add(
        SimulationOutcome(
            id="synthetic-run",
            status="completed",
            result={"counts": {"0": 7, "1": 3, "student@example.invalid": 99}, "private": "secret"},
        )
    )
    g.session.commit()
    fields = ["operational.evidence", "operational.adaptations", "operational.simulation"]
    receipt = capture(g, fields)
    projected = g.collector.read(g.educator.id, g.study, g.course.id, receipt.id, fields)
    assert projected[fields[0]]["value"][0]["instructional_support_level"] == 4
    assert projected[fields[1]]["value"][0]["decision"]["rule_version"] == "rule-v1"
    assert projected[fields[2]]["value"][0]["counts"] == {"0": 7, "1": 3}
    assert "example.invalid" not in json.dumps(projected)


def test_operational_api_requires_auth_csrf_and_exact_field_selection(operational):
    from fastapi.testclient import TestClient

    from app.core.config import settings
    from app.core.security import hash_password
    from app.db.session import create_session_factory, get_db_session
    from app.main import create_app

    g = operational
    g.educator.email = "operational-api@example.com"
    g.educator.password_hash = hash_password("synthetic-password")
    g.session.commit()
    factory = create_session_factory(g.session.get_bind())

    def database():
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = database
    base = f"/api/v1/research/instruments/{g.study}/{g.course.id}/study/operational"
    body = {**g.selection.model_dump(mode="json"), "fields": ["operational.latency_ms"]}
    with TestClient(app) as client:
        assert client.post(base + "/preview", json=body).status_code == 401
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": g.educator.email, "password": "synthetic-password"},
            ).status_code
            == 200
        )
        assert client.post(base + "/preview", json=body).status_code == 403
        headers = {
            settings.csrf_header_name: client.cookies.get(settings.csrf_cookie_name),
            "Origin": settings.frontend_origin,
        }
        preview = client.post(base + "/preview", json=body, headers=headers)
        assert preview.status_code == 200, preview.text
        assert preview.headers["cache-control"] == "no-store"
        saved = client.post(
            base + "/snapshots",
            json={**body, "request_key": "api-snapshot", "expected_revision": 0},
            headers=headers,
        )
        assert saved.status_code == 201, saved.text
        read = client.get(
            base + "/snapshots/" + saved.json()["id"], params={"fields": "operational.latency_ms"}
        )
        assert read.status_code == 200 and read.json()["operational.latency_ms"]["value"] == 23
        assert (
            client.get(
                "/api/v1/research/exports", params={"fields": "operational.code"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                base + "/preview", json={**body, "fields": ["subject_user_id"]}, headers=headers
            ).status_code
            == 422
        )
