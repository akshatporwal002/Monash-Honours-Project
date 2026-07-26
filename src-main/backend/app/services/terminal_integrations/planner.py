from __future__ import annotations

import asyncio

from app.schemas.feedback import FeedbackContext, FeedbackPipelineResult
from app.services.feedback.contracts import FeedbackAttemptPersistence
from app.services.research.cases import RETRIEVAL_RELEVANCE_THRESHOLD
from app.services.research.contracts import (
    ResearchEligibilityPolicy,
    ResearchPseudonymizer,
)
from app.services.terminal_integrations.contracts import (
    ContinuationIntegrationIntent,
    ResearchIntegrationIntent,
    RetrievedSourceIntent,
    TerminalIntegrationIntent,
)
from app.services.terminal_integrations.repository import valid_intent


class DurableTerminalIntegrationPlanner:
    """Prepare bounded metadata-only handoffs before the terminal commit.

    This phase never dispatches baseline work. The outbox worker creates the
    paired research rows after feedback is durable; the later serial baseline
    pass then claims the pending baseline row.
    """

    def __init__(
        self,
        pseudonymizer: ResearchPseudonymizer | None,
        *,
        research_eligibility: ResearchEligibilityPolicy | None = None,
        fallback_provider: str = "unavailable",
        fallback_model: str = "unavailable",
        enable_continuation: bool = True,
        eligibility_timeout_seconds: float = 5,
    ) -> None:
        if not 0 < eligibility_timeout_seconds <= 60:
            raise ValueError("eligibility_timeout_seconds must be between 0 and 60")
        self._pseudonymizer = pseudonymizer
        self._research_eligibility = research_eligibility
        self._fallback_provider = fallback_provider
        self._fallback_model = fallback_model
        self._enable_continuation = enable_continuation
        self._eligibility_timeout_seconds = eligibility_timeout_seconds

    async def plan(
        self,
        context: FeedbackContext,
        result: FeedbackPipelineResult,
        attempts: tuple[FeedbackAttemptPersistence, ...],
    ) -> tuple[TerminalIntegrationIntent, ...]:
        del attempts
        if self._pseudonymizer is None or result.submission_id != context.submission.submission_id:
            return ()

        intents: list[TerminalIntegrationIntent] = []
        if self._enable_continuation:
            continuation = self._continuation_intent(context)
            if continuation is not None and valid_intent(
                result.workflow_run_id,
                continuation,
            ):
                intents.append(continuation)

        if await self._eligible(context):
            research = self._research_intent(context)
            if research is not None and valid_intent(
                result.workflow_run_id,
                research,
            ):
                intents.append(research)
        return tuple(intents)

    def _continuation_intent(
        self,
        context: FeedbackContext,
    ) -> ContinuationIntegrationIntent | None:
        try:
            actor = self._pseudonymizer.pseudonymize(
                "continuation-actor",
                context.submission.student_id,
            )
        except Exception:
            return None
        return ContinuationIntegrationIntent(
            correlation_id=context.correlation_id,
            pseudonymous_actor_reference=actor,
            course_reference=context.task.course_id,
            completed_task_reference=context.task.task_id,
        )

    async def _eligible(self, context: FeedbackContext) -> bool:
        if self._research_eligibility is None:
            return False
        try:
            return await asyncio.wait_for(
                self._research_eligibility.is_eligible(context),
                timeout=self._eligibility_timeout_seconds,
            )
        except Exception:
            return False

    def _research_intent(
        self,
        context: FeedbackContext,
    ) -> ResearchIntegrationIntent | None:
        try:
            actor = self._pseudonymizer.pseudonymize(
                "research-actor",
                context.submission.student_id,
            )
            submission = self._pseudonymizer.pseudonymize(
                "research-submission",
                context.submission.submission_id,
            )
        except Exception:
            return None
        return ResearchIntegrationIntent(
            correlation_id=context.correlation_id,
            pseudonymous_user_id=actor,
            pseudonymous_submission_reference=submission,
            task_type=context.task.task_type,
            fallback_provider=self._fallback_provider,
            fallback_model=self._fallback_model,
            input_references=tuple(context.task.source_references),
            retrieved_sources=tuple(
                RetrievedSourceIntent(
                    source_id=item.source_id,
                    # Labels are measurement metadata, not source content.
                    # Normalize to the durable research schema's bounded width.
                    label=item.source_label[:255],
                    relevance_score=item.relevance_score,
                )
                for item in context.retrieval_context
            ),
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
        )
