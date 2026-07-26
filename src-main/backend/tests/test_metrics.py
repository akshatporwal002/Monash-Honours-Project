from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models.enums import ExperimentalCondition, LearningEventType
from app.services.analytics import (
    LearningMetricEvent,
    ResearchMetricRecord,
    RosterLearner,
    calculate_inactive_learners,
    calculate_learning_metrics,
    calculate_research_metrics,
)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


def research_record(
    case_id: str,
    condition: ExperimentalCondition,
    **updates: object,
) -> ResearchMetricRecord:
    values: dict[str, object] = {
        "case_id": case_id,
        "condition": condition,
        "judge_valid": True,
        "final_pass": True,
        "first_pass": True,
        "unsupported_claim_count": 0,
        "relevance_score": 90,
        "latency_ms": 100,
        "total_tokens": 20,
        "estimated_cost": Decimal("0.02"),
        "usage_complete": True,
    }
    values.update(updates)
    return ResearchMetricRecord(**values)  # type: ignore[arg-type]


def test_research_metrics_use_locked_denominators_and_paired_differences() -> None:
    records = [
        research_record(
            "case-1",
            ExperimentalCondition.AGENTIC_RAG,
            retrieval_request_count=2,
            retrieval_hit_count=1,
        ),
        research_record(
            "case-1",
            ExperimentalCondition.SINGLE_STEP_BASELINE,
            final_pass=False,
            relevance_score=70,
            latency_ms=50,
            total_tokens=10,
            estimated_cost=Decimal("0.01"),
        ),
        research_record(
            "case-2",
            ExperimentalCondition.AGENTIC_RAG,
            first_pass=False,
            final_pass=True,
            regeneration_count=1,
            unsupported_claim_count=1,
            retrieval_request_count=1,
            retrieval_hit_count=1,
        ),
        research_record(
            "case-2",
            ExperimentalCondition.SINGLE_STEP_BASELINE,
            final_pass=True,
            relevance_score=80,
        ),
        research_record(
            "legacy",
            ExperimentalCondition.AGENTIC_RAG,
            metrics_eligible=False,
        ),
    ]

    result = calculate_research_metrics(records)

    assert result.first_pass_rate.value == 0.5
    assert result.first_pass_rate.denominator == 2
    assert result.regeneration_success_rate.value == 1
    assert result.retrieval_hit_rate.value == 2 / 3
    assert result.by_condition[ExperimentalCondition.AGENTIC_RAG].hallucination_rate.value == 0.5
    assert result.paired_agentic_minus_baseline.pass_rate.value == 0.5
    assert result.paired_agentic_minus_baseline.relevance.value == 15
    assert result.paired_agentic_minus_baseline.latency_ms.value == 25
    assert result.excluded_incomplete_count == 1


def test_research_metrics_return_null_for_empty_denominators() -> None:
    result = calculate_research_metrics([])

    assert result.first_pass_rate.value is None
    assert result.first_pass_rate.denominator == 0
    assert result.retrieval_hit_rate.value is None
    assert all(metrics.overall_pass_rate.value is None for metrics in result.by_condition.values())


def test_research_incomplete_count_includes_every_distinct_excluded_record() -> None:
    records = [
        research_record("complete", ExperimentalCondition.AGENTIC_RAG),
        research_record("complete", ExperimentalCondition.SINGLE_STEP_BASELINE),
        research_record(
            "pending",
            ExperimentalCondition.AGENTIC_RAG,
            terminal=False,
        ),
        research_record(
            "legacy",
            ExperimentalCondition.SINGLE_STEP_BASELINE,
            metrics_eligible=False,
        ),
        research_record(
            "usage",
            ExperimentalCondition.AGENTIC_RAG,
            usage_complete=False,
        ),
        research_record("usage", ExperimentalCondition.SINGLE_STEP_BASELINE),
        research_record("unpaired", ExperimentalCondition.AGENTIC_RAG),
        research_record(
            "missing-first",
            ExperimentalCondition.AGENTIC_RAG,
            first_pass=None,
        ),
        research_record(
            "missing-first",
            ExperimentalCondition.SINGLE_STEP_BASELINE,
        ),
        research_record(
            "noncomparable",
            ExperimentalCondition.AGENTIC_RAG,
            comparable=False,
        ),
        research_record(
            "noncomparable",
            ExperimentalCondition.SINGLE_STEP_BASELINE,
            comparable=False,
        ),
    ]

    result = calculate_research_metrics(records)

    assert result.excluded_incomplete_count == 7


def event(
    actor: str,
    task: str,
    event_type: LearningEventType,
    minute: int,
    **metadata: object,
) -> LearningMetricEvent:
    return LearningMetricEvent(
        pseudonymous_user_id=actor,
        task_id=task,
        event_type=event_type,
        occurred_at=NOW + timedelta(minutes=minute),
        metadata=metadata,
    )


def test_learning_metrics_calculate_ordered_funnel_and_inactivity() -> None:
    events = [
        event("student-1", "task-1", LearningEventType.TASK_VIEW, 0),
        event("student-1", "task-1", LearningEventType.DRAFT_SAVE, 1),
        event("student-1", "task-1", LearningEventType.SUBMISSION, 2, score=80),
        LearningMetricEvent(
            pseudonymous_user_id="student-1",
            task_id="task-1",
            event_type=LearningEventType.FEEDBACK_VIEW,
            occurred_at=NOW + timedelta(minutes=3),
            metadata={},
            workflow_reference="workflow-1",
        ),
        event("student-1", "task-1", LearningEventType.COMPLETION, 4),
        event("student-2", "task-1", LearningEventType.TASK_VIEW, 0),
        event("student-2", "task-1", LearningEventType.SUBMISSION, 2, score=60),
        event("student-2", "task-1", LearningEventType.SUBMISSION, 3, score=70),
        event("student-old", "task-2", LearningEventType.TASK_VIEW, -60 * 24 * 20),
    ]
    result = calculate_learning_metrics(
        events,
        released_workflow_ids={"workflow-1", "workflow-2"},
        roster=[
            RosterLearner("student-1"),
            RosterLearner("student-2"),
            RosterLearner("student-old"),
            RosterLearner("student-never"),
        ],
        as_of=NOW + timedelta(days=1),
    )

    assert result.completion_rate.value == 0.5
    assert result.average_score.value == 70
    assert result.average_attempts.value == 1.5
    assert result.feedback_view_rate.value == 0.5
    assert [stage.count for stage in result.funnel] == [3, 1, 1, 1, 1]
    assert result.inactive_learner_count.value == 2
    assert result.inactive_learner_count.denominator == 4
    inactive = calculate_inactive_learners(
        events,
        roster=[
            RosterLearner("student-1"),
            RosterLearner("student-2"),
            RosterLearner("student-old"),
            RosterLearner("student-never"),
        ],
        as_of=NOW + timedelta(days=1),
    )
    assert [learner.pseudonymous_user_id for learner in inactive] == [
        "student-never",
        "student-old",
    ]


def test_feedback_view_rate_uses_workflow_linkage_and_excludes_legacy_nulls() -> None:
    events = [
        LearningMetricEvent(
            pseudonymous_user_id="actor-b",
            task_id="shared-task",
            event_type=LearningEventType.FEEDBACK_VIEW,
            occurred_at=NOW,
            metadata={},
            workflow_reference="workflow-a",
        ),
        event("actor-a", "shared-task", LearningEventType.FEEDBACK_VIEW, 1),
    ]

    result = calculate_learning_metrics(
        events,
        released_workflow_ids={"workflow-a", "workflow-b"},
        roster=[],
        as_of=NOW,
    )

    assert result.feedback_view_rate.value == 0.5
    assert result.feedback_view_rate.numerator == 1
    assert result.feedback_view_rate.denominator == 2
    assert result.excluded_incomplete_count == 1
