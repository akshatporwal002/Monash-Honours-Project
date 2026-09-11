"""Exact server context and authenticated findings for generated task approval."""

from app.models.source_history import SourcePassage
from app.schemas.category_review import (
    CategoryAssessment,
    CategoryReviewRequest,
    OutputCategory,
    ReviewEvidence,
    ReviewProvenance,
)
from app.schemas.task_review import TaskCategoryReviewSubmission
from app.services.category_review import review_output

TASK_QUALITY_POLICY = "educator-task-review-fr17-v1"


def requires_category_review(task, revision):
    return revision.provenance == "GENERATED" or bool(task.generation_provider)


def task_review_request(session, task, revision, sources, previous):
    evidence = []
    for reference, approval in sorted(sources.items()):
        passage = session.get(SourcePassage, reference)
        evidence.append(
            ReviewEvidence(
                reference=reference,
                version=passage.revision_id,
                kind="approved_content",
                approval_reference=approval,
                content={"text": passage.chunk_text, "location": passage.location_label},
            )
        )
    evidence.append(
        ReviewEvidence(
            reference=f"task-revision:{revision.id}",
            version=revision.content_digest,
            kind="policy",
            content={
                "outcome": revision.snapshot.get("outcome"),
                "marking_criteria": revision.snapshot.get("marking_criteria"),
            },
        )
    )
    return CategoryReviewRequest(
        category=OutputCategory.TASK,
        course_id=task.course_id,
        subject_id=revision.id,
        output=revision.snapshot,
        evidence=tuple(evidence),
        versions={
            "task_revision": revision.id,
            "task_digest": revision.content_digest,
            "review_event": previous.id if previous else "none",
            "model": task.generation_model or "human-authored",
            "prompt": task.generation_prompt_version or "human-authored",
            "policy": TASK_QUALITY_POLICY,
        },
    )


def authenticated_task_review(request, payload, actor):
    submission = TaskCategoryReviewSubmission.model_validate(payload)
    return review_output(
        request,
        lambda _: CategoryAssessment(
            request_digest=submission.request_digest,
            reviewer=ReviewProvenance(
                kind="human", reference=f"user:{actor.id}", version=TASK_QUALITY_POLICY
            ),
            findings=tuple(submission.findings),
        ),
    )
