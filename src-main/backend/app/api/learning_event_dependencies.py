from typing import NoReturn

from app.api.feedback_dependencies import FeedbackApiException
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.learning_events import (
    BestEffortFeedbackViewTracker,
    BestEffortLearningEventSink,
    FeedbackViewTracker,
    HmacSha256Pseudonymizer,
    InvalidPseudonymizationSecretError,
    LearningEventAccessPolicy,
    LearningEventRecorder,
    NoOpFeedbackViewTracker,
    TrustedLearningEventHooks,
)


def get_learning_event_access_policy() -> LearningEventAccessPolicy:
    _unavailable(
        "learning_event_authorization_unavailable",
        "Learning-event authorization is not configured.",
    )


def get_learning_event_recorder() -> LearningEventRecorder:
    configured_secret = settings.learning_event_pseudonym_secret
    if configured_secret is None:
        _unavailable(
            "learning_event_recording_unavailable",
            "Learning-event recording is not configured.",
        )
    try:
        pseudonymizer = HmacSha256Pseudonymizer(configured_secret.get_secret_value())
    except InvalidPseudonymizationSecretError:
        _unavailable(
            "learning_event_recording_unavailable",
            "Learning-event recording is not configured.",
        )
    return LearningEventRecorder(SessionLocal, pseudonymizer)


def get_feedback_view_tracker() -> FeedbackViewTracker:
    configured_secret = settings.learning_event_pseudonym_secret
    if configured_secret is None:
        return NoOpFeedbackViewTracker()
    try:
        pseudonymizer = HmacSha256Pseudonymizer(configured_secret.get_secret_value())
    except InvalidPseudonymizationSecretError:
        return NoOpFeedbackViewTracker()
    recorder = LearningEventRecorder(SessionLocal, pseudonymizer)
    hooks = TrustedLearningEventHooks(BestEffortLearningEventSink(recorder))
    return BestEffortFeedbackViewTracker(hooks)


def _unavailable(code: str, message: str) -> NoReturn:
    raise FeedbackApiException(503, code, message)
