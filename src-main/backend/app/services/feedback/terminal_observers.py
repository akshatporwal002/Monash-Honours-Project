from __future__ import annotations

import logging

from app.schemas.feedback import FeedbackContext, FeedbackPipelineResult
from app.services.feedback.contracts import (
    FeedbackAttemptPersistence,
    TerminalFeedbackObserver,
)


class CompositeTerminalFeedbackObserver:
    """Run terminal integrations independently after feedback is durable."""

    def __init__(
        self,
        *observers: TerminalFeedbackObserver,
        logger: logging.Logger | None = None,
    ) -> None:
        self._observers = tuple(observers)
        self._logger = logger or logging.getLogger(__name__)

    async def after_terminal_feedback(
        self,
        context: FeedbackContext,
        result: FeedbackPipelineResult,
        attempts: tuple[FeedbackAttemptPersistence, ...],
    ) -> None:
        for observer_slot, observer in enumerate(self._observers):
            try:
                await observer.after_terminal_feedback(context, result, attempts)
            except Exception:
                self._log_failure(
                    observer_slot=observer_slot,
                    correlation_id=context.correlation_id,
                )

    def _log_failure(self, *, observer_slot: int, correlation_id: str) -> None:
        try:
            self._logger.warning(
                "terminal_feedback_observer_failed",
                extra={
                    "correlation_id": correlation_id,
                    "stage": f"terminal_observer_{observer_slot}",
                    "failure_category": "terminal_integration_unavailable",
                },
            )
        except Exception:
            # An operational logger must not stop another terminal integration.
            pass
