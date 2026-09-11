"""Read-only expected-stage reconciliation; never invent records or participant outcomes."""

from collections import Counter

from sqlalchemy import select

from app.models.research_instruments import ResearchInstrumentForm, ResearchInstrumentRecord
from app.models.research_study import ResearchStudyEvent
from app.schemas.research_study import StudyReconciliationRead, StudyStageStatus
from app.services.research.governance import GovernanceDenied
from app.services.research.instruments import BASE_FIELDS
from app.services.research.study import STUDY_EXPORT_FIELDS

RECONCILIATION_FIELDS = BASE_FIELDS | {
    "instrument.missing_reason",
    "instrument.reason_code",
    "instrument.item_id",
}


def reconcile(service, actor, study, course):
    fields = STUDY_EXPORT_FIELDS | RECONCILIATION_FIELDS
    scope = service.scope(actor, study, course, fields, "read")
    service.instruments._scope(actor, study, course, RECONCILIATION_FIELDS, "read")
    events = service.session.scalars(
        select(ResearchStudyEvent)
        .where(
            ResearchStudyEvent.scope_id == scope.id,
            ResearchStudyEvent.course_id == course,
        )
        .order_by(ResearchStudyEvent.recorded_at, ResearchStudyEvent.id)
        .limit(1001)
    ).all()
    observations = service.session.scalars(
        select(ResearchInstrumentRecord)
        .join(ResearchInstrumentForm)
        .where(
            ResearchInstrumentForm.scope_id == scope.id,
            ResearchInstrumentForm.course_id == course,
        )
        .order_by(ResearchInstrumentRecord.id)
        .limit(1001)
    ).all()
    if len(events) > 1000 or len(observations) > 1000:
        raise GovernanceDenied("study_reconciliation_limit")
    latest = max(
        (row for row in events if row.kind == "plan"), key=lambda row: row.revision, default=None
    )
    if latest is None:
        return StudyReconciliationRead(plan_id=None, rows=[], excluded_counts={})
    _, plan = service.plan(latest.id, study, course, scope)
    excluded = Counter()
    superseded = {row.supersedes_id for row in observations if row.supersedes_id}
    rows = []
    for allocation in (row for row in events if row.kind == "allocation"):
        try:
            service.allocation(allocation.id, study, course, scope, fields)
        except GovernanceDenied as error:
            excluded[str(error)] += 1
            continue
        stages = {stage.stage: [] for stage in plan.stages}
        for record in observations:
            if record.sequence_id != allocation.data["sequence_id"] or record.id in superseded:
                continue
            try:
                _, binding = service.instruments._readable(
                    actor, study, course, record, RECONCILIATION_FIELDS, "read"
                )
                if binding.subject_user_id != allocation.subject_user_id or not any(
                    stage.stage == record.stage and stage.form_id == record.form_id
                    for stage in plan.stages
                ):
                    raise GovernanceDenied("study_stage_link_denied")
            except GovernanceDenied as error:
                excluded[str(error)] += 1
                continue
            stages[record.stage].append(record)
        for stage in plan.stages:
            records = stages[stage.stage]
            responses = [row for row in records if row.kind == "response"]
            gaps = [row for row in records if row.kind in {"missingness", "attrition"}]
            status = (
                "ambiguous"
                if len(responses) > 1 or (responses and gaps)
                else "response"
                if responses
                else "explicit_gap"
                if gaps
                else "unrecorded"
            )
            linked = {"packet": [], "rating": [], "outcome": []}
            for event in events:
                if (
                    event.kind not in linked
                    or event.data.get("allocation_id") != allocation.id
                    or event.data.get("stage") != stage.stage
                ):
                    continue
                try:
                    service.study_readable(
                        event.id, actor, study, course, STUDY_EXPORT_FIELDS, "read"
                    )
                except GovernanceDenied as error:
                    excluded[str(error)] += 1
                    continue
                linked[event.kind].append(event.id)
            rows.append(
                StudyStageStatus(
                    allocation_id=allocation.id,
                    participant_id=service.instruments._pseudonym(
                        study, "participant", allocation.subject_user_id
                    ),
                    sequence_id=allocation.data["sequence_id"],
                    stage=stage.stage,
                    form_id=stage.form_id,
                    status=status,
                    observations=[
                        dict(
                            record_id=record.id,
                            kind=record.kind,
                            missing_reason=record.data["missing_reason"],
                            reason_code=record.data["reason_code"],
                            missing_item_count=sum(
                                answer.get("missing_reason") is not None
                                for answer in record.data["answers"]
                            ),
                        )
                        for record in records
                    ],
                    packet_ids=linked["packet"],
                    rating_ids=linked["rating"],
                    outcome_ids=linked["outcome"],
                )
            )
    # A concurrent consent or grant change must not release the prepared status snapshot.
    service.scope(actor, study, course, fields, "read")
    for identity in {row.allocation_id for row in rows}:
        service.allocation(identity, study, course, scope, fields)
    return StudyReconciliationRead(
        plan_id=latest.id,
        rows=rows,
        excluded_counts=dict(excluded),
        production_active=service.policy.release_active(study),
    )
