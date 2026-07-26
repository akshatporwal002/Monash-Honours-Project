from collections.abc import Mapping
from copy import deepcopy

from app.models.enums import JudgeEvaluationStatus
from app.schemas.feedback import (
    FeedbackContext,
    FeedbackRegenerationContext,
    GeneratedFeedback,
    JudgeEvaluationOutcome,
    JudgeResult,
    RetrievalContext,
    SimulationContext,
    SubmissionContext,
    TaskContext,
)
from app.services.feedback.contracts import StructuredLlmRequest, StructuredLlmResponse


class RecordingStructuredLlmClient:
    def __init__(
        self,
        response: StructuredLlmResponse,
        error: Exception | None = None,
    ) -> None:
        self._response = response
        self._error = error
        self.call_count = 0
        self.requests: list[StructuredLlmRequest] = []

    async def generate_structured(
        self,
        request: StructuredLlmRequest,
    ) -> StructuredLlmResponse:
        self.call_count += 1
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        return StructuredLlmResponse(
            output=deepcopy(self._response.output),
            provider=self._response.provider,
            model=self._response.model,
            token_usage=self._response.token_usage.model_copy(deep=True),
            estimated_cost=self._response.estimated_cost,
            usage_complete=self._response.usage_complete,
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
        result: GeneratedFeedback | list[GeneratedFeedback],
        error: Exception | None = None,
        error_on_calls: Mapping[int, Exception] | None = None,
    ) -> None:
        self._results = list(result) if isinstance(result, list) else [result]
        self._errors = dict(error_on_calls or {})
        if error is not None:
            self._errors[1] = error
        self.call_count = 0
        self.contexts: list[FeedbackContext] = []
        self.regenerations: list[FeedbackRegenerationContext | None] = []

    async def generate(
        self,
        context: FeedbackContext,
        regeneration: FeedbackRegenerationContext | None = None,
    ) -> GeneratedFeedback:
        self.call_count += 1
        self.contexts.append(context)
        self.regenerations.append(regeneration)
        if self.call_count in self._errors:
            raise self._errors[self.call_count]
        result_index = min(self.call_count - 1, len(self._results) - 1)
        return self._results[result_index].model_copy(deep=True)


class FakeFeedbackJudge:
    def __init__(
        self,
        result: JudgeResult | JudgeEvaluationOutcome | list[JudgeResult | JudgeEvaluationOutcome],
        error: Exception | None = None,
        error_on_calls: Mapping[int, Exception] | None = None,
    ) -> None:
        raw_results = list(result) if isinstance(result, list) else [result]
        self._results = [self._as_outcome(item) for item in raw_results]
        self._errors = dict(error_on_calls or {})
        if error is not None:
            self._errors[1] = error
        self.call_count = 0
        self.contexts: list[FeedbackContext] = []
        self.feedback: list[GeneratedFeedback] = []

    async def evaluate(
        self,
        context: FeedbackContext,
        feedback: GeneratedFeedback,
    ) -> JudgeEvaluationOutcome:
        self.call_count += 1
        self.contexts.append(context)
        self.feedback.append(feedback)
        if self.call_count in self._errors:
            raise self._errors[self.call_count]
        result_index = min(self.call_count - 1, len(self._results) - 1)
        return self._results[result_index].model_copy(deep=True)

    @staticmethod
    def _as_outcome(
        result: JudgeResult | JudgeEvaluationOutcome,
    ) -> JudgeEvaluationOutcome:
        if isinstance(result, JudgeEvaluationOutcome):
            return result
        return JudgeEvaluationOutcome(
            evaluation_status=JudgeEvaluationStatus.VALID,
            reported_decision=result.decision,
            judge_result=result,
            reason=result.reason,
            provider="fake-provider",
            model="fake-judge-model",
            prompt_version="quality-judge-v1",
        )
