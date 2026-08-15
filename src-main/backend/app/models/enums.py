from enum import Enum

from app.domain.assessment import AssessmentPurpose as AssessmentPurpose
from app.domain.assessment import AssessmentResult as AssessmentResult
from app.domain.assessment import BloomKnowledge as BloomKnowledge
from app.domain.assessment import BloomProcess as BloomProcess
from app.domain.assessment import CriterionDecision as CriterionDecision
from app.domain.assessment import MisconceptionState as MisconceptionState
from app.domain.assessment import QualityReviewDecision as QualityReviewDecision
from app.domain.assessment import ResultState as ResultState
from app.domain.assessment import SubmissionState as SubmissionState


class WorkflowStage(str, Enum):
    PENDING = "pending"
    CONTEXT_COLLECTION = "context_collection"
    GENERATING = "generating"
    JUDGING = "judging"
    REGENERATING = "regenerating"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowOutcome(str, Enum):
    FIRST_PASS = "first_pass"
    SECOND_PASS = "second_pass"
    SAFE_FALLBACK = "safe_fallback"
    WORKFLOW_FAILED = "workflow_failed"


class FeedbackStatus(str, Enum):
    PENDING_JUDGEMENT = "pending_judgement"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SAFE_FALLBACK = "safe_fallback"


class FeedbackReportCategory(str, Enum):
    INCORRECT = "incorrect"
    UNSAFE = "unsafe"
    UNCLEAR = "unclear"
    CITATION_ISSUE = "citation_issue"
    OTHER = "other"


class JudgeEvaluationStatus(str, Enum):
    VALID = "valid"
    MALFORMED = "malformed"
    PROVIDER_ERROR = "provider_error"


class JudgeDecision(str, Enum):
    PASS = "pass"
    FAIL = "fail"


class LearningEventType(str, Enum):
    TASK_VIEW = "task_view"
    DRAFT_SAVE = "draft_save"
    SUBMISSION = "submission"
    FEEDBACK_VIEW = "feedback_view"
    COMPLETION = "completion"


class ExperimentalCondition(str, Enum):
    AGENTIC_RAG = "agentic_rag"
    SINGLE_STEP_BASELINE = "single_step_baseline"


class ResearchStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    MULTIPLE_ANSWER = "multiple_answer"
    SHORT_ANSWER = "short_answer"
    CODE_EXPLANATION = "code_explanation"
    CODE_COMPLETION = "code_completion"
    QUANTUM_CIRCUIT = "quantum_circuit"

    # Kept for rows created by the early demo. New LMS code uses the six
    # requirement-named values above.
    QUIZ = "quiz"
    CODE = "code"
    CIRCUIT = "circuit"


class SubmissionStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    COMPLETED = "completed"


class NotificationKind(str, Enum):
    REMINDER = "reminder"
    ACHIEVEMENT = "achievement"
    FEEDBACK = "feedback"


class MaterialIndexStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    INDEXED = "indexed"
    FAILED = "failed"


class ContinuationState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    RETRY_SCHEDULED = "retry_scheduled"
    COMPLETED = "completed"
    FAILED = "failed"


class ContinuationFailureCategory(str, Enum):
    INVALID_NOTICE = "invalid_continuation_notice"
    REPOSITORY_NOT_CONFIGURED = "continuation_repository_not_configured"
    PROGRESS_ADAPTER_NOT_CONFIGURED = "progress_adapter_not_configured"
    RECOMMENDER_NOT_CONFIGURED = "next_task_recommender_not_configured"
    PROGRESS_UNAVAILABLE = "progress_adapter_unavailable"
    RECOMMENDER_UNAVAILABLE = "next_task_recommender_unavailable"
    INVALID_RECOMMENDATION = "invalid_next_task_reference"
    PERSISTENCE_UNAVAILABLE = "continuation_persistence_unavailable"


class TerminalIntegrationType(str, Enum):
    RESEARCH_PAIR = "research_pair"
    CONTINUATION = "continuation"


class TerminalIntegrationState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    RETRY_SCHEDULED = "retry_scheduled"
    COMPLETED = "completed"
    FAILED = "failed"


class TerminalIntegrationFailureCategory(str, Enum):
    INVALID_PAYLOAD = "invalid_terminal_integration_payload"
    INTEGRATION_UNAVAILABLE = "terminal_integration_unavailable"
    PERSISTENCE_UNAVAILABLE = "terminal_integration_persistence_unavailable"
