"""Synthetic-only governance evidence. No approval in this module is a live record."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.lms import Course, Enrollment, EnrollmentStatus
from app.models.research_governance import ResearchCaseGovernance, ResearchGovernanceEvent
from app.models.user import RoleAssignment, ScopedRole, User, UserRole
from app.schemas.research_governance import (
    PROCESSING_FIELDS,
    ApprovalDecision,
    ConsentDecision,
    EligibilityDecision,
    GovernanceCommand,
    ResearchGrant,
    RetentionClass,
    RetentionHold,
    StudyScope,
)
from app.services.research import governance
from app.services.research.governance import (
    GovernanceConflict,
    GovernanceDenied,
    ResearchGovernanceService,
)


@pytest.fixture
def governed(db_session, monkeypatch):
    now = datetime.now(UTC)
    users = [
        User(
            email=f"synthetic-{role}@example.invalid",
            full_name="Synthetic fixture",
            password_hash="unused",
            role=role,
            is_active=True,
        )
        for role in UserRole
    ]
    db_session.add_all(users)
    db_session.flush()
    student, educator, admin = users
    course = Course(code="SYNTHETIC", title="Synthetic only", educator_id=educator.id)
    db_session.add(course)
    db_session.flush()
    db_session.add(
        Enrollment(student_id=student.id, course_id=course.id, status=EnrollmentStatus.ACTIVE)
    )
    db_session.add(
        RoleAssignment(
            subject_user_id=educator.id,
            course_id=course.id,
            role=ScopedRole.RESEARCH,
            version=1,
            assigned_by_user_id=admin.id,
            reason="Synthetic only",
            assigned_at=now,
            valid_from=now - timedelta(days=1),
        )
    )
    db_session.commit()
    service = ResearchGovernanceService(db_session, now=lambda: now)
    state = SimpleNamespace(
        session=db_session,
        service=service,
        now=now,
        student=student,
        educator=educator,
        admin=admin,
        course=course,
        study="synthetic-study",
    )

    def record(decision, actor=None, **kwargs):
        events = service.events(state.study)
        command = GovernanceCommand(
            request_key=str(uuid4()),
            expected_revision=events[-1].revision if events else 0,
            reason="synthetic-fixture-only",
            decision=decision,
            **kwargs,
        )
        return service.record(actor or admin.id, state.study, command)

    state.record = record
    state.scope = StudyScope(
        protocol_version="synthetic-v1",
        data_plan_version="synthetic-v1",
        consent_version="synthetic-v1",
        eligibility_rule_version="synthetic-v1",
        withdrawal_rule_reference="synthetic-only",
        course_ids=[course.id],
        processing_researcher_id=educator.id,
        fields=["case_id", "latency_ms", "pseudonymous_user_id", *sorted(PROCESSING_FIELDS)],
        purposes=["technical_pair", "provider_processing"],
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=10),
        retention=[
            RetentionClass(
                record_class=c,
                authority_reference="synthetic-only",
                authority_version="v1",
                owner_reference="synthetic-owner",
                trigger="synthetic-closure",
                retention_rule="review-with-authority-no-deletion",
                review_at=now + timedelta(days=20),
            )
            for c in ("governance", "identity_mapping", "technical_pairs", "export_audit")
        ],
    )
    state.scope_event = record(state.scope)
    state.approval = ApprovalDecision(
        scope_id=state.scope_event.id,
        state="approved",
        authority_reference="synthetic-only",
        evidence_reference="synthetic-only",
        valid_from=state.scope.valid_from,
        valid_until=state.scope.valid_until,
    )
    record(state.approval)
    state.consent = ConsentDecision(
        scope_id=state.scope_event.id,
        course_id=course.id,
        subject_user_id=student.id,
        decision="consented",
        consent_version="synthetic-v1",
        fields=state.scope.fields,
        purposes=state.scope.purposes,
    )
    state.consent_event = record(state.consent, student.id)
    state.eligibility = EligibilityDecision(
        scope_id=state.scope_event.id,
        course_id=course.id,
        subject_user_id=student.id,
        eligible=True,
        rule_version="synthetic-v1",
        evidence_reference="synthetic-only",
        valid_until=state.scope.valid_until,
    )
    record(state.eligibility)
    state.grant = ResearchGrant(
        scope_id=state.scope_event.id,
        course_id=course.id,
        subject_user_id=educator.id,
        fields=state.scope.fields,
        valid_from=state.scope.valid_from,
        valid_until=state.scope.valid_until,
        authority_reference="synthetic-only",
        evidence_reference="synthetic-only",
    )
    record(state.grant)
    monkeypatch.setattr(governance, "research_processing_approved", lambda: True)
    # Synthetic functional fixtures explicitly bypass release; they are not approval records.
    monkeypatch.setattr(
        ResearchGovernanceService, "require_release", lambda self, study: self.approved(study)
    )
    monkeypatch.setattr(
        ResearchGovernanceService, "require_form_release", lambda self, study, form: None
    )
    monkeypatch.setattr(ResearchGovernanceService, "release_active", lambda self, study: False)
    return state


def participant(g, **kwargs):
    return g.service.participant(
        kwargs.pop("study", g.study),
        kwargs.pop("course", g.course.id),
        kwargs.pop("user", g.student.id),
        fields=kwargs.pop("fields", {"case_id"}),
        purposes=kwargs.pop("purposes", {"technical_pair"}),
    )


@pytest.mark.parametrize("state", ["pending", "suspended", "revoked"])
def test_approval_state_denies(governed, state):
    g = governed
    g.record(g.approval.model_copy(update={"state": state}))
    with pytest.raises(GovernanceDenied, match="approval_inactive"):
        participant(g)


@pytest.mark.parametrize("change", ["missing", "expired", "future", "new_scope", "retention_due"])
def test_approval_version_and_time(governed, change):
    g = governed
    if change == "missing":
        g.study = "other-study"
    elif change == "expired":
        g.service.now = lambda: g.now + timedelta(days=11)
    elif change == "future":
        g.record(g.approval.model_copy(update={"valid_from": g.now + timedelta(days=1)}))
    elif change == "new_scope":
        g.record(g.scope.model_copy(update={"consent_version": "v2"}))
    else:
        scope = g.scope.model_copy(
            update={
                "retention": [r.model_copy(update={"review_at": g.now}) for r in g.scope.retention]
            }
        )
        scope_event = g.record(scope)
        g.record(g.approval.model_copy(update={"scope_id": scope_event.id}))
    with pytest.raises(GovernanceDenied):
        participant(g)


@pytest.mark.parametrize(
    "change",
    [
        "withdrawn",
        "declined",
        "fields",
        "purpose",
        "ineligible",
        "eligibility_expired",
        "inactive",
        "unenrolled",
        "user",
        "course",
        "study",
    ],
)
def test_participant_boundaries(governed, change):
    g = governed
    args = {}
    if change in ("withdrawn", "declined"):
        g.record(g.consent.model_copy(update={"decision": change}), g.student.id)
    elif change == "fields":
        g.record(g.consent.model_copy(update={"fields": ["latency_ms"]}), g.student.id)
    elif change == "purpose":
        g.record(g.consent.model_copy(update={"purposes": []}), g.student.id)
    elif change in ("ineligible", "eligibility_expired"):
        g.record(
            g.eligibility.model_copy(
                update={"eligible": False} if change == "ineligible" else {"valid_until": g.now}
            )
        )
    elif change == "inactive":
        g.student.is_active = False
        g.session.commit()
    elif change == "unenrolled":
        g.session.delete(g.session.scalar(select(Enrollment)))
        g.session.commit()
    else:
        args[change] = g.educator.id if change == "user" else "other"
    with pytest.raises(GovernanceDenied):
        participant(g, **args)


@pytest.mark.parametrize("change", ["revoked", "expired", "fields", "wrong_actor", "role_revoked"])
def test_grants_are_additional_to_course_roles(governed, change):
    g = governed
    actor = g.educator.id
    if change == "revoked":
        g.record(g.grant.model_copy(update={"revoked": True}))
    elif change == "expired":
        g.record(g.grant.model_copy(update={"valid_until": g.now}))
    elif change == "fields":
        g.record(g.grant.model_copy(update={"fields": ["latency_ms"]}))
    elif change == "wrong_actor":
        actor = g.admin.id
    else:
        role = g.session.scalar(select(RoleAssignment))
        role.revoked_at = g.now
        role.revoked_by_user_id = g.admin.id
        role.revocation_reason = "synthetic-only"
        g.session.commit()
    with pytest.raises(GovernanceDenied):
        g.service.grant(g.study, g.course.id, actor, {"case_id"})


def test_consent_version_and_self_only(governed):
    g = governed
    with pytest.raises(GovernanceDenied, match="consent_owner"):
        g.record(g.consent, g.admin.id)
    with pytest.raises(GovernanceDenied, match="consent_scope"):
        g.record(g.consent.model_copy(update={"consent_version": "wrong"}), g.student.id)
    with pytest.raises(GovernanceDenied, match="custodian"):
        g.record(g.approval, g.educator.id)
    with pytest.raises(ValidationError):
        ConsentDecision(**(g.consent.model_dump() | {"fields": ["raw_answer"]}))


def test_exact_replay_and_concurrent_revision(governed):
    g = governed
    revision = g.service.events(g.study)[-1].revision
    command = GovernanceCommand(
        request_key=str(uuid4()),
        expected_revision=revision,
        reason="synthetic-only",
        decision=g.approval,
    )
    actor_id, study_id, engine = g.admin.id, g.study, g.session.get_bind()
    g.session.rollback()

    def run(cmd):
        with Session(engine) as session:
            try:
                return ResearchGovernanceService(session).record(actor_id, study_id, cmd).id
            except GovernanceConflict:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, [command, command]))
    assert len(set(results)) == 1 and results[0] != "conflict"
    assert run(command.model_copy(update={"reason": "different"})) == "conflict"
    next_command = command.model_copy(
        update={"request_key": str(uuid4()), "expected_revision": revision + 1}
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                run, [next_command, next_command.model_copy(update={"request_key": str(uuid4())})]
            )
        )
    assert results.count("conflict") == 1


def test_holds_preserve_all_history_and_never_dispose(governed):
    g = governed
    hold = RetentionHold(
        scope_id=g.scope_event.id,
        record_class="technical_pairs",
        hold_reference="synthetic-hold",
        authority_reference="synthetic-only",
        active=True,
    )
    g.record(hold)
    assert g.service.retention_disposition(g.study, "technical_pairs")["status"] == "held"
    g.record(hold.model_copy(update={"active": False}))
    assert (
        g.service.retention_disposition(g.study, "technical_pairs")["disposal_permitted"] is False
    )
    for sql in (
        "DELETE FROM research_governance_events",
        "UPDATE research_governance_events SET revision=100",
        "INSERT OR REPLACE INTO research_governance_events SELECT * FROM research_governance_events LIMIT 1",
    ):
        with pytest.raises(IntegrityError):
            g.session.execute(text(sql))
        g.session.rollback()
    assert g.session.scalar(select(func.count()).select_from(ResearchGovernanceEvent)) == 7


def test_case_rechecks_withdrawal_and_reconsent_does_not_revive(governed):
    g = governed
    case = str(uuid4())
    g.session.add(
        ResearchCaseGovernance(
            case_id=case,
            scope_id=g.scope_event.id,
            consent_id=g.consent_event.id,
            course_id=g.course.id,
            pseudonymous_user_id="v1_" + "a" * 64,
        )
    )
    g.session.commit()
    assert g.service.require_case(case).case_id == case
    g.record(g.consent.model_copy(update={"decision": "withdrawn"}), g.student.id)
    with pytest.raises(GovernanceDenied, match="consent_inactive"):
        g.service.require_case(case)
    g.record(g.consent, g.student.id)
    with pytest.raises(GovernanceDenied, match="case_consent_changed"):
        g.service.require_case(case)


def test_gate_stays_closed_despite_approvals_and_settings(governed, monkeypatch):
    g = governed
    monkeypatch.setattr(governance, "research_processing_approved", lambda: False)
    with pytest.raises(GovernanceDenied, match="pending"):
        g.service.processing_scope(g.course.id, g.student.id)
    assert participant(g)


def test_refusal_preserves_teaching_access_and_continuation(governed):
    from app.schemas.feedback_api import AuthenticatedActor
    from app.services.access import SqlAlchemyAnalyticsAccessPolicy, SqlAlchemyCourseAccessPolicy

    g = governed
    course_access = SqlAlchemyCourseAccessPolicy(g.session)
    course_access.require_read(str(g.student.id), g.course.id)
    before = asyncio.run(
        SqlAlchemyAnalyticsAccessPolicy(g.session).authorized_course_ids(str(g.educator.id))
    )
    g.record(g.consent.model_copy(update={"decision": "withdrawn"}), g.student.id)
    course_access.require_read(str(g.student.id), g.course.id)
    assert (
        asyncio.run(
            SqlAlchemyAnalyticsAccessPolicy(g.session).authorized_course_ids(str(g.educator.id))
        )
        == before
    )
    assert AuthenticatedActor(actor_reference=str(g.student.id), role="student").role == "student"
