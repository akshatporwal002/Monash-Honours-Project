"""API request and response schemas with lazy package exports."""

from importlib import import_module
from typing import Any

_EXPORT_MODULES = {
    "ALLOWED_LEARNING_EVENT_METADATA_KEYS": "app.schemas.persistence",
    "ASSESSMENT_CONTRACT_TYPES": "app.schemas.assessment",
    "AccessDeniedEvidenceReference": "app.schemas.assessment",
    "AssessmentPurpose": "app.schemas.assessment",
    "AssessmentReasonCode": "app.schemas.assessment",
    "AssessmentResult": "app.schemas.assessment",
    "AssessmentVersionReference": "app.schemas.assessment",
    "AuthenticatedActor": "app.schemas.feedback_api",
    "BloomKnowledge": "app.schemas.assessment",
    "BloomProcess": "app.schemas.assessment",
    "BrowserLearningEventRequest": "app.schemas.learning_events",
    "CompletionMetadata": "app.schemas.learning_events",
    "CompletionStatus": "app.schemas.learning_events",
    "ConflictingEvidenceReference": "app.schemas.assessment",
    "ContextProviderStatus": "app.schemas.feedback",
    "CriterionDecision": "app.schemas.assessment",
    "DraftSaveMetadata": "app.schemas.learning_events",
    "EvidenceReference": "app.schemas.assessment",
    "EvidenceReferenceResolution": "app.schemas.assessment",
    "EvidenceReferenceResolutionEnvelope": "app.schemas.assessment",
    "FeedbackAgentOutput": "app.schemas.feedback",
    "FeedbackApiErrorResponse": "app.schemas.feedback_api",
    "FeedbackContext": "app.schemas.feedback",
    "FeedbackPipelineResult": "app.schemas.feedback",
    "FeedbackPipelineStatus": "app.schemas.feedback",
    "FeedbackRecordCreate": "app.schemas.persistence",
    "FeedbackRecordRead": "app.schemas.persistence",
    "FeedbackRegenerationContext": "app.schemas.feedback",
    "FeedbackReportRequest": "app.schemas.feedback_api",
    "FeedbackReportResponse": "app.schemas.feedback_api",
    "FeedbackResponseClassification": "app.schemas.feedback",
    "FeedbackSourceAttribution": "app.schemas.feedback",
    "FeedbackSourceView": "app.schemas.feedback_api",
    "FeedbackViewMetadata": "app.schemas.learning_events",
    "FeedbackWorkflowResponse": "app.schemas.feedback_api",
    "FeedbackWorkflowStatus": "app.schemas.feedback_api",
    "FormalResultSummary": "app.schemas.assessment",
    "GeneratedFeedback": "app.schemas.feedback",
    "InvalidEvidenceReference": "app.schemas.assessment",
    "JudgeAgentOutput": "app.schemas.feedback",
    "JudgeEvaluationCreate": "app.schemas.persistence",
    "JudgeEvaluationOutcome": "app.schemas.feedback",
    "JudgeEvaluationRead": "app.schemas.persistence",
    "JudgeResult": "app.schemas.feedback",
    "LearningEventCreate": "app.schemas.persistence",
    "LearningEventRead": "app.schemas.persistence",
    "LearningEventReceipt": "app.schemas.learning_events",
    "LearningMaterialCreate": "app.schemas.content",
    "LearningMaterialRead": "app.schemas.content",
    "MaterialChunkCreate": "app.schemas.content",
    "MaterialChunkRead": "app.schemas.content",
    "MaterialProcessingRead": "app.schemas.content",
    "MissingEvidenceReference": "app.schemas.assessment",
    "MisconceptionState": "app.schemas.assessment",
    "QualityReviewDecision": "app.schemas.assessment",
    "ResearchEvaluationCreate": "app.schemas.persistence",
    "ResearchEvaluationRead": "app.schemas.persistence",
    "ResolvedEvidenceReference": "app.schemas.assessment",
    "ResultState": "app.schemas.assessment",
    "RetrievalContext": "app.schemas.feedback",
    "RetrievalHitRead": "app.schemas.content",
    "RetrievalResult": "app.schemas.feedback",
    "RetrievalResultRead": "app.schemas.content",
    "RetrievalSearchRequest": "app.schemas.content",
    "SafeFallbackFeedback": "app.schemas.feedback",
    "SafeFallbackView": "app.schemas.feedback_api",
    "SimulationContext": "app.schemas.feedback",
    "SimulationResult": "app.schemas.feedback",
    "StaleEvidenceReference": "app.schemas.assessment",
    "SubmissionContext": "app.schemas.feedback",
    "SubmissionMetadata": "app.schemas.learning_events",
    "SubmissionState": "app.schemas.assessment",
    "TaskContext": "app.schemas.feedback",
    "TaskGenerationMetadata": "app.schemas.content",
    "TaskViewMetadata": "app.schemas.learning_events",
    "TokenUsage": "app.schemas.feedback",
    "ValidatedFeedbackView": "app.schemas.feedback_api",
    "WorkflowRunCreate": "app.schemas.persistence",
    "WorkflowRunRead": "app.schemas.persistence",
    "legacy_judge_decision_to_quality_review": "app.schemas.assessment",
}

__all__ = sorted(_EXPORT_MODULES)


def __getattr__(name: str) -> Any:
    """Load package exports only when callers request them."""
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Include lazy exports in interactive discovery."""
    return sorted(set(globals()) | set(__all__))
