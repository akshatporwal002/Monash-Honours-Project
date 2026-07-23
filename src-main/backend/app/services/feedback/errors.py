class FeedbackPipelineError(Exception):
    """Base class for controlled feedback-pipeline failures."""


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
