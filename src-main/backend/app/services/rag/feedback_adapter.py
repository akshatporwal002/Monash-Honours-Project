"""Bridge task-scoped, reviewed source retrieval into feedback context."""

from __future__ import annotations

import anyio

from app.models import LearningMaterial, MaterialIndexStatus
from app.models.source_history import SourcePassage, SourceRevision
from app.schemas.feedback import RetrievalContext, SubmissionContext, TaskContext
from app.services.rag.contracts import RetrievalPurpose, RetrievalQuery
from app.services.rag.local_retrieval import LocalCourseRetrievalService
from app.services.rag.retrieval import RetrievalService
from app.services.rag.source_history import latest_approval

FEEDBACK_RETRIEVAL_VERSION = "task-feedback-retrieval-v1"


class RagFeedbackRetrievalProvider:
    def __init__(self, retrieval: RetrievalService | LocalCourseRetrievalService) -> None:
        self.retrieval = retrieval

    async def get_retrieval_context(
        self, task: TaskContext, submission: SubmissionContext
    ) -> list[RetrievalContext]:
        if submission.task_id != task.task_id or submission.course_id != task.course_id:
            raise ValueError("feedback retrieval scope mismatch")
        if not task.source_references:
            return []
        return await anyio.to_thread.run_sync(self._retrieve, task)

    def _retrieve(self, task: TaskContext) -> list[RetrievalContext]:
        session = self.retrieval.session
        eligible = []
        metadata = {}
        for reference in dict.fromkeys(task.source_references):
            passage = session.get(SourcePassage, reference)
            if passage is None:
                if not task.assessed:
                    # The existing retrieval service can snapshot legacy practice chunks.
                    eligible.append(reference)
                continue
            revision = session.get(SourceRevision, passage.revision_id)
            material = session.get(LearningMaterial, revision.material_id) if revision else None
            if (
                passage.course_id != task.course_id
                or revision is None
                or revision.course_id != task.course_id
                or material is None
                or material.course_id != task.course_id
                or material.retired_at is not None
                or (task.assessed and material.indexing_status != MaterialIndexStatus.INDEXED)
            ):
                continue
            approval = latest_approval(session, revision.id)
            if (approval is not None and approval.state != "APPROVED") or (
                task.assessed
                and (approval is None or approval.id != task.source_approvals.get(reference))
            ):
                continue
            eligible.append(reference)
            metadata[reference] = {
                "source_revision_id": revision.id,
                "source_digest": revision.content_hash or None,
                "passage_digest": passage.chunk_hash or None,
                "approval_id": approval.id if approval else None,
                "retrieval_version": FEEDBACK_RETRIEVAL_VERSION,
            }
        if not eligible:
            return []
        # Learner text cannot make an unrelated source relevant to the approved task.
        marking = task.marking_criteria
        descriptions = (
            [item.get("learner_description", "") for item in marking if isinstance(item, dict)]
            if isinstance(marking, list)
            else [str(marking or task.expected_answer or "")]
        )
        text = "\n".join([task.prompt, *descriptions])
        result = self.retrieval.search(
            RetrievalQuery(
                course_id=task.course_id,
                text=text,
                purpose=RetrievalPurpose.FEEDBACK,
                task_id=task.task_id,
                allowed_chunk_ids=tuple(eligible),
            )
        )
        return [
            RetrievalContext(
                retrieval_request_id=result.request_id,
                task_id=task.task_id,
                course_id=task.course_id,
                source_id=hit.chunk_id,
                document_id=hit.material_id,
                chunk_id=hit.chunk_id,
                chunk_text=hit.chunk_text,
                relevance_score=hit.relevance_score,
                source_label=hit.source_label,
                **metadata.get(hit.chunk_id, {}),
            )
            for hit in result.hits
            if not task.assessed or hit.chunk_id in metadata
        ]


def cached_sources_available(session, claims, task):
    """Validate saved passage bindings without running retrieval or creating an audit on GET."""
    if not claims:
        return False
    for claim in claims:
        if not isinstance(claim, dict) or claim.get("source_id") not in task.source_references:
            return False
        passage = session.get(SourcePassage, claim["source_id"])
        revision = session.get(SourceRevision, passage.revision_id) if passage else None
        material = session.get(LearningMaterial, revision.material_id) if revision else None
        approval = latest_approval(session, revision.id) if revision else None
        if (
            passage is None
            or revision is None
            or material is None
            or approval is None
            or passage.course_id != task.course_id
            or revision.course_id != task.course_id
            or material.course_id != task.course_id
            or material.retired_at is not None
            or material.indexing_status != MaterialIndexStatus.INDEXED
            or approval.state != "APPROVED"
            or approval.id != claim.get("approval_id")
            or approval.id != task.source_approvals.get(passage.id)
            or revision.id != claim.get("source_revision_id")
            or revision.content_hash != claim.get("source_digest")
            or passage.chunk_hash != claim.get("passage_digest")
        ):
            return False
    return True
