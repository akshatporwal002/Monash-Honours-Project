import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import (
    ExperimentalCondition,
    JudgeDecision,
    JudgeEvaluationStatus,
    LearningEvent,
    LearningEventType,
    ResearchEvaluation,
    ResearchStatus,
    WorkflowOutcome,
    WorkflowRun,
    WorkflowStage,
)
from app.services.analytics import (
    AnalyticsApplication,
    AnalyticsQuery,
    SqlAlchemyAnalyticsRepository,
)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
ACTIVE = f"v1_{'a' * 64}"
NEVER = f"v1_{'b' * 64}"


class Roster:
    async def learner_references(self, course_ids: set[str]) -> list[str]:
        assert course_ids == {"course-1"}
        return ["active", "never"]


class Pseudonymizer:
    def pseudonymize(self, namespace: str, reference: str) -> str:
        assert namespace == "learning-actor"
        return {"active": ACTIVE, "never": NEVER}[reference]


def query() -> AnalyticsQuery:
    return AnalyticsQuery(
        course_ids=("course-1",),
        start_at=NOW - timedelta(days=1),
        end_at=NOW + timedelta(days=1),
    )


def test_sql_analytics_use_half_open_filters_roster_and_terminal_research(
    db_session: Session,
) -> None:
    workflow = WorkflowRun(
        submission_id="submission-1",
        course_id="course-1",
        task_id="task-1",
        current_stage=WorkflowStage.COMPLETED,
        final_outcome=WorkflowOutcome.FIRST_PASS,
        completed_at=NOW,
        execution_attempt_count=1,
        latency_ms=100,
    )
    unviewed_workflow = WorkflowRun(
        submission_id="submission-2",
        course_id="course-1",
        task_id="task-1",
        current_stage=WorkflowStage.COMPLETED,
        final_outcome=WorkflowOutcome.FIRST_PASS,
        completed_at=NOW,
        execution_attempt_count=1,
        latency_ms=90,
    )
    db_session.add_all([workflow, unviewed_workflow])
    db_session.flush()
    db_session.add_all(
        [
            LearningEvent(
                pseudonymous_user_id=ACTIVE,
                course_id="course-1",
                task_id="task-1",
                event_type=LearningEventType.TASK_VIEW,
                occurred_at=NOW - timedelta(minutes=2),
                correlation_id=workflow.id,
                metadata_payload={},
            ),
            LearningEvent(
                pseudonymous_user_id=ACTIVE,
                course_id="course-1",
                task_id="task-1",
                event_type=LearningEventType.SUBMISSION,
                occurred_at=NOW - timedelta(minutes=1),
                correlation_id=workflow.id,
                metadata_payload={"attempt_number": 1, "score": 80},
            ),
            LearningEvent(
                pseudonymous_user_id=ACTIVE,
                course_id="course-1",
                task_id="task-1",
                event_type=LearningEventType.FEEDBACK_VIEW,
                occurred_at=NOW - timedelta(seconds=30),
                correlation_id=workflow.id,
                workflow_reference=workflow.id,
                metadata_payload={"feedback_status": "validated"},
            ),
            # Legacy feedback views cannot be safely attributed to a workflow.
            LearningEvent(
                pseudonymous_user_id=ACTIVE,
                course_id="course-1",
                task_id="task-1",
                event_type=LearningEventType.FEEDBACK_VIEW,
                occurred_at=NOW - timedelta(seconds=15),
                correlation_id=workflow.id,
                metadata_payload={"feedback_status": "validated"},
            ),
            LearningEvent(
                pseudonymous_user_id=ACTIVE,
                course_id="course-1",
                task_id="task-1",
                event_type=LearningEventType.COMPLETION,
                occurred_at=NOW,
                correlation_id=workflow.id,
                metadata_payload={"status": "completed", "score": 80},
            ),
            # The UTC end boundary is excluded.
            LearningEvent(
                pseudonymous_user_id=ACTIVE,
                course_id="course-1",
                task_id="task-2",
                event_type=LearningEventType.TASK_VIEW,
                occurred_at=NOW + timedelta(days=1),
                correlation_id=workflow.id,
                metadata_payload={},
            ),
            ResearchEvaluation(
                case_id=workflow.id,
                workflow_run_id=workflow.id,
                pseudonymous_user_id=ACTIVE,
                course_id="course-1",
                task_id="task-1",
                task_type="short_answer",
                submission_reference=f"v1_{'c' * 64}",
                experimental_condition=ExperimentalCondition.AGENTIC_RAG,
                prompt_version="feedback-v1",
                provider="provider",
                model="model",
                input_references=[],
                retrieved_sources=[],
                simulation_status="not_requested",
                generated_output={"summary": "Measured output"},
                judge_result={"reason": "Pass"},
                measurement_schema_version="research-v1",
                latency_ms=100,
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                estimated_cost=Decimal("0.01"),
                usage_complete=True,
                comparable=True,
                first_judge_status=JudgeEvaluationStatus.VALID,
                first_judge_decision=JudgeDecision.PASS,
                final_judge_status=JudgeEvaluationStatus.VALID,
                final_judge_decision=JudgeDecision.PASS,
                correctness_score=90,
                relevance_score=91,
                grounding_score=92,
                actionability_score=93,
                safety_score=100,
                unsupported_claim_count=0,
                quality_policy_version="quality-policy-v1",
                status=ResearchStatus.COMPLETED,
                created_at=NOW,
                completed_at=NOW,
            ),
            ResearchEvaluation(
                case_id=workflow.id,
                workflow_run_id=workflow.id,
                pseudonymous_user_id=ACTIVE,
                course_id="course-1",
                task_id="task-1",
                task_type="short_answer",
                submission_reference=f"v1_{'c' * 64}",
                experimental_condition=ExperimentalCondition.SINGLE_STEP_BASELINE,
                prompt_version="baseline-v1",
                provider="provider",
                model="model",
                input_references=[],
                retrieved_sources=[],
                simulation_status="not_requested",
                generated_output={},
                measurement_schema_version="research-v1",
                comparable=True,
                status=ResearchStatus.PENDING,
                created_at=NOW,
            ),
        ]
    )
    db_session.commit()
    application = AnalyticsApplication(
        SqlAlchemyAnalyticsRepository(db_session),
        Roster(),
        Pseudonymizer(),
        now=lambda: NOW + timedelta(hours=1),
    )

    learning = asyncio.run(application.learning(query()))
    research = application.research(query())
    options = application.filter_options({"course-1"})

    assert learning.task_views.value == 1
    assert learning.unique_submissions.value == 1
    assert learning.completion_rate.value == 1
    assert learning.feedback_view_rate.value == 0.5
    assert learning.feedback_view_rate.denominator == 2
    assert learning.excluded_incomplete_count == 1
    assert learning.inactive_learner_count.value == 1
    assert learning.inactive_learner_count.denominator == 2
    inactive = asyncio.run(application.inactive_learners(query(), page=1, page_size=25))
    assert [item.pseudonymous_user_id for item in inactive.items] == [NEVER]
    assert inactive.total == 1
    assert inactive.schema_version == "inactive-learners-v1"
    assert inactive.filters.course_ids == ["course-1"]
    assert inactive.inactive_learner_count.value == 1
    assert inactive.inactive_learner_count.denominator == 2
    assert inactive.inactive_learner_count.unit == "learners"
    assert inactive.excluded_incomplete_count == 0
    assert research.first_pass_rate.value == 1
    assert research.retrieval_hit_rate.value is None
    assert research.excluded_incomplete_count == 2
    assert options.courses == ["course-1"]
    assert options.task_types == ["short_answer"]
    assert options.models == ["model"]


def test_research_analytics_use_half_open_created_at_boundaries(
    db_session: Session,
) -> None:
    start_at = NOW - timedelta(days=1)
    end_at = NOW + timedelta(days=1)

    def record(case_id: str, created_at: datetime) -> ResearchEvaluation:
        return ResearchEvaluation(
            case_id=case_id,
            pseudonymous_user_id=ACTIVE,
            course_id="course-1",
            task_id="task-1",
            task_type="short_answer",
            submission_reference=f"v1_{case_id[-1] * 64}",
            experimental_condition=ExperimentalCondition.SINGLE_STEP_BASELINE,
            prompt_version="baseline-v1",
            provider="provider",
            model="model",
            created_at=created_at,
        )

    db_session.add_all(
        [
            record("case-at-start-a", start_at),
            record("case-before-end-b", end_at - timedelta(microseconds=1)),
            record("case-at-end-c", end_at),
        ]
    )
    db_session.commit()

    records = SqlAlchemyAnalyticsRepository(db_session).research_records(
        AnalyticsQuery(
            course_ids=("course-1",),
            start_at=start_at,
            end_at=end_at,
        )
    )

    assert {record.case_id for record in records} == {
        "case-at-start-a",
        "case-before-end-b",
    }


def test_inactivity_uses_latest_activity_before_historical_range_end(
    db_session: Session,
) -> None:
    historical_end = datetime(2026, 1, 31, 12, 0, tzinfo=UTC)
    db_session.add(
        LearningEvent(
            pseudonymous_user_id=ACTIVE,
            course_id="course-1",
            task_id="task-before-window",
            event_type=LearningEventType.TASK_VIEW,
            occurred_at=historical_end - timedelta(days=10),
            correlation_id=str(uuid4()),
            metadata_payload={},
        )
    )
    db_session.commit()
    historical_query = AnalyticsQuery(
        course_ids=("course-1",),
        start_at=historical_end - timedelta(days=7),
        end_at=historical_end,
    )
    application = AnalyticsApplication(
        SqlAlchemyAnalyticsRepository(db_session),
        Roster(),
        Pseudonymizer(),
        now=lambda: NOW,
    )

    learning = asyncio.run(application.learning(historical_query))
    inactive = asyncio.run(
        application.inactive_learners(
            historical_query,
            page=1,
            page_size=25,
        )
    )

    assert learning.task_views.value == 0
    assert learning.inactive_learner_count.value == 1
    assert [item.pseudonymous_user_id for item in inactive.items] == [NEVER]
