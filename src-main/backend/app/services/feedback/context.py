from app.schemas.feedback import FeedbackContext, SubmissionContext
from app.services.feedback.contracts import RetrievalProvider, SimulationProvider, TaskProvider
from app.services.feedback.errors import ContextCollectionError, TaskNotFoundError


class DefaultFeedbackContextCollector:
    def __init__(
        self,
        task_provider: TaskProvider,
        retrieval_provider: RetrievalProvider | None = None,
        simulation_provider: SimulationProvider | None = None,
    ) -> None:
        self._task_provider = task_provider
        self._retrieval_provider = retrieval_provider
        self._simulation_provider = simulation_provider

    async def collect(
        self,
        submission: SubmissionContext,
        correlation_id: str,
    ) -> FeedbackContext:
        try:
            task = await self._task_provider.get_task(submission.task_id)
            if task is None:
                raise TaskNotFoundError(submission.task_id)

            retrieval_context = []
            if self._retrieval_provider is not None:
                retrieval_context = await self._retrieval_provider.get_retrieval_context(
                    task,
                    submission,
                )

            simulation_context = None
            if self._simulation_provider is not None:
                simulation_context = await self._simulation_provider.get_simulation_context(
                    task,
                    submission,
                )

            return FeedbackContext(
                correlation_id=correlation_id,
                task=task,
                submission=submission,
                retrieval_context=retrieval_context,
                simulation_context=simulation_context,
            )
        except TaskNotFoundError:
            raise
        except Exception:
            raise ContextCollectionError() from None
