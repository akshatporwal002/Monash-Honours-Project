"""Narrow operational manifests; materialization always rechecks authority and lineage."""

import re
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.research_instruments import (
    ResearchInstrumentBinding,
    ResearchInstrumentRecord,
    RestrictedInstrumentEvidence,
)
from app.models.research_study import ResearchStudyEvent
from app.models.user import User
from app.schemas.research_governance import OPERATIONAL_FIELDS
from app.schemas.research_operational import OperationalPreview, OperationalSelection
from app.services.research import governance
from app.services.research.governance import (
    GovernanceConflict,
    GovernanceDenied,
    lock_governance_write,
)
from app.services.research.instruments import digest
from app.services.research.operational_sources import RAW_FIELDS, OperationalSources


class OperationalCollector:
    def __init__(self, study_service):
        self.study = study_service
        self.session, self.policy = study_service.session, study_service.policy

    def scope(self, actor, study, course, fields, operation):
        if not governance.research_processing_approved():
            raise GovernanceDenied("research_governance_pending")
        scope, definition, _ = self.policy.approved(study)
        self.policy.require_release(study)
        if not {"study_instruments", "study_operational_evidence"} <= set(definition.purposes):
            raise GovernanceDenied("operational_purpose_not_approved")
        if "study_operational_manifests" not in {r.record_class for r in definition.retention}:
            raise GovernanceDenied("operational_retention_missing")
        if not fields or not set(fields) <= OPERATIONAL_FIELDS:
            raise GovernanceDenied("operational_fields_denied")
        self.policy.grant(study, course, actor, set(fields) | {"operational." + operation})
        return scope

    def sources(self, actor, study, course, command, operation):
        fields = set(command.fields)
        scope = self.scope(actor, study, course, fields, operation)
        allocation, plan = self.study.allocation(
            command.allocation_id, study, course, scope, fields
        )
        _, consent = self.policy.participant(
            study,
            course,
            allocation.subject_user_id,
            fields=fields,
            purposes={"study_instruments", "study_operational_evidence"},
        )
        record = self.session.get(ResearchInstrumentRecord, command.instrument_record_id)
        binding = self.session.get(ResearchInstrumentBinding, record.binding_id) if record else None
        if (
            not record
            or not binding
            or (
                binding.subject_user_id,
                binding.scope_id,
                binding.course_id,
                record.sequence_id,
                record.consent_id,
            )
            != (
                allocation.subject_user_id,
                scope.id,
                course,
                allocation.data["sequence_id"],
                consent.id,
            )
        ):
            raise GovernanceDenied("operational_anchor_denied")
        from app.services.research.disposal import disposed

        if disposed(self.policy, study, record.id):
            raise GovernanceDenied("instrument_evidence_disposed")
        self.study.instruments._form(record.form_id, study, course, scope)
        raw = self.session.scalar(
            select(RestrictedInstrumentEvidence).where(
                RestrictedInstrumentEvidence.record_id == record.id
            )
        )
        restricted = raw.response_text if raw else {}
        if (raw and digest(restricted) != raw.content_digest) or digest(
            [record.data, restricted, record.links]
        ) != record.content_digest:
            raise GovernanceDenied("instrument_integrity_denied")
        if not any(s.stage == record.stage and s.form_id == record.form_id for s in plan.stages):
            raise GovernanceDenied("study_stage_link_denied")
        if self.session.scalar(
            select(ResearchInstrumentRecord.id).where(
                ResearchInstrumentRecord.supersedes_id == record.id
            )
        ):
            raise GovernanceDenied("study_evidence_superseded")
        return (
            scope,
            allocation,
            plan,
            record,
            OperationalSources(self.study, study, course, allocation, record),
        )

    def redacted(self, text, approval, source, plan, subject):
        if (
            approval.source_digest != source.content_digest
            or approval.rule_reference != plan.redaction_rule_reference
        ):
            raise GovernanceDenied("operational_redaction_stale")
        spans = sorted(approval.spans, key=lambda span: span.start)
        previous, chunks = 0, []
        for span in spans:
            if span.start < previous or span.end > len(text):
                raise GovernanceDenied("operational_redaction_spans_invalid")
            chunks += [
                text[previous : span.start],
                "[REDACTED]" + "\n" * text[span.start : span.end].count("\n"),
            ]
            previous = span.end
        chunks.append(text[previous:])
        value = "".join(chunks)
        user = self.session.get(User, subject)
        for identity in (user.email, user.full_name) if user else ():
            if identity and len(identity) >= 3:
                value = re.sub(re.escape(identity), "[REDACTED]", value, flags=re.IGNORECASE)
        for pattern in (
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            r"(?i)\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{8,}|AKIA[A-Z0-9]{12,}|Bearer\s+[^\s\"']+)",
            r"(?im)(?:api[_-]?key|password|secret|authorization)\s*[:=][^\r\n]+",
            r'(?im)"(?:user_id|student_id|learner_id|actor_id|email|full_name|api_key|password|secret|authorization)"\s*:\s*(?:"[^"\r\n]*"|[0-9]+)',
            r"https?://[^\s\"'<>]+",
            r"(?:[A-Za-z]:[\\/]|/(?:Users|home|tmp)/)[^\s\"'<>]+",
        ):
            value = re.sub(pattern, "[REDACTED]", value)
        return value

    def materialize(self, actor, study, course, command, operation, *, preview=False):
        scope, allocation, plan, record, sources = self.sources(
            actor, study, course, command, operation
        )
        approvals = {r.field: r for r in command.redactions}
        fields = {}
        for field in sorted(set(command.fields)):
            source = sources.value(field)
            if len(str(source.value)) > 2_000_000:
                raise GovernanceDenied("operational_field_size_limit")
            value, missing = source.value, source.missing
            if field in RAW_FIELDS and value is not None:
                if field not in approvals:
                    if not preview:
                        raise GovernanceDenied("operational_redaction_required")
                    value, missing = None, "redaction_required"
                else:
                    value = self.redacted(
                        value, approvals[field], source, plan, allocation.subject_user_id
                    )
            fields[field] = {
                "value": value,
                "missing_reason": missing,
                "source_digest": source.content_digest,
                "source_references": [sources.ref("source", ref) for ref in source.references],
                "adapter_version": source.version,
            }
        return scope, allocation, record, fields

    def preview(self, actor, study, course, command):
        _, _, _, fields = self.materialize(actor, study, course, command, "read", preview=True)
        return OperationalPreview(fields=fields)

    def capture(self, actor, study, course, command):
        try:
            lock_governance_write(self.session)
            scope, allocation, record, fields = self.materialize(
                actor, study, course, command, "collect"
            )
            request_digest = digest([study, course, command.model_dump(mode="json")])
            prior = self.study.instruments._replay(
                ResearchStudyEvent, actor, command.request_key, request_digest
            )
            if prior:
                self.read(actor, study, course, prior.id, command.fields, operation="collect")
                return self.study.receipt(prior)
            slot = "snapshot:" + record.id
            latest = (
                self.session.scalar(
                    select(ResearchStudyEvent.revision)
                    .where(
                        ResearchStudyEvent.scope_id == scope.id,
                        ResearchStudyEvent.course_id == course,
                        ResearchStudyEvent.slot == slot,
                    )
                    .order_by(ResearchStudyEvent.revision.desc())
                    .limit(1)
                )
                or 0
            )
            if command.expected_revision != latest:
                raise GovernanceConflict("operational_snapshot_revision_changed")
            data = {
                "allocation_id": allocation.id,
                "plan_id": allocation.data["plan_id"],
                "stage": record.stage,
                "sequence_id": record.sequence_id,
                "instrument_record_id": record.id,
                "selection": command.model_dump(
                    mode="json", exclude={"request_key", "expected_revision"}
                ),
                "manifest": {
                    field: {k: v for k, v in value.items() if k != "value"}
                    for field, value in fields.items()
                },
            }
            row = ResearchStudyEvent(
                id=str(uuid4()),
                study_id=study,
                course_id=course,
                scope_id=scope.id,
                kind="snapshot",
                slot=slot,
                revision=latest + 1,
                subject_user_id=allocation.subject_user_id,
                consent_id=allocation.consent_id,
                data=data,
                content_digest=digest(data),
                actor_user_id=actor,
                request_key=command.request_key,
                request_digest=request_digest,
                recorded_at=self.policy.now(),
            )
            self.session.add(row)
            self.session.commit()
            return self.study.receipt(row)
        except IntegrityError:
            self.session.rollback()
            raise GovernanceConflict("operational_snapshot_conflict") from None
        finally:
            self.session.rollback()

    def read(self, actor, study, course, identity, fields, *, operation="read"):
        scope = self.scope(actor, study, course, fields, operation)
        row = self.study.event(identity, study, course, scope, "snapshot")
        self.study.eligible(row, fields)
        if not set(fields) <= set(row.data["manifest"]):
            raise GovernanceDenied("operational_field_not_captured")
        selection = OperationalSelection.model_validate(
            {
                **row.data["selection"],
                "fields": list(fields),
                "redactions": [
                    r for r in row.data["selection"]["redactions"] if r["field"] in fields
                ],
            }
        )
        _, _, _, projected = self.materialize(actor, study, course, selection, operation)
        for field, current in projected.items():
            expected = row.data["manifest"][field]
            if any(
                current[key] != expected[key]
                for key in ("source_digest", "adapter_version", "source_references")
            ):
                raise GovernanceDenied("operational_source_changed")
        return projected
