"""Resolve a reviewed candidate into the existing, unapproved assessment draft contract."""

from sqlalchemy import update

from app.models.lms import Course
from app.models.persistence import LearningTask
from app.models.source_history import SourcePassage
from app.schemas.lms import AssessmentDefinitionDraftCreate
from app.services.assessment.access import RoleAssignmentService, ScopedRoleAccessDeniedError
from app.services.multipart_generation import validate_multipart
from app.services.task_review import TaskReviewError, TaskReviewService


def generated_assessment_draft(
    session, actor, course_id, task_id, expected_revision_id, *, lock=False
):
    try:
        RoleAssignmentService(session).require_assessor_access(actor, course_id)
    except ScopedRoleAccessDeniedError as error:
        raise TaskReviewError(
            "Active assessor permission is required for this course", 403
        ) from error
    if lock:
        session.execute(
            update(Course)
            .where(Course.id == course_id)
            .values(id=Course.id, updated_at=Course.updated_at)
        )
    task = session.get(LearningTask, task_id, populate_existing=True)
    if task is None or task.course_id != course_id:
        raise TaskReviewError("Task not found in this course", 404)
    review = TaskReviewService(session)
    summary = review.summary(task)
    if not summary["available"] or summary["revision_id"] != expected_revision_id:
        raise TaskReviewError(
            "Reload the current reviewed task before using its generated design", 409
        )
    criteria = task.marking_criteria or {}
    try:
        candidate = validate_multipart(
            criteria,
            task.task_type.value,
            {
                ref: passage.chunk_text
                for ref in task.source_references
                if (passage := session.get(SourcePassage, ref)) is not None
            },
        )
    except ValueError as error:
        raise TaskReviewError(str(error), 422) from error
    payload = candidate.assessment_design.model_dump(mode="json")
    payload["task_forms"] = [
        {
            "learning_task_id": task.id,
            "source_version": f"task-revision:{summary['revision_id']}",
            "source_digest": summary["content_digest"],
            "task_family": candidate.family,
            "context": {
                "source_anchors": [anchor.model_dump() for anchor in candidate.source_anchors],
                "criterion_sources": candidate.criterion_sources,
                "generation_candidate_version": candidate.schema_version,
            },
            "constraints": {
                "episode_plan": candidate.episode_plan.model_dump(mode="json"),
                "elicited_bloom_processes": [],
                "bloom_review_required": True,
                "prior_work_policy": candidate.prior_work_policy,
            },
        }
    ]
    return task, AssessmentDefinitionDraftCreate.model_validate(payload)
