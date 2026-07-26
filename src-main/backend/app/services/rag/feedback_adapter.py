"""Bridge synchronous course retrieval into the asynchronous feedback contract."""

from __future__ import annotations

import anyio

from app.schemas.feedback import RetrievalContext, SubmissionContext, TaskContext
from app.services.rag.contracts import RetrievalPurpose, RetrievalQuery
from app.services.rag.retrieval import RetrievalService


class RagFeedbackRetrievalProvider:
    def __init__(self, retrieval: RetrievalService) -> None:
        self.retrieval = retrieval

    async def get_retrieval_context(
        self, task: TaskContext, submission: SubmissionContext
    ) -> list[RetrievalContext]:
        marking = str(task.marking_criteria or task.expected_answer or "")
        text = "\n".join(
            [task.prompt, task.difficulty, marking, submission.submitted_answer[:2000]]
        )
        result = await anyio.to_thread.run_sync(
            self.retrieval.search,
            RetrievalQuery(
                course_id=task.course_id,
                text=text,
                purpose=RetrievalPurpose.FEEDBACK,
                task_id=task.task_id,
                allowed_chunk_ids=tuple(task.source_references),
            ),
        )
        return [
            RetrievalContext(
                retrieval_request_id=result.request_id,
                task_id=task.task_id,
                course_id=task.course_id,
                source_id=hit.material_id,
                document_id=hit.material_id,
                chunk_id=hit.chunk_id,
                chunk_text=hit.chunk_text,
                relevance_score=hit.relevance_score,
                source_label=hit.source_label,
            )
            for hit in result.hits
        ]
