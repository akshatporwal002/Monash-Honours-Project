"""Governed study allocation, blinded review and stage outcomes; no operational writes."""

import json
from typing import get_args

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.research_instruments import (
    ResearchInstrumentBinding,
    ResearchInstrumentForm,
    ResearchInstrumentRecord,
)
from app.models.research_study import ResearchStudyEvent
from app.schemas.research_governance import OPERATIONAL_FIELDS
from app.schemas.research_study import StudyExportField, StudyPacketRead, StudyPlan, StudyReceipt
from app.services.research import governance
from app.services.research.governance import (
    GovernanceConflict,
    GovernanceDenied,
    lock_governance_write,
)
from app.services.research.instruments import (
    EXPORT_FIELDS,
    InstrumentExport,
    ResearchInstrumentService,
    csv_row,
    digest,
)
from app.services.research.operational import OperationalCollector

STUDY_EXPORT_FIELDS = frozenset(get_args(StudyExportField))


class ResearchStudyService:
    def __init__(self, session, *, now=None):
        self.session = session
        self.instruments = ResearchInstrumentService(session, now=now)
        self.policy = self.instruments.policy

    def scope(self, actor, study, course, fields, operation, *, live=True):
        if live and not governance.research_processing_approved():
            raise GovernanceDenied("research_governance_pending")
        scope, definition, _ = self.policy.approved(study)
        if "study_instruments" not in definition.purposes:
            raise GovernanceDenied("instrument_purpose_not_approved")
        self.policy.grant(study, course, actor, set(fields) | {"study." + operation})
        if not {"study_workflows", "study_reviewer_packets"} <= {
            r.record_class for r in definition.retention
        }:
            raise GovernanceDenied("study_retention_missing")
        return scope

    def event(self, identity, study, course, scope, kind=None):
        row = self.session.get(ResearchStudyEvent, identity)
        if (
            row is None
            or (row.study_id, row.course_id, row.scope_id) != (study, course, scope.id)
            or (kind and row.kind != kind)
        ):
            raise GovernanceDenied("study_record_scope_denied")
        if digest(row.data) != row.content_digest:
            raise GovernanceDenied("study_integrity_denied")
        return row

    def plan(self, identity, study, course, scope):
        row = self.event(identity, study, course, scope, "plan")
        latest = self.session.scalar(
            select(ResearchStudyEvent.id)
            .where(
                ResearchStudyEvent.scope_id == scope.id,
                ResearchStudyEvent.course_id == course,
                ResearchStudyEvent.kind == "plan",
            )
            .order_by(ResearchStudyEvent.revision.desc())
            .limit(1)
        )
        if latest != row.id:
            raise GovernanceDenied("study_plan_replaced")
        return row, StudyPlan.model_validate(row.data)

    def eligible(self, row, fields):
        _, consent = self.policy.participant(
            row.study_id,
            row.course_id,
            row.subject_user_id,
            fields=fields,
            purposes={"study_instruments"},
        )
        if consent.id != row.consent_id:
            raise GovernanceDenied("record_consent_version_changed")
        return consent

    def allocation(self, identity, study, course, scope, fields=STUDY_EXPORT_FIELDS):
        row = self.event(identity, study, course, scope, "allocation")
        self.eligible(row, fields)
        _, plan = self.plan(row.data["plan_id"], study, course, scope)
        return row, plan

    def packet_source(self, packet, scope):
        record = self.session.get(ResearchInstrumentRecord, packet.data["instrument_record_id"])
        if (
            record is None
            or record.consent_id != packet.consent_id
            or record.stage != packet.data["stage"]
        ):
            raise GovernanceDenied("study_stage_link_denied")
        self.instruments._form(record.form_id, packet.study_id, packet.course_id, scope)
        if self.session.scalar(
            select(ResearchInstrumentRecord.id).where(
                ResearchInstrumentRecord.supersedes_id == record.id
            )
        ):
            raise GovernanceDenied("study_evidence_superseded")
        return record

    def record(self, actor, study, course, command):
        try:
            lock_governance_write(self.session)
            decision = command.decision
            kind = decision.kind
            fields = set() if kind == "plan" else set(STUDY_EXPORT_FIELDS) | {"study.provenance"}
            if kind == "packet":
                fields.add("study.redacted_evidence")
            scope = self.scope(
                actor,
                study,
                course,
                fields,
                {
                    "plan": "prepare",
                    "allocation": "allocate",
                    "packet": "packet",
                    "rating": "rate",
                    "outcome": "outcome",
                }[kind],
                live=kind != "plan",
            )
            data = decision.model_dump(mode="json")
            request_digest = digest([study, course, data])
            prior = self.instruments._replay(
                ResearchStudyEvent, actor, command.request_key, request_digest
            )
            subject, consent_id, revision = None, None, 1
            if kind == "plan":
                for stage in decision.stages:
                    form = self.instruments._form(stage.form_id, study, course, scope)
                    if (
                        stage.stage not in form.definition["stages"]
                        or not self.instruments.form_read(form).frozen_for_synthetic_validation
                    ):
                        raise GovernanceDenied("study_form_stage_denied")
                slot = "plan"
                revision = decision.expected_revision + 1
                latest = (
                    self.session.scalar(
                        select(ResearchStudyEvent.revision)
                        .where(
                            ResearchStudyEvent.scope_id == scope.id,
                            ResearchStudyEvent.course_id == course,
                            ResearchStudyEvent.kind == "plan",
                        )
                        .order_by(ResearchStudyEvent.revision.desc())
                        .limit(1)
                    )
                    or 0
                )
                if not prior and latest != decision.expected_revision:
                    raise GovernanceConflict("study_plan_revision_changed")
            elif kind == "allocation":
                _, plan = self.plan(decision.plan_id, study, course, scope)
                if decision.condition not in plan.conditions:
                    raise GovernanceDenied("study_condition_denied")
                subject = decision.subject_user_id
                _, consent = self.policy.participant(
                    study, course, subject, fields=fields, purposes={"study_instruments"}
                )
                consent_id = consent.id
                sequence = self.instruments._pseudonym(
                    study,
                    "sequence",
                    f"{self.instruments._pseudonym(study, 'participant', subject)}:{decision.sequence_key}",
                )
                data.pop("subject_user_id")
                data.pop("sequence_key")
                data["sequence_id"] = sequence
                slot = f"allocation:{subject}:{sequence}"
            else:
                if kind == "packet":
                    allocation, plan = self.allocation(decision.allocation_id, study, course, scope)
                    record = self.session.get(
                        ResearchInstrumentRecord, decision.instrument_record_id
                    )
                    self.instruments._readable(actor, study, course, record, EXPORT_FIELDS, "read")
                    binding = self.session.get(ResearchInstrumentBinding, record.binding_id)
                    if record.kind != "response" or (
                        binding.subject_user_id,
                        record.consent_id,
                        record.sequence_id,
                    ) != (
                        allocation.subject_user_id,
                        allocation.consent_id,
                        allocation.data["sequence_id"],
                    ):
                        raise GovernanceDenied("study_stage_link_denied")
                    if not any(
                        s.stage == record.stage and s.form_id == record.form_id for s in plan.stages
                    ):
                        raise GovernanceDenied("study_stage_link_denied")
                    if decision.rubric_code not in {r.code for r in plan.rubrics}:
                        raise GovernanceDenied("study_rubric_denied")
                    self.policy.grant(study, course, actor, {"instrument.response_text"})
                    self.policy.participant(
                        study,
                        course,
                        allocation.subject_user_id,
                        fields={"instrument.response_text"},
                        purposes={"study_instruments"},
                    )
                    if self.session.scalar(
                        select(ResearchInstrumentRecord.id).where(
                            ResearchInstrumentRecord.supersedes_id == record.id
                        )
                    ):
                        raise GovernanceDenied("study_evidence_superseded")
                    self.policy.grant(
                        study,
                        course,
                        decision.reviewer_user_id,
                        {"study.rate", "study.redacted_evidence"},
                    )
                    if decision.reviewer_user_id in {actor, allocation.subject_user_id}:
                        raise GovernanceDenied("independent_study_reviewer_required")
                    data.update(
                        stage=record.stage,
                        plan_id=allocation.data["plan_id"],
                        sequence_id=record.sequence_id,
                    )
                    slot = f"packet:{record.id}:{decision.reviewer_user_id}:{decision.rubric_code}"
                else:
                    packet = self.event(decision.packet_id, study, course, scope, "packet")
                    allocation, plan = self.allocation(
                        packet.data["allocation_id"], study, course, scope
                    )
                    self.eligible(packet, fields)
                    self.packet_source(packet, scope)
                    rubric = next(r for r in plan.rubrics if r.code == packet.data["rubric_code"])
                    if decision.value_code is not None and decision.value_code not in rubric.values:
                        raise GovernanceDenied("study_rating_code_denied")
                    if kind == "rating" and packet.data["reviewer_user_id"] != actor:
                        raise GovernanceDenied("study_reviewer_assignment_denied")
                    if kind == "outcome":
                        rating = self.event(decision.rating_id, study, course, scope, "rating")
                        self.eligible(rating, fields)
                        if rating.data["packet_id"] != packet.id:
                            raise GovernanceDenied("study_rating_link_denied")
                    data.update(
                        allocation_id=allocation.id,
                        plan_id=allocation.data["plan_id"],
                        stage=packet.data["stage"],
                        sequence_id=allocation.data["sequence_id"],
                        instrument_record_id=packet.data["instrument_record_id"],
                        rubric_code=packet.data["rubric_code"],
                    )
                    slot = f"{kind}:{packet.id}"
                subject, consent_id = allocation.subject_user_id, allocation.consent_id
                self.policy.participant(
                    study, course, subject, fields=fields, purposes={"study_instruments"}
                )
            if prior:
                self.event(prior.id, study, course, scope, kind)
                if prior.consent_id != consent_id:
                    raise GovernanceDenied("record_consent_version_changed")
                return self.receipt(prior)
            row = ResearchStudyEvent(
                scope_id=scope.id,
                study_id=study,
                course_id=course,
                kind=kind,
                slot=slot,
                revision=revision,
                subject_user_id=subject,
                consent_id=consent_id,
                data=data,
                content_digest=digest(data),
                actor_user_id=actor,
                request_key=command.request_key,
                request_digest=request_digest,
                recorded_at=self.policy.now(),
            )
            self.session.add(row)
            self.session.commit()
            return self.receipt(row)
        except IntegrityError:
            self.session.rollback()
            raise GovernanceConflict("study_record_conflict") from None
        finally:
            self.session.rollback()

    @staticmethod
    def receipt(row):
        return StudyReceipt(id=row.id, kind=row.kind, revision=row.revision)

    def participant_forms(self, actor, study, course):
        if not governance.research_processing_approved():
            raise GovernanceDenied("research_governance_pending")
        scope, _ = self.policy.participant(
            study, course, actor, fields=STUDY_EXPORT_FIELDS, purposes={"study_instruments"}
        )
        _, definition, _ = self.policy.approved(study)
        self.instruments._scope(definition.processing_researcher_id, study, course, (), "collect")
        rows = self.session.scalars(
            select(ResearchStudyEvent)
            .where(
                ResearchStudyEvent.scope_id == scope.id,
                ResearchStudyEvent.course_id == course,
                ResearchStudyEvent.subject_user_id == actor,
                ResearchStudyEvent.kind == "allocation",
            )
            .order_by(ResearchStudyEvent.id)
        ).all()
        result = []
        for row in rows:
            allocation, plan = self.allocation(row.id, study, course, scope)
            result.append(
                {
                    "allocation_id": row.id,
                    "stages": [
                        {
                            "stage": s.stage,
                            "form": self.instruments.form_read(
                                self.instruments._form(s.form_id, study, course, scope)
                            ).model_dump(mode="json"),
                        }
                        for s in plan.stages
                    ],
                }
            )
        return result

    def submit_researcher(self, actor, study, course, command):
        try:
            lock_governance_write(self.session)
            scope, _, _ = self.policy.approved(study)
            allocation, plan = self.allocation(command.allocation_id, study, course, scope)
            record = command.record
            if record.subject_user_id != allocation.subject_user_id or not any(
                s.stage == record.stage and s.form_id == record.form_version_id for s in plan.stages
            ):
                raise GovernanceDenied("study_assignment_denied")
            return self.instruments.collect(
                actor, study, course, record, allocated_sequence=allocation.data["sequence_id"]
            )
        finally:
            self.session.rollback()

    def submit_self(self, actor, study, course, command):
        # Keep allocation and consent validation ordered with collection's write transaction.
        try:
            lock_governance_write(self.session)
            scope, _, _ = self.policy.approved(study)
            allocation, plan = self.allocation(command.allocation_id, study, course, scope)
            record = command.record
            if (
                allocation.subject_user_id != actor
                or record.subject_user_id != actor
                or not any(
                    s.stage == record.stage and s.form_id == record.form_version_id
                    for s in plan.stages
                )
            ):
                raise GovernanceDenied("study_self_assignment_denied")
            return self.instruments.collect(
                actor,
                study,
                course,
                record,
                participant_self=True,
                allocated_sequence=allocation.data["sequence_id"],
            )
        finally:
            self.session.rollback()

    def packet(self, actor, study, course, identity):
        scope = self.scope(actor, study, course, {"study.redacted_evidence"}, "rate")
        packet = self.event(identity, study, course, scope, "packet")
        if packet.data["reviewer_user_id"] != actor:
            raise GovernanceDenied("study_reviewer_assignment_denied")
        self.eligible(packet, {"study.redacted_evidence"})
        self.packet_source(packet, scope)
        _, plan = self.allocation(
            packet.data["allocation_id"], study, course, scope, {"study.redacted_evidence"}
        )
        return StudyPacketRead(
            id=packet.id,
            stage=packet.data["stage"],
            redacted_evidence=packet.data["redacted_evidence"],
            rubric=next(r for r in plan.rubrics if r.code == packet.data["rubric_code"]),
        )

    def project(self, row, fields):
        data = {
            **row.data,
            "record_id": row.id,
            "record_kind": row.kind,
            "participant_id": self.instruments._pseudonym(
                row.study_id, "participant", row.subject_user_id
            ),
        }
        if row.kind == "allocation":
            data["stage"] = None
        elif "study.condition" in fields:
            allocation = self.session.get(ResearchStudyEvent, row.data["allocation_id"])
            data["condition"] = allocation.data["condition"]
        return {field: data.get(field.removeprefix("study.")) for field in sorted(fields)}

    def read_events(self, actor, study, course):
        scope = self.scope(actor, study, course, STUDY_EXPORT_FIELDS, "read")
        result = []
        for index, row in enumerate(
            self.session.scalars(
                select(ResearchStudyEvent)
                .where(
                    ResearchStudyEvent.scope_id == scope.id,
                    ResearchStudyEvent.course_id == course,
                    ResearchStudyEvent.kind != "plan",
                )
                .order_by(ResearchStudyEvent.recorded_at)
                .limit(1001)
            )
        ):
            if index == 1000:
                raise GovernanceDenied("study_read_limit")
            if row.kind == "snapshot":
                continue
            try:
                self.study_readable(row.id, actor, study, course, STUDY_EXPORT_FIELDS, "read")
            except GovernanceDenied:
                continue
            result.append(self.project(row, STUDY_EXPORT_FIELDS))
        return result

    def read_plan(self, actor, study, course):
        scope = self.scope(actor, study, course, (), "prepare", live=False)
        row = self.session.scalar(
            select(ResearchStudyEvent)
            .where(
                ResearchStudyEvent.scope_id == scope.id,
                ResearchStudyEvent.course_id == course,
                ResearchStudyEvent.kind == "plan",
            )
            .order_by(ResearchStudyEvent.revision.desc())
            .limit(1)
        )
        return (
            None
            if row is None
            else {
                "id": row.id,
                "revision": row.revision,
                "plan": row.data,
                "production_active": False,
            }
        )

    def study_readable(self, identity, actor, study, course, fields, operation):
        scope = self.scope(actor, study, course, fields, operation)
        row = self.event(identity, study, course, scope)
        self.eligible(row, fields)
        self.plan(row.data["plan_id"], study, course, scope)
        if row.kind in {"packet", "rating", "outcome"}:
            packet = (
                row
                if row.kind == "packet"
                else self.event(row.data["packet_id"], study, course, scope, "packet")
            )
            self.packet_source(packet, scope)
        return row

    def instrument_projection(self, identity, actor, study, course, fields):
        scope = self.scope(actor, study, course, fields, "export")
        record = self.session.get(ResearchInstrumentRecord, identity)
        instrument_fields = fields & EXPORT_FIELDS
        form, binding = self.instruments._readable(
            actor, study, course, record, instrument_fields, "export"
        )
        allocations = self.session.scalars(
            select(ResearchStudyEvent).where(
                ResearchStudyEvent.scope_id == scope.id,
                ResearchStudyEvent.course_id == course,
                ResearchStudyEvent.kind == "allocation",
                ResearchStudyEvent.subject_user_id == binding.subject_user_id,
                ResearchStudyEvent.consent_id == record.consent_id,
            )
        ).all()
        allocation = next(
            (a for a in allocations if a.data["sequence_id"] == record.sequence_id), None
        )
        if allocation is None:
            raise GovernanceDenied("study_allocation_missing")
        _, plan = self.allocation(allocation.id, study, course, scope, fields)
        if not any(s.stage == record.stage and s.form_id == record.form_id for s in plan.stages):
            raise GovernanceDenied("study_stage_link_denied")
        if self.session.scalar(
            select(ResearchInstrumentRecord.id).where(
                ResearchInstrumentRecord.supersedes_id == identity
            )
        ):
            raise GovernanceDenied("study_evidence_superseded")
        shared = {
            **allocation.data,
            "record_id": record.id,
            "record_kind": "instrument_" + record.kind,
            "instrument_record_id": record.id,
            "stage": record.stage,
            "participant_id": binding.participant_id,
        }
        projection = self.instruments._project(study, record, form, binding, instrument_fields)
        return [
            {
                **row,
                **{
                    f: shared.get(f.removeprefix("study."))
                    for f in sorted(fields & STUDY_EXPORT_FIELDS)
                },
            }
            for row in projection
        ]

    def export(self, actor, study, course, command):
        fields = set(command.fields)
        scope = self.scope(actor, study, course, fields, "export")
        study_fields, instrument_fields = fields & STUDY_EXPORT_FIELDS, fields & EXPORT_FIELDS
        operational_fields = fields & OPERATIONAL_FIELDS
        collector = OperationalCollector(self)
        if operational_fields:
            collector.scope(actor, study, course, operational_fields, "export")
        if instrument_fields:
            self.instruments._scope(actor, study, course, instrument_fields, "export")
        included, excluded = [], {}
        rows = self.session.scalars(
            select(ResearchStudyEvent)
            .where(
                ResearchStudyEvent.scope_id == scope.id,
                ResearchStudyEvent.course_id == course,
                ResearchStudyEvent.kind != "plan",
            )
            .order_by(ResearchStudyEvent.id)
            .limit(1001)
        ).all()
        observations = (
            self.session.scalars(
                select(ResearchInstrumentRecord)
                .join(ResearchInstrumentForm)
                .where(
                    ResearchInstrumentForm.scope_id == scope.id,
                    ResearchInstrumentForm.course_id == course,
                    ResearchInstrumentRecord.stage.in_(command.stages),
                )
                .order_by(ResearchInstrumentRecord.id)
                .limit(1001)
            ).all()
            if instrument_fields
            else []
        )
        if len(rows) > 1000 or len(observations) > 1000:
            raise GovernanceDenied("study_export_limit")
        for row in rows if study_fields else []:
            if row.kind == "snapshot":
                continue
            if row.kind != "allocation" and row.data["stage"] not in command.stages:
                continue
            try:
                self.study_readable(row.id, actor, study, course, study_fields, "export")
                included.append(("study", row.id, [self.project(row, study_fields)]))
            except GovernanceDenied as error:
                excluded[str(error)] = excluded.get(str(error), 0) + 1
        superseded = {r.supersedes_id for r in observations if r.supersedes_id}
        for row in observations:
            if row.id in superseded:
                continue
            try:
                projected = self.instrument_projection(row.id, actor, study, course, fields)
                included.append(("instrument", row.id, projected))
            except GovernanceDenied as error:
                excluded[str(error)] = excluded.get(str(error), 0) + 1
        latest_snapshots = {}
        for row in rows:
            if row.kind == "snapshot" and row.data["stage"] in command.stages:
                previous = latest_snapshots.get(row.slot)
                if previous is None or row.revision > previous.revision:
                    latest_snapshots[row.slot] = row
        for row in latest_snapshots.values() if operational_fields else []:
            try:
                projected = collector.read(
                    actor, study, course, row.id, operational_fields, operation="export"
                )
                if study_fields:
                    self.study_readable(row.id, actor, study, course, study_fields, "export")
                included.append(
                    ("snapshot", row.id, [{**self.project(row, study_fields), **projected}])
                )
            except GovernanceDenied as error:
                excluded[str(error)] = excluded.get(str(error), 0) + 1
        export_id = self.instruments._audit(
            actor,
            study,
            scope.id,
            {
                "record_kind": "full_study",
                "phase": "prepared",
                "fields": sorted(fields),
                "stages": command.stages,
                "record_ids": [identity for _, identity, _ in included],
                "row_count": sum(len(rows) for _, _, rows in included),
                "projection_digest": digest(included),
                "excluded_counts": excluded,
            },
        )

        def check(kind, identity):
            self.scope(actor, study, course, fields, "export")
            if kind == "snapshot":
                collector.read(
                    actor, study, course, identity, operational_fields, operation="export"
                )
                if study_fields:
                    self.study_readable(identity, actor, study, course, study_fields, "export")
            elif kind == "instrument":
                self.instrument_projection(identity, actor, study, course, fields)
            else:
                self.study_readable(identity, actor, study, course, study_fields, "export")

        def stream():
            try:
                self.scope(actor, study, course, fields, "export")
                for kind, identity, _ in included:
                    check(kind, identity)
                yield (
                    csv_row(sorted(fields))
                    if command.format == "csv"
                    else b'{"schema_version":"learnlens.full-study-export.v1","records":['
                )
                first = True
                for kind, identity, rows in included:
                    for row in rows:
                        check(kind, identity)
                        yield (
                            csv_row(
                                [
                                    json.dumps(row.get(f), ensure_ascii=False, sort_keys=True)
                                    if isinstance(row.get(f), (dict, list))
                                    else row.get(f)
                                    for f in sorted(fields)
                                ]
                            )
                            if command.format == "csv"
                            else (("" if first else ",") + json.dumps(row, sort_keys=True)).encode()
                        )
                        first = False
                self.scope(actor, study, course, fields, "export")
                self.instruments._audit(
                    actor,
                    study,
                    scope.id,
                    {"record_kind": "full_study", "phase": "completed", "export_id": export_id},
                )
                if command.format == "json":
                    yield b"]}"
            except BaseException:
                self.instruments._audit(
                    actor,
                    study,
                    scope.id,
                    {"record_kind": "full_study", "phase": "interrupted", "export_id": export_id},
                )
                raise

        return InstrumentExport(
            stream(),
            sum(len(rows) for _, _, rows in included),
            export_id,
            "text/csv; charset=utf-8" if command.format == "csv" else "application/json",
        )
