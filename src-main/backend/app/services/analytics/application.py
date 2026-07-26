from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.models.enums import ExperimentalCondition, JudgeDecision
from app.schemas.analytics import AnalyticsFilterOptions, InactiveLearnerPage
from app.services.analytics.metrics import (
    AnalyticsFilterSnapshot,
    LearningMetricsResult,
    MetricValue,
    ResearchMetricsResult,
    RosterLearner,
    calculate_inactive_learners,
    calculate_learning_metrics,
    calculate_research_metrics,
)
from app.services.analytics.repository import (
    AnalyticsQuery,
    SqlAlchemyAnalyticsRepository,
)

_PSEUDONYM = re.compile(r"^v1_[0-9a-f]{64}$")


class AnalyticsAccessPolicy(Protocol):
    async def authorized_course_ids(self, actor_reference: str) -> set[str]: ...


class RosterAdapter(Protocol):
    async def learner_references(self, course_ids: set[str]) -> list[str]: ...


class AnalyticsPseudonymizer(Protocol):
    def pseudonymize(self, namespace: str, reference: str) -> str: ...


class AnalyticsApplication:
    def __init__(
        self,
        repository: SqlAlchemyAnalyticsRepository,
        roster_adapter: RosterAdapter,
        pseudonymizer: AnalyticsPseudonymizer,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._roster_adapter = roster_adapter
        self._pseudonymizer = pseudonymizer
        self._now = now

    async def learning(self, query: AnalyticsQuery) -> LearningMetricsResult:
        generated_at = self._now()
        roster = await self._roster(query)
        inactivity_as_of = min(generated_at, query.end_at)
        return calculate_learning_metrics(
            self._repository.learning_events(query),
            released_workflow_ids=self._repository.released_workflow_ids(query),
            roster=roster,
            as_of=inactivity_as_of,
            last_activity_by_actor=self._repository.learner_last_activity(
                query,
                before=inactivity_as_of,
            ),
            inactivity_window=timedelta(days=14),
            filters=_snapshot(query),
            generated_at=generated_at,
        )

    def research(self, query: AnalyticsQuery) -> ResearchMetricsResult:
        generated_at = self._now()
        return calculate_research_metrics(
            self._repository.research_records(query),
            filters=_snapshot(query),
            generated_at=generated_at,
        )

    async def inactive_learners(
        self,
        query: AnalyticsQuery,
        *,
        page: int,
        page_size: int,
    ) -> InactiveLearnerPage:
        generated_at = self._now()
        inactivity_as_of = min(generated_at, query.end_at)
        roster = await self._roster(query)
        inactive = calculate_inactive_learners(
            [],
            roster=roster,
            as_of=inactivity_as_of,
            last_activity_by_actor=self._repository.learner_last_activity(
                query,
                before=inactivity_as_of,
            ),
            inactivity_window=timedelta(days=14),
        )
        start = (page - 1) * page_size
        return InactiveLearnerPage(
            filters=_snapshot(query),
            generated_at=generated_at,
            inactive_learner_count=MetricValue(
                value=float(len(inactive)),
                numerator=float(len(inactive)),
                denominator=len(roster),
                sample_size=len(roster),
                unit="learners",
            ),
            items=inactive[start : start + page_size],
            page=page,
            page_size=page_size,
            total=len(inactive),
        )

    async def _roster(self, query: AnalyticsQuery) -> list[RosterLearner]:
        references = await self._roster_adapter.learner_references(set(query.course_ids))
        pseudonyms: set[str] = set()
        for reference in references:
            pseudonym = self._pseudonymizer.pseudonymize(
                "learning-actor",
                reference,
            )
            if _PSEUDONYM.fullmatch(pseudonym) is None:
                raise ValueError("analytics pseudonymization is unavailable")
            pseudonyms.add(pseudonym)
        return [RosterLearner(pseudonymous_user_id=pseudonym) for pseudonym in sorted(pseudonyms)]

    def filter_options(
        self,
        authorized_course_ids: set[str],
    ) -> AnalyticsFilterOptions:
        options = self._repository.filter_options(authorized_course_ids)
        return AnalyticsFilterOptions(
            generated_at=self._now(),
            courses=options.courses,
            task_types=options.task_types,
            models=options.models,
            experimental_conditions=[condition.value for condition in ExperimentalCondition],
            judge_decisions=[decision.value for decision in JudgeDecision],
        )


def _snapshot(query: AnalyticsQuery) -> AnalyticsFilterSnapshot:
    return AnalyticsFilterSnapshot(
        course_ids=list(query.course_ids),
        start_at=query.start_at,
        end_at=query.end_at,
        experimental_conditions=(
            [query.experimental_condition] if query.experimental_condition is not None else []
        ),
        task_types=[query.task_type] if query.task_type is not None else [],
        models=[query.model] if query.model is not None else [],
        judge_decisions=([query.judge_decision.value] if query.judge_decision is not None else []),
    )
