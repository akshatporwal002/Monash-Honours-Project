class LearningEventError(Exception):
    """Base exception for controlled learning-event failures."""


class LearningEventConflictError(LearningEventError):
    """A caller event UUID was reused with different event content."""


class LearningEventPersistenceError(LearningEventError):
    """The event could not be persisted."""


class InvalidPseudonymizationSecretError(LearningEventError):
    """The configured pseudonymization secret is absent or too weak."""
