from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.enums import (
    FeedbackStatus,
    TerminalIntegrationFailureCategory,
    TerminalIntegrationType,
    WorkflowStage,
)
from app.models.persistence import FeedbackRecord, JudgeEvaluation, WorkflowRun
from app.services.continuation.contracts import TerminalFeedbackNotice
from app.services.continuation.repository import SqlAlchemyContinuationRepository
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository
from app.services.research.cases import (
    JudgeMeasurement,
    ResearchCaseSeed,
    RetrievedSourceMeasurement,
)
from app.services.research.repository import SqlAlchemyResearchJobRepository
from app.services.terminal_integrations.contracts import (
    ContinuationIntegrationIntent,
    ResearchIntegrationIntent,
    RetrievedSourceIntent,
    TerminalIntegrationClaim,
)
from app.services.terminal_integrations.repository import (
    SqlAlchemyTerminalIntegrationRepository,
    TerminalIntegrationPayloadError,
    valid_intent,
)

_SCHEMA_VERSION = "terminal-integration.v1"


@dataclass(frozen=True, slots=True)
class TerminalIntegrationWorkerOutcome:
    processed: bool
    workflow_run_id: str | None = None
    integration_type: TerminalIntegrationType | None = None
    retryable: bool = False
    stale_claim: bool = False
    failure_category: TerminalIntegrationFailureCategory | None = None


class TerminalIntegrationWorker:
    """Reconcile one privacy-safe terminal handoff under a fenced lease."""

    def __init__(
        self,
        session: Session,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        lease_duration: timedelta = timedelta(minutes=5),
        maximum_attempts: int = 3,
    ) -> None:
        if not 1 <= maximum_attempts <= 3:
            raise ValueError("maximum_attempts must be between 1 and 3")
        self._session = session
        self._repository = SqlAlchemyTerminalIntegrationRepository(session)
        self._now = now
        self._lease_duration = lease_duration
        self._maximum_attempts = maximum_attempts

    async def run_once(self) -> TerminalIntegrationWorkerOutcome:
        observed_at = self._now()
        exhausted = self._repository.finalize_next_exhausted(
            observed_at=observed_at,
            maximum_attempts=self._maximum_attempts,
        )
        if exhausted is not None:
            return TerminalIntegrationWorkerOutcome(
                processed=True,
                failure_category=(TerminalIntegrationFailureCategory.INTEGRATION_UNAVAILABLE),
            )
        claim = self._repository.claim_next(
            now=observed_at,
            lease_expires_at=observed_at + self._lease_duration,
            execution_token=str(uuid4()),
            maximum_attempts=self._maximum_attempts,
        )
        if claim is None:
            return TerminalIntegrationWorkerOutcome(processed=False)
        try:
            self._apply(claim)
        except TerminalIntegrationPayloadError:
            return self._failure(
                claim,
                TerminalIntegrationFailureCategory.INVALID_PAYLOAD,
                retryable=False,
            )
        except Exception:
            return self._failure(
                claim,
                TerminalIntegrationFailureCategory.INTEGRATION_UNAVAILABLE,
                retryable=claim.processing_attempts < self._maximum_attempts,
            )

        try:
            completed = self._repository.complete(
                claim,
                completed_at=self._now(),
            )
        except Exception:
            # The target commit may already be durable. The expired outbox claim
            # will replay idempotently without duplicating either integration.
            return TerminalIntegrationWorkerOutcome(
                processed=True,
                workflow_run_id=claim.workflow_run_id,
                integration_type=claim.integration_type,
                retryable=True,
            )
        return TerminalIntegrationWorkerOutcome(
            processed=True,
            workflow_run_id=claim.workflow_run_id,
            integration_type=claim.integration_type,
            stale_claim=not completed,
        )

    def _apply(self, claim: TerminalIntegrationClaim) -> None:
        if claim.integration_type is TerminalIntegrationType.CONTINUATION:
            self._ensure_continuation(claim)
            return
        if claim.integration_type is TerminalIntegrationType.RESEARCH_PAIR:
            seed = self._research_seed(claim)
            SqlAlchemyResearchJobRepository(self._session).create_pair(seed)
            return
        raise TerminalIntegrationPayloadError("terminal integration payload is invalid")

    def _ensure_continuation(self, claim: TerminalIntegrationClaim) -> None:
        payload = claim.payload
        self._require_keys(
            payload,
            {
                "schema_version",
                "pseudonymous_actor_reference",
                "course_reference",
                "completed_task_reference",
            },
        )
        self._require_schema(payload)
        try:
            intent = ContinuationIntegrationIntent(
                correlation_id=claim.correlation_id,
                pseudonymous_actor_reference=self._text(payload["pseudonymous_actor_reference"]),
                course_reference=self._text(payload["course_reference"]),
                completed_task_reference=self._text(payload["completed_task_reference"]),
            )
            if not valid_intent(claim.workflow_run_id, intent):
                raise TerminalIntegrationPayloadError("terminal integration payload is invalid")
            notice = TerminalFeedbackNotice(
                workflow_run_id=claim.workflow_run_id,
                pseudonymous_actor_reference=intent.pseudonymous_actor_reference,
                course_reference=intent.course_reference,
                completed_task_reference=intent.completed_task_reference,
                correlation_id=claim.correlation_id,
            )
            SqlAlchemyContinuationRepository(self._session).ensure_pending(notice)
        except TerminalIntegrationPayloadError:
            raise
        except (KeyError, TypeError, ValueError):
            raise TerminalIntegrationPayloadError(
                "terminal integration payload is invalid"
            ) from None

    def _research_seed(self, claim: TerminalIntegrationClaim) -> ResearchCaseSeed:
        payload = claim.payload
        self._require_keys(
            payload,
            {
                "schema_version",
                "pseudonymous_user_id",
                "pseudonymous_submission_reference",
                "task_type",
                "fallback_provider",
                "fallback_model",
                "input_references",
                "retrieved_sources",
                "retrieval_request_count",
                "retrieval_hit_count",
                "simulation_reference",
                "simulation_status",
            },
        )
        self._require_schema(payload)
        intent = self._parse_research_intent(claim)
        workflow = self._terminal_workflow(claim.workflow_run_id)
        terminal_result = SqlAlchemyFeedbackWorkflowRepository(self._session).get_by_submission(
            workflow.submission_id
        )
        if terminal_result is None or terminal_result.workflow_run_id != claim.workflow_run_id:
            raise TerminalIntegrationPayloadError("terminal workflow is invalid")
        generated = sorted(
            (
                record
                for record in workflow.feedback_records
                if record.generation_attempt is not None
            ),
            key=lambda record: record.generation_attempt or 0,
        )
        released = [
            record
            for record in workflow.feedback_records
            if record.status in {FeedbackStatus.ACCEPTED, FeedbackStatus.SAFE_FALLBACK}
        ]
        if len(released) != 1:
            raise TerminalIntegrationPayloadError("terminal workflow is invalid")
        last = generated[-1] if generated else None
        final_output = last.feedback_content if last is not None else released[0].feedback_content
        provider = last.provider if last is not None else intent.fallback_provider
        model = last.model if last is not None else intent.fallback_model
        prompt_version = last.prompt_version if last is not None else "unavailable"
        if not all(isinstance(item, str) and item for item in (provider, model, prompt_version)):
            raise TerminalIntegrationPayloadError("terminal workflow is invalid")

        measurements = [self._judge_measurement(record.judge_evaluation) for record in generated]
        try:
            retrieved = tuple(
                RetrievedSourceMeasurement(
                    source_id=source.source_id,
                    label=source.label,
                    relevance_score=source.relevance_score,
                )
                for source in intent.retrieved_sources
            )
            kwargs: dict[str, object] = {
                "case_id": workflow.id,
                "workflow_run_id": workflow.id,
                "correlation_id": claim.correlation_id,
                "pseudonymous_user_id": intent.pseudonymous_user_id,
                "pseudonymous_submission_reference": (intent.pseudonymous_submission_reference),
                "course_id": self._required(workflow.course_id),
                "task_id": self._required(workflow.task_id),
                "task_type": intent.task_type,
                "provider": provider,
                "model": model,
                "prompt_version": prompt_version,
                "input_references": intent.input_references,
                "retrieved_sources": retrieved,
                "retrieval_request_count": intent.retrieval_request_count,
                "retrieval_hit_count": intent.retrieval_hit_count,
                "simulation_reference": intent.simulation_reference,
                "simulation_status": intent.simulation_status,
                "generated_output": dict(final_output),
                "first_judge": measurements[0] if measurements else None,
                "final_judge": measurements[-1] if measurements else None,
                "primary_latency_ms": terminal_result.latency_ms,
                "input_tokens": terminal_result.token_usage.input_tokens,
                "output_tokens": terminal_result.token_usage.output_tokens,
                "total_tokens": terminal_result.token_usage.total_tokens,
                "estimated_cost": terminal_result.estimated_cost,
                "regeneration_count": terminal_result.regeneration_count,
                "fallback_used": terminal_result.fallback_used,
                "comparable": bool(generated)
                and all(
                    record.provider == provider and record.model == model for record in generated
                ),
                "usage_complete": bool(generated)
                and all(
                    record.usage_complete
                    and record.judge_evaluation is not None
                    and record.judge_evaluation.usage_complete
                    for record in generated
                ),
            }
            return ResearchCaseSeed(**kwargs)
        except (KeyError, TypeError, ValueError):
            raise TerminalIntegrationPayloadError(
                "terminal integration payload is invalid"
            ) from None

    def _parse_research_intent(
        self,
        claim: TerminalIntegrationClaim,
    ) -> ResearchIntegrationIntent:
        payload = claim.payload
        input_references = payload["input_references"]
        retrieved_sources = payload["retrieved_sources"]
        request_count = payload["retrieval_request_count"]
        hit_count = payload["retrieval_hit_count"]
        if (
            not isinstance(input_references, list)
            or not isinstance(retrieved_sources, list)
            or not isinstance(request_count, int)
            or isinstance(request_count, bool)
            or not isinstance(hit_count, int)
            or isinstance(hit_count, bool)
        ):
            raise TerminalIntegrationPayloadError("terminal integration payload is invalid")
        try:
            parsed_sources = []
            for source in retrieved_sources:
                if not isinstance(source, dict) or set(source) != {
                    "source_id",
                    "label",
                    "relevance_score",
                }:
                    raise TerminalIntegrationPayloadError("terminal integration payload is invalid")
                score = source["relevance_score"]
                if not isinstance(score, (int, float)) or isinstance(score, bool):
                    raise TerminalIntegrationPayloadError("terminal integration payload is invalid")
                parsed_sources.append(
                    RetrievedSourceIntent(
                        source_id=self._text(source["source_id"]),
                        label=self._text(source["label"]),
                        relevance_score=float(score),
                    )
                )
            simulation = payload["simulation_reference"]
            intent = ResearchIntegrationIntent(
                correlation_id=claim.correlation_id,
                pseudonymous_user_id=self._text(payload["pseudonymous_user_id"]),
                pseudonymous_submission_reference=self._text(
                    payload["pseudonymous_submission_reference"]
                ),
                task_type=self._text(payload["task_type"]),
                fallback_provider=self._text(payload["fallback_provider"]),
                fallback_model=self._text(payload["fallback_model"]),
                input_references=tuple(self._text(reference) for reference in input_references),
                retrieved_sources=tuple(parsed_sources),
                retrieval_request_count=request_count,
                retrieval_hit_count=hit_count,
                simulation_reference=(self._text(simulation) if simulation is not None else None),
                simulation_status=self._text(payload["simulation_status"]),
            )
        except (KeyError, TypeError, ValueError):
            raise TerminalIntegrationPayloadError(
                "terminal integration payload is invalid"
            ) from None
        if not valid_intent(claim.workflow_run_id, intent):
            raise TerminalIntegrationPayloadError("terminal integration payload is invalid")
        return intent

    def _terminal_workflow(self, workflow_run_id: str) -> WorkflowRun:
        try:
            workflow = self._session.scalar(
                select(WorkflowRun)
                .where(WorkflowRun.id == workflow_run_id)
                .options(
                    selectinload(WorkflowRun.feedback_records).selectinload(
                        FeedbackRecord.judge_evaluation
                    )
                )
            )
        except SQLAlchemyError:
            self._session.rollback()
            raise
        if (
            workflow is None
            or workflow.current_stage is not WorkflowStage.COMPLETED
            or workflow.completed_at is None
        ):
            raise TerminalIntegrationPayloadError("terminal workflow is invalid")
        return workflow

    @staticmethod
    def _judge_measurement(
        evaluation: JudgeEvaluation | None,
    ) -> JudgeMeasurement | None:
        if evaluation is None:
            return None
        result = (
            {
                "reported_decision": (
                    evaluation.reported_decision.value
                    if evaluation.reported_decision is not None
                    else None
                ),
                "effective_decision": (
                    evaluation.decision.value if evaluation.decision is not None else None
                ),
                "correctness_score": evaluation.correctness_score,
                "relevance_score": evaluation.relevance_score,
                "grounding_score": evaluation.grounding_score,
                "actionability_score": evaluation.actionability_score,
                "safety_score": evaluation.safety_score,
                "reason": evaluation.reason,
                "unsupported_claims": list(evaluation.unsupported_claims),
                "regeneration_instructions": list(evaluation.regeneration_instructions),
                "quality_policy_version": evaluation.quality_policy_version,
            }
            if evaluation.decision is not None
            else None
        )
        return JudgeMeasurement(
            evaluation_status=evaluation.evaluation_status.value,
            reported_decision=(
                evaluation.reported_decision.value
                if evaluation.reported_decision is not None
                else None
            ),
            effective_decision=(
                evaluation.decision.value if evaluation.decision is not None else None
            ),
            correctness_score=evaluation.correctness_score,
            relevance_score=evaluation.relevance_score,
            grounding_score=evaluation.grounding_score,
            actionability_score=evaluation.actionability_score,
            safety_score=evaluation.safety_score,
            unsupported_claim_count=(
                len(evaluation.unsupported_claims) if evaluation.decision is not None else None
            ),
            quality_policy_version=evaluation.quality_policy_version,
            result=result,
        )

    def _failure(
        self,
        claim: TerminalIntegrationClaim,
        category: TerminalIntegrationFailureCategory,
        *,
        retryable: bool,
    ) -> TerminalIntegrationWorkerOutcome:
        failed_at = self._now()
        next_retry_at = (
            failed_at + timedelta(seconds=min(30, 2**claim.processing_attempts))
            if retryable
            else None
        )
        try:
            updated = self._repository.fail(
                claim,
                category,
                failed_at=failed_at,
                retryable=retryable,
                next_retry_at=next_retry_at,
            )
        except Exception:
            updated = False
        return TerminalIntegrationWorkerOutcome(
            processed=True,
            workflow_run_id=claim.workflow_run_id,
            integration_type=claim.integration_type,
            retryable=retryable,
            stale_claim=not updated,
            failure_category=category,
        )

    @staticmethod
    def _require_keys(payload: dict[str, object], expected: set[str]) -> None:
        if set(payload) != expected:
            raise TerminalIntegrationPayloadError("terminal integration payload is invalid")

    @staticmethod
    def _require_schema(payload: dict[str, object]) -> None:
        if payload.get("schema_version") != _SCHEMA_VERSION:
            raise TerminalIntegrationPayloadError("terminal integration payload is invalid")

    @staticmethod
    def _required(value: str | None) -> str:
        if value is None or not value:
            raise TerminalIntegrationPayloadError("terminal workflow is invalid")
        return value

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str) or not value:
            raise TerminalIntegrationPayloadError("terminal integration payload is invalid")
        return value
