"""Governed synthetic instrument foundation; no teaching, grading, or allocation writes."""

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from typing import get_args
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models.assessment import AssessmentAttempt
from app.models.lms import LearningOutcome, SubmissionAttempt
from app.models.persistence import LearningTask
from app.models.research_governance import ResearchExportEligibility
from app.models.research_instruments import (
    ResearchInstrumentBinding,
    ResearchInstrumentForm,
    ResearchInstrumentFreeze,
    ResearchInstrumentRecord,
    RestrictedInstrumentEvidence,
)
from app.schemas.research_instruments import (
    ExportField,
    FormRead,
    InstrumentDefinition,
    InstrumentReceipt,
)
from app.services.learning_events import HmacSha256Pseudonymizer
from app.services.research import governance
from app.services.research.governance import (
    GovernanceConflict,
    GovernanceDenied,
    ResearchGovernanceService,
    lock_governance_write,
    utc,
)
from app.services.research_export import _csv_value

BASE_FIELDS = frozenset(
    "instrument." + key
    for key in (
        "record_id",
        "participant_id",
        "course_ref",
        "sequence_id",
        "form_id",
        "form_version",
        "stage",
        "event_kind",
        "revision",
        "supersedes_id",
    )
)
EXPORT_FIELDS = frozenset(get_args(ExportField))


def digest(value):
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
            ).encode()
        ).hexdigest()
    )


@dataclass(frozen=True)
class InstrumentExport:
    body: object
    record_count: int
    export_id: str
    media_type: str


class ResearchInstrumentService:
    def __init__(self, session, *, now=None):
        self.session = session
        self.policy = ResearchGovernanceService(session, now=now)

    def _scope(self, actor_id, study_id, course_id, fields, operation, *, live=True):
        if live and not governance.research_processing_approved():
            raise GovernanceDenied("research_governance_pending")
        scope, definition, _ = self.policy.approved(study_id)
        if "study_instruments" not in definition.purposes:
            raise GovernanceDenied("instrument_purpose_not_approved")
        self.policy.grant(study_id, course_id, actor_id, set(fields) | {"instrument." + operation})
        return scope

    def _pseudonym(self, study_id, kind, value):
        secret = settings.learning_event_pseudonym_secret
        if secret is None:
            raise GovernanceDenied("pseudonym_key_unavailable")
        return HmacSha256Pseudonymizer(secret.get_secret_value()).pseudonymize(
            f"study:{study_id}:instrument:{kind}", str(value)
        )

    def _form(self, form_id, study_id, course_id, scope):
        form = self.session.get(ResearchInstrumentForm, form_id)
        if form is None or (form.study_id, form.course_id, form.scope_id) != (
            study_id,
            course_id,
            scope.id,
        ):
            raise GovernanceDenied("instrument_scope_denied")
        if digest(form.definition) != form.content_digest:
            raise GovernanceDenied("instrument_integrity_denied")
        InstrumentDefinition.model_validate(form.definition)
        return form

    def _replay(self, model, actor_id, request_key, request_digest):
        row = self.session.scalar(
            select(model).where(model.actor_user_id == actor_id, model.request_key == request_key)
        )
        if row and row.request_digest != request_digest:
            raise GovernanceConflict("request_key_reused")
        return row

    def save_form(self, actor_id, study_id, course_id, instrument_key, command):
        try:
            lock_governance_write(self.session)
            scope = self._scope(actor_id, study_id, course_id, (), "define", live=False)
            request_digest = digest(
                [study_id, course_id, instrument_key, command.model_dump(mode="json")]
            )
            prior = self._replay(
                ResearchInstrumentForm, actor_id, command.request_key, request_digest
            )
            if prior:
                self._form(prior.id, study_id, course_id, scope)
                return self.form_read(prior)
            latest = self.session.scalar(
                select(ResearchInstrumentForm)
                .where(
                    ResearchInstrumentForm.study_id == study_id,
                    ResearchInstrumentForm.course_id == course_id,
                    ResearchInstrumentForm.instrument_key == instrument_key,
                )
                .order_by(ResearchInstrumentForm.version.desc())
                .limit(1)
            )
            if command.expected_version != (latest.version if latest else 0):
                raise GovernanceConflict("instrument_version_changed")
            definition = command.definition.model_dump(mode="json")
            form = ResearchInstrumentForm(
                study_id=study_id,
                course_id=course_id,
                scope_id=scope.id,
                instrument_key=instrument_key,
                version=command.expected_version + 1,
                definition=definition,
                content_digest=digest(definition),
                actor_user_id=actor_id,
                request_key=command.request_key,
                request_digest=request_digest,
                recorded_at=self.policy.now(),
            )
            self.session.add(form)
            self.session.commit()
            return self.form_read(form)
        except IntegrityError:
            self.session.rollback()
            raise GovernanceConflict("instrument_version_changed") from None
        except Exception:
            self.session.rollback()
            raise
        finally:
            self.session.rollback()

    def form_read(self, form):
        frozen = self.session.scalar(
            select(ResearchInstrumentFreeze.id).where(ResearchInstrumentFreeze.form_id == form.id)
        )
        return FormRead(
            id=form.id,
            version=form.version,
            content_digest=form.content_digest,
            definition=form.definition,
            frozen_for_synthetic_validation=frozen is not None,
        )

    def read_form(self, actor_id, study_id, course_id, form_id):
        scope = self._scope(actor_id, study_id, course_id, (), "define", live=False)
        return self.form_read(self._form(form_id, study_id, course_id, scope))

    def freeze_form(self, actor_id, study_id, course_id, form_id, command):
        try:
            lock_governance_write(self.session)
            scope = self._scope(actor_id, study_id, course_id, (), "define", live=False)
            form = self._form(form_id, study_id, course_id, scope)
            request_digest = digest([study_id, course_id, form_id, command.model_dump(mode="json")])
            existing = self._replay(
                ResearchInstrumentFreeze, actor_id, command.request_key, request_digest
            )
            if not existing:
                if form.content_digest != command.content_digest:
                    raise GovernanceConflict("instrument_digest_changed")
                self.session.add(
                    ResearchInstrumentFreeze(
                        form_id=form.id,
                        actor_user_id=actor_id,
                        request_key=command.request_key,
                        request_digest=request_digest,
                        synthetic_review_reference=command.synthetic_review_reference,
                        recorded_at=self.policy.now(),
                    )
                )
                self.session.commit()
            return self.form_read(form)
        except IntegrityError:
            self.session.rollback()
            raise GovernanceConflict("instrument_already_frozen") from None
        except Exception:
            self.session.rollback()
            raise
        finally:
            self.session.rollback()

    def _fields(self, command):
        fields = set(BASE_FIELDS)
        for key, value in command.links.model_dump().items():
            if value is not None:
                fields.add("instrument." + key.replace("_id", "_ref"))
        if command.answers:
            fields.add("instrument.item_id")
        for answer in command.answers:
            for key in ("choice_code", "integer_value", "response_text", "missing_reason"):
                if getattr(answer, key) is not None:
                    fields.add("instrument." + key)
        for key in ("reason_code", "missing_reason", "correction_reason_code"):
            if getattr(command, key) is not None:
                fields.add("instrument." + key)
        return fields

    def _validate_links(self, command, course_id, consent_time):
        links = command.links
        task = self.session.get(LearningTask, links.task_id) if links.task_id else None
        outcome = self.session.get(LearningOutcome, links.outcome_id) if links.outcome_id else None
        if links.task_id and (not task or task.course_id != course_id):
            raise GovernanceDenied("learning_link_scope_denied")
        if links.outcome_id and (
            not outcome
            or outcome.module.course_id != course_id
            or (task and task.learning_outcome_id != outcome.id)
        ):
            raise GovernanceDenied("learning_link_scope_denied")
        if links.response_id:
            response = self.session.get(SubmissionAttempt, links.response_id)
            if (
                not task
                or not response
                or (response.student_id, response.task_id) != (command.subject_user_id, task.id)
            ):
                raise GovernanceDenied("learning_link_scope_denied")
            if utc(response.submitted_at) < utc(consent_time):
                raise GovernanceDenied("historical_use_not_approved")
        formal_response = command.kind == "response" and command.stage in {
            "T1_FORMAL_SUPPORTED",
            "T1_FORMAL_UNAIDED",
        }
        if formal_response and (
            not links.response_id
            or not self.session.scalar(
                select(AssessmentAttempt.id).where(
                    AssessmentAttempt.response_version_id == links.response_id,
                    AssessmentAttempt.course_id == course_id,
                    AssessmentAttempt.student_id == command.subject_user_id,
                )
            )
        ):
            raise GovernanceDenied("formal_observation_reference_required")

    def _validate_data(self, command, definition):
        if command.stage not in definition.stages:
            raise GovernanceDenied("instrument_stage_denied")
        for code in (command.reason_code, command.correction_reason_code):
            if code is not None and code not in definition.event_reason_codes:
                raise GovernanceDenied("instrument_reason_denied")
        items = {i.item_id: i for i in definition.items}
        if command.kind == "response" and {a.item_id for a in command.answers} != set(items):
            raise GovernanceDenied("instrument_items_incomplete")
        answers, restricted = [], {}
        for answer in command.answers:
            item = items[answer.item_id]
            if answer.missing_reason is None:
                expected = {
                    "choice": "choice_code",
                    "integer": "integer_value",
                    "text": "response_text",
                }[item.response_type]
                value = getattr(answer, expected)
                if (
                    value is None
                    or (item.response_type == "choice" and value not in item.choices)
                    or (
                        item.response_type == "integer"
                        and not item.minimum <= value <= item.maximum
                    )
                    or (item.response_type == "text" and len(value) > item.max_characters)
                ):
                    raise GovernanceDenied("instrument_answer_denied")
            projected = answer.model_dump(exclude={"response_text"})
            if answer.response_text is not None:
                restricted[answer.item_id] = answer.response_text
            answers.append(projected)
        return {
            "answers": answers,
            "reason_code": command.reason_code,
            "missing_reason": command.missing_reason,
        }, restricted

    def collect(
        self,
        actor_id,
        study_id,
        course_id,
        command,
        *,
        participant_self=False,
        allocated_sequence=None,
    ):
        try:
            lock_governance_write(self.session)
            fields = self._fields(command)
            collector_id = actor_id
            if participant_self:
                if command.subject_user_id != actor_id:
                    raise GovernanceDenied("participant_self_required")
                _, definition, _ = self.policy.approved(study_id)
                collector_id = definition.processing_researcher_id
            scope = self._scope(collector_id, study_id, course_id, fields, "collect")
            _, consent = self.policy.participant(
                study_id,
                course_id,
                command.subject_user_id,
                fields=fields,
                purposes={"study_instruments"},
            )
            form = self._form(command.form_version_id, study_id, course_id, scope)
            if not self.session.scalar(
                select(ResearchInstrumentFreeze.id).where(
                    ResearchInstrumentFreeze.form_id == form.id
                )
            ):
                raise GovernanceDenied("instrument_not_frozen")
            self._validate_links(command, course_id, consent.recorded_at)
            data, restricted = self._validate_data(
                command, InstrumentDefinition.model_validate(form.definition)
            )
            request_digest = digest([study_id, course_id, command.model_dump(mode="json")])
            prior = self._replay(
                ResearchInstrumentRecord, actor_id, command.request_key, request_digest
            )
            if prior:
                if prior.consent_id != consent.id:
                    raise GovernanceDenied("record_consent_version_changed")
                return self.receipt(prior)
            binding = self.session.scalar(
                select(ResearchInstrumentBinding).where(
                    ResearchInstrumentBinding.scope_id == scope.id,
                    ResearchInstrumentBinding.course_id == course_id,
                    ResearchInstrumentBinding.subject_user_id == command.subject_user_id,
                )
            )
            if binding is None:
                binding = ResearchInstrumentBinding(
                    scope_id=scope.id,
                    course_id=course_id,
                    subject_user_id=command.subject_user_id,
                    participant_id=self._pseudonym(
                        study_id, "participant", command.subject_user_id
                    ),
                )
                self.session.add(binding)
                self.session.flush()
            sequence = allocated_sequence or self._pseudonym(
                study_id, "sequence", f"{binding.participant_id}:{command.sequence_key}"
            )
            previous = (
                self.session.get(ResearchInstrumentRecord, command.supersedes_id)
                if command.supersedes_id
                else None
            )
            if command.supersedes_id:
                if previous is None or (
                    previous.form_id,
                    previous.binding_id,
                    previous.stage,
                    previous.kind,
                    previous.sequence_id,
                    previous.consent_id,
                ) != (form.id, binding.id, command.stage, command.kind, sequence, consent.id):
                    raise GovernanceDenied("correction_scope_denied")
                if self.session.scalar(
                    select(ResearchInstrumentRecord.id).where(
                        ResearchInstrumentRecord.supersedes_id == previous.id
                    )
                ):
                    raise GovernanceConflict("correction_revision_changed")
            record = ResearchInstrumentRecord(
                form_id=form.id,
                binding_id=binding.id,
                consent_id=consent.id,
                series_id=previous.series_id if previous else str(uuid4()),
                revision=previous.revision + 1 if previous else 1,
                supersedes_id=command.supersedes_id,
                correction_reason_code=command.correction_reason_code,
                sequence_id=sequence,
                stage=command.stage,
                kind=command.kind,
                links=command.links.model_dump(exclude_none=True),
                data=data,
                content_digest=digest(
                    [data, restricted, command.links.model_dump(exclude_none=True)]
                ),
                actor_user_id=actor_id,
                request_key=command.request_key,
                request_digest=request_digest,
                recorded_at=self.policy.now(),
            )
            self.session.add(record)
            self.session.flush()
            if restricted:
                self.session.add(
                    RestrictedInstrumentEvidence(
                        record_id=record.id,
                        response_text=restricted,
                        content_digest=digest(restricted),
                    )
                )
            self.session.commit()
            return self.receipt(record)
        except IntegrityError:
            self.session.rollback()
            raise GovernanceConflict("instrument_record_conflict") from None
        except Exception:
            self.session.rollback()
            raise
        finally:
            self.session.rollback()

    @staticmethod
    def receipt(record):
        return InstrumentReceipt(
            id=record.id, revision=record.revision, recorded_at=utc(record.recorded_at)
        )

    def _readable(self, actor_id, study_id, course_id, record, fields, operation):
        scope = self._scope(actor_id, study_id, course_id, fields, operation)
        if not fields or not set(fields) <= EXPORT_FIELDS or record is None:
            raise GovernanceDenied("instrument_fields_denied")
        form = self._form(record.form_id, study_id, course_id, scope)
        binding = self.session.get(ResearchInstrumentBinding, record.binding_id)
        if binding.scope_id != scope.id or binding.course_id != course_id:
            raise GovernanceDenied("instrument_scope_denied")
        _, consent = self.policy.participant(
            study_id,
            course_id,
            binding.subject_user_id,
            fields=fields,
            purposes={"study_instruments"},
        )
        if consent.id != record.consent_id or utc(record.recorded_at) < utc(consent.recorded_at):
            raise GovernanceDenied("record_consent_version_changed")
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
        return form, binding

    def _project(self, study_id, record, form, binding, fields):
        shared = {
            "record_id": record.id,
            "participant_id": binding.participant_id,
            "course_ref": self._pseudonym(study_id, "course", form.course_id),
            "sequence_id": record.sequence_id,
            "form_id": form.id,
            "form_version": form.version,
            "stage": record.stage,
            "event_kind": record.kind,
            "reason_code": record.data["reason_code"],
            "revision": record.revision,
            "supersedes_id": record.supersedes_id,
            "correction_reason_code": record.correction_reason_code,
        }
        for key in ("outcome", "task", "response"):
            value = record.links.get(key + "_id")
            shared[key + "_ref"] = self._pseudonym(study_id, key, value) if value else None
        rows = []
        for answer in record.data["answers"] or [{"missing_reason": record.data["missing_reason"]}]:
            value = {**shared, **answer}
            rows.append(
                {
                    field: value.get(field.removeprefix("instrument."))
                    for field in sorted(set(fields))
                }
            )
        return rows

    def read(self, actor_id, study_id, course_id, record_id, fields):
        record = self.session.get(ResearchInstrumentRecord, record_id)
        form, binding = self._readable(actor_id, study_id, course_id, record, fields, "read")
        return self._project(study_id, record, form, binding, fields)

    def _audit(self, actor_id, study_id, scope_id, manifest):
        record = ResearchExportEligibility(
            study_id=study_id,
            scope_id=scope_id,
            actor_user_id=actor_id,
            manifest={"record_kind": "study_instruments", **manifest},
            recorded_at=self.policy.now(),
        )
        self.session.add(record)
        self.session.commit()
        return record.id

    def export(self, actor_id, study_id, course_id, command):
        fields = tuple(sorted(set(command.fields)))
        if not fields or not set(fields) <= EXPORT_FIELDS:
            raise GovernanceDenied("instrument_fields_denied")
        scope = self._scope(actor_id, study_id, course_id, fields, "export")
        records = list(
            self.session.scalars(
                select(ResearchInstrumentRecord)
                .join(ResearchInstrumentForm)
                .where(
                    ResearchInstrumentForm.study_id == study_id,
                    ResearchInstrumentForm.course_id == course_id,
                    ResearchInstrumentRecord.stage.in_(command.stages),
                )
                .order_by(ResearchInstrumentRecord.series_id, ResearchInstrumentRecord.revision)
                .limit(1001)
            )
        )
        if len(records) > 1000:
            raise GovernanceDenied("instrument_export_limit")
        superseded = {r.supersedes_id for r in records if r.supersedes_id}
        included, excluded = [], {}
        for record in records:
            if record.id in superseded:
                continue
            try:
                form, binding = self._readable(
                    actor_id, study_id, course_id, record, fields, "export"
                )
                included.append((record.id, self._project(study_id, record, form, binding, fields)))
            except GovernanceDenied as error:
                excluded[str(error)] = excluded.get(str(error), 0) + 1
        export_id = self._audit(
            actor_id,
            study_id,
            scope.id,
            {
                "phase": "prepared",
                "fields": fields,
                "course_id": course_id,
                "stages": sorted(set(command.stages)),
                "row_count": sum(len(rows) for _, rows in included),
                "projection_digest": digest(included),
                "record_ids": [identity for identity, _ in included],
                "excluded_counts": excluded,
            },
        )
        count = sum(len(rows) for _, rows in included)

        def stream():
            try:
                self._scope(actor_id, study_id, course_id, fields, "export")
                for identity, _ in included:
                    self._readable(
                        actor_id,
                        study_id,
                        course_id,
                        self.session.get(ResearchInstrumentRecord, identity),
                        fields,
                        "export",
                    )
                if command.format == "csv":
                    yield csv_row(fields)
                else:
                    yield b'{"schema_version":"learnlens.instrument-export.v1","records":['
                first = True
                for identity, rows in included:
                    self._readable(
                        actor_id,
                        study_id,
                        course_id,
                        self.session.get(ResearchInstrumentRecord, identity),
                        fields,
                        "export",
                    )
                    for row in rows:
                        self._readable(
                            actor_id,
                            study_id,
                            course_id,
                            self.session.get(ResearchInstrumentRecord, identity),
                            fields,
                            "export",
                        )
                        if command.format == "csv":
                            yield csv_row([row[f] for f in fields])
                        else:
                            yield (
                                ("" if first else ",")
                                + json.dumps(
                                    row, sort_keys=True, ensure_ascii=False, separators=(",", ":")
                                )
                            ).encode()
                            first = False
                self._scope(actor_id, study_id, course_id, fields, "export")
                self._audit(
                    actor_id, study_id, scope.id, {"phase": "completed", "export_id": export_id}
                )
                if command.format == "json":
                    yield b"]}"
            except BaseException:
                self._audit(
                    actor_id, study_id, scope.id, {"phase": "interrupted", "export_id": export_id}
                )
                raise

        return InstrumentExport(
            stream(),
            count,
            export_id,
            "text/csv; charset=utf-8" if command.format == "csv" else "application/json",
        )


def csv_row(values):
    buffer = io.StringIO(newline="")
    csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\r\n").writerow(
        [_csv_value(value) for value in values]
    )
    return buffer.getvalue().encode()
