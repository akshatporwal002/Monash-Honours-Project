"""Require exact current teaching approval for a formal assessment form."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LearningMaterial, LearningOutcome, LearningTask, User
from app.models.assessment import OutcomeVersion, TaskApproval, TaskFormVersion
from app.models.source_history import SourcePassage, SourceRevision
from app.models.task_review import TaskReviewEvent, TaskRevision
from app.services.episode_contract import validate_reviewed_episode_plan
from app.services.task_review import TaskReviewError, TaskReviewService


def current_form_review(
    session: Session, form: TaskFormVersion, *, require_scan: bool = True
) -> TaskReviewEvent:
    """Return the current educator approval or reject a missing or stale binding."""
    task = session.get(LearningTask, form.learning_task_id, populate_existing=True)
    revision = session.get(TaskRevision, form.task_revision_id) if form.task_revision_id else None
    if task is None or revision is None:
        raise TaskReviewError("The formal task form needs a saved teaching revision", 409)
    if (
        task.course_id != form.course_id
        or revision.task_id != task.id
        or revision.course_id != form.course_id
        or form.source_digest != revision.content_digest
        or form.source_version != f"task-revision:{revision.id}"
    ):
        raise TaskReviewError("The formal task form does not match its teaching revision", 409)
    review = TaskReviewService(session)
    review.require_available(task)
    if review.latest_revision(task.id).id != revision.id:
        raise TaskReviewError("Teaching content changed; save a new assessment definition", 409)
    frozen_plan = (
        form.constraints.get("episode_plan") if isinstance(form.constraints, dict) else None
    )
    reviewed_marking = revision.snapshot.get("marking_criteria")
    try:
        plan = validate_reviewed_episode_plan(
            reviewed_marking if isinstance(reviewed_marking, dict) else None, frozen_plan
        )
        if plan is not None and frozen_plan is None:
            raise ValueError("The frozen form is missing its reviewed episode plan")
    except ValueError as error:
        raise TaskReviewError(
            "The formal episode does not match its reviewed teaching revision", 409
        ) from error
    sources = review.validate_ready(task, require_sources=True, require_scan=require_scan)
    event = review.latest_event(revision.id)
    if event is None or event.state != "APPROVED" or event.source_approvals != sources:
        raise TaskReviewError("The formal task needs current source and educator approval", 409)
    outcome = session.get(LearningOutcome, task.learning_outcome_id, populate_existing=True)
    frozen = session.get(OutcomeVersion, form.assessment_definition_version.outcome_version_id)
    if (
        outcome is None
        or frozen is None
        or frozen.learning_outcome_id != outcome.id
        or frozen.course_id != form.course_id
        or frozen.title != outcome.title
        or frozen.statement != outcome.statement
    ):
        raise TaskReviewError("Outcome wording changed; save a new assessment definition", 409)
    return event


def require_current_publication(
    session: Session, form: TaskFormVersion, approval: TaskApproval
) -> None:
    event = current_form_review(session, form, require_scan=False)
    if (
        approval.task_review_event_id != event.id
        or approval.course_id != form.course_id
        or approval.assessment_definition_version_id != form.assessment_definition_version_id
    ):
        raise TaskReviewError("The formal publication no longer matches educator review", 409)


def require_learner_task_available(session: Session, task: LearningTask) -> None:
    from app.services.assessment.submissions import AssessmentSubmissionService

    TaskReviewService(session).require_available(task)
    declaration = AssessmentSubmissionService(session).declaration_for_task(task)
    if (
        isinstance(task.marking_criteria, dict)
        and "multipart_candidate" in task.marking_criteria
        and declaration is None
    ):
        raise TaskReviewError(
            "The generated multipart episode needs its approved assessment form before learner use",
            409,
        )


def learner_task_available(session: Session, task: LearningTask) -> bool:
    try:
        require_learner_task_available(session, task)
    except TaskReviewError:
        return False
    return True


def authoring_tasks(
    session: Session, actor: User, course_id: str, *, limit: int = 20, offset: int = 0
) -> list[dict]:
    review = TaskReviewService(session)
    review.require_review_access(actor, course_id)
    tasks = session.scalars(
        select(LearningTask)
        .where(LearningTask.course_id == course_id)
        .order_by(LearningTask.position, LearningTask.id)
        .limit(limit)
        .offset(offset)
    )
    result = []
    for task in tasks:
        summary = review.summary(task)
        outcome = session.get(LearningOutcome, task.learning_outcome_id)
        if outcome is None:
            continue
        materials = list(
            session.execute(
                select(
                    LearningMaterial.id,
                    LearningMaterial.original_filename,
                    SourceRevision.source_label,
                )
                .join(SourceRevision, SourceRevision.material_id == LearningMaterial.id)
                .join(SourcePassage, SourcePassage.revision_id == SourceRevision.id)
                .where(
                    SourcePassage.id.in_(task.source_references or []),
                    SourcePassage.course_id == course_id,
                )
                .distinct()
            )
        )
        result.append(
            {
                "task_id": task.id,
                "generated_assessment_candidate": isinstance(task.marking_criteria, dict)
                and "multipart_candidate" in task.marking_criteria,
                "title": task.title,
                "task_type": task.task_type.value,
                "outcome_id": outcome.id,
                "outcome_statement": outcome.statement,
                "revision_id": summary["revision_id"],
                "content_digest": summary["content_digest"],
                "reviewed": summary["available"],
                "issues": summary["issues"],
                "source_materials": [
                    {"material_id": row.id, "label": row.original_filename or row.source_label}
                    for row in materials
                ],
            }
        )
    return result
