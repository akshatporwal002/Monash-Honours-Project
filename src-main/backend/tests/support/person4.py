"""Stable deterministic support for the browser E2E server."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from alembic.config import Config
from sqlalchemy.orm import Session, sessionmaker

from app.models import JudgeDecision, JudgeEvaluationStatus
from app.schemas.feedback import (
    FeedbackContext,
    FeedbackResponseClassification,
    FeedbackSourceAttribution,
    GeneratedFeedback,
    JudgeEvaluationOutcome,
    JudgeResult,
    TokenUsage,
)
from app.services.continuation import (
    ContinuationClaim,
    ContinuationFailureCategory,
    ContinuationRecord,
    ContinuationState,
    TerminalContinuationService,
    TerminalFeedbackNotice,
)
from app.services.feedback.contracts import FeedbackAttemptPersistence
from app.services.learning_events import HmacSha256Pseudonymizer
from app.services.research import (
    BASELINE_PROMPT_VERSION,
    DatabaseResearchJobDispatcher,
    ResearchCaseFactory,
    SqlAlchemyResearchJobRepository,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 7, 26, 10, 0, tzinfo=UTC)
PSEUDONYM_SECRET = "e2e-pseudonym-secret-material-32-bytes-minimum"
SUBMISSION_ID = "submission-e2e"
COURSE_ID = "course-e2e"
TASK_ID = "task-e2e"
STUDENT_ACTOR = "opaque-student-subject"


class EligibleResearch:
    async def is_eligible(self, context: FeedbackContext) -> bool:
        return context.task.course_id == COURSE_ID


class MemoryContinuationRepository:
    def __init__(self) -> None:
        self.records: dict[str, ContinuationRecord] = {}
        self.tokens: dict[str, str] = {}
        self.leases: dict[str, datetime] = {}

    def ensure_pending(self, notice: TerminalFeedbackNotice) -> ContinuationRecord:
        existing = self.records.get(notice.workflow_run_id)
        if existing is not None:
            replay = (
                notice.pseudonymous_actor_reference,
                notice.course_reference,
                notice.completed_task_reference,
                notice.correlation_id,
            )
            stored = (
                existing.pseudonymous_actor_reference,
                existing.course_reference,
                existing.completed_task_reference,
                existing.correlation_id,
            )
            if replay != stored:
                raise RuntimeError("continuation notice conflict")
            return existing
        record = ContinuationRecord(
            workflow_run_id=notice.workflow_run_id,
            pseudonymous_actor_reference=notice.pseudonymous_actor_reference,
            course_reference=notice.course_reference,
            completed_task_reference=notice.completed_task_reference,
            correlation_id=notice.correlation_id,
            state=ContinuationState.PENDING,
        )
        self.records[notice.workflow_run_id] = record
        return record

    def claim_next(
        self,
        *,
        now: datetime,
        lease_expires_at: datetime,
        execution_token: str,
        maximum_attempts: int,
    ) -> ContinuationClaim | None:
        for workflow_id, record in self.records.items():
            lease = self.leases.get(workflow_id)
            expired = (
                record.state is ContinuationState.RUNNING and lease is not None and lease <= now
            )
            retry_due = record.state is ContinuationState.RETRY_SCHEDULED and (
                record.next_retry_at is None or record.next_retry_at <= now
            )
            if not (record.state is ContinuationState.PENDING or retry_due or expired):
                continue
            if record.processing_attempts >= maximum_attempts:
                continue
            running = replace(
                record,
                state=ContinuationState.RUNNING,
                processing_attempts=record.processing_attempts + 1,
                next_retry_at=None,
                retryable=False,
                failure_category=None,
            )
            self.records[workflow_id] = running
            self.tokens[workflow_id] = execution_token
            self.leases[workflow_id] = lease_expires_at
            return ContinuationClaim(
                workflow_run_id=workflow_id,
                execution_token=execution_token,
                pseudonymous_actor_reference=running.pseudonymous_actor_reference,
                course_reference=running.course_reference,
                completed_task_reference=running.completed_task_reference,
                correlation_id=running.correlation_id,
                progress_recorded=running.progress_recorded,
                processing_attempts=running.processing_attempts,
                lease_expires_at=lease_expires_at,
            )
        return None

    def finalize_next_exhausted(
        self,
        *,
        observed_at: datetime,
        maximum_attempts: int,
    ) -> str | None:
        for workflow_id, record in self.records.items():
            lease = self.leases.get(workflow_id)
            if (
                record.state is ContinuationState.RUNNING
                and record.processing_attempts >= maximum_attempts
                and lease is not None
                and lease <= observed_at
            ):
                self.records[workflow_id] = replace(
                    record,
                    state=ContinuationState.FAILED,
                    retryable=False,
                    next_retry_at=None,
                    failure_category=ContinuationFailureCategory.PERSISTENCE_UNAVAILABLE,
                )
                self.tokens.pop(workflow_id, None)
                self.leases.pop(workflow_id, None)
                return workflow_id
        return None

    def mark_progress_recorded(self, claim: ContinuationClaim) -> bool:
        if self.tokens.get(claim.workflow_run_id) != claim.execution_token:
            return False
        self.records[claim.workflow_run_id] = replace(
            self.records[claim.workflow_run_id],
            progress_recorded=True,
        )
        return True

    def complete(
        self,
        claim: ContinuationClaim,
        next_task_reference: str,
        *,
        completed_at: datetime,
    ) -> bool:
        del completed_at
        if self.tokens.get(claim.workflow_run_id) != claim.execution_token:
            return False
        self.records[claim.workflow_run_id] = replace(
            self.records[claim.workflow_run_id],
            state=ContinuationState.COMPLETED,
            next_task_reference=next_task_reference,
        )
        return True

    def fail(
        self,
        claim: ContinuationClaim,
        category: ContinuationFailureCategory,
        *,
        failed_at: datetime,
        retryable: bool,
        next_retry_at: datetime | None,
    ) -> bool:
        del failed_at
        if self.tokens.get(claim.workflow_run_id) != claim.execution_token:
            return False
        self.records[claim.workflow_run_id] = replace(
            self.records[claim.workflow_run_id],
            state=(ContinuationState.RETRY_SCHEDULED if retryable else ContinuationState.FAILED),
            failure_category=category,
            retryable=retryable,
            next_retry_at=next_retry_at,
        )
        return True

    def get(self, workflow_run_id: str) -> ContinuationRecord | None:
        return self.records.get(workflow_run_id)


class ResearchObserver:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        pseudonymizer: HmacSha256Pseudonymizer,
        dispatcher: DatabaseResearchJobDispatcher,
        continuation: TerminalContinuationService,
        *,
        fast_path: bool = True,
    ) -> None:
        self._session_factory = session_factory
        self._pseudonymizer = pseudonymizer
        self._dispatcher = dispatcher
        self._continuation = continuation
        self._fast_path = fast_path
        self.contexts: dict[str, FeedbackContext] = {}
        self.notices: dict[str, TerminalFeedbackNotice] = {}

    async def after_terminal_feedback(
        self,
        context: FeedbackContext,
        result: object,
        attempts: object,
    ) -> None:
        from app.schemas.feedback import FeedbackPipelineResult

        pipeline_result = FeedbackPipelineResult.model_validate(result)
        typed_attempts = tuple(
            FeedbackAttemptPersistence(
                feedback_id=item.feedback_id,
                generation_attempt=item.generation_attempt,
                generated_feedback=item.generated_feedback,
                judge_evaluation=item.judge_evaluation,
            )
            for item in attempts
        )
        if self._fast_path:
            with self._session_factory() as session:
                factory = ResearchCaseFactory(
                    EligibleResearch(),
                    SqlAlchemyResearchJobRepository(session),
                    self._dispatcher,
                    self._pseudonymizer,
                    fallback_provider="deterministic-provider",
                    fallback_model="deterministic-model",
                )
                await factory.create_after_feedback(
                    context,
                    pipeline_result,
                    typed_attempts,
                )
        self.contexts[pipeline_result.workflow_run_id] = context
        notice = TerminalFeedbackNotice(
            workflow_run_id=pipeline_result.workflow_run_id,
            pseudonymous_actor_reference=self._pseudonymizer.pseudonymize(
                "continuation-actor",
                context.submission.student_id,
            ),
            course_reference=context.task.course_id,
            completed_task_reference=context.task.task_id,
            correlation_id=context.correlation_id,
        )
        self.notices[pipeline_result.workflow_run_id] = notice
        if self._fast_path:
            self._continuation.after_terminal_feedback(notice)


class BaselineContextProvider:
    def __init__(self, contexts: dict[str, FeedbackContext]) -> None:
        self._contexts = contexts

    async def get_context(self, workflow_run_id: str) -> FeedbackContext | None:
        return self._contexts.get(workflow_run_id)


class DeterministicBaselineGenerator:
    def __init__(self) -> None:
        self.contexts: list[FeedbackContext] = []

    async def generate(
        self,
        context: FeedbackContext,
        *,
        expected_provider: str,
        expected_model: str,
    ) -> GeneratedFeedback:
        self.contexts.append(context)
        assert context.retrieval_context == []
        assert context.simulation_context is None
        return GeneratedFeedback(
            feedback_content={
                "response_classification": (FeedbackResponseClassification.PARTIALLY_CORRECT.value),
                "summary": "The baseline identifies the main idea.",
                "identified_error": None,
                "explanation": "The measurement step needs more detail.",
                "improvement_actions": ["Describe the measurement outcome."],
                "recommended_next_step": "Review measurement.",
                "source_references": [],
                "simulation_references": [],
            },
            provider=expected_provider,
            model=expected_model,
            prompt_version=BASELINE_PROMPT_VERSION,
            source_references=[],
            simulation_references=[],
            token_usage=TokenUsage(input_tokens=12, output_tokens=8, total_tokens=20),
            estimated_cost=Decimal("0.002000"),
        )


class DeterministicBaselineJudge:
    def __init__(self) -> None:
        self.calls = 0

    async def evaluate(
        self,
        context: FeedbackContext,
        feedback: GeneratedFeedback,
    ) -> JudgeEvaluationOutcome:
        del context, feedback
        self.calls += 1
        return judge_outcome("pass")


def migration_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def generated_feedback(summary: str) -> GeneratedFeedback:
    return GeneratedFeedback(
        feedback_content={
            "response_classification": FeedbackResponseClassification.PARTIALLY_CORRECT.value,
            "summary": summary,
            "identified_error": "The measurement step is incomplete.",
            "explanation": "Connect superposition to the measurement probabilities.",
            "improvement_actions": ["Explain both possible measurement outcomes."],
            "recommended_next_step": "Review the measurement postulate.",
            "source_references": ["source-safe-1"],
            "simulation_references": ["simulation-safe-1"],
        },
        provider="deterministic-provider",
        model="deterministic-model",
        prompt_version="feedback-v2",
        source_references=["source-safe-1"],
        source_attributions=[
            FeedbackSourceAttribution(
                source_id="source-safe-1",
                label="Week 2 course notes",
            )
        ],
        simulation_references=["simulation-safe-1"],
        token_usage=TokenUsage(input_tokens=20, output_tokens=10, total_tokens=30),
        estimated_cost=Decimal("0.003000"),
    )


def judge_outcome(decision: str) -> JudgeEvaluationOutcome:
    typed_decision = JudgeDecision(decision)
    result = JudgeResult(
        decision=typed_decision,
        correctness_score=90,
        relevance_score=91,
        grounding_score=92,
        actionability_score=93,
        safety_score=100,
        reason="The output is grounded and actionable.",
        unsupported_claims=[],
        regeneration_instructions=([] if decision == "pass" else ["Clarify the measurement step."]),
    )
    return JudgeEvaluationOutcome(
        evaluation_status=JudgeEvaluationStatus.VALID,
        reported_decision=typed_decision,
        judge_result=result,
        reason=result.reason,
        provider="deterministic-provider",
        model="deterministic-judge",
        prompt_version="quality-judge-v1",
        quality_policy_version="quality-policy-v1",
        token_usage=TokenUsage(input_tokens=6, output_tokens=4, total_tokens=10),
        estimated_cost=Decimal("0.001000"),
    )
