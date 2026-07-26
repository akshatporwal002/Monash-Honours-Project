from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from uuid import UUID, uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.enums import (
    ExperimentalCondition,
    ResearchStatus,
)
from app.models.persistence import ResearchEvaluation
from app.services.research.baseline import BASELINE_PROMPT_VERSION
from app.services.research.cases import JudgeMeasurement, ResearchCaseSeed
from app.services.research.worker import (
    BaselineCompletion,
    ResearchBaselineJobRepository,
    ResearchJobClaim,
)


class ResearchPersistenceError(Exception):
    """A sanitized research persistence failure."""


class ResearchCaseConflictError(ResearchPersistenceError):
    """A case ID was reused for different immutable input."""


_STORED_COST_QUANTUM = Decimal("0.000001")
_STORED_COST_LIMIT = Decimal("1000000")


def _stored_cost(value: Decimal) -> Decimal:
    try:
        normalized = value.quantize(
            _STORED_COST_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )
    except (InvalidOperation, ValueError):
        raise ResearchPersistenceError("research cost is invalid") from None
    if normalized < 0 or normalized >= _STORED_COST_LIMIT:
        raise ResearchPersistenceError("research cost exceeds the storage contract")
    return normalized


def _uuid() -> str:
    return str(uuid4())


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _judge_fields(
    measurement: JudgeMeasurement | None,
    *,
    prefix: str,
) -> dict[str, object]:
    if measurement is None:
        return {
            f"{prefix}_judge_status": None,
            f"{prefix}_judge_decision": None,
        }
    return {
        f"{prefix}_judge_status": measurement.evaluation_status,
        f"{prefix}_judge_decision": measurement.effective_decision,
    }


class SqlAlchemyResearchJobRepository(ResearchBaselineJobRepository):
    def __init__(
        self,
        session: Session,
        *,
        lease_duration: timedelta = timedelta(minutes=5),
        uuid_factory: Callable[[], str] = _uuid,
    ) -> None:
        self._session = session
        self._lease_duration = lease_duration
        self._uuid_factory = uuid_factory

    def create_pair(self, seed: ResearchCaseSeed) -> None:
        self._validate_seed(seed)
        existing = self._case_rows(seed.case_id)
        if existing:
            self._validate_exact_replay(existing, seed)
            return

        final_judge = seed.final_judge
        final_scores = {
            "correctness_score": (
                final_judge.correctness_score if final_judge is not None else None
            ),
            "relevance_score": (final_judge.relevance_score if final_judge is not None else None),
            "grounding_score": (final_judge.grounding_score if final_judge is not None else None),
            "actionability_score": (
                final_judge.actionability_score if final_judge is not None else None
            ),
            "safety_score": final_judge.safety_score if final_judge is not None else None,
            "unsupported_claim_count": (
                final_judge.unsupported_claim_count if final_judge is not None else None
            ),
            "quality_policy_version": (
                final_judge.quality_policy_version if final_judge is not None else None
            ),
        }
        completed_at = datetime.now(UTC)
        shared = {
            "case_id": seed.case_id,
            "workflow_run_id": seed.workflow_run_id,
            "correlation_id": seed.correlation_id,
            "pseudonymous_user_id": seed.pseudonymous_user_id,
            "course_id": seed.course_id,
            "task_id": seed.task_id,
            "task_type": seed.task_type,
            "submission_reference": seed.pseudonymous_submission_reference,
            "provider": seed.provider,
            "model": seed.model,
            "measurement_schema_version": seed.measurement_schema_version,
        }
        agentic = ResearchEvaluation(
            id=self._uuid_factory(),
            **shared,
            experimental_condition=ExperimentalCondition.AGENTIC_RAG,
            prompt_version=seed.prompt_version,
            input_references=list(seed.input_references),
            retrieved_sources=[
                {
                    "source_id": source.source_id,
                    "label": source.label,
                    "relevance_score": source.relevance_score,
                }
                for source in seed.retrieved_sources
            ],
            simulation_reference=seed.simulation_reference,
            simulation_status=seed.simulation_status,
            generated_output=seed.generated_output,
            judge_result=final_judge.result if final_judge is not None else None,
            latency_ms=seed.primary_latency_ms,
            input_tokens=seed.input_tokens,
            output_tokens=seed.output_tokens,
            total_tokens=seed.total_tokens,
            estimated_cost=_stored_cost(seed.estimated_cost),
            regeneration_count=seed.regeneration_count,
            fallback_used=seed.fallback_used,
            comparable=seed.comparable,
            usage_complete=seed.usage_complete,
            retrieval_request_count=seed.retrieval_request_count,
            retrieval_hit_count=seed.retrieval_hit_count,
            **_judge_fields(seed.first_judge, prefix="first"),
            **_judge_fields(seed.final_judge, prefix="final"),
            **final_scores,
            status=ResearchStatus.COMPLETED,
            completed_at=completed_at,
        )
        baseline = ResearchEvaluation(
            id=self._uuid_factory(),
            **shared,
            experimental_condition=ExperimentalCondition.SINGLE_STEP_BASELINE,
            prompt_version=BASELINE_PROMPT_VERSION,
            input_references=[],
            retrieved_sources=[],
            simulation_reference=None,
            simulation_status="not_requested",
            generated_output={},
            judge_result=None,
            latency_ms=None,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            regeneration_count=0,
            fallback_used=False,
            comparable=seed.comparable,
            usage_complete=False,
            retrieval_request_count=0,
            retrieval_hit_count=0,
            status=ResearchStatus.PENDING,
        )
        self._session.add_all([agentic, baseline])
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            winner = self._case_rows(seed.case_id)
            if not winner:
                raise ResearchPersistenceError("research case could not be stored") from None
            self._validate_exact_replay(winner, seed)
        except SQLAlchemyError:
            self._session.rollback()
            raise ResearchPersistenceError("research case could not be stored") from None

    def claim_next(
        self,
        *,
        now: datetime,
        maximum_attempts: int = 3,
    ) -> ResearchJobClaim | None:
        observed_at = _utc(now)
        if not 1 <= maximum_attempts <= 3:
            raise ResearchPersistenceError("research claim request is invalid")
        try:
            candidate = self._session.scalar(
                select(ResearchEvaluation)
                .where(
                    ResearchEvaluation.experimental_condition
                    == ExperimentalCondition.SINGLE_STEP_BASELINE,
                    ResearchEvaluation.processing_attempts < maximum_attempts,
                    or_(
                        ResearchEvaluation.status == ResearchStatus.PENDING,
                        (
                            (ResearchEvaluation.status == ResearchStatus.RUNNING)
                            & (ResearchEvaluation.lease_expires_at <= observed_at)
                        ),
                    ),
                )
                .order_by(ResearchEvaluation.created_at, ResearchEvaluation.id)
                .limit(1)
            )
        except SQLAlchemyError:
            self._session.rollback()
            raise ResearchPersistenceError("research job could not be claimed") from None
        if candidate is None or candidate.workflow_run_id is None:
            return None

        previous_status = candidate.status
        previous_token = candidate.execution_token
        previous_lease = candidate.lease_expires_at
        next_attempt = candidate.processing_attempts + 1
        token = self._uuid_factory()
        lease_expires_at = observed_at + self._lease_duration
        statement = update(ResearchEvaluation).where(
            ResearchEvaluation.id == candidate.id,
            ResearchEvaluation.status == previous_status,
        )
        if previous_token is None:
            statement = statement.where(ResearchEvaluation.execution_token.is_(None))
        else:
            statement = statement.where(ResearchEvaluation.execution_token == previous_token)
        if previous_lease is None:
            statement = statement.where(ResearchEvaluation.lease_expires_at.is_(None))
        else:
            statement = statement.where(ResearchEvaluation.lease_expires_at == previous_lease)
        try:
            result = self._session.execute(
                statement.values(
                    status=ResearchStatus.RUNNING,
                    execution_token=token,
                    lease_expires_at=lease_expires_at,
                    processing_attempts=next_attempt,
                    failure_category=None,
                )
            )
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise ResearchPersistenceError("research job could not be claimed") from None
        if result.rowcount != 1:
            return None
        return ResearchJobClaim(
            research_evaluation_id=candidate.id,
            case_id=candidate.case_id,
            workflow_run_id=candidate.workflow_run_id,
            correlation_id=candidate.correlation_id or candidate.case_id,
            execution_token=token,
            provider=candidate.provider,
            model=candidate.model,
            lease_expires_at=lease_expires_at,
            processing_attempts=next_attempt,
        )

    def finalize_next_exhausted(
        self,
        *,
        now: datetime,
        maximum_attempts: int = 3,
    ) -> str | None:
        observed_at = _utc(now)
        if not 1 <= maximum_attempts <= 3:
            raise ResearchPersistenceError("research claim request is invalid")
        try:
            candidate = self._session.scalar(
                select(ResearchEvaluation)
                .where(
                    ResearchEvaluation.experimental_condition
                    == ExperimentalCondition.SINGLE_STEP_BASELINE,
                    ResearchEvaluation.status == ResearchStatus.RUNNING,
                    ResearchEvaluation.lease_expires_at <= observed_at,
                    ResearchEvaluation.processing_attempts >= maximum_attempts,
                )
                .order_by(ResearchEvaluation.created_at, ResearchEvaluation.id)
                .limit(1)
            )
            if candidate is None:
                return None
            result = self._session.execute(
                update(ResearchEvaluation)
                .where(
                    ResearchEvaluation.id == candidate.id,
                    ResearchEvaluation.status == ResearchStatus.RUNNING,
                    ResearchEvaluation.execution_token == candidate.execution_token,
                    ResearchEvaluation.lease_expires_at == candidate.lease_expires_at,
                    ResearchEvaluation.processing_attempts == candidate.processing_attempts,
                )
                .values(
                    status=ResearchStatus.FAILED,
                    execution_token=None,
                    lease_expires_at=None,
                    failure_category="baseline_worker_lease_expired",
                    usage_complete=False,
                    comparable=False,
                    completed_at=observed_at,
                )
            )
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise ResearchPersistenceError(
                "research exhausted job could not be finalized"
            ) from None
        return candidate.id if result.rowcount == 1 else None

    def complete(
        self,
        claim: ResearchJobClaim,
        completion: BaselineCompletion,
        *,
        completed_at: datetime,
    ) -> bool:
        generated = completion.generated_feedback
        if (
            generated.provider != claim.provider
            or generated.model != claim.model
            or generated.prompt_version != BASELINE_PROMPT_VERSION
            or generated.source_references
            or generated.simulation_references
        ):
            raise ResearchPersistenceError("baseline isolation validation failed")
        evaluation = completion.judge_evaluation
        result = evaluation.judge_result
        values: dict[str, object] = {
            "prompt_version": completion.generated_feedback.prompt_version,
            "generated_output": completion.generated_feedback.feedback_content,
            "judge_result": (
                {
                    "reported_decision": evaluation.reported_decision.value,
                    "effective_decision": result.decision.value,
                    "correctness_score": result.correctness_score,
                    "relevance_score": result.relevance_score,
                    "grounding_score": result.grounding_score,
                    "actionability_score": result.actionability_score,
                    "safety_score": result.safety_score,
                    "reason": result.reason,
                    "unsupported_claims": list(result.unsupported_claims),
                    "regeneration_instructions": list(result.regeneration_instructions),
                    "quality_policy_version": evaluation.quality_policy_version,
                }
                if result is not None
                else None
            ),
            "latency_ms": completion.generation_latency_ms,
            "input_tokens": completion.generation_token_usage.input_tokens,
            "output_tokens": completion.generation_token_usage.output_tokens,
            "total_tokens": completion.generation_token_usage.total_tokens,
            "estimated_cost": completion.generation_cost,
            "usage_complete": completion.usage_complete,
            "comparable": (ResearchEvaluation.comparable if completion.comparable else False),
            "first_judge_status": evaluation.evaluation_status,
            "first_judge_decision": (result.decision if result is not None else None),
            "final_judge_status": evaluation.evaluation_status,
            "final_judge_decision": (result.decision if result is not None else None),
            "correctness_score": (result.correctness_score if result is not None else None),
            "relevance_score": result.relevance_score if result is not None else None,
            "grounding_score": result.grounding_score if result is not None else None,
            "actionability_score": (result.actionability_score if result is not None else None),
            "safety_score": result.safety_score if result is not None else None,
            "unsupported_claim_count": (
                len(result.unsupported_claims) if result is not None else None
            ),
            "quality_policy_version": evaluation.quality_policy_version,
            "evaluation_latency_ms": completion.evaluation_latency_ms,
            "evaluation_input_tokens": completion.evaluation_token_usage.input_tokens,
            "evaluation_output_tokens": completion.evaluation_token_usage.output_tokens,
            "evaluation_total_tokens": completion.evaluation_token_usage.total_tokens,
            "evaluation_estimated_cost": completion.evaluation_cost,
            "evaluation_usage_complete": evaluation.usage_complete,
            "status": ResearchStatus.COMPLETED,
            "execution_token": None,
            "lease_expires_at": None,
            "failure_category": None,
            "completed_at": _utc(completed_at),
        }
        return self._terminal_update(claim, values)

    def fail(
        self,
        claim: ResearchJobClaim,
        failure_category: str,
        *,
        completed_at: datetime,
    ) -> bool:
        return self._terminal_update(
            claim,
            {
                "status": ResearchStatus.FAILED,
                "execution_token": None,
                "lease_expires_at": None,
                "failure_category": failure_category,
                "completed_at": _utc(completed_at),
                "usage_complete": False,
                "comparable": False,
            },
        )

    def _terminal_update(
        self,
        claim: ResearchJobClaim,
        values: dict[str, object],
    ) -> bool:
        try:
            result = self._session.execute(
                update(ResearchEvaluation)
                .where(
                    ResearchEvaluation.id == claim.research_evaluation_id,
                    ResearchEvaluation.status == ResearchStatus.RUNNING,
                    ResearchEvaluation.execution_token == claim.execution_token,
                )
                .values(**values)
            )
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise ResearchPersistenceError("research job could not be updated") from None
        return result.rowcount == 1

    def _case_rows(self, case_id: str) -> list[ResearchEvaluation]:
        try:
            return list(
                self._session.scalars(
                    select(ResearchEvaluation).where(ResearchEvaluation.case_id == case_id)
                )
            )
        except SQLAlchemyError:
            self._session.rollback()
            raise ResearchPersistenceError("research case could not be read") from None

    @staticmethod
    def _validate_exact_replay(
        rows: list[ResearchEvaluation],
        seed: ResearchCaseSeed,
    ) -> None:
        if len(rows) != 2 or {row.experimental_condition for row in rows} != set(
            ExperimentalCondition
        ):
            raise ResearchPersistenceError("research case is incomplete")
        by_condition = {row.experimental_condition: row for row in rows}
        for row in rows:
            comparable = (
                row.case_id,
                row.workflow_run_id,
                row.correlation_id,
                row.pseudonymous_user_id,
                row.submission_reference,
                row.course_id,
                row.task_id,
                row.task_type,
                row.provider,
                row.model,
                row.measurement_schema_version,
            )
            expected = (
                seed.case_id,
                seed.workflow_run_id,
                seed.correlation_id,
                seed.pseudonymous_user_id,
                seed.pseudonymous_submission_reference,
                seed.course_id,
                seed.task_id,
                seed.task_type,
                seed.provider,
                seed.model,
                seed.measurement_schema_version,
            )
            if comparable != expected:
                raise ResearchCaseConflictError("research case ID was reused")

        agentic = by_condition[ExperimentalCondition.AGENTIC_RAG]
        first_judge = seed.first_judge
        final_judge = seed.final_judge
        expected_agentic = (
            seed.prompt_version,
            list(seed.input_references),
            [
                {
                    "source_id": source.source_id,
                    "label": source.label,
                    "relevance_score": source.relevance_score,
                }
                for source in seed.retrieved_sources
            ],
            seed.simulation_reference,
            seed.simulation_status,
            seed.generated_output,
            final_judge.result if final_judge is not None else None,
            seed.primary_latency_ms,
            seed.input_tokens,
            seed.output_tokens,
            seed.total_tokens,
            _stored_cost(seed.estimated_cost),
            seed.regeneration_count,
            seed.fallback_used,
            seed.comparable,
            seed.usage_complete,
            seed.retrieval_request_count,
            seed.retrieval_hit_count,
            first_judge.evaluation_status if first_judge is not None else None,
            first_judge.effective_decision if first_judge is not None else None,
            final_judge.evaluation_status if final_judge is not None else None,
            final_judge.effective_decision if final_judge is not None else None,
            final_judge.correctness_score if final_judge is not None else None,
            final_judge.relevance_score if final_judge is not None else None,
            final_judge.grounding_score if final_judge is not None else None,
            final_judge.actionability_score if final_judge is not None else None,
            final_judge.safety_score if final_judge is not None else None,
            final_judge.unsupported_claim_count if final_judge is not None else None,
            final_judge.quality_policy_version if final_judge is not None else None,
            ResearchStatus.COMPLETED.value,
        )
        persisted_agentic = (
            agentic.prompt_version,
            agentic.input_references,
            agentic.retrieved_sources,
            agentic.simulation_reference,
            agentic.simulation_status,
            agentic.generated_output,
            agentic.judge_result,
            agentic.latency_ms,
            agentic.input_tokens,
            agentic.output_tokens,
            agentic.total_tokens,
            agentic.estimated_cost,
            agentic.regeneration_count,
            agentic.fallback_used,
            agentic.comparable,
            agentic.usage_complete,
            agentic.retrieval_request_count,
            agentic.retrieval_hit_count,
            (agentic.first_judge_status.value if agentic.first_judge_status is not None else None),
            (
                agentic.first_judge_decision.value
                if agentic.first_judge_decision is not None
                else None
            ),
            (agentic.final_judge_status.value if agentic.final_judge_status is not None else None),
            (
                agentic.final_judge_decision.value
                if agentic.final_judge_decision is not None
                else None
            ),
            agentic.correctness_score,
            agentic.relevance_score,
            agentic.grounding_score,
            agentic.actionability_score,
            agentic.safety_score,
            agentic.unsupported_claim_count,
            agentic.quality_policy_version,
            agentic.status.value,
        )
        if persisted_agentic != expected_agentic:
            raise ResearchCaseConflictError("research case ID was reused")

        baseline = by_condition[ExperimentalCondition.SINGLE_STEP_BASELINE]
        if (
            baseline.prompt_version != BASELINE_PROMPT_VERSION
            or baseline.input_references
            or baseline.retrieved_sources
            or baseline.simulation_reference is not None
            or baseline.simulation_status != "not_requested"
            or baseline.retrieval_request_count != 0
            or baseline.retrieval_hit_count != 0
            or baseline.regeneration_count != 0
            or baseline.fallback_used
        ):
            raise ResearchCaseConflictError("research case ID was reused")

    @staticmethod
    def _validate_seed(seed: ResearchCaseSeed) -> None:
        pseudonym = re.compile(r"^v1_[0-9a-f]{64}$")
        try:
            correlation = UUID(seed.correlation_id)
            case_id = UUID(seed.case_id)
            workflow_id = UUID(seed.workflow_run_id)
        except ValueError:
            raise ResearchPersistenceError("research identifiers are invalid") from None
        if (
            correlation.version != 4
            or str(correlation) != seed.correlation_id.lower()
            or case_id.version != 4
            or str(case_id) != seed.case_id.lower()
            or workflow_id.version != 4
            or str(workflow_id) != seed.workflow_run_id.lower()
            or seed.case_id != seed.workflow_run_id
            or pseudonym.fullmatch(seed.pseudonymous_user_id) is None
            or pseudonym.fullmatch(seed.pseudonymous_submission_reference) is None
        ):
            raise ResearchPersistenceError("research references must be pseudonymous")
        if len(seed.input_references) > 100 or len(seed.retrieved_sources) > 100:
            raise ResearchPersistenceError("research reference limits were exceeded")
        _stored_cost(seed.estimated_cost)
        if (
            len(
                json.dumps(
                    seed.generated_output,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
            > 65_536
        ):
            raise ResearchPersistenceError("research output exceeds the size limit")


class DatabaseResearchJobDispatcher:
    """Wake-up hook for the database-backed single worker."""

    def __init__(self, notify: Callable[[str], None] | None = None) -> None:
        self._notify = notify

    def schedule_baseline(self, case_id: str) -> None:
        if self._notify is not None:
            self._notify(case_id)
