from __future__ import annotations

from app.schemas.feedback import FeedbackContext, FeedbackPipelineResult
from app.services.feedback.contracts import FeedbackAttemptPersistence
from app.services.research.cases import ResearchCaseSeed, seed_from_terminal_feedback
from app.services.research.contracts import (
    ResearchCaseRepository,
    ResearchEligibilityPolicy,
    ResearchJobDispatcher,
    ResearchPseudonymizer,
)


class ResearchCaseFactory:
    """Creates the paired case only after the student-facing result is durable."""

    def __init__(
        self,
        eligibility_policy: ResearchEligibilityPolicy,
        repository: ResearchCaseRepository,
        dispatcher: ResearchJobDispatcher,
        pseudonymizer: ResearchPseudonymizer,
        *,
        fallback_provider: str,
        fallback_model: str,
    ) -> None:
        self._eligibility_policy = eligibility_policy
        self._repository = repository
        self._dispatcher = dispatcher
        self._pseudonymizer = pseudonymizer
        self._fallback_provider = fallback_provider
        self._fallback_model = fallback_model

    async def create_after_feedback(
        self,
        context: FeedbackContext,
        result: FeedbackPipelineResult,
        attempts: tuple[FeedbackAttemptPersistence, ...],
    ) -> ResearchCaseSeed | None:
        if not await self._eligibility_policy.is_eligible(context):
            return None
        seed = seed_from_terminal_feedback(
            context=context,
            result=result,
            attempts=attempts,
            pseudonymous_user_id=self._pseudonymizer.pseudonymize(
                "research-actor",
                context.submission.student_id,
            ),
            pseudonymous_submission_reference=self._pseudonymizer.pseudonymize(
                "research-submission",
                context.submission.submission_id,
            ),
            fallback_provider=self._fallback_provider,
            fallback_model=self._fallback_model,
        )
        self._repository.create_pair(seed)
        self._dispatcher.schedule_baseline(seed.case_id)
        return seed

    async def after_terminal_feedback(
        self,
        context: FeedbackContext,
        result: FeedbackPipelineResult,
        attempts: tuple[FeedbackAttemptPersistence, ...],
    ) -> None:
        await self.create_after_feedback(context, result, attempts)
