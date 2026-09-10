"""Scoped v2 projection over existing technical records; no raw responses or prose."""

import csv
import io
import json
from collections import Counter
from uuid import uuid4

from app.models.research_governance import ResearchExportEligibility
from app.schemas.research_export import ResearchExportFormat, _contains_sensitive_value
from app.services.research.governance import GovernanceDenied, ResearchGovernanceService
from app.services.research_export import (
    PreparedResearchExport,
    ResearchExportError,
    ResearchExportTooLargeError,
    _csv_value,
)
from app.services.research_export_repository import SqlAlchemyResearchExportRepository


class ResearchExportGovernanceError(ResearchExportError):
    """The requested study, participant or researcher scope does not allow release."""


class GovernedResearchExportService:
    def __init__(self, session, actor_id, study_id, fields, *, row_limit=100_000):
        self.session = session
        self.actor_id = actor_id
        self.study_id = study_id
        self.fields = tuple(sorted(set(fields or ())))
        self.row_limit = row_limit
        self.policy = ResearchGovernanceService(session)

    def _authorize(self, course_ids):
        from app.services.research.governance import research_processing_approved

        if not research_processing_approved():
            raise GovernanceDenied("research_governance_pending")
        if (
            not self.study_id
            or not self.fields
            or any(field.startswith("processing.") for field in self.fields)
        ):
            raise GovernanceDenied("explicit_study_and_export_fields_required")
        return [
            self.policy.grant(self.study_id, course, self.actor_id, self.fields).id
            for course in course_ids
        ]

    def _audit(self, scope_id, manifest):
        receipt = ResearchExportEligibility(
            id=str(uuid4()),
            study_id=self.study_id or "unspecified",
            scope_id=scope_id,
            actor_user_id=self.actor_id,
            manifest=manifest,
        )
        self.session.add(receipt)
        self.session.commit()  # Durable before any response bytes; failure closes export.
        return receipt.id

    def prepare(
        self, *, export_format, filters, actor_reference, correlation_id, generated_at=None
    ):
        del actor_reference, generated_at
        courses = sorted(
            set(filters.course_ids)
            & ({filters.course_id} if filters.course_id else set(filters.course_ids))
        )
        scope_id = None
        try:
            if not courses:
                raise GovernanceDenied("course_scope_required")
            grants = self._authorize(courses)
            scope, _, _ = self.policy.approved(self.study_id)
            scope_id = scope.id
            repository = SqlAlchemyResearchExportRepository(self.session)
            included, excluded = [], Counter()
            # Limit inspected rows as well as exported rows to bound synchronous work.
            for index, row in enumerate(
                repository._iter_rows(filters, batch_size=250, include_legacy=True)
            ):
                if index >= self.row_limit:
                    raise ResearchExportTooLargeError("research export row limit exceeded")
                try:
                    binding = self.policy.require_case(
                        row.case_id, fields=self.fields, purposes=("technical_pair",)
                    )
                    if (
                        binding.scope_id != scope_id
                        or binding.course_id != row.course_id
                        or binding.pseudonymous_user_id != row.pseudonymous_user_id
                    ):
                        raise GovernanceDenied("case_scope_mismatch")
                    record = repository._safe_record(row)
                    if record is None:
                        raise GovernanceDenied("unsafe_legacy_record")
                    raw = record.model_dump(mode="json")
                    projected = {field: raw[field] for field in self.fields}
                    if any(
                        isinstance(value, str) and _contains_sensitive_value(value)
                        for value in projected.values()
                    ):
                        raise GovernanceDenied("unsafe_legacy_record")
                    included.append((row.case_id, binding.consent_id, projected))
                except GovernanceDenied as error:
                    excluded[str(error)] += 1
            export_id = self._audit(
                scope_id,
                {
                    "phase": "prepared",
                    "fields": list(self.fields),
                    "courses": courses,
                    "grant_ids": grants,
                    "correlation_id": correlation_id,
                    "included": [
                        {"case_id": case, "consent_id": consent} for case, consent, _ in included
                    ],
                    "excluded_counts": dict(excluded),
                    "record_count": len(included),
                },
            )
        except GovernanceDenied as error:
            self._audit(
                scope_id,
                {
                    "phase": "denied",
                    "reason": str(error),
                    "fields": list(self.fields),
                    "correlation_id": correlation_id,
                },
            )
            raise ResearchExportGovernanceError("research governance denied export") from None
        return PreparedResearchExport(
            export_id=export_id,
            filename=f"research-v2-{export_id}.{export_format.value}",
            media_type="text/csv; charset=utf-8"
            if export_format == ResearchExportFormat.CSV
            else "application/json",
            body=self._stream(export_id, scope_id, courses, included, export_format),
            record_count=len(included),
        )

    def _stream(self, export_id, scope_id, courses, included, export_format):
        try:
            self._authorize(courses)
            # Preflight every included participant before even the header is released.
            for case, _, _ in included:
                self.policy.require_case(case, fields=self.fields, purposes=("technical_pair",))
            if export_format == ResearchExportFormat.CSV:
                yield self._csv(dict(zip(self.fields, self.fields, strict=True)), bom=True)
            else:
                yield (
                    json.dumps(
                        {
                            "schema_version": "learnlens.research-export.v2",
                            "record_kind": "technical_feedback_pair",
                            "study_id": self.study_id,
                            "scope_id": scope_id,
                            "export_id": export_id,
                            "fields": self.fields,
                            "record_count": len(included),
                        }
                    )[:-1]
                    + ',"records":['
                ).encode()
            for index, (case, _, projected) in enumerate(included):
                self._authorize(courses)
                self.policy.require_case(case, fields=self.fields, purposes=("technical_pair",))
                if export_format == ResearchExportFormat.CSV:
                    yield self._csv(projected)
                else:
                    yield (("," if index else "") + json.dumps(projected, sort_keys=True)).encode()
            self._authorize(courses)
            self._audit(scope_id, {"phase": "completed", "export_id": export_id})
            if export_format == ResearchExportFormat.JSON:
                yield b"]}"
        except BaseException:
            self._audit(scope_id, {"phase": "interrupted", "export_id": export_id})
            raise

    def _csv(self, row, *, bom=False):
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
        writer.writerow([_csv_value(row[field]) for field in self.fields])
        return buffer.getvalue().encode("utf-8-sig" if bom else "utf-8")
