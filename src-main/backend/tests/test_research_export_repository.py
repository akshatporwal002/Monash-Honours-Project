import csv
import io
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import (
    ExperimentalCondition,
    JudgeDecision,
    JudgeEvaluationStatus,
    ResearchEvaluation,
    ResearchStatus,
)
from app.schemas.research_export import ResearchExportFilters, ResearchExportFormat
from app.services.audit import AuditRecorder
from app.services.research_export import ResearchExportService
from app.services.research_export_repository import (
    SqlAlchemyResearchExportRepository,
)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
EXPORT_ACTOR = f"v1_{'9' * 64}"


def _terminal_record(
    *,
    case_id: str | None = None,
    input_references: list[object] | None = None,
    retrieved_sources: list[object] | None = None,
    generated_output: dict[str, object] | None = None,
) -> ResearchEvaluation:
    return ResearchEvaluation(
        case_id=case_id or str(uuid4()),
        pseudonymous_user_id=f"v1_{'a' * 64}",
        course_id="course-privacy",
        task_id=f"task-{uuid4()}",
        task_type="short_answer",
        submission_reference=f"v1_{'b' * 64}",
        experimental_condition=ExperimentalCondition.AGENTIC_RAG,
        prompt_version="feedback-v1",
        provider="provider",
        model="model",
        input_references=input_references or [],
        retrieved_sources=retrieved_sources or [],
        simulation_status="not_requested",
        generated_output=generated_output or {"summary": "Allowed output"},
        measurement_schema_version="research-v1",
        status=ResearchStatus.COMPLETED,
        completed_at=NOW,
        created_at=NOW,
    )


def test_sql_export_repository_scopes_filters_and_returns_only_terminal_rows(
    db_session: Session,
) -> None:
    terminal = ResearchEvaluation(
        case_id="00000000-0000-4000-8000-000000000601",
        pseudonymous_user_id=f"v1_{'a' * 64}",
        course_id="course-1",
        task_id="task-1",
        task_type="short_answer",
        submission_reference=f"v1_{'b' * 64}",
        experimental_condition=ExperimentalCondition.AGENTIC_RAG,
        prompt_version="feedback-v1",
        provider="provider",
        model="model",
        input_references=[],
        retrieved_sources=[],
        simulation_status="not_requested",
        generated_output={"summary": "Allowed output"},
        judge_result={"reason": "Pass"},
        measurement_schema_version="research-v1",
        latency_ms=10,
        input_tokens=1,
        output_tokens=1,
        total_tokens=2,
        estimated_cost=Decimal("0.01"),
        first_judge_status=JudgeEvaluationStatus.VALID,
        first_judge_decision=JudgeDecision.PASS,
        final_judge_status=JudgeEvaluationStatus.VALID,
        final_judge_decision=JudgeDecision.PASS,
        correctness_score=90,
        relevance_score=90,
        grounding_score=90,
        actionability_score=90,
        safety_score=100,
        unsupported_claim_count=0,
        quality_policy_version="quality-policy-v1",
        status=ResearchStatus.COMPLETED,
        completed_at=NOW,
        created_at=NOW,
    )
    pending = ResearchEvaluation(
        case_id="00000000-0000-4000-8000-000000000602",
        pseudonymous_user_id=f"v1_{'c' * 64}",
        course_id="course-1",
        task_id="task-2",
        task_type="short_answer",
        submission_reference=f"v1_{'d' * 64}",
        experimental_condition=ExperimentalCondition.SINGLE_STEP_BASELINE,
        prompt_version="baseline-v1",
        provider="provider",
        model="model",
        input_references=[],
        retrieved_sources=[],
        simulation_status="not_requested",
        generated_output={},
        measurement_schema_version="research-v1",
        status=ResearchStatus.PENDING,
        created_at=NOW,
    )
    db_session.add_all([terminal, pending])
    db_session.commit()
    repository = SqlAlchemyResearchExportRepository(db_session)
    filters = ResearchExportFilters(
        course_ids=["course-1"],
        date_from=NOW - timedelta(days=1),
        date_to=NOW + timedelta(days=1),
        model="model",
        judge_decision=JudgeDecision.PASS,
    )

    assert repository.count_for_export(filters, limit=100) == 1
    records = list(repository.iter_for_export(filters, batch_size=1))

    assert len(records) == 1
    assert records[0].case_id == terminal.case_id
    assert records[0].submission_reference.startswith("v1_")
    assert records[0].judge_reason == "Pass"


def test_sql_export_repository_excludes_non_pseudonymous_legacy_rows(
    db_session: Session,
) -> None:
    valid = ResearchEvaluation(
        case_id=str(uuid4()),
        pseudonymous_user_id=f"v1_{'e' * 64}",
        course_id="course-1",
        task_id="task-valid",
        task_type="short_answer",
        submission_reference=f"v1_{'f' * 64}",
        experimental_condition=ExperimentalCondition.AGENTIC_RAG,
        prompt_version="feedback-v1",
        provider="provider",
        model="model",
        input_references=[],
        retrieved_sources=[],
        simulation_status="not_requested",
        generated_output={"summary": "Allowed output"},
        measurement_schema_version="research-v1",
        status=ResearchStatus.COMPLETED,
        completed_at=NOW,
        created_at=NOW,
    )
    invalid = ResearchEvaluation(
        case_id=str(uuid4()),
        pseudonymous_user_id="legacy-direct-student-id",
        course_id="course-1",
        task_id="task-invalid",
        task_type="short_answer",
        submission_reference="legacy-direct-submission-id",
        experimental_condition=ExperimentalCondition.AGENTIC_RAG,
        prompt_version="feedback-v1",
        provider="provider",
        model="model",
        input_references=[],
        retrieved_sources=[],
        simulation_status="not_requested",
        generated_output={"summary": "Must not export"},
        measurement_schema_version="legacy-v1",
        status=ResearchStatus.COMPLETED,
        completed_at=NOW,
        created_at=NOW,
    )
    db_session.add_all([valid, invalid])
    db_session.commit()
    filters = ResearchExportFilters(
        course_ids=["course-1"],
        date_from=NOW - timedelta(days=1),
        date_to=NOW + timedelta(days=1),
    )
    repository = SqlAlchemyResearchExportRepository(db_session)

    assert repository.count_for_export(filters, limit=100) == 1
    assert [record.case_id for record in repository.iter_for_export(filters, batch_size=1)] == [
        valid.case_id
    ]


@pytest.mark.parametrize("export_format", [ResearchExportFormat.CSV, ResearchExportFormat.JSON])
def test_export_excludes_nested_malicious_and_oversized_database_json(
    db_session: Session,
    export_format: ResearchExportFormat,
) -> None:
    raw_answer = "PRIVATE-SUBMITTED-ANSWER-SENTINEL"
    raw_chunk = "PRIVATE-SOURCE-CHUNK-SENTINEL"
    api_key = "sk-privateCredential123456789"
    bearer_token = "Bearer private-access-token-value"
    provider_exception = "PRIVATE_PROVIDER_EXCEPTION student@example.test"
    valid = _terminal_record(
        retrieved_sources=[
            {
                "source_id": "source-safe",
                "label": "Course notes",
                "relevance_score": 0.9,
            }
        ]
    )
    invalid_rows = [
        _terminal_record(
            input_references=[
                {
                    "metadata": {
                        "submitted_answer": raw_answer,
                    }
                }
            ]
        ),
        _terminal_record(
            retrieved_sources=[
                {
                    "source_id": "source-corrupt",
                    "label": "Course notes",
                    "relevance_score": 0.9,
                    "metadata": {"source_chunk": raw_chunk},
                }
            ]
        ),
        _terminal_record(
            generated_output={
                "summary": "Safe-looking wrapper",
                "metadata": {"api_key": api_key},
            }
        ),
        _terminal_record(generated_output={"summary": "é" * 33_000}),
        _terminal_record(
            generated_output={
                "summary": "Safe-looking wrapper",
                "details": ["item"] * 101,
            }
        ),
        _terminal_record(generated_output={"summary": bearer_token}),
    ]
    invalid_failure = _terminal_record()
    invalid_failure.status = ResearchStatus.FAILED
    invalid_failure.failure_category = provider_exception
    invalid_rows.append(invalid_failure)
    db_session.add_all([valid, *invalid_rows])
    db_session.commit()
    filters = ResearchExportFilters(
        course_ids=["course-privacy"],
        date_from=NOW - timedelta(days=1),
        date_to=NOW + timedelta(days=1),
    )
    repository = SqlAlchemyResearchExportRepository(db_session)

    assert repository.count_for_export(filters, limit=100) == 1

    prepared = ResearchExportService(
        repository,
        AuditRecorder(db_session),
        batch_size=2,
    ).prepare(
        export_format=export_format,
        filters=filters,
        actor_reference=EXPORT_ACTOR,
        correlation_id=str(uuid4()),
        generated_at=NOW,
    )
    serialized = b"".join(prepared.body).decode("utf-8-sig")

    if export_format is ResearchExportFormat.JSON:
        payload = json.loads(serialized)
        assert payload["record_count"] == 1
        assert [record["case_id"] for record in payload["records"]] == [valid.case_id]
    else:
        rows = list(csv.DictReader(io.StringIO(serialized)))
        assert [row["case_id"] for row in rows] == [valid.case_id]
    for forbidden in (raw_answer, raw_chunk, api_key, bearer_token, provider_exception):
        assert forbidden not in serialized
