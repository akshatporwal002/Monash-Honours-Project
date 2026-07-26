class FeedbackPipelineError(Exception):
    """Base class for controlled feedback-pipeline failures."""


class FeedbackAgentError(Exception):
    """Base class for sanitized failures inside a feedback generator."""


class FeedbackClientError(FeedbackAgentError):
    def __init__(self) -> None:
        super().__init__("The feedback model client could not complete the request")


class InvalidFeedbackOutputError(FeedbackAgentError):
    def __init__(self) -> None:
        super().__init__("The feedback model returned invalid structured output")


class SubmissionNotFoundError(FeedbackPipelineError):
    def __init__(self, submission_id: str) -> None:
        self.submission_id = submission_id
        super().__init__(f"Submission '{submission_id}' was not found")


class TaskNotFoundError(FeedbackPipelineError):
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task '{task_id}' was not found")


class ContextCollectionError(FeedbackPipelineError):
    def __init__(self) -> None:
        super().__init__("Feedback context could not be collected")


class ContextIntegrityError(FeedbackPipelineError):
    def __init__(self) -> None:
        super().__init__("Feedback context did not match the requested workflow")


class LostWorkflowLeaseError(FeedbackPipelineError):
    def __init__(self, workflow_run_id: str) -> None:
        self.workflow_run_id = workflow_run_id
        super().__init__(f"Workflow lease '{workflow_run_id}' is no longer owned")


class FeedbackGenerationError(FeedbackPipelineError):
    def __init__(self, correlation_id: str) -> None:
        self.correlation_id = correlation_id
        super().__init__(f"Feedback generation failed for workflow '{correlation_id}'")


class FeedbackJudgementError(FeedbackPipelineError):
    def __init__(self, correlation_id: str) -> None:
        self.correlation_id = correlation_id
        super().__init__(f"Feedback judgement failed for workflow '{correlation_id}'")


class PipelinePersistenceError(FeedbackPipelineError):
    def __init__(self, submission_id: str) -> None:
        self.submission_id = submission_id
        super().__init__(f"Feedback workflow for submission '{submission_id}' could not be stored")


class FeedbackReportConflictError(FeedbackPipelineError):
    def __init__(self) -> None:
        super().__init__("A different report already exists for this feedback")
