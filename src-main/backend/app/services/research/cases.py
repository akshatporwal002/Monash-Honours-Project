from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.models.enums import JudgeDecision, JudgeEvaluationStatus
from app.schemas.feedback import FeedbackContext, FeedbackPipelineResult, JudgeEvaluationOutcome
from app.services.feedback.contracts import FeedbackAttemptPersistence

RESEARCH_MEASUREMENT_VERSION = "research-v1"
RETRIEVAL_RELEVANCE_THRESHOLD = 0.5
RESEARCH_COST_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class RetrievedSourceMeasurement:
    source_id: str
    label: str
    relevance_score: float


@dataclass(frozen=True, slots=True)
class JudgeMeasurement:
    evaluation_status: str
    reported_decision: str | None
    effective_decision: str | None
    correctness_score: int | None
    relevance_score: int | None
    grounding_score: int | None
    actionability_score: int | None
    safety_score: int | None
    unsupported_claim_count: int | None
    quality_policy_version: str
    result: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class ResearchCaseSeed:
    case_id: str
    workflow_run_id: str
    correlation_id: str
    pseudonymous_user_id: str
    pseudonymous_submission_reference: str
    course_id: str
    task_id: str
    task_type: str
    provider: str
    model: str
    prompt_version: str
    input_references: tuple[str, ...]
    retrieved_sources: tuple[RetrievedSourceMeasurement, ...]
    retrieval_request_count: int
    retrieval_hit_count: int
    simulation_reference: str | None
    simulation_status: str
    generated_output: dict[str, Any]
    first_judge: JudgeMeasurement | None
    final_judge: JudgeMeasurement | None
    primary_latency_ms: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: Decimal
    regeneration_count: int
    fallback_used: bool
    comparable: bool
    usage_complete: bool
    measurement_schema_version: str = RESEARCH_MEASUREMENT_VERSION


def judge_measurement(outcome: JudgeEvaluationOutcome | None) -> JudgeMeasurement | None:
    if outcome is None:
        return None
    result = outcome.judge_result
    return JudgeMeasurement(
        evaluation_status=outcome.evaluation_status.value,
        reported_decision=(
            outcome.reported_decision.value if outcome.reported_decision is not None else None
        ),
        effective_decision=result.decision.value if result is not None else None,
        correctness_score=result.correctness_score if result is not None else None,
        relevance_score=result.relevance_score if result is not None else None,
        grounding_score=result.grounding_score if result is not None else None,
        actionability_score=result.actionability_score if result is not None else None,
        safety_score=result.safety_score if result is not None else None,
        unsupported_claim_count=(len(result.unsupported_claims) if result is not None else None),
        quality_policy_version=outcome.quality_policy_version,
        result=(
            {
                "reported_decision": outcome.reported_decision.value,
                "effective_decision": result.decision.value,
                "correctness_score": result.correctness_score,
                "relevance_score": result.relevance_score,
                "grounding_score": result.grounding_score,
                "actionability_score": result.actionability_score,
                "safety_score": result.safety_score,
                "reason": result.reason,
                "unsupported_claims": list(result.unsupported_claims),
                "regeneration_instructions": list(result.regeneration_instructions),
                "quality_policy_version": outcome.quality_policy_version,
            }
            if result is not None
            else None
        ),
    )


def final_effective_pass(seed: ResearchCaseSeed) -> bool:
    return (
        seed.final_judge is not None
        and seed.final_judge.evaluation_status == JudgeEvaluationStatus.VALID.value
        and seed.final_judge.effective_decision == JudgeDecision.PASS.value
    )


def seed_from_terminal_feedback(
    *,
    context: FeedbackContext,
    result: FeedbackPipelineResult,
    attempts: tuple[FeedbackAttemptPersistence, ...],
    pseudonymous_user_id: str,
    pseudonymous_submission_reference: str,
    fallback_provider: str,
    fallback_model: str,
) -> ResearchCaseSeed:
    last_attempt = attempts[-1] if attempts else None
    first_judge = judge_measurement(attempts[0].judge_evaluation if attempts else None)
    final_judge = judge_measurement(attempts[-1].judge_evaluation if attempts else None)
    generated_output: dict[str, Any]
    if last_attempt is not None:
        generated_output = dict(last_attempt.generated_feedback.feedback_content)
    elif result.safe_fallback is not None:
        generated_output = dict(result.safe_fallback.feedback_content)
    else:
        generated_output = {}

    generated = last_attempt.generated_feedback if last_attempt is not None else None
    provider = generated.provider if generated is not None else fallback_provider
    model = generated.model if generated is not None else fallback_model
    prompt_version = generated.prompt_version if generated is not None else "unavailable"
    provider_consistent = all(
        attempt.generated_feedback.provider == provider
        and attempt.generated_feedback.model == model
        for attempt in attempts
    )
    retrieval_sources = tuple(
        RetrievedSourceMeasurement(
            source_id=item.source_id,
            label=item.source_label,
            relevance_score=item.relevance_score,
        )
        for item in context.retrieval_context
    )
    usage_complete = bool(attempts) and all(
        attempt.generated_feedback.usage_complete and attempt.judge_evaluation.usage_complete
        for attempt in attempts
    )
    return ResearchCaseSeed(
        case_id=result.workflow_run_id,
        workflow_run_id=result.workflow_run_id,
        correlation_id=context.correlation_id,
        pseudonymous_user_id=pseudonymous_user_id,
        pseudonymous_submission_reference=pseudonymous_submission_reference,
        course_id=context.task.course_id,
        task_id=context.task.task_id,
        task_type=context.task.task_type,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        input_references=tuple(context.task.source_references),
        retrieved_sources=retrieval_sources,
        retrieval_request_count=len(context.retrieval_request_ids),
        retrieval_hit_count=len(
            {
                item.retrieval_request_id
                for item in context.retrieval_context
                if item.relevance_score >= RETRIEVAL_RELEVANCE_THRESHOLD
            }
        ),
        simulation_reference=(
            context.simulation_context.simulation_id
            if context.simulation_context is not None
            else None
        ),
        simulation_status=context.simulation_status.value,
        generated_output=generated_output,
        first_judge=first_judge,
        final_judge=final_judge,
        primary_latency_ms=result.latency_ms,
        input_tokens=result.token_usage.input_tokens,
        output_tokens=result.token_usage.output_tokens,
        total_tokens=result.token_usage.total_tokens,
        estimated_cost=result.estimated_cost.quantize(RESEARCH_COST_QUANTUM),
        regeneration_count=result.regeneration_count,
        fallback_used=result.fallback_used,
        comparable=bool(attempts) and provider_consistent,
        usage_complete=usage_complete,
    )
