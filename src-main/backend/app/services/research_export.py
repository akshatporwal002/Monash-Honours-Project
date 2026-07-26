from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import uuid4

from app.models.audit import AuditAction, AuditOutcome
from app.schemas.audit import AuditEventCommand
from app.schemas.research_export import (
    ResearchExportFilters,
    ResearchExportFormat,
    ResearchExportRecord,
    ResearchJsonEnvelope,
)
from app.services.audit import AuditRecorder

RESEARCH_EXPORT_COLUMNS = (
    "case_id",
    "pseudonymous_user_id",
    "course_id",
    "task_id",
    "task_type",
    "submission_reference",
    "experimental_condition",
    "input_reference",
    "retrieved_sources",
    "simulation_reference",
    "generated_output",
    "judge_decision",
    "judge_reason",
    "correctness_score",
    "relevance_score",
    "grounding_score",
    "actionability_score",
    "safety_score",
    "unsupported_claim_count",
    "latency_ms",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "estimated_cost",
    "regeneration_count",
    "fallback_used",
    "status",
    "failure_category",
    "comparable",
    "usage_complete",
    "measurement_schema_version",
    "created_at",
    "completed_at",
)


class ResearchExportError(Exception):
    """Base controlled research-export error."""


class ResearchExportTooLargeError(ResearchExportError):
    """The synchronous row limit was exceeded."""


class ResearchExportRepository(Protocol):
    def count_for_export(
        self,
        filters: ResearchExportFilters,
        *,
        limit: int,
    ) -> int: ...

    def iter_for_export(
        self,
        filters: ResearchExportFilters,
        *,
        batch_size: int,
    ) -> Iterator[ResearchExportRecord]: ...


def _utc_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _neutralize_formula(value: str) -> str:
    trimmed = value.lstrip(" \t\r\n")
    if value and (value[0] in "\t\r\n" or (trimmed and trimmed[0] in "=+-@")):
        return f"'{value}"
    return value


def _csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return _utc_iso(value)
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list | dict):
        return _canonical_json(value)
    enum_value = getattr(value, "value", value)
    return _neutralize_formula(str(enum_value))


def iter_csv(records: Iterable[ResearchExportRecord]) -> Iterator[bytes]:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=RESEARCH_EXPORT_COLUMNS,
        extrasaction="ignore",
        quoting=csv.QUOTE_ALL,
        lineterminator="\r\n",
    )
    writer.writeheader()
    yield buffer.getvalue().encode("utf-8-sig")
    buffer.seek(0)
    buffer.truncate(0)

    for record in records:
        raw = record.model_dump(mode="python")
        writer.writerow({column: _csv_value(raw.get(column)) for column in RESEARCH_EXPORT_COLUMNS})
        yield buffer.getvalue().encode("utf-8")
        buffer.seek(0)
        buffer.truncate(0)


def iter_json(
    records: Iterable[ResearchExportRecord],
    filters: ResearchExportFilters,
    generated_at: datetime,
) -> Iterator[bytes]:
    envelope = ResearchJsonEnvelope(
        generated_at=generated_at,
        filters=filters,
        record_count=0,
        records=[],
    )
    metadata = envelope.model_dump(mode="json")
    metadata.pop("records")
    metadata.pop("record_count")
    yield (
        b'{"filters":'
        + _canonical_json(metadata["filters"]).encode("utf-8")
        + b',"generated_at":'
        + _canonical_json(metadata["generated_at"]).encode("utf-8")
    )
    # record_count is injected by ResearchExportService before this iterator is
    # exposed, via the private attribute set below.
    record_count = getattr(records, "record_count", None)
    if not isinstance(record_count, int):
        raise ResearchExportError("record count is unavailable")
    yield f',"record_count":{record_count},"records":['.encode()
    first = True
    for record in records:
        if not first:
            yield b","
        first = False
        yield _canonical_json(record.model_dump(mode="json")).encode("utf-8")
    yield b'],"schema_version":"quantumlearn.research-export.v1"}'


class PreparedResearchExport:
    def __init__(
        self,
        *,
        export_id: str,
        filename: str,
        media_type: str,
        body: Iterable[bytes],
        record_count: int,
    ) -> None:
        self.export_id = export_id
        self.filename = filename
        self.media_type = media_type
        self.body = body
        self.record_count = record_count


class ResearchExportService:
    def __init__(
        self,
        repository: ResearchExportRepository,
        audit_recorder: AuditRecorder,
        *,
        row_limit: int = 100_000,
        batch_size: int = 1_000,
    ) -> None:
        self._repository = repository
        self._audit_recorder = audit_recorder
        self._row_limit = row_limit
        self._batch_size = batch_size

    def prepare(
        self,
        *,
        export_format: ResearchExportFormat,
        filters: ResearchExportFilters,
        actor_reference: str,
        correlation_id: str,
        generated_at: datetime | None = None,
    ) -> PreparedResearchExport:
        record_count = self._repository.count_for_export(
            filters,
            limit=self._row_limit + 1,
        )
        if record_count > self._row_limit:
            raise ResearchExportTooLargeError(
                f"research export exceeds the {self._row_limit} row limit"
            )

        export_id = str(uuid4())
        timestamp = generated_at or datetime.now(UTC)
        self._audit_recorder.record(
            AuditEventCommand(
                actor_reference=actor_reference,
                action=AuditAction.RESEARCH_EXPORT_CREATED,
                outcome=AuditOutcome.SUCCESS,
                correlation_id=correlation_id,
                resource_type="research_export",
                resource_id=export_id,
                deduplication_key=f"research-export:{export_id}:created",
                occurred_at=timestamp,
            )
        )
        date_slug = timestamp.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        records = _CountedRecords(
            self._repository.iter_for_export(
                filters,
                batch_size=self._batch_size,
            ),
            record_count,
        )
        if export_format is ResearchExportFormat.CSV:
            body = self._audited_stream(
                iter_csv(records),
                actor_reference=actor_reference,
                correlation_id=correlation_id,
                export_id=export_id,
                occurred_at=timestamp,
            )
            return PreparedResearchExport(
                export_id=export_id,
                filename=f"quantumlearn-research-{date_slug}.csv",
                media_type="text/csv; charset=utf-8",
                body=body,
                record_count=record_count,
            )
        body = self._audited_stream(
            iter_json(records, filters, timestamp),
            actor_reference=actor_reference,
            correlation_id=correlation_id,
            export_id=export_id,
            occurred_at=timestamp,
        )
        return PreparedResearchExport(
            export_id=export_id,
            filename=f"quantumlearn-research-{date_slug}.json",
            media_type="application/json",
            body=body,
            record_count=record_count,
        )

    def _audited_stream(
        self,
        body: Iterable[bytes],
        *,
        actor_reference: str,
        correlation_id: str,
        export_id: str,
        occurred_at: datetime,
    ) -> Iterator[bytes]:
        try:
            yield from body
        except BaseException as error:
            if isinstance(error, KeyboardInterrupt | SystemExit):
                raise
            self._audit_recorder.record(
                AuditEventCommand(
                    actor_reference=actor_reference,
                    action=AuditAction.RESEARCH_EXPORT_CREATED,
                    outcome=AuditOutcome.FAILURE,
                    correlation_id=correlation_id,
                    resource_type="research_export",
                    resource_id=export_id,
                    failure_category="stream_interrupted",
                    deduplication_key=f"research-export:{export_id}:stream-failed",
                    occurred_at=occurred_at,
                )
            )
            if isinstance(error, Exception):
                raise ResearchExportError("research export stream interrupted") from None
            # GeneratorExit and cancellation must retain their control-flow
            # semantics after the failed stream has been audited.
            raise


class _CountedRecords:
    def __init__(
        self,
        records: Iterator[ResearchExportRecord],
        record_count: int,
    ) -> None:
        self._records = records
        self.record_count = record_count

    def __iter__(self) -> Iterator[ResearchExportRecord]:
        return self._records
