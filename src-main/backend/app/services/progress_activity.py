"""Practice participation under approved exit rules, independent of legacy marks."""

from fastapi import HTTPException
from sqlalchemy import select

from app.models.lms import SubmissionAttempt
from app.models.persistence import LearningTask
from app.services.assessment.submissions import AssessmentSubmissionService
from app.services.task_review import TaskReviewError


def completed_practice_tasks(session, learner_id, task_ids):
    from app.services.curriculum import CurriculumService

    if not task_ids:
        return set()
    submitted = set(
        session.scalars(
            select(SubmissionAttempt.task_id).where(
                SubmissionAttempt.student_id == learner_id,
                SubmissionAttempt.task_id.in_(task_ids),
                SubmissionAttempt.task_form_version_id.is_(None),
            )
        )
    )
    tasks = list(session.scalars(select(LearningTask).where(LearningTask.id.in_(submitted))))
    curriculum = CurriculumService(session)
    paths = {}
    completed = set()
    for task in tasks:
        try:
            if AssessmentSubmissionService(session).declaration_for_task(task) is not None:
                continue
        except TaskReviewError:
            # Earlier practice cannot complete a now-declared formal assessment.
            continue
        if task.learning_outcome_id not in paths:
            paths[task.learning_outcome_id] = curriculum._latest(task.learning_outcome_id)
        path = paths[task.learning_outcome_id]
        if path and task.id in path.bindings:
            try:
                curriculum._current(path)
            except (HTTPException, TaskReviewError) as error:
                if error.status_code not in {403, 404, 409, 422}:
                    raise
                # Stale approval prevents this completion, not unrelated course work.
                continue
            step = next(item for item in path.payload["steps"] if item["task_id"] == task.id)
            if path.bindings[task.id]["assessment"] or step["exit_rule"] != "accepted_response":
                continue
        # A submitted practice item is an activity observation, never a formal result.
        completed.add(task.id)
    return completed
