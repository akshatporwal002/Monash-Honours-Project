"""Isolated synthetic authority fixtures exercise release without approving a real study."""

import pytest
from test_research_governance import governed as governed
from test_research_instruments import instruments as instruments
from test_research_study import study as study

from app.core.config import settings
from app.schemas.research_governance import InstrumentApprovalDecision, StudyReleaseDecision
from app.schemas.research_study import StudySelfResponse
from app.services.research import governance
from app.services.research.governance import GovernanceDenied, ResearchGovernanceService

REAL_GATE = governance.research_processing_approved
REAL_RELEASE = ResearchGovernanceService.require_release
REAL_FORM_RELEASE = ResearchGovernanceService.require_form_release
REAL_ACTIVE = ResearchGovernanceService.release_active


def prepare(g, monkeypatch):
    monkeypatch.setattr(governance, "research_processing_approved", REAL_GATE)
    monkeypatch.setattr(ResearchGovernanceService, "require_release", REAL_RELEASE)
    monkeypatch.setattr(ResearchGovernanceService, "require_form_release", REAL_FORM_RELEASE)
    monkeypatch.setattr(ResearchGovernanceService, "release_active", REAL_ACTIVE)
    monkeypatch.setattr(settings, "research_release_enabled", False)
    form = g.instruments.save_form(
        g.educator.id,
        g.study,
        g.course.id,
        "synthetic_form",
        g.form_command.model_copy(
            update={
                "request_key": "release-form",
                "expected_version": 2,
                "definition": g.definition.model_copy(update={"synthetic_only": False}),
            }
        ),
    )
    g.instruments.freeze_form(
        g.educator.id,
        g.study,
        g.course.id,
        form.id,
        g.freeze.model_copy(
            update={"request_key": "release-freeze", "content_digest": form.content_digest}
        ),
    )
    approval = InstrumentApprovalDecision(
        scope_id=g.scope_event.id,
        form_id=form.id,
        content_digest=form.content_digest,
        state="approved",
        authority_reference="synthetic-only",
        evidence_reference="synthetic-only",
        valid_from=g.scope.valid_from,
        valid_until=g.scope.valid_until,
    )
    form_approval = g.record(approval)
    plan = g.write(
        "plan",
        **{
            **g.plan_data,
            "expected_revision": 1,
            "stages": [
                {"stage": stage["stage"], "form_id": form.id} for stage in g.plan_data["stages"]
            ],
        },
    )
    approval_id = next(
        event.id for event in reversed(g.service.events(g.study)) if event.kind == "approval"
    )
    command = StudyReleaseDecision(
        scope_id=g.scope_event.id,
        approval_id=approval_id,
        plan_ids=[plan.id],
        instrument_approval_ids=[form_approval.id],
        state="active",
        authority_reference="synthetic-only",
        evidence_reference="synthetic-only",
        valid_from=g.scope.valid_from,
        valid_until=g.scope.valid_until,
    )
    return form, approval, plan, command


def test_supplied_release_can_activate_and_suspend_without_code_change(study, monkeypatch):
    g = study
    form, _, plan, release = prepare(g, monkeypatch)
    g.record(release)
    assert g.service.release_active(g.study) is False
    with pytest.raises(GovernanceDenied, match="pending"):
        g.workflow.participant_forms(g.student.id, g.study, g.course.id)
    monkeypatch.setattr(settings, "research_release_enabled", True)
    assert g.service.release_active(g.study) is True
    allocation = g.write(
        "allocation",
        subject_user_id=g.student.id,
        plan_id=plan.id,
        sequence_key="released-sequence",
        condition="condition_a",
        allocation_evidence_reference="synthetic-only",
    )
    assert (
        g.workflow.participant_forms(g.student.id, g.study, g.course.id)[0]["allocation_id"]
        == allocation.id
    )
    response = g.workflow.submit_self(
        g.student.id,
        g.study,
        g.course.id,
        StudySelfResponse(
            allocation_id=allocation.id,
            record=g.command.model_copy(update={"form_version_id": form.id}),
        ),
    )
    assert response.id and response.production_active
    g.record(release.model_copy(update={"state": "suspended"}))
    with pytest.raises(GovernanceDenied, match="inactive"):
        g.workflow.participant_forms(g.student.id, g.study, g.course.id)


@pytest.mark.parametrize("change", ["plan", "approval", "instrument", "scope"])
def test_release_is_invalidated_by_exact_authority_or_content_revision(study, monkeypatch, change):
    g = study
    _, approval, _, release = prepare(g, monkeypatch)
    g.record(release)
    monkeypatch.setattr(settings, "research_release_enabled", True)
    assert g.service.release_active(g.study)
    if change == "plan":
        g.write("plan", **{**g.plan_data, "expected_revision": 2})
    elif change == "approval":
        g.record(g.approval)
    elif change == "instrument":
        g.record(approval.model_copy(update={"state": "revoked"}))
    else:
        g.record(g.scope)
    assert not g.service.release_active(g.study)
    with pytest.raises(GovernanceDenied):
        g.workflow.read_events(g.educator.id, g.study, g.course.id)


def test_release_rejects_synthetic_forms_missing_plans_and_unauthorized_actor(study, monkeypatch):
    g = study
    _, approval, _, release = prepare(g, monkeypatch)
    with pytest.raises(GovernanceDenied, match="instrument_approval_inactive"):
        g.record(
            approval.model_copy(
                update={"form_id": g.form.id, "content_digest": g.form.content_digest}
            )
        )
    with pytest.raises(GovernanceDenied, match="plans_missing"):
        g.record(release.model_copy(update={"plan_ids": []}))
    with pytest.raises(GovernanceDenied, match="custodian"):
        g.record(release, g.educator.id)
    monkeypatch.setattr(settings, "research_release_enabled", True)
    assert not g.service.release_active(g.study)
