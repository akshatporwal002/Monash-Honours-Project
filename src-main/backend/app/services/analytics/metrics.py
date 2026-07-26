from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import ceil
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExperimentalCondition, LearningEventType

MAX_ANALYTICS_FILTER_VALUES = 1_000


class MetricsContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MetricValue(MetricsContract):
    value: float | None
    numerator: float
    denominator: int = Field(ge=0)
    sample_size: int = Field(ge=0)
    unit: str


class AnalyticsFilterSnapshot(MetricsContract):
    course_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_ANALYTICS_FILTER_VALUES,
    )
    start_at: datetime | None = None
    end_at: datetime | None = None
    experimental_conditions: list[ExperimentalCondition] = Field(
        default_factory=list,
        max_length=MAX_ANALYTICS_FILTER_VALUES,
    )
    task_types: list[str] = Field(
        default_factory=list,
        max_length=MAX_ANALYTICS_FILTER_VALUES,
    )
    models: list[str] = Field(
        default_factory=list,
        max_length=MAX_ANALYTICS_FILTER_VALUES,
    )
    judge_decisions: list[str] = Field(
        default_factory=list,
        max_length=MAX_ANALYTICS_FILTER_VALUES,
    )


class ConditionMetrics(MetricsContract):
    hallucination_rate: MetricValue
    overall_pass_rate: MetricValue
    average_relevance: MetricValue
    average_latency_ms: MetricValue
    p95_latency_ms: MetricValue
    average_total_tokens: MetricValue
    average_cost: MetricValue
    fallback_rate: MetricValue


class PairedDifferences(MetricsContract):
    pass_rate: MetricValue
    relevance: MetricValue
    latency_ms: MetricValue
    total_tokens: MetricValue
    cost: MetricValue


class ResearchMetricsResult(MetricsContract):
    schema_version: str = "research-metrics-v1"
    filters: AnalyticsFilterSnapshot = Field(default_factory=AnalyticsFilterSnapshot)
    generated_at: datetime
    retrieval_threshold: float = 0.5
    retrieval_threshold_version: str = "retrieval-relevance-v1"
    by_condition: dict[ExperimentalCondition, ConditionMetrics]
    first_pass_rate: MetricValue
    regeneration_success_rate: MetricValue
    retrieval_hit_rate: MetricValue
    paired_agentic_minus_baseline: PairedDifferences
    excluded_incomplete_count: int = Field(ge=0)


class FunnelStage(MetricsContract):
    event_type: LearningEventType
    count: int = Field(ge=0)
    previous_stage_rate: MetricValue


class InactiveLearner(MetricsContract):
    pseudonymous_user_id: str
    last_activity_at: datetime | None


class LearningMetricsResult(MetricsContract):
    schema_version: str = "learning-metrics-v1"
    filters: AnalyticsFilterSnapshot = Field(default_factory=AnalyticsFilterSnapshot)
    generated_at: datetime
    task_views: MetricValue
    unique_task_views: MetricValue
    submissions: MetricValue
    unique_submissions: MetricValue
    completion_rate: MetricValue
    average_score: MetricValue
    total_attempts: MetricValue
    average_attempts: MetricValue
    feedback_view_rate: MetricValue
    funnel: list[FunnelStage]
    inactive_learner_count: MetricValue
    excluded_incomplete_count: int = Field(default=0, ge=0)


@dataclass(frozen=True, slots=True)
class ResearchMetricRecord:
    case_id: str
    condition: ExperimentalCondition
    terminal: bool = True
    metrics_eligible: bool = True
    judge_valid: bool = False
    final_pass: bool = False
    first_pass: bool | None = None
    unsupported_claim_count: int | None = None
    regeneration_count: int = 0
    relevance_score: float | None = None
    retrieval_request_count: int | None = None
    retrieval_hit_count: int | None = None
    latency_ms: int | None = None
    total_tokens: int | None = None
    estimated_cost: Decimal | None = None
    usage_complete: bool = False
    fallback_used: bool = False
    comparable: bool = True


@dataclass(frozen=True, slots=True)
class LearningMetricEvent:
    pseudonymous_user_id: str
    task_id: str
    event_type: LearningEventType
    occurred_at: datetime
    metadata: dict[str, object]
    workflow_reference: str | None = None


@dataclass(frozen=True, slots=True)
class RosterLearner:
    pseudonymous_user_id: str


def _metric(
    numerator: float,
    denominator: int,
    unit: str,
    *,
    value: float | None = None,
    sample_size: int | None = None,
) -> MetricValue:
    resolved = value
    if resolved is None and denominator:
        resolved = numerator / denominator
    return MetricValue(
        value=resolved,
        numerator=numerator,
        denominator=denominator,
        sample_size=denominator if sample_size is None else sample_size,
        unit=unit,
    )


def _average(values: list[float], unit: str) -> MetricValue:
    if not values:
        return _metric(0, 0, unit)
    total = float(sum(values))
    return _metric(total, len(values), unit, value=total / len(values))


def _p95(values: list[float], unit: str) -> MetricValue:
    if not values:
        return _metric(0, 0, unit)
    ordered = sorted(values)
    value = ordered[max(0, ceil(0.95 * len(ordered)) - 1)]
    return _metric(value, len(ordered), unit, value=value)


def _condition_metrics(records: list[ResearchMetricRecord]) -> ConditionMetrics:
    judged = [
        record
        for record in records
        if record.judge_valid and record.unsupported_claim_count is not None
    ]
    terminal = [record for record in records if record.terminal and record.metrics_eligible]
    relevance = [
        record.relevance_score
        for record in records
        if record.judge_valid and record.relevance_score is not None
    ]
    latencies = [float(record.latency_ms) for record in terminal if record.latency_ms is not None]
    usage = [
        record
        for record in terminal
        if record.usage_complete
        and record.total_tokens is not None
        and record.estimated_cost is not None
    ]
    return ConditionMetrics(
        hallucination_rate=_metric(
            sum(record.unsupported_claim_count > 0 for record in judged),
            len(judged),
            "ratio",
        ),
        overall_pass_rate=_metric(
            sum(record.final_pass for record in terminal),
            len(terminal),
            "ratio",
        ),
        average_relevance=_average([float(value) for value in relevance], "score"),
        average_latency_ms=_average(latencies, "milliseconds"),
        p95_latency_ms=_p95(latencies, "milliseconds"),
        average_total_tokens=_average(
            [float(record.total_tokens) for record in usage if record.total_tokens is not None],
            "tokens",
        ),
        average_cost=_average(
            [float(record.estimated_cost) for record in usage if record.estimated_cost is not None],
            "currency_units",
        ),
        fallback_rate=_metric(
            sum(record.fallback_used for record in terminal),
            len(terminal),
            "ratio",
        ),
    )


def _paired_metric(
    pairs: list[tuple[ResearchMetricRecord, ResearchMetricRecord]],
    getter: Callable[[ResearchMetricRecord], object],
    unit: str,
) -> MetricValue:
    differences: list[float] = []
    for agentic, baseline in pairs:
        agentic_value = getter(agentic)
        baseline_value = getter(baseline)
        if agentic_value is not None and baseline_value is not None:
            differences.append(float(agentic_value) - float(baseline_value))
    return _average(differences, unit)


def calculate_research_metrics(
    records: list[ResearchMetricRecord],
    *,
    filters: AnalyticsFilterSnapshot | None = None,
    generated_at: datetime | None = None,
) -> ResearchMetricsResult:
    eligible = [record for record in records if record.terminal and record.metrics_eligible]
    by_condition = {
        condition: _condition_metrics(
            [record for record in eligible if record.condition is condition]
        )
        for condition in ExperimentalCondition
    }
    agentic = [
        record for record in eligible if record.condition is ExperimentalCondition.AGENTIC_RAG
    ]
    regenerated = [record for record in agentic if record.regeneration_count == 1]
    retrieval_records = [
        record
        for record in agentic
        if record.retrieval_request_count is not None and record.retrieval_hit_count is not None
    ]

    grouped: dict[str, dict[ExperimentalCondition, ResearchMetricRecord]] = defaultdict(dict)
    for record in eligible:
        if record.comparable:
            grouped[record.case_id][record.condition] = record
    pairs = [
        (
            condition_rows[ExperimentalCondition.AGENTIC_RAG],
            condition_rows[ExperimentalCondition.SINGLE_STEP_BASELINE],
        )
        for condition_rows in grouped.values()
        if set(condition_rows) == set(ExperimentalCondition)
    ]
    paired_case_ids = {agentic_record.case_id for agentic_record, _baseline_record in pairs}
    condition_filtered = bool(filters and filters.experimental_conditions)

    def is_excluded_or_incomplete(record: ResearchMetricRecord) -> bool:
        if not record.terminal or not record.metrics_eligible:
            return True
        if (
            not record.judge_valid
            or record.unsupported_claim_count is None
            or record.relevance_score is None
            or record.latency_ms is None
            or not record.usage_complete
            or record.total_tokens is None
            or record.estimated_cost is None
            or not record.comparable
        ):
            return True
        if record.condition is ExperimentalCondition.AGENTIC_RAG and record.first_pass is None:
            return True
        return not condition_filtered and record.case_id not in paired_case_ids

    return ResearchMetricsResult(
        filters=filters or AnalyticsFilterSnapshot(),
        generated_at=generated_at or datetime.now(UTC),
        by_condition=by_condition,
        first_pass_rate=_metric(
            sum(record.first_pass is True for record in agentic),
            len(agentic),
            "ratio",
        ),
        regeneration_success_rate=_metric(
            sum(record.final_pass for record in regenerated),
            len(regenerated),
            "ratio",
        ),
        retrieval_hit_rate=_metric(
            sum(record.retrieval_hit_count or 0 for record in retrieval_records),
            sum(record.retrieval_request_count or 0 for record in retrieval_records),
            "ratio",
        ),
        paired_agentic_minus_baseline=PairedDifferences(
            pass_rate=_paired_metric(
                pairs,
                lambda record: 1 if record.final_pass else 0,
                "ratio_points",
            ),
            relevance=_paired_metric(pairs, lambda record: record.relevance_score, "score"),
            latency_ms=_paired_metric(pairs, lambda record: record.latency_ms, "milliseconds"),
            total_tokens=_paired_metric(
                [pair for pair in pairs if pair[0].usage_complete and pair[1].usage_complete],
                lambda record: record.total_tokens,
                "tokens",
            ),
            cost=_paired_metric(
                [pair for pair in pairs if pair[0].usage_complete and pair[1].usage_complete],
                lambda record: record.estimated_cost,
                "currency_units",
            ),
        ),
        excluded_incomplete_count=sum(is_excluded_or_incomplete(record) for record in records),
    )


def _chronological_funnel(
    events_by_pair: dict[tuple[str, str], list[LearningMetricEvent]],
) -> list[FunnelStage]:
    stages = [
        LearningEventType.TASK_VIEW,
        LearningEventType.DRAFT_SAVE,
        LearningEventType.SUBMISSION,
        LearningEventType.FEEDBACK_VIEW,
        LearningEventType.COMPLETION,
    ]
    counts: list[int] = []
    for stage_index, stage in enumerate(stages):
        reached = 0
        required = stages[: stage_index + 1]
        for events in events_by_pair.values():
            cursor: datetime | None = None
            valid = True
            for required_stage in required:
                candidates = [
                    event.occurred_at
                    for event in events
                    if event.event_type is required_stage
                    and (cursor is None or event.occurred_at >= cursor)
                ]
                if not candidates:
                    valid = False
                    break
                cursor = min(candidates)
            reached += valid
        counts.append(reached)

    result: list[FunnelStage] = []
    for index, (stage, count) in enumerate(zip(stages, counts, strict=True)):
        denominator = len(events_by_pair) if index == 0 else counts[index - 1]
        result.append(
            FunnelStage(
                event_type=stage,
                count=count,
                previous_stage_rate=_metric(count, denominator, "ratio"),
            )
        )
    return result


def calculate_learning_metrics(
    events: list[LearningMetricEvent],
    *,
    released_workflow_ids: set[str],
    roster: list[RosterLearner],
    as_of: datetime,
    last_activity_by_actor: dict[str, datetime] | None = None,
    inactivity_window: timedelta = timedelta(days=14),
    filters: AnalyticsFilterSnapshot | None = None,
    generated_at: datetime | None = None,
) -> LearningMetricsResult:
    by_pair: dict[tuple[str, str], list[LearningMetricEvent]] = defaultdict(list)
    for event in events:
        by_pair[(event.pseudonymous_user_id, event.task_id)].append(event)
    for pair_events in by_pair.values():
        pair_events.sort(key=lambda event: event.occurred_at)

    views = [event for event in events if event.event_type is LearningEventType.TASK_VIEW]
    submissions = [event for event in events if event.event_type is LearningEventType.SUBMISSION]
    submitted_pairs = {(event.pseudonymous_user_id, event.task_id) for event in submissions}
    viewed_pairs = {(event.pseudonymous_user_id, event.task_id) for event in views}
    completed_pairs = {
        (event.pseudonymous_user_id, event.task_id)
        for event in events
        if event.event_type is LearningEventType.COMPLETION
    }
    viewed_feedback_workflows = {
        event.workflow_reference
        for event in events
        if event.event_type is LearningEventType.FEEDBACK_VIEW
        and event.workflow_reference is not None
    }
    scores = [
        float(event.metadata["score"])
        for event in submissions
        if isinstance(event.metadata.get("score"), int | float)
        and not isinstance(event.metadata.get("score"), bool)
    ]
    attempt_counts: dict[tuple[str, str], int] = defaultdict(int)
    for event in submissions:
        attempt_counts[(event.pseudonymous_user_id, event.task_id)] += 1

    inactive = calculate_inactive_learners(
        events,
        roster=roster,
        as_of=as_of,
        last_activity_by_actor=last_activity_by_actor,
        inactivity_window=inactivity_window,
    )
    legacy_feedback_views = sum(
        event.event_type is LearningEventType.FEEDBACK_VIEW and event.workflow_reference is None
        for event in events
    )

    return LearningMetricsResult(
        filters=filters or AnalyticsFilterSnapshot(),
        generated_at=generated_at or datetime.now(UTC),
        task_views=_metric(len(views), len(views), "events", value=float(len(views))),
        unique_task_views=_metric(
            len(viewed_pairs),
            len(viewed_pairs),
            "actor_task_pairs",
            value=float(len(viewed_pairs)),
        ),
        submissions=_metric(
            len(submissions),
            len(submissions),
            "events",
            value=float(len(submissions)),
        ),
        unique_submissions=_metric(
            len(submitted_pairs),
            len(submitted_pairs),
            "actor_task_pairs",
            value=float(len(submitted_pairs)),
        ),
        completion_rate=_metric(
            len(completed_pairs & submitted_pairs),
            len(submitted_pairs),
            "ratio",
        ),
        average_score=_average(scores, "score"),
        total_attempts=_metric(
            len(submissions),
            len(submitted_pairs),
            "attempts",
            value=float(len(submissions)),
            sample_size=len(submitted_pairs),
        ),
        average_attempts=_average(
            [float(value) for value in attempt_counts.values()],
            "attempts",
        ),
        feedback_view_rate=_metric(
            len(viewed_feedback_workflows & released_workflow_ids),
            len(released_workflow_ids),
            "ratio",
        ),
        funnel=_chronological_funnel(by_pair),
        inactive_learner_count=_metric(
            len(inactive),
            len(roster),
            "learners",
            value=float(len(inactive)),
            sample_size=len(roster),
        ),
        excluded_incomplete_count=legacy_feedback_views,
    )


def calculate_inactive_learners(
    events: list[LearningMetricEvent],
    *,
    roster: list[RosterLearner],
    as_of: datetime,
    last_activity_by_actor: dict[str, datetime] | None = None,
    inactivity_window: timedelta = timedelta(days=14),
) -> list[InactiveLearner]:
    latest_activity: dict[str, datetime] = dict(last_activity_by_actor or {})
    if last_activity_by_actor is None:
        for event in events:
            previous = latest_activity.get(event.pseudonymous_user_id)
            if previous is None or event.occurred_at > previous:
                latest_activity[event.pseudonymous_user_id] = event.occurred_at
    cutoff = as_of - inactivity_window
    inactive = [
        InactiveLearner(
            pseudonymous_user_id=learner.pseudonymous_user_id,
            last_activity_at=latest_activity.get(learner.pseudonymous_user_id),
        )
        for learner in roster
        if latest_activity.get(learner.pseudonymous_user_id) is None
        or latest_activity[learner.pseudonymous_user_id] < cutoff
    ]
    return sorted(
        inactive,
        key=lambda learner: (
            learner.last_activity_at is not None,
            learner.last_activity_at or as_of,
            learner.pseudonymous_user_id,
        ),
    )
