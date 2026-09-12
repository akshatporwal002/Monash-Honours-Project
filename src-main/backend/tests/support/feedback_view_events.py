"""Retain separately observed telemetry adapters in API contract fixtures."""


class FeedbackViewEventsAdapter:
    def __init__(self, learning, audit):
        self.learning = learning
        self.audit = audit

    def record(self, *, feedback_id, **values):
        self.learning.record_terminal_view(**values)
        if feedback_id is not None:
            self.audit.record_feedback_view(
                actor_reference=values["actor_reference"],
                feedback_id=feedback_id,
                correlation_id=values["correlation_id"],
            )
