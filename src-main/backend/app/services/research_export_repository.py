from __future__ import annotations

from collections.abc import Iterator

from pydantic import ValidationError
from sqlalchemy import Select, and_, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.enums import ResearchStatus
from app.models.persistence import ResearchEvaluation
from app.schemas.research_export import ResearchExportFilters, ResearchExportRecord
from app.services.research_export import ResearchExportError


class SqlAlchemyResearchExportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def count_for_export(
        self,
        filters: ResearchExportFilters,
        *,
        limit: int,
    ) -> int:
        count = 0
        for row in self._iter_rows(filters, batch_size=1_000):
            if self._safe_record(row) is None:
                continue
            count += 1
            if count >= limit:
                return count
        return count

    def iter_for_export(
        self,
        filters: ResearchExportFilters,
        *,
        batch_size: int,
    ) -> Iterator[ResearchExportRecord]:
        for row in self._iter_rows(filters, batch_size=batch_size):
            record = self._safe_record(row)
            if record is not None:
                yield record

    def _iter_rows(
        self,
        filters: ResearchExportFilters,
        *,
        batch_size: int,
    ) -> Iterator[ResearchEvaluation]:
        offset = 0
        while True:
            try:
                rows = list(
                    self._session.scalars(
                        self._statement(filters)
                        .order_by(
                            ResearchEvaluation.created_at,
                            ResearchEvaluation.id,
                        )
                        .offset(offset)
                        .limit(batch_size)
                    )
                )
            except SQLAlchemyError:
                self._session.rollback()
                raise ResearchExportError("research export stream failed") from None
            if not rows:
                return
            for row in rows:
                yield row
            if len(rows) < batch_size:
                return
            offset += len(rows)

    @staticmethod
    def _statement(filters: ResearchExportFilters) -> Select[tuple[ResearchEvaluation]]:
        course_ids = set(filters.course_ids)
        if filters.course_id is not None:
            course_ids = course_ids & {filters.course_id} if course_ids else {filters.course_id}
        if not course_ids:
            raise ResearchExportError("research export authorization scope is empty")
        statement = select(ResearchEvaluation).where(
            ResearchEvaluation.course_id.in_(course_ids),
            ResearchEvaluation.created_at >= filters.date_from,
            ResearchEvaluation.created_at < filters.date_to,
            ResearchEvaluation.status.in_([ResearchStatus.COMPLETED, ResearchStatus.FAILED]),
            _is_v1_pseudonym(ResearchEvaluation.pseudonymous_user_id),
            _is_v1_pseudonym(ResearchEvaluation.submission_reference),
        )
        if filters.experimental_condition is not None:
            statement = statement.where(
                ResearchEvaluation.experimental_condition == filters.experimental_condition
            )
        if filters.task_type is not None:
            statement = statement.where(ResearchEvaluation.task_type == filters.task_type)
        if filters.model is not None:
            statement = statement.where(ResearchEvaluation.model == filters.model)
        if filters.judge_decision is not None:
            statement = statement.where(
                ResearchEvaluation.final_judge_decision == filters.judge_decision
            )
        return statement

    @classmethod
    def _safe_record(cls, row: ResearchEvaluation) -> ResearchExportRecord | None:
        try:
            return cls._record(row)
        except (ArithmeticError, TypeError, ValueError, ValidationError):
            # Legacy or corrupted JSON is excluded fail-closed. Do not include
            # validation details here because they can contain the rejected data.
            return None

    @staticmethod
    def _record(row: ResearchEvaluation) -> ResearchExportRecord:
        judge_result = row.judge_result if isinstance(row.judge_result, dict) else {}
        reason = judge_result.get("reason")
        return ResearchExportRecord(
            case_id=row.case_id,
            pseudonymous_user_id=row.pseudonymous_user_id,
            course_id=row.course_id,
            task_id=row.task_id,
            task_type=row.task_type,
            submission_reference=row.submission_reference,
            experimental_condition=row.experimental_condition,
            input_reference=row.input_references,
            retrieved_sources=row.retrieved_sources,
            simulation_reference=row.simulation_reference,
            generated_output=row.generated_output,
            judge_decision=row.final_judge_decision,
            judge_reason=reason if isinstance(reason, str) else None,
            correctness_score=row.correctness_score,
            relevance_score=row.relevance_score,
            grounding_score=row.grounding_score,
            actionability_score=row.actionability_score,
            safety_score=row.safety_score,
            unsupported_claim_count=row.unsupported_claim_count or 0,
            latency_ms=row.latency_ms,
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            total_tokens=row.total_tokens,
            estimated_cost=row.estimated_cost,
            regeneration_count=row.regeneration_count,
            fallback_used=row.fallback_used,
            status=row.status,
            failure_category=row.failure_category,
            comparable=row.comparable,
            usage_complete=row.usage_complete,
            measurement_schema_version=row.measurement_schema_version,
            created_at=row.created_at,
            completed_at=row.completed_at,
        )


def _is_v1_pseudonym(column: object):
    suffix = func.substr(column, 4)
    return and_(
        func.length(column) == 67,
        func.substr(column, 1, 3) == "v1_",
        suffix.op("NOT GLOB")("*[^0-9a-f]*"),
    )
