"""Controlled restricted-text disposal; no authority derives from an export grant."""

from sqlalchemy import delete, select

from app.models.research_governance import ResearchGovernanceEvent
from app.models.research_instruments import (
    ResearchInstrumentForm,
    ResearchInstrumentRecord,
    RestrictedInstrumentEvidence,
)
from app.models.user import User, UserRole
from app.schemas.research_governance import DisposalExecution, GovernanceCommand
from app.services.research.governance import (
    GovernanceConflict,
    GovernanceDenied,
    lock_governance_write,
    utc,
)
from app.services.research.instruments import digest

RECORD_CLASS = "restricted_instrument_evidence"


def custodian(policy, actor):
    user = policy.session.get(User, actor, populate_existing=True)
    if user is None or not user.is_active or user.role != UserRole.ADMINISTRATOR:
        raise GovernanceDenied("disposal_custodian_required")


def inventory(policy, study, record_ids):
    if not record_ids or len(record_ids) > 200 or len(set(record_ids)) != len(record_ids):
        raise GovernanceDenied("exact_disposal_inventory_required")
    events = policy.events(study)
    scope = next((event for event in reversed(events) if event.kind == "scope"), None)
    if scope is None:
        raise GovernanceDenied("schedule_missing")
    definition = policy.decision(scope)
    disposition = policy.retention_disposition(study, RECORD_CLASS)
    if disposition["status"] == "schedule_missing":
        raise GovernanceDenied("schedule_missing")
    rows = policy.session.execute(
        select(RestrictedInstrumentEvidence, ResearchInstrumentForm.course_id)
        .join(
            ResearchInstrumentRecord,
            ResearchInstrumentRecord.id == RestrictedInstrumentEvidence.record_id,
        )
        .join(ResearchInstrumentForm, ResearchInstrumentForm.id == ResearchInstrumentRecord.form_id)
        .where(
            ResearchInstrumentForm.study_id == study,
            RestrictedInstrumentEvidence.record_id.in_(record_ids),
        )
        .execution_options(populate_existing=True)
    ).all()
    if len(rows) != len(record_ids) or any(
        course not in definition.course_ids for _, course in rows
    ):
        raise GovernanceDenied("disposal_inventory_scope_denied")
    records = []
    for row, _ in rows:
        if digest(row.response_text) != row.content_digest:
            raise GovernanceDenied("disposal_inventory_integrity_denied")
        records.append(
            dict(evidence_id=row.id, record_id=row.record_id, content_digest=row.content_digest)
        )
    manifest = dict(
        scope_id=scope.id,
        record_class=RECORD_CLASS,
        schedule=disposition["schedule"],
        records=sorted(records, key=lambda row: row["evidence_id"]),
    )
    return {
        **manifest,
        "manifest_digest": digest(manifest),
        "held": disposition["status"] == "held",
        "disposal_permitted": False,
        "status": "held" if disposition["status"] == "held" else "exact_authorization_required",
    }


def validate_authorization(policy, study, command):
    custodian(policy, command.executor_user_id)
    manifest = inventory(policy, study, command.record_ids)
    if manifest["held"]:
        raise GovernanceDenied("retention_hold_active")
    if (
        manifest["scope_id"] != command.scope_id
        or manifest["manifest_digest"] != command.manifest_digest
    ):
        raise GovernanceConflict("disposal_manifest_changed")
    return manifest


def disposed(policy, study, record_id):
    return any(
        event.kind == "disposal_execution"
        and any(row["record_id"] == record_id for row in event.command["decision"]["records"])
        for event in policy.events(study)
    )


def execute(policy, actor, study, command):
    try:
        lock_governance_write(policy.session)
        custodian(policy, actor)
        events = policy.events(study)
        replay = next(
            (
                event
                for event in events
                if event.actor_user_id == actor and event.request_key == command.request_key
            ),
            None,
        )
        if replay:
            if (
                replay.kind != "disposal_execution"
                or replay.command["decision"]["authorization_id"] != command.authorization_id
            ):
                raise GovernanceConflict("request_key_reused")
            return {"id": replay.id, "disposed_count": len(replay.command["decision"]["records"])}
        event = next(
            (
                event
                for event in events
                if event.id == command.authorization_id and event.kind == "disposal_authorization"
            ),
            None,
        )
        if event is None:
            raise GovernanceDenied("disposal_authorization_missing")
        authorization = policy.decision(event)
        latest = next(
            item
            for item in reversed(events)
            if item.kind == "disposal_authorization"
            and policy.decision(item).manifest_digest == authorization.manifest_digest
        )
        if (
            latest.id != event.id
            or authorization.state != "authorized"
            or authorization.executor_user_id != actor
        ):
            raise GovernanceDenied("disposal_authorization_inactive")
        if not (authorization.not_before <= utc(policy.now()) < authorization.valid_until):
            raise GovernanceDenied("disposal_window_inactive")
        manifest = validate_authorization(policy, study, authorization)
        receipt_command = GovernanceCommand(
            request_key=command.request_key,
            expected_revision=events[-1].revision,
            reason="authorized-restricted-text-disposal",
            decision=DisposalExecution(
                scope_id=authorization.scope_id,
                authorization_id=event.id,
                manifest_digest=authorization.manifest_digest,
                records=manifest["records"],
            ),
        )
        receipt = ResearchGovernanceEvent(
            study_id=study,
            revision=events[-1].revision + 1,
            actor_user_id=actor,
            request_key=command.request_key,
            kind="disposal_execution",
            command=receipt_command.model_dump(mode="json"),
            recorded_at=policy.now(),
        )
        policy.session.add(receipt)
        policy.session.flush()
        result = policy.session.execute(
            delete(RestrictedInstrumentEvidence).where(
                RestrictedInstrumentEvidence.id.in_(
                    [row["evidence_id"] for row in manifest["records"]]
                )
            )
        )
        if result.rowcount != len(authorization.record_ids):
            raise GovernanceConflict("disposal_inventory_changed")
        policy.session.commit()
        return {"id": receipt.id, "disposed_count": result.rowcount}
    except Exception:
        policy.session.rollback()
        raise
