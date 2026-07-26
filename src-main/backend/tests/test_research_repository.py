from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ExperimentalCondition,
    JudgeDecision,
    JudgeEvaluationStatus,
    ResearchEvaluation,
    ResearchStatus,
    WorkflowRun,
)
from app.schemas.feedback import (
    FeedbackResponseClassification,
    GeneratedFeedback,
    JudgeEvaluationOutcome,
    JudgeResult,
    TokenUsage,
)
from app.services.research import (
    BaselineCompletion,
    JudgeMeasurement,
    ResearchCaseConflictError,
    ResearchCaseSeed,
    ResearchPersistenceError,
    SqlAlchemyResearchJobRepository,
)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


def measurement(decision: JudgeDecision) -> JudgeMeasurement:
    return JudgeMeasurement(
        evaluation_status=JudgeEvaluationStatus.VALID.value,
        reported_decision=decision.value,
        effective_decision=decision.value,
        correctness_score=90,
        relevance_score=91,
        grounding_score=92,
        actionability_score=93,
        safety_score=100,
        unsupported_claim_count=0,
        quality_policy_version="quality-policy-v1",
        result={
            "effective_decision": decision.value,
            "correctness_score": 90,
            "relevance_score": 91,
        },
    )


def seed(workflow_id: str) -> ResearchCaseSeed:
    judged = measurement(JudgeDecision.PASS)
    return ResearchCaseSeed(
        case_id=workflow_id,
        workflow_run_id=workflow_id,
        correlation_id=workflow_id,
        pseudonymous_user_id=f"v1_{'a' * 64}",
        pseudonymous_submission_reference=f"v1_{'b' * 64}",
        course_id="course-1",
        task_id="task-1",
        task_type="short_answer",
        provider="provider",
        model="model",
        prompt_version="feedback-v1",
        input_references=("source-1",),
        retrieved_sources=(),
        retrieval_request_count=1,
        retrieval_hit_count=0,
        simulation_reference=None,
        simulation_status="not_requested",
        generated_output={"summary": "Student-facing candidate"},
        first_judge=judged,
        final_judge=judged,
        primary_latency_ms=250,
        input_tokens=20,
        output_tokens=10,
        total_tokens=30,
        estimated_cost=Decimal("0.03"),
        regeneration_count=0,
        fallback_used=False,
        comparable=True,
        usage_complete=True,
    )


def completion() -> BaselineCompletion:
    generated = GeneratedFeedback(
        feedback_content={
            "response_classification": FeedbackResponseClassification.CORRECT.value,
            "summary": "Baseline result",
            "identified_error": None,
            "explanation": "Correct",
            "improvement_actions": [],
            "recommended_next_step": "Continue",
            "source_references": [],
            "simulation_references": [],
        },
        provider="provider",
        model="model",
        prompt_version="baseline-v1",
        source_references=[],
        simulation_references=[],
        token_usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        estimated_cost=Decimal("0.01"),
    )
    evaluation = JudgeEvaluationOutcome(
        evaluation_status=JudgeEvaluationStatus.VALID,
        reported_decision=JudgeDecision.PASS,
        judge_result=JudgeResult(
            decision=JudgeDecision.PASS,
            correctness_score=90,
            relevance_score=90,
            grounding_score=90,
            actionability_score=90,
            safety_score=100,
            reason="Pass",
        ),
        reason="Pass",
        provider="provider",
        model="judge",
        prompt_version="quality-judge-v1",
        token_usage=TokenUsage(input_tokens=3, output_tokens=2, total_tokens=5),
        estimated_cost=Decimal("0.002"),
    )
    return BaselineCompletion(
        generated_feedback=generated,
        judge_evaluation=evaluation,
        generation_latency_ms=100,
        generation_token_usage=generated.token_usage,
        generation_cost=generated.estimated_cost,
        evaluation_latency_ms=20,
        evaluation_token_usage=evaluation.token_usage,
        evaluation_cost=evaluation.estimated_cost,
        usage_complete=True,
        comparable=True,
    )


def workflow(db_session: Session) -> WorkflowRun:
    record = WorkflowRun(id=str(uuid4()), submission_id=f"submission-{uuid4()}")
    db_session.add(record)
    db_session.commit()
    return record


def test_create_pair_is_atomic_private_and_exactly_replayable(
    db_session: Session,
) -> None:
    workflow_record = workflow(db_session)
    repository = SqlAlchemyResearchJobRepository(db_session)
    case = seed(workflow_record.id)

    repository.create_pair(case)
    repository.create_pair(case)

    rows = list(
        db_session.scalars(
            select(ResearchEvaluation).order_by(ResearchEvaluation.experimental_condition)
        )
    )
    assert len(rows) == 2
    agentic = next(
        row for row in rows if row.experimental_condition is ExperimentalCondition.AGENTIC_RAG
    )
    baseline = next(
        row
        for row in rows
        if row.experimental_condition is ExperimentalCondition.SINGLE_STEP_BASELINE
    )
    assert agentic.status is ResearchStatus.COMPLETED
    assert baseline.status is ResearchStatus.PENDING
    assert baseline.input_references == []
    assert baseline.retrieved_sources == []
    assert baseline.simulation_reference is None
    assert "submission-" not in repr(rows)

    with pytest.raises(ResearchCaseConflictError):
        repository.create_pair(replace(case, task_id="different-task"))
    for changed_measurement in (
        replace(case, generated_output={"summary": "Different candidate"}),
        replace(case, primary_latency_ms=251),
        replace(case, input_tokens=21, total_tokens=31),
        replace(case, fallback_used=True),
    ):
        with pytest.raises(ResearchCaseConflictError):
            repository.create_pair(changed_measurement)


def test_create_pair_requires_workflow_id_as_the_shared_case_id(
    db_session: Session,
) -> None:
    workflow_record = workflow(db_session)
    repository = SqlAlchemyResearchJobRepository(db_session)

    with pytest.raises(ResearchPersistenceError):
        repository.create_pair(
            replace(
                seed(workflow_record.id),
                case_id=str(uuid4()),
            )
        )

    assert list(db_session.scalars(select(ResearchEvaluation))) == []


def test_create_pair_canonicalizes_cost_for_exact_storage_replay(
    db_session: Session,
) -> None:
    workflow_record = workflow(db_session)
    repository = SqlAlchemyResearchJobRepository(db_session)
    precise = replace(
        seed(workflow_record.id),
        estimated_cost=Decimal("0.0300001"),
    )

    repository.create_pair(precise)
    repository.create_pair(precise)

    agentic = db_session.scalar(
        select(ResearchEvaluation).where(
            ResearchEvaluation.experimental_condition == ExperimentalCondition.AGENTIC_RAG
        )
    )
    assert agentic is not None
    assert agentic.estimated_cost == Decimal("0.030000")


def test_stale_baseline_claim_is_fenced_and_measurements_are_separated(
    db_session: Session,
) -> None:
    workflow_record = workflow(db_session)
    repository = SqlAlchemyResearchJobRepository(
        db_session,
        lease_duration=timedelta(minutes=5),
    )
    repository.create_pair(seed(workflow_record.id))

    stale = repository.claim_next(now=NOW)
    assert stale is not None
    winner = repository.claim_next(now=NOW + timedelta(minutes=6))
    assert winner is not None
    assert winner.execution_token != stale.execution_token
    assert winner.processing_attempts == 2

    assert repository.complete(stale, completion(), completed_at=NOW) is False
    assert repository.complete(winner, completion(), completed_at=NOW) is True

    baseline = db_session.scalar(
        select(ResearchEvaluation).where(
            ResearchEvaluation.experimental_condition == ExperimentalCondition.SINGLE_STEP_BASELINE
        )
    )
    assert baseline is not None
    assert baseline.status is ResearchStatus.COMPLETED
    assert baseline.latency_ms == 100
    assert baseline.total_tokens == 15
    assert baseline.evaluation_latency_ms == 20
    assert baseline.evaluation_total_tokens == 5
    assert baseline.evaluation_estimated_cost == Decimal("0.002000")


def test_failed_baseline_is_terminal_without_ordinary_retry(db_session: Session) -> None:
    workflow_record = workflow(db_session)
    repository = SqlAlchemyResearchJobRepository(db_session)
    repository.create_pair(seed(workflow_record.id))
    claim = repository.claim_next(now=NOW)
    assert claim is not None

    assert repository.fail(
        claim,
        "baseline_processing_failed",
        completed_at=NOW,
    )
    assert repository.claim_next(now=NOW + timedelta(days=1)) is None


def test_third_expired_baseline_claim_is_fenced_and_terminally_failed(
    db_session: Session,
) -> None:
    workflow_record = workflow(db_session)
    repository = SqlAlchemyResearchJobRepository(
        db_session,
        lease_duration=timedelta(minutes=5),
    )
    repository.create_pair(seed(workflow_record.id))

    first = repository.claim_next(now=NOW, maximum_attempts=3)
    assert first is not None
    second = repository.claim_next(
        now=NOW + timedelta(minutes=6),
        maximum_attempts=3,
    )
    assert second is not None
    third = repository.claim_next(
        now=NOW + timedelta(minutes=12),
        maximum_attempts=3,
    )
    assert third is not None
    assert third.processing_attempts == 3
    assert (
        repository.claim_next(
            now=NOW + timedelta(minutes=18),
            maximum_attempts=3,
        )
        is None
    )

    finalized = repository.finalize_next_exhausted(
        now=NOW + timedelta(minutes=18),
        maximum_attempts=3,
    )

    assert finalized == third.research_evaluation_id
    baseline = db_session.get(ResearchEvaluation, third.research_evaluation_id)
    assert baseline is not None
    assert baseline.status is ResearchStatus.FAILED
    assert baseline.processing_attempts == 3
    assert baseline.execution_token is None
    assert baseline.lease_expires_at is None
    assert baseline.failure_category == "baseline_worker_lease_expired"
