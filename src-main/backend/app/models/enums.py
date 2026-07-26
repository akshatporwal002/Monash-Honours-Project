from enum import Enum


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
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(str, Enum):
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
