"""Explicit institutional study release, independent of AI evaluator release."""

from sqlalchemy import select

from app.models.research_instruments import ResearchInstrumentForm, ResearchInstrumentFreeze
from app.models.research_study import ResearchStudyEvent
from app.schemas.research_study import StudyPlan
from app.services.research.governance import GovernanceDenied, utc


def approved_form(policy, study, approval, *, current=True, event_id=None):
    from app.services.research.instruments import digest

    scope, _, events = policy.approved(study)
    form = policy.session.get(ResearchInstrumentForm, approval.form_id, populate_existing=True)
    latest = next(
        (
            event
            for event in reversed(events)
            if event.kind == "instrument_approval"
            and policy.decision(event).form_id == approval.form_id
        ),
        None,
    )
    if (
        approval.scope_id != scope.id
        or approval.state != "approved"
        or form is None
        or form.study_id != study
        or form.scope_id != scope.id
        or form.definition.get("synthetic_only", True)
        or form.content_digest != approval.content_digest
        or digest(form.definition) != form.content_digest
        or not (approval.valid_from <= utc(policy.now()) < approval.valid_until)
        or (
            current
            and (latest is None or policy.decision(latest) != approval or latest.id != event_id)
        )
        or not policy.session.scalar(
            select(ResearchInstrumentFreeze.id).where(ResearchInstrumentFreeze.form_id == form.id)
        )
    ):
        raise GovernanceDenied("instrument_approval_inactive")
    return form


def validate_release(policy, study, release):
    from app.services.research.instruments import digest

    scope, definition, events = policy.approved(study)
    approval = next(event for event in reversed(events) if event.kind == "approval")
    if (
        release.scope_id != scope.id
        or release.approval_id != approval.id
        or not (release.valid_from <= utc(policy.now()) < release.valid_until)
    ):
        raise GovernanceDenied("study_release_binding_changed")
    forms = {}
    for identity in release.instrument_approval_ids:
        event = next(
            (
                event
                for event in events
                if event.id == identity and event.kind == "instrument_approval"
            ),
            None,
        )
        if event is None:
            raise GovernanceDenied("instrument_approval_missing")
        form = approved_form(policy, study, policy.decision(event), event_id=event.id)
        if form.id in forms:
            raise GovernanceDenied("duplicate_instrument_approval")
        forms[form.id] = form
    courses = set()
    for identity in release.plan_ids:
        row = policy.session.get(ResearchStudyEvent, identity, populate_existing=True)
        if (
            row is None
            or row.kind != "plan"
            or row.study_id != study
            or row.scope_id != scope.id
            or digest(row.data) != row.content_digest
        ):
            raise GovernanceDenied("release_plan_denied")
        latest = policy.session.scalar(
            select(ResearchStudyEvent.id)
            .where(
                ResearchStudyEvent.scope_id == scope.id,
                ResearchStudyEvent.course_id == row.course_id,
                ResearchStudyEvent.kind == "plan",
            )
            .order_by(ResearchStudyEvent.revision.desc())
            .limit(1)
        )
        if latest != row.id or row.course_id in courses:
            raise GovernanceDenied("release_plan_replaced")
        plan = StudyPlan.model_validate(row.data)
        if any(
            stage.form_id not in forms
            or forms[stage.form_id].course_id != row.course_id
            or stage.stage not in forms[stage.form_id].definition["stages"]
            for stage in plan.stages
        ):
            raise GovernanceDenied("release_instrument_missing")
        courses.add(row.course_id)
    if "study_instruments" in definition.purposes and courses != set(definition.course_ids):
        raise GovernanceDenied("release_course_plans_missing")
    if not courses <= set(definition.course_ids):
        raise GovernanceDenied("release_course_denied")
    return scope, definition, events


def require_release(policy, study):
    from app.services.research.governance import research_processing_approved

    if not research_processing_approved():
        raise GovernanceDenied("research_governance_pending")
    events = policy.events(study)
    event = next((event for event in reversed(events) if event.kind == "release"), None)
    if event is None:
        raise GovernanceDenied("study_release_missing")
    release = policy.decision(event)
    if release.state != "active":
        raise GovernanceDenied("study_release_inactive")
    return validate_release(policy, study, release)
