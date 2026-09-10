"""Real governed adapters with synthetic isolated records and explicit gate override."""

import asyncio
import json
from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import select
from test_research_baseline_worker import NOW, ContextProvider, Generator, Judge, Repository
from test_research_export_repository import _terminal_record
from test_research_governance import governed as governed

from app.models.research_governance import ResearchCaseGovernance, ResearchExportEligibility
from app.schemas.research_export import ResearchExportFilters, ResearchExportFormat
from app.services.research.governance import GovernanceDenied
from app.services.research.governed_export import GovernedResearchExportService
from app.services.research.worker import BaselineJobExecutor
from app.services.research_export import ResearchExportError


def export_fixture(g, *, bind=True):
    row = _terminal_record(generated_output={"summary": "SYNTHETIC-PROSE-MUST-NOT-EXPORT"})
    row.course_id = g.course.id
    row.created_at = g.now
    row.completed_at = g.now
    row.latency_ms = 42
    g.session.add(row)
    if bind:
        g.session.add(
            ResearchCaseGovernance(
                case_id=row.case_id,
                scope_id=g.scope_event.id,
                consent_id=g.consent_event.id,
                course_id=g.course.id,
                pseudonymous_user_id=row.pseudonymous_user_id,
            )
        )
    g.session.commit()
    return row


def prepare(g, *, fields=("case_id", "latency_ms"), format=ResearchExportFormat.JSON):
    service = GovernedResearchExportService(g.session, g.educator.id, g.study, fields)
    return service.prepare(
        export_format=format,
        filters=ResearchExportFilters(
            course_ids=[g.course.id],
            date_from=g.now - timedelta(days=1),
            date_to=g.now + timedelta(days=1),
        ),
        actor_reference="unused",
        correlation_id="synthetic-only",
    )


@pytest.mark.parametrize("format", list(ResearchExportFormat))
def test_scoped_export_projects_only_approved_fields(governed, format):
    g = governed
    row = export_fixture(g)
    prepared = prepare(g, format=format)
    assert g.session.scalar(select(ResearchExportEligibility)).manifest["phase"] == "prepared"
    body = b"".join(prepared.body).decode("utf-8-sig")
    assert row.case_id in body and "42" in body
    for forbidden in (
        "generated_output",
        "pseudonymous_user_id",
        "SYNTHETIC-PROSE",
        "student_id",
        g.student.email,
    ):
        assert forbidden not in body
    if format == ResearchExportFormat.JSON:
        payload = json.loads(body)
        assert payload["schema_version"] == "learnlens.research-export.v2"
        assert payload["records"] == [{"case_id": row.case_id, "latency_ms": 42}]


@pytest.mark.parametrize("change", ["withdrawal", "revoked", "expired", "scope_changed"])
def test_export_rechecks_before_first_byte(governed, change):
    g = governed
    export_fixture(g)
    prepared = prepare(g)
    if change == "withdrawal":
        g.record(g.consent.model_copy(update={"decision": "withdrawn"}), g.student.id)
    elif change == "revoked":
        g.record(g.grant.model_copy(update={"revoked": True}))
    elif change == "expired":
        g.record(g.grant.model_copy(update={"valid_until": g.now}))
    else:
        g.record(g.scope)
    with pytest.raises(GovernanceDenied):
        next(iter(prepared.body))
    assert (
        list(g.session.scalars(select(ResearchExportEligibility)))[-1].manifest["phase"]
        == "interrupted"
    )


def test_export_withdrawal_between_rows_stops_further_release(governed):
    g = governed
    export_fixture(g)
    export_fixture(g)
    stream = iter(prepare(g).body)
    next(stream)  # envelope
    next(stream)  # first row
    g.record(g.consent.model_copy(update={"decision": "withdrawn"}), g.student.id)
    with pytest.raises(GovernanceDenied):
        next(stream)


@pytest.mark.parametrize(
    "change", ["legacy", "withdrawn", "nested_raw", "wrong_study", "wrong_pseudonym"]
)
def test_ineligible_export_rows_are_excluded_and_audited(governed, change):
    g = governed
    row = export_fixture(g, bind=change != "legacy")
    if change == "withdrawn":
        g.record(g.consent.model_copy(update={"decision": "withdrawn"}), g.student.id)
    elif change == "nested_raw":
        row.generated_output = {"nested": {"raw_answer": "SYNTHETIC-SECRET"}}
        g.session.commit()
    elif change == "wrong_study":
        g.study = "unapproved-other-study"
        with pytest.raises(ResearchExportError):
            prepare(g)
        return
    elif change == "wrong_pseudonym":
        row.pseudonymous_user_id = "v1_" + "f" * 64
        g.session.commit()
    prepared = prepare(g)
    assert json.loads(b"".join(prepared.body))["records"] == []
    receipt = g.session.scalar(select(ResearchExportEligibility))
    assert sum(receipt.manifest["excluded_counts"].values()) == 1


@pytest.mark.parametrize(
    "fields", [[], ["processing.provider_input"], ["generated_output"], ["student_id"], ["task_id"]]
)
def test_export_denies_unapproved_fields_before_bytes(governed, fields):
    g = governed
    export_fixture(g)
    g.record(g.grant.model_copy(update={"fields": ["case_id", "latency_ms"]}))
    with pytest.raises(ResearchExportError):
        prepare(g, fields=fields)
    assert (
        list(g.session.scalars(select(ResearchExportEligibility)))[-1].manifest["phase"] == "denied"
    )


@pytest.mark.parametrize("stage", ["queued", "context", "generation", "judgement"])
def test_worker_rechecks_around_each_external_step(governed, stage):
    g = governed
    row = export_fixture(g)
    repository, generator, judge = Repository(), Generator(), Judge()
    repository.claim = replace(repository.claim, case_id=row.case_id)

    def withdraw():
        g.record(g.consent.model_copy(update={"decision": "withdrawn"}), g.student.id)

    class Context(ContextProvider):
        async def get_context(self, reference):
            if stage == "context":
                withdraw()
            return await super().get_context(reference)

    class Generate:
        async def generate(self, *args, **kwargs):
            result = await generator.generate(*args, **kwargs)
            if stage == "generation":
                withdraw()
            return result

    class Evaluate:
        async def evaluate(self, *args, **kwargs):
            result = await judge.evaluate(*args, **kwargs)
            if stage == "judgement":
                withdraw()
            return result

    if stage == "queued":
        withdraw()
    executor = BaselineJobExecutor(
        repository,
        Context(),
        Generate(),
        Evaluate(),
        now=lambda: NOW,
        check_eligibility=lambda claim: g.service.require_case(claim.case_id),
    )
    assert asyncio.run(executor.run_once()) is True
    assert repository.completion is None and repository.failure is not None
    if stage in ("queued", "context"):
        assert generator.context is None


def test_export_audit_failure_releases_nothing(governed, monkeypatch):
    g = governed
    export_fixture(g)

    def fail():
        raise RuntimeError("synthetic audit unavailable")

    monkeypatch.setattr(g.session, "commit", fail)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        prepare(g)


def test_grant_for_another_approved_study_cannot_release_original_rows(governed):
    g = governed
    original = export_fixture(g)
    g.study = "synthetic-other-approved-study"
    scope = g.record(g.scope)
    g.record(g.approval.model_copy(update={"scope_id": scope.id}))
    g.record(g.grant.model_copy(update={"scope_id": scope.id}))
    prepared = prepare(g)
    payload = json.loads(b"".join(prepared.body))
    assert payload["records"] == [] and original.case_id not in json.dumps(payload)
    receipt = g.session.scalar(select(ResearchExportEligibility))
    assert receipt.manifest["excluded_counts"] == {"case_scope_mismatch": 1}


def processing_fixture(g):
    from uuid import uuid4

    from test_research_repository import seed

    from app.models.enums import TaskType, WorkflowStage
    from app.models.lms import AttemptStatus, SubmissionAttempt, SubmissionDraft
    from app.models.persistence import LearningTask, WorkflowRun

    task = LearningTask(
        slug=str(uuid4()),
        title="Synthetic",
        module="Synthetic",
        description="Synthetic",
        instructions="Synthetic",
        task_type=TaskType.SHORT_ANSWER,
        difficulty="intro",
        points=0,
        position=1,
        course_id=g.course.id,
    )
    g.session.add(task)
    g.session.flush()
    draft = SubmissionDraft(student_id=g.student.id, task_id=task.id)
    g.session.add(draft)
    g.session.flush()
    attempt = SubmissionAttempt(
        draft_id=draft.id,
        student_id=g.student.id,
        task_id=task.id,
        attempt_number=1,
        status=AttemptStatus.SUBMITTED,
        answer="Synthetic answer",
        feedback="Recorded",
        submitted_at=g.now + timedelta(seconds=1),
    )
    g.session.add(attempt)
    g.session.flush()
    workflow = WorkflowRun(
        submission_id=attempt.id,
        course_id=g.course.id,
        task_id=task.id,
        started_at=g.now + timedelta(seconds=1),
        current_stage=WorkflowStage.COMPLETED,
        completed_at=g.now + timedelta(seconds=2),
    )
    g.session.add(workflow)
    g.session.commit()
    return replace(seed(workflow.id), course_id=g.course.id, task_id=task.id), workflow


def test_governed_pair_is_atomic_scoped_and_replay_safe(governed, monkeypatch):
    from pydantic import SecretStr

    from app.core.config import settings
    from app.models.persistence import ResearchEvaluation
    from app.services.learning_events import HmacSha256Pseudonymizer
    from app.services.research.governed_processing import GovernedResearchJobRepository

    g = governed
    monkeypatch.setattr(
        settings, "learning_event_pseudonym_secret", SecretStr("synthetic-only-key-" * 4)
    )
    seed, _ = processing_fixture(g)
    repo = GovernedResearchJobRepository(g.session, now=lambda: g.now + timedelta(seconds=3))
    repo.create_pair(seed)
    repo.create_pair(seed)
    rows = list(g.session.scalars(select(ResearchEvaluation)))
    bindings = list(g.session.scalars(select(ResearchCaseGovernance)))
    assert len(rows) == 2 and len(bindings) == 1
    expected = HmacSha256Pseudonymizer(
        settings.learning_event_pseudonym_secret.get_secret_value()
    ).pseudonymize(f"study:{g.study}:actor", str(g.student.id))
    assert {row.pseudonymous_user_id for row in rows} == {expected}
    assert expected != seed.pseudonymous_user_id
    g.record(g.consent.model_copy(update={"decision": "withdrawn"}), g.student.id)
    with pytest.raises(GovernanceDenied):
        repo.create_pair(seed)
    assert len(list(g.session.scalars(select(ResearchEvaluation)))) == 2


@pytest.mark.parametrize(
    "change", ["historical", "wrong_course", "wrong_task", "no_consent", "gate", "field_denied"]
)
def test_governed_pair_denials_write_no_pair_or_binding(governed, monkeypatch, change):
    from pydantic import SecretStr

    from app.core.config import settings
    from app.models.persistence import ResearchEvaluation
    from app.services.research import governance
    from app.services.research.governed_processing import GovernedResearchJobRepository

    g = governed
    monkeypatch.setattr(
        settings, "learning_event_pseudonym_secret", SecretStr("synthetic-only-key-" * 4)
    )
    seed, workflow = processing_fixture(g)
    if change == "historical":
        workflow.started_at = g.now - timedelta(days=1)
        g.session.commit()
    elif change in ("wrong_course", "wrong_task"):
        seed = replace(
            seed, **({"course_id": "other"} if change == "wrong_course" else {"task_id": "other"})
        )
    elif change == "no_consent":
        g.record(g.consent.model_copy(update={"decision": "withdrawn"}), g.student.id)
    elif change == "field_denied":
        g.record(g.consent.model_copy(update={"fields": ["case_id"]}), g.student.id)
    else:
        monkeypatch.setattr(governance, "research_processing_approved", lambda: False)
    with pytest.raises(GovernanceDenied):
        GovernedResearchJobRepository(g.session).create_pair(seed)
    assert list(g.session.scalars(select(ResearchEvaluation))) == []
    assert list(g.session.scalars(select(ResearchCaseGovernance))) == []


def test_mounted_governance_csrf_owner_revision_and_real_export(governed, monkeypatch):
    from uuid import uuid4

    from fastapi.testclient import TestClient
    from pydantic import SecretStr

    from app.api.feedback_dependencies import require_actor
    from app.core.config import settings
    from app.db.session import get_db_session
    from app.main import create_app
    from app.schemas.feedback_api import AuthenticatedActor
    from app.schemas.research_governance import GovernanceCommand

    g = governed
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(
        settings, "learning_event_pseudonym_secret", SecretStr("synthetic-only-key-" * 4)
    )
    app = create_app()
    actor = [g.student]
    app.dependency_overrides[get_db_session] = lambda: g.session
    app.dependency_overrides[require_actor] = lambda: AuthenticatedActor(
        actor_reference=str(actor[0].id), role=actor[0].role.value
    )
    # Route dependency captured the original gate before the explicit fixture override.
    from app.api.routes import research_exports

    app.dependency_overrides[research_exports.research_processing_approved] = lambda: True
    export_fixture(g)
    url = f"/api/v1/research/governance/{g.study}"
    with TestClient(app) as client:
        state = client.get(url + f"/participation/{g.course.id}")
        assert state.status_code == 200 and state.json()["production_active"] is False
        assert client.get(url + "/decisions").status_code == 403
        cmd = GovernanceCommand(
            request_key=str(uuid4()),
            expected_revision=state.json()["revision"],
            reason="synthetic-withdrawal",
            decision=g.consent.model_copy(update={"decision": "withdrawn"}),
        )
        client.cookies.set(settings.csrf_cookie_name, "synthetic-csrf")
        assert client.post(url + "/decisions", json=cmd.model_dump(mode="json")).status_code == 403
        headers = {
            settings.csrf_header_name: "synthetic-csrf",
            "Origin": settings.allowed_cors_origins[0],
        }
        actor[0] = g.educator
        query = [
            ("format", "json"),
            ("study_id", g.study),
            ("course_id", g.course.id),
            ("fields", "case_id"),
        ]
        exported = client.get("/api/v1/research/exports", params=query)
        assert exported.status_code == 200 and len(exported.json()["records"]) == 1
        assert (
            client.post(
                url + "/decisions", json=cmd.model_dump(mode="json"), headers=headers
            ).status_code
            == 403
        )
        actor[0] = g.student
        saved = client.post(url + "/decisions", json=cmd.model_dump(mode="json"), headers=headers)
        assert saved.status_code == 201 and saved.json()["production_active"] is False
        assert (
            client.post(
                url + "/decisions", json=cmd.model_dump(mode="json"), headers=headers
            ).json()["id"]
            == saved.json()["id"]
        )
        stale = cmd.model_copy(update={"request_key": str(uuid4())})
        assert (
            client.post(
                url + "/decisions", json=stale.model_dump(mode="json"), headers=headers
            ).status_code
            == 409
        )
        actor[0] = g.educator
        assert client.get("/api/v1/research/exports", params=query).json()["records"] == []
        actor[0] = g.admin
        assert client.get(url + "/decisions").status_code == 200


def test_participation_and_both_technical_conditions_preserve_formal_history(governed, monkeypatch):
    from pydantic import SecretStr
    from test_assessor_review_api import (
        _assign_assessor,
        _decision_context,
        _request,
        _review_service,
    )

    from app.core.config import settings
    from app.db.base import Base
    from app.domain.assessment import AssessorReviewAction, ResultState
    from app.models.lms import Course, Enrollment, EnrollmentStatus
    from app.models.user import RoleAssignment, ScopedRole, User
    from app.services.research.governed_processing import GovernedResearchJobRepository

    g = governed
    attempt, _, decision, assessor = _decision_context(g.session)
    _assign_assessor(g.session, assessor, attempt.course_id, assessor)
    confirmed = _review_service(g.session, assessor).act(
        assessor, decision_id=decision.id, request=_request(AssessorReviewAction.CONFIRM)
    )
    assert confirmed.result_state == ResultState.CONFIRMED
    g.student = g.session.get(User, attempt.student_id)
    g.course = g.session.get(Course, attempt.course_id)
    g.session.add(
        Enrollment(student_id=g.student.id, course_id=g.course.id, status=EnrollmentStatus.ACTIVE)
    )
    g.session.commit()
    scope = g.record(g.scope.model_copy(update={"course_ids": [g.course.id]}))
    g.record(g.approval.model_copy(update={"scope_id": scope.id}))
    consent = g.consent.model_copy(
        update={"scope_id": scope.id, "course_id": g.course.id, "subject_user_id": g.student.id}
    )
    eligibility = g.eligibility.model_copy(
        update={"scope_id": scope.id, "course_id": g.course.id, "subject_user_id": g.student.id}
    )
    g.record(consent, g.student.id)
    g.record(eligibility)
    g.session.add(
        RoleAssignment(
            subject_user_id=g.educator.id,
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
    g.record(g.grant.model_copy(update={"scope_id": scope.id, "course_id": g.course.id}))
    seed, _ = processing_fixture(g)

    def operational_snapshot():
        return {
            table.name: [tuple(row) for row in g.session.execute(select(table))]
            for table in Base.metadata.sorted_tables
            if not table.name.startswith("research_")
        }

    before = operational_snapshot()
    monkeypatch.setattr(
        settings, "learning_event_pseudonym_secret", SecretStr("synthetic-only-key-" * 4)
    )
    GovernedResearchJobRepository(g.session, now=lambda: g.now + timedelta(seconds=3)).create_pair(
        seed
    )
    assert operational_snapshot() == before
    for state in ("withdrawn", "declined", "consented"):
        g.record(consent.model_copy(update={"decision": state}), g.student.id)
        assert operational_snapshot() == before
    assert (
        _review_service(g.session, assessor)
        .get_detail(assessor, decision_id=decision.id)
        .result_state
        == ResultState.CONFIRMED
    )


def test_withdrawal_does_not_block_real_operational_adaptation(db_session, monkeypatch):
    from test_activity_continuation import context, run_worker

    from app.models.activity_continuation import ActivitySuggestion
    from app.models.learner_model import LearnerModelSnapshot

    curriculum, _, factory, _ = context.__wrapped__(db_session)
    g = governed.__wrapped__(db_session, monkeypatch)
    _, _, learner, course, _, _, _ = curriculum
    scope = g.record(g.scope.model_copy(update={"course_ids": [course.id]}))
    g.record(g.approval.model_copy(update={"scope_id": scope.id}))
    consent = g.consent.model_copy(
        update={"scope_id": scope.id, "course_id": course.id, "subject_user_id": learner.id}
    )
    g.record(consent, learner.id)
    g.record(consent.model_copy(update={"decision": "withdrawn"}), learner.id)
    run_worker(factory)
    assert g.session.scalar(select(LearnerModelSnapshot)) is not None
    assert g.session.scalar(select(ActivitySuggestion)) is not None


@pytest.mark.parametrize(
    "change", ["allowed", "revoked_grant", "wrong_user", "wrong_course", "withdrawn"]
)
def test_wired_worker_checks_principal_and_context(governed, monkeypatch, change):
    from types import SimpleNamespace

    from pydantic import SecretStr
    from test_research_baseline_worker import context

    from app.core.config import Settings, settings
    from app.db.session import create_session_factory
    from app.models.enums import ExperimentalCondition, ResearchStatus
    from app.models.persistence import ResearchEvaluation
    from app.services.research.governed_processing import GovernedResearchJobRepository
    from app.worker import _GovernedResearchPass

    g = governed
    monkeypatch.setattr(
        settings, "learning_event_pseudonym_secret", SecretStr("synthetic-only-key-" * 4)
    )
    seed, workflow = processing_fixture(g)
    GovernedResearchJobRepository(g.session, now=lambda: g.now + timedelta(seconds=3)).create_pair(
        seed
    )
    source = context()
    correct = source.model_copy(
        update={
            "task": source.task.model_copy(
                update={"task_id": seed.task_id, "course_id": seed.course_id}
            ),
            "submission": source.submission.model_copy(
                update={
                    "submission_id": workflow.submission_id,
                    "student_id": str(g.student.id),
                    "task_id": seed.task_id,
                    "course_id": seed.course_id,
                }
            ),
        }
    )
    if change == "revoked_grant":
        g.record(g.grant.model_copy(update={"revoked": True}))
    elif change == "withdrawn":
        g.record(g.consent.model_copy(update={"decision": "withdrawn"}), g.student.id)
    elif change == "wrong_user":
        correct = correct.model_copy(
            update={
                "submission": correct.submission.model_copy(
                    update={"student_id": str(g.educator.id)}
                )
            }
        )
    elif change == "wrong_course":
        correct = correct.model_copy(
            update={"task": correct.task.model_copy(update={"course_id": "other"})}
        )

    class Provider:
        async def get_context(self, _):
            return correct

    generator = Generator()
    worker = _GovernedResearchPass(
        create_session_factory(g.session.get_bind()),
        SimpleNamespace(
            baseline_context_provider=Provider(),
            baseline_generator=generator,
            baseline_judge=Judge(),
        ),
        Settings(_env_file=None, research_enabled=True),
        lambda: g.now + timedelta(seconds=4),
    )
    assert asyncio.run(worker.run_once())
    g.session.expire_all()
    baseline = g.session.scalar(
        select(ResearchEvaluation).where(
            ResearchEvaluation.experimental_condition == ExperimentalCondition.SINGLE_STEP_BASELINE
        )
    )
    assert baseline.status == (
        ResearchStatus.COMPLETED if change == "allowed" else ResearchStatus.FAILED
    )
    if change != "allowed":
        assert generator.context is None and baseline.generated_output == {}
