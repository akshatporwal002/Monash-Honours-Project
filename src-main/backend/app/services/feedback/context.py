import asyncio

from pydantic import ValidationError

from app.schemas.feedback import (
    AssessmentContextStatus,
    ContextProviderStatus,
    FeedbackContext,
    RetrievalContext,
    RetrievalResult,
    SimulationContext,
    SimulationResult,
    SubmissionContext,
)
from app.services.feedback.contracts import (
    AssessmentFeedbackContextProvider,
    RetrievalProvider,
    SimulationProvider,
    TaskProvider,
)
from app.services.feedback.errors import (
    ContextCollectionError,
    ContextIntegrityError,
    TaskNotFoundError,
)


class DefaultFeedbackContextCollector:
    def __init__(
        self,
        task_provider: TaskProvider,
        retrieval_provider: RetrievalProvider | None = None,
        simulation_provider: SimulationProvider | None = None,
        assessment_context_provider: AssessmentFeedbackContextProvider | None = None,
        *,
        provider_timeout_seconds: float = 60,
    ) -> None:
        if not 0 < provider_timeout_seconds <= 60:
            raise ValueError("provider_timeout_seconds must be between 0 and 60")
        self._task_provider = task_provider
        self._retrieval_provider = retrieval_provider
        self._simulation_provider = simulation_provider
        self._assessment_context_provider = assessment_context_provider
        self._provider_timeout_seconds = provider_timeout_seconds

    async def collect(
        self,
        submission: SubmissionContext,
        correlation_id: str,
    ) -> FeedbackContext:
        try:
            assessment_context = None
            if self._assessment_context_provider is not None:
                resolution = await asyncio.wait_for(
                    self._assessment_context_provider.resolve(submission),
                    timeout=self._provider_timeout_seconds,
                )
                if resolution.status is AssessmentContextStatus.RESOLVED:
                    assessment_context = resolution.context
                    assert assessment_context is not None
                    task = assessment_context.task
                elif resolution.status is AssessmentContextStatus.NOT_ASSESSED:
                    task = await asyncio.wait_for(
                        self._task_provider.get_task(submission.task_id),
                        timeout=self._provider_timeout_seconds,
                    )
                else:
                    raise ContextIntegrityError()
            else:
                task = await asyncio.wait_for(
                    self._task_provider.get_task(submission.task_id),
                    timeout=self._provider_timeout_seconds,
                )
            if task is None:
                raise TaskNotFoundError(submission.task_id)
            if task.task_id != submission.task_id:
                raise ContextIntegrityError()
            if task.course_id != submission.course_id:
                raise ContextIntegrityError()

            retrieval_result = RetrievalResult(status=ContextProviderStatus.NOT_REQUESTED)
            if self._retrieval_provider is not None:
                raw_retrieval = await asyncio.wait_for(
                    self._retrieval_provider.get_retrieval_context(task, submission),
                    timeout=self._provider_timeout_seconds,
                )
                retrieval_result = self._normalize_retrieval(raw_retrieval)

            simulation_result = SimulationResult(status=ContextProviderStatus.NOT_REQUESTED)
            if self._simulation_provider is not None:
                raw_simulation = await asyncio.wait_for(
                    self._simulation_provider.get_simulation_context(task, submission),
                    timeout=self._provider_timeout_seconds,
                )
                simulation_result = self._normalize_simulation(raw_simulation)

            return FeedbackContext(
                correlation_id=correlation_id,
                task=task,
                submission=submission,
                retrieval_context=retrieval_result.items,
                retrieval_status=retrieval_result.status,
                retrieval_request_ids=retrieval_result.request_ids,
                simulation_context=simulation_result.context,
                simulation_status=simulation_result.status,
                assessment_context=assessment_context,
            )
        except (ContextIntegrityError, TaskNotFoundError):
            raise
        except ValidationError:
            raise ContextIntegrityError() from None
        except Exception:
            raise ContextCollectionError() from None

    @staticmethod
    def _normalize_retrieval(
        result: RetrievalResult | list[RetrievalContext],
    ) -> RetrievalResult:
        if isinstance(result, RetrievalResult):
            return result
        items = [RetrievalContext.model_validate(item) for item in result]
        if not items:
            return RetrievalResult(status=ContextProviderStatus.EMPTY)
        return RetrievalResult(
            status=ContextProviderStatus.COMPLETED,
            request_ids=sorted({item.retrieval_request_id for item in items}),
            items=items,
        )

    @staticmethod
    def _normalize_simulation(
        result: SimulationResult | SimulationContext | None,
    ) -> SimulationResult:
        if isinstance(result, SimulationResult):
            return result
        if result is None:
            return SimulationResult(status=ContextProviderStatus.EMPTY)
        return SimulationResult(
            status=ContextProviderStatus.COMPLETED,
            context=SimulationContext.model_validate(result),
        )
