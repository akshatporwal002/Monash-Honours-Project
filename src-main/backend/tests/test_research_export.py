import csv
import io
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditAction, AuditEvent, AuditOutcome
from app.models.enums import ExperimentalCondition, JudgeDecision, ResearchStatus
from app.schemas.research_export import (
    ResearchExportFilters,
    ResearchExportFormat,
    ResearchExportRecord,
)
from app.services.audit import AuditPersistenceError, AuditRecorder
from app.services.research_export import (
    RESEARCH_EXPORT_COLUMNS,
    ResearchExportError,
    ResearchExportService,
    ResearchExportTooLargeError,
    iter_csv,
)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
ACTOR = f"v1_{'b' * 64}"
GOLDEN_DIRECTORY = Path(__file__).with_name("golden")


def export_record(**updates: object) -> ResearchExportRecord:
    values: dict[str, object] = {
        "case_id": "case-1",
        "pseudonymous_user_id": f"v1_{'a' * 64}",
        "course_id": "course-1",
        "task_id": "task-1",
        "task_type": "short_answer",
        "submission_reference": f"v1_{'b' * 64}",
        "experimental_condition": ExperimentalCondition.AGENTIC_RAG,
        "input_reference": ["input-ref"],
        "retrieved_sources": [
            {
                "source_id": "source-1",
                "label": "Course notes",
                "relevance_score": 0.9,
            }
        ],
        "generated_output": {"summary": "Safe"},
        "judge_decision": JudgeDecision.PASS,
        "judge_reason": "+formula",
        "correctness_score": 90,
        "relevance_score": 90,
        "grounding_score": 90,
        "actionability_score": 90,
        "safety_score": 100,
        "unsupported_claim_count": 0,
        "latency_ms": 120,
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "estimated_cost": Decimal("0.012300"),
        "regeneration_count": 0,
        "fallback_used": False,
        "status": ResearchStatus.COMPLETED,
        "comparable": True,
        "usage_complete": True,
        "measurement_schema_version": "research-v1",
        "created_at": NOW,
        "completed_at": NOW,
    }
    values.update(updates)
    return ResearchExportRecord.model_validate(values)


class StaticRepository:
    def __init__(self, records: list[ResearchExportRecord]) -> None:
        self.records = records

    def count_for_export(
        self,
        _: ResearchExportFilters,
        *,
        limit: int,
    ) -> int:
        return min(len(self.records), limit)

    def iter_for_export(
        self,
        _: ResearchExportFilters,
        *,
        batch_size: int,
    ):
        assert batch_size == 1_000
        yield from self.records


def filters() -> ResearchExportFilters:
    return ResearchExportFilters(
        course_id="course-1",
        date_from=NOW - timedelta(days=1),
        date_to=NOW + timedelta(days=1),
    )


def test_csv_has_stable_order_canonical_json_and_formula_protection(
    db_session: Session,
) -> None:
    service = ResearchExportService(
        StaticRepository([export_record()]),
        AuditRecorder(db_session),
    )
    prepared = service.prepare(
        export_format=ResearchExportFormat.CSV,
        filters=filters(),
        actor_reference=ACTOR,
        correlation_id=str(uuid4()),
        generated_at=NOW,
    )

    rows = list(csv.DictReader(io.StringIO(b"".join(prepared.body).decode("utf-8-sig"))))

    assert tuple(rows[0]) == RESEARCH_EXPORT_COLUMNS
    assert rows[0]["submission_reference"] == f"v1_{'b' * 64}"
    assert rows[0]["judge_reason"] == "'+formula"
    assert rows[0]["estimated_cost"] == "0.012300"
    assert rows[0]["retrieved_sources"] == (
        '[{"label":"Course notes","relevance_score":0.9,"source_id":"source-1"}]'
    )
    audit = db_session.scalar(select(AuditEvent))
    assert audit is not None
    assert audit.action is AuditAction.RESEARCH_EXPORT_CREATED


@pytest.mark.parametrize(
    "hostile",
    [
        "=1+1",
        "+1+1",
        "-1+1",
        "@SUM(1,1)",
        "  =1+1",
        "\t=1+1",
        "\r@SUM(1,1)",
        "\n-1+1",
    ],
)
def test_csv_neutralizes_whitespace_and_control_prefixed_formulas(
    hostile: str,
) -> None:
    safe = export_record()
    # Defense in depth: the serializer remains safe even if a caller bypasses
    # the validated export schema with a constructed legacy object.
    corrupted = safe.model_copy(update={"failure_category": hostile})

    rows = list(csv.DictReader(io.StringIO(b"".join(iter_csv([corrupted])).decode("utf-8-sig"))))

    assert rows[0]["failure_category"] == f"'{hostile}"


def test_json_uses_versioned_envelope_and_omits_forbidden_fields(
    db_session: Session,
) -> None:
    prepared = ResearchExportService(
        StaticRepository([export_record()]),
        AuditRecorder(db_session),
    ).prepare(
        export_format=ResearchExportFormat.JSON,
        filters=filters(),
        actor_reference=ACTOR,
        correlation_id=str(uuid4()),
        generated_at=NOW,
    )
    payload = json.loads(b"".join(prepared.body))

    assert payload["schema_version"] == "quantumlearn.research-export.v1"
    assert payload["record_count"] == 1
    serialized = json.dumps(payload)
    for forbidden in ("submitted_answer", "prompt", "source_chunk", "api_key"):
        assert forbidden not in serialized


def test_versioned_csv_and_json_serializers_match_golden_files(
    db_session: Session,
) -> None:
    service = ResearchExportService(
        StaticRepository([export_record()]),
        AuditRecorder(db_session),
    )
    csv_export = service.prepare(
        export_format=ResearchExportFormat.CSV,
        filters=filters(),
        actor_reference=ACTOR,
        correlation_id=str(uuid4()),
        generated_at=NOW,
    )
    json_export = service.prepare(
        export_format=ResearchExportFormat.JSON,
        filters=filters(),
        actor_reference=ACTOR,
        correlation_id=str(uuid4()),
        generated_at=NOW,
    )

    actual_csv = b"".join(csv_export.body).decode("utf-8-sig").replace("\r\n", "\n")
    actual_json = b"".join(json_export.body).decode("utf-8")
    expected_csv = (GOLDEN_DIRECTORY / "research_export_v1.csv").read_text(encoding="utf-8")
    expected_json = (
        (GOLDEN_DIRECTORY / "research_export_v1.json").read_text(encoding="utf-8").rstrip("\r\n")
    )

    assert actual_csv == expected_csv
    assert actual_json == expected_json


def test_export_enforces_row_limit_before_auditing(db_session: Session) -> None:
    service = ResearchExportService(
        StaticRepository([export_record(case_id="one"), export_record(case_id="two")]),
        AuditRecorder(db_session),
        row_limit=1,
    )

    with pytest.raises(ResearchExportTooLargeError):
        service.prepare(
            export_format=ResearchExportFormat.JSON,
            filters=filters(),
            actor_reference=ACTOR,
            correlation_id=str(uuid4()),
        )

    assert db_session.scalar(select(AuditEvent)) is None


def test_stream_failure_appends_sanitized_failed_export_audit(
    db_session: Session,
) -> None:
    class FaultyRepository(StaticRepository):
        def iter_for_export(
            self,
            _: ResearchExportFilters,
            *,
            batch_size: int,
        ):
            del batch_size
            yield self.records[0]
            raise RuntimeError("PRIVATE PROVIDER OUTPUT")

    prepared = ResearchExportService(
        FaultyRepository([export_record()]),
        AuditRecorder(db_session),
    ).prepare(
        export_format=ResearchExportFormat.CSV,
        filters=filters(),
        actor_reference=ACTOR,
        correlation_id=str(uuid4()),
        generated_at=NOW,
    )

    with pytest.raises(ResearchExportError) as exc_info:
        b"".join(prepared.body)

    audits = list(db_session.scalars(select(AuditEvent).order_by(AuditEvent.id)))
    assert len(audits) == 2
    failed = next(audit for audit in audits if audit.outcome is AuditOutcome.FAILURE)
    assert failed.failure_category == "stream_interrupted"
    assert "PRIVATE PROVIDER OUTPUT" not in repr(exc_info.value)
    assert "PRIVATE PROVIDER OUTPUT" not in repr(audits)


def test_client_closed_stream_appends_failed_export_audit(db_session: Session) -> None:
    prepared = ResearchExportService(
        StaticRepository([export_record()]),
        AuditRecorder(db_session),
    ).prepare(
        export_format=ResearchExportFormat.JSON,
        filters=filters(),
        actor_reference=ACTOR,
        correlation_id=str(uuid4()),
        generated_at=NOW,
    )
    body = iter(prepared.body)

    next(body)
    body.close()

    audits = list(db_session.scalars(select(AuditEvent)))
    assert len(audits) == 2
    assert {audit.outcome for audit in audits} == {
        AuditOutcome.SUCCESS,
        AuditOutcome.FAILURE,
    }
    failed = next(audit for audit in audits if audit.outcome is AuditOutcome.FAILURE)
    assert failed.failure_category == "stream_interrupted"


def test_initial_audit_failure_is_fail_closed_before_export_body_exists() -> None:
    class BrokenAudit:
        def record(self, _: object) -> None:
            raise AuditPersistenceError("private database exception")

    service = ResearchExportService(
        StaticRepository([export_record()]),
        BrokenAudit(),  # type: ignore[arg-type]
    )

    with pytest.raises(AuditPersistenceError):
        service.prepare(
            export_format=ResearchExportFormat.JSON,
            filters=filters(),
            actor_reference=ACTOR,
            correlation_id=str(uuid4()),
        )
