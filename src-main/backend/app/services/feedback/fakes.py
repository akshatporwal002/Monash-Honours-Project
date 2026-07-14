from collections.abc import Mapping

from app.schemas.feedback import (
    FeedbackContext,
    GeneratedFeedback,
    JudgeResult,
    RetrievalContext,
    SimulationContext,
    SubmissionContext,
    TaskContext,
)


class InMemorySubmissionProvider:
    def __init__(self, submissions: Mapping[str, SubmissionContext]) -> None:
        self._submissions = dict(submissions)
        self.call_count = 0

    async def get_submission(self, submission_id: str) -> SubmissionContext | None:
        self.call_count += 1
        return self._submissions.get(submission_id)


class InMemoryTaskProvider:
    def __init__(self, tasks: Mapping[str, TaskContext]) -> None:
        self._tasks = dict(tasks)
        self.call_count = 0

    async def get_task(self, task_id: str) -> TaskContext | None:
        self.call_count += 1
        return self._tasks.get(task_id)


class StaticRetrievalProvider:
    def __init__(self, items_by_task: Mapping[str, list[RetrievalContext]]) -> None:
        self._items_by_task = {key: list(value) for key, value in items_by_task.items()}
        self.call_count = 0

    async def get_retrieval_context(
        self,
        task: TaskContext,
        submission: SubmissionContext,
    ) -> list[RetrievalContext]:
        self.call_count += 1
        return list(self._items_by_task.get(task.task_id, []))


class StaticSimulationProvider:
    def __init__(self, items_by_task: Mapping[str, SimulationContext | None]) -> None:
        self._items_by_task = dict(items_by_task)
        self.call_count = 0

    async def get_simulation_context(
        self,
        task: TaskContext,
        submission: SubmissionContext,
    ) -> SimulationContext | None:
        self.call_count += 1
        return self._items_by_task.get(task.task_id)


class FakeFeedbackGenerator:
    def __init__(
        self,
        result: GeneratedFeedback,
        error: Exception | None = None,
    ) -> None:
        self._result = result
        self._error = error
        self.call_count = 0
        self.contexts: list[FeedbackContext] = []

    async def generate(self, context: FeedbackContext) -> GeneratedFeedback:
        self.call_count += 1
        self.contexts.append(context)
        if self._error is not None:
            raise self._error
        return self._result.model_copy(deep=True)


class FakeFeedbackJudge:
    def __init__(
        self,
        result: JudgeResult,
        error: Exception | None = None,
    ) -> None:
        self._result = result
        self._error = error
        self.call_count = 0
        self.contexts: list[FeedbackContext] = []
        self.feedback: list[GeneratedFeedback] = []

    async def evaluate(
        self,
        context: FeedbackContext,
        feedback: GeneratedFeedback,
    ) -> JudgeResult:
        self.call_count += 1
        self.contexts.append(context)
        self.feedback.append(feedback)
        if self._error is not None:
            raise self._error
        return self._result.model_copy(deep=True)
