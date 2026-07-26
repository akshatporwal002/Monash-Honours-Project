from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.enums import (
    ExperimentalCondition,
    JudgeDecision,
    JudgeEvaluationStatus,
    ResearchStatus,
    WorkflowStage,
)
from app.models.persistence import LearningEvent, ResearchEvaluation, WorkflowRun
from app.services.analytics.metrics import LearningMetricEvent, ResearchMetricRecord

_MAX_ANALYTICS_FILTER_VALUES = 1_000


class AnalyticsPersistenceError(Exception):
    """A sanitized analytics query failure."""


@dataclass(frozen=True, slots=True)
class AnalyticsQuery:
    course_ids: tuple[str, ...]
    start_at: datetime
    end_at: datetime
    experimental_condition: ExperimentalCondition | None = None
    task_type: str | None = None
    model: str | None = None
    judge_decision: JudgeDecision | None = None

    def __post_init__(self) -> None:
        if (
            not self.course_ids
            or len(self.course_ids) > _MAX_ANALYTICS_FILTER_VALUES
            or len(set(self.course_ids)) != len(self.course_ids)
        ):
            raise ValueError("analytics course scope is invalid")


@dataclass(frozen=True, slots=True)
class AnalyticsOptions:
    courses: list[str]
    task_types: list[str]
    models: list[str]


class SqlAlchemyAnalyticsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def learning_events(self, query: AnalyticsQuery) -> list[LearningMetricEvent]:
        statement = (
            select(LearningEvent)
            .where(
                LearningEvent.course_id.in_(query.course_ids),
                LearningEvent.occurred_at >= query.start_at,
                LearningEvent.occurred_at < query.end_at,
            )
            .order_by(LearningEvent.occurred_at, LearningEvent.id)
        )
        try:
            rows = list(self._session.scalars(statement))
        except SQLAlchemyError:
            self._session.rollback()
            raise AnalyticsPersistenceError("learning metrics are unavailable") from None
        return [
            LearningMetricEvent(
                pseudonymous_user_id=row.pseudonymous_user_id,
                task_id=row.task_id,
                event_type=row.event_type,
                occurred_at=_utc(row.occurred_at),
                metadata=dict(row.metadata_payload),
                workflow_reference=row.workflow_reference,
            )
            for row in rows
        ]

    def released_workflow_ids(self, query: AnalyticsQuery) -> set[str]:
        try:
            released_workflows = set(
                self._session.scalars(
                    select(WorkflowRun.id)
                    .where(
                        WorkflowRun.current_stage == WorkflowStage.COMPLETED,
                        WorkflowRun.course_id.in_(query.course_ids),
                        WorkflowRun.completed_at >= query.start_at,
                        WorkflowRun.completed_at < query.end_at,
                    )
                    .distinct()
                )
            )
        except SQLAlchemyError:
            self._session.rollback()
            raise AnalyticsPersistenceError("learning metrics are unavailable") from None
        return released_workflows

    def learner_last_activity(
        self,
        query: AnalyticsQuery,
        *,
        before: datetime,
    ) -> dict[str, datetime]:
        """Return each learner's latest activity before the inactivity as-of time."""
        statement = (
            select(
                LearningEvent.pseudonymous_user_id,
                func.max(LearningEvent.occurred_at),
            )
            .where(
                LearningEvent.course_id.in_(query.course_ids),
                LearningEvent.occurred_at < before,
            )
            .group_by(LearningEvent.pseudonymous_user_id)
        )
        try:
            rows = self._session.execute(statement).all()
        except SQLAlchemyError:
            self._session.rollback()
            raise AnalyticsPersistenceError("learning metrics are unavailable") from None
        return {
            actor_reference: _utc(last_activity_at) for actor_reference, last_activity_at in rows
        }

    def research_records(self, query: AnalyticsQuery) -> list[ResearchMetricRecord]:
        statement = select(ResearchEvaluation).where(
            ResearchEvaluation.course_id.in_(query.course_ids),
            ResearchEvaluation.created_at >= query.start_at,
            ResearchEvaluation.created_at < query.end_at,
        )
        if query.experimental_condition is not None:
            statement = statement.where(
                ResearchEvaluation.experimental_condition == query.experimental_condition
            )
        if query.task_type is not None:
            statement = statement.where(ResearchEvaluation.task_type == query.task_type)
        if query.model is not None:
            statement = statement.where(ResearchEvaluation.model == query.model)
        if query.judge_decision is not None:
            statement = statement.where(
                ResearchEvaluation.final_judge_decision == query.judge_decision
            )
        try:
            rows = list(self._session.scalars(statement))
        except SQLAlchemyError:
            self._session.rollback()
            raise AnalyticsPersistenceError("research metrics are unavailable") from None
        return [
            ResearchMetricRecord(
                case_id=row.case_id,
                condition=row.experimental_condition,
                terminal=row.status in {ResearchStatus.COMPLETED, ResearchStatus.FAILED},
                metrics_eligible=(row.measurement_schema_version == "research-v1"),
                judge_valid=(row.final_judge_status is JudgeEvaluationStatus.VALID),
                final_pass=row.final_judge_decision is JudgeDecision.PASS,
                first_pass=(
                    row.first_judge_decision is JudgeDecision.PASS
                    if row.first_judge_status is JudgeEvaluationStatus.VALID
                    and row.first_judge_decision is not None
                    else None
                ),
                unsupported_claim_count=row.unsupported_claim_count,
                regeneration_count=row.regeneration_count,
                relevance_score=row.relevance_score,
                retrieval_request_count=row.retrieval_request_count,
                retrieval_hit_count=row.retrieval_hit_count,
                latency_ms=row.latency_ms,
                total_tokens=row.total_tokens,
                estimated_cost=row.estimated_cost,
                usage_complete=row.usage_complete,
                fallback_used=row.fallback_used,
                comparable=row.comparable,
            )
            for row in rows
        ]

    def filter_options(self, authorized_course_ids: set[str]) -> AnalyticsOptions:
        if not authorized_course_ids:
            return AnalyticsOptions([], [], [])
        if len(authorized_course_ids) > _MAX_ANALYTICS_FILTER_VALUES:
            raise AnalyticsPersistenceError("analytics filters are unavailable")
        try:
            learning_courses = set(
                self._session.scalars(
                    select(LearningEvent.course_id)
                    .where(LearningEvent.course_id.in_(authorized_course_ids))
                    .distinct()
                    .order_by(LearningEvent.course_id)
                    .limit(_MAX_ANALYTICS_FILTER_VALUES + 1)
                )
            )
            research_rows = self._session.execute(
                select(
                    ResearchEvaluation.course_id,
                    ResearchEvaluation.task_type,
                    ResearchEvaluation.model,
                )
                .where(ResearchEvaluation.course_id.in_(authorized_course_ids))
                .distinct()
                .order_by(
                    ResearchEvaluation.course_id,
                    ResearchEvaluation.task_type,
                    ResearchEvaluation.model,
                )
                .limit(_MAX_ANALYTICS_FILTER_VALUES + 1)
            ).all()
        except SQLAlchemyError:
            self._session.rollback()
            raise AnalyticsPersistenceError("analytics filters are unavailable") from None
        courses = sorted(learning_courses | {row.course_id for row in research_rows})
        task_types = sorted({row.task_type for row in research_rows})
        models = sorted({row.model for row in research_rows})
        if any(
            len(values) > _MAX_ANALYTICS_FILTER_VALUES for values in (courses, task_types, models)
        ):
            raise AnalyticsPersistenceError("analytics filters are unavailable")
        return AnalyticsOptions(courses=courses, task_types=task_types, models=models)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
