from __future__ import annotations

import logging
from typing import Protocol

from app.schemas.feedback import FeedbackContext, FeedbackPipelineResult
from app.services.continuation.contracts import (
    ContinuationScheduleReceipt,
    TerminalFeedbackNotice,
)
from app.services.feedback.contracts import (
    FeedbackAttemptPersistence,
    TerminalFeedbackObserver,
)
from app.services.feedback.terminal_observers import (
    CompositeTerminalFeedbackObserver,
)


class ContinuationPseudonymizer(Protocol):
    def pseudonymize(self, namespace: str, reference: str) -> str: ...


class ContinuationScheduler(Protocol):
    def after_terminal_feedback(
        self,
        notice: TerminalFeedbackNotice,
    ) -> ContinuationScheduleReceipt: ...


class ContinuationTerminalFeedbackObserver:
    """Adapt a rich terminal callback to a privacy-minimal continuation notice."""

    def __init__(
        self,
        scheduler: ContinuationScheduler,
        pseudonymizer: ContinuationPseudonymizer | None,
    ) -> None:
        self._scheduler = scheduler
        self._pseudonymizer = pseudonymizer

    async def after_terminal_feedback(
        self,
        context: FeedbackContext,
        result: FeedbackPipelineResult,
        attempts: tuple[FeedbackAttemptPersistence, ...],
    ) -> None:
        del attempts
        if self._pseudonymizer is None:
            return
        if result.submission_id != context.submission.submission_id:
            return
        pseudonymous_actor = self._pseudonymizer.pseudonymize(
            "continuation-actor",
            context.submission.student_id,
        )
        self._scheduler.after_terminal_feedback(
            TerminalFeedbackNotice(
                workflow_run_id=result.workflow_run_id,
                pseudonymous_actor_reference=pseudonymous_actor,
                course_reference=context.task.course_id,
                completed_task_reference=context.task.task_id,
                correlation_id=context.correlation_id,
            )
        )


def compose_research_and_continuation(
    research_case_observer: TerminalFeedbackObserver,
    continuation_scheduler: ContinuationScheduler,
    pseudonymizer: ContinuationPseudonymizer | None,
    *,
    logger: logging.Logger | None = None,
) -> CompositeTerminalFeedbackObserver:
    """Create the observer supplied to ``FeedbackPipeline.terminal_observer``."""

    return CompositeTerminalFeedbackObserver(
        research_case_observer,
        ContinuationTerminalFeedbackObserver(
            continuation_scheduler,
            pseudonymizer,
        ),
        logger=logger,
    )
