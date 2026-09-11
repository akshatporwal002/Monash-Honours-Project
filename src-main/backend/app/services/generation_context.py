"""Resolve scoped, immutable generation inputs before invoking a provider."""

from app.models import (
    FeedbackRecord,
    FeedbackStatus,
    JudgeDecision,
    JudgeEvaluationStatus,
    LearningTask,
)
from app.models.lms import SubmissionAttempt
from app.services.rag.source_history import output_digest
from app.services.task_review import TaskReviewService, snapshot_digest, task_snapshot


def resolve_generation_context(session, request):
    context = request.generation_context
    if context is None:
        return None, None
    if context.variant_task_id:
        task = session.get(LearningTask, context.variant_task_id, populate_existing=True)
        _task_scope(task, request)
        revision = TaskReviewService(session).latest_revision(task.id)
        if (
            revision is None
            or revision.id != context.variant_revision_id
            or revision.content_digest != snapshot_digest(task_snapshot(session, task))
        ):
            raise ValueError("Reload the current task revision before generating a variant")
        lineage = {
            "kind": "variant",
            "task_id": task.id,
            "task_revision_id": revision.id,
            "revision_digest": revision.content_digest,
        }
        return lineage, {
            "kind": "variant",
            "title": task.title,
            "prompt": task.description,
            "instructions": task.instructions,
            "instruction": "Vary the example or context while preserving the outcome. Equivalence requires educator review.",
        }
    if context.response_version_id:
        attempt = session.get(SubmissionAttempt, context.response_version_id)
        feedback = session.get(FeedbackRecord, context.feedback_id, populate_existing=True)
        task = session.get(LearningTask, attempt.task_id) if attempt else None
        _task_scope(task, request)
        judge = feedback.judge_evaluation if feedback else None
        if (
            feedback is None
            or feedback.submission_id != attempt.id
            or feedback.status != FeedbackStatus.ACCEPTED
            or judge is None
            or judge.evaluation_status != JudgeEvaluationStatus.VALID
            or judge.decision != JudgeDecision.PASS
        ):
            raise ValueError(
                "Feedback must be quality-approved and linked to the selected real response"
            )
        if attempt.assessment_work_start_id or (attempt.episode or {}).get("transfer"):
            raise ValueError("Feedback-conditioned drafts use supported practice work only")
        lineage = {
            "kind": "feedback",
            "task_id": task.id,
            "response_version_id": attempt.id,
            "response_digest": output_digest(
                [attempt.answer, attempt.code, attempt.circuit, attempt.episode]
            ),
            "feedback_id": feedback.id,
            "feedback_digest": output_digest(feedback.feedback_content),
        }
        return lineage, {
            "kind": "feedback",
            "prior_response": {
                "answer": attempt.answer,
                "code": attempt.code,
                "circuit": attempt.circuit,
                "episode": attempt.episode,
            },
            "feedback": feedback.feedback_content,
            "instruction": "Address the evidenced gap with a new supported practice example. Do not copy learner work, identify the learner, invent a diagnosis, or claim this is a same-work revision.",
        }
    return None, None


def _task_scope(task, request):
    if (
        task is None
        or task.course_id != request.course_id
        or task.learning_outcome_id != request.learning_outcome_id
    ):
        raise ValueError("Generation context must belong to this course and learning outcome")


def generation_options(session, course_id, outcome_id):
    from types import SimpleNamespace

    from sqlalchemy import select

    from app.schemas.generation_context import GenerationContext

    options = []
    tasks = session.scalars(
        select(LearningTask)
        .where(
            LearningTask.course_id == course_id,
            LearningTask.learning_outcome_id == outcome_id,
        )
        .order_by(LearningTask.position.desc())
        .limit(100)
    ).all()
    for task in tasks:
        revision = TaskReviewService(session).latest_revision(task.id)
        if revision and revision.content_digest == snapshot_digest(task_snapshot(session, task)):
            options.append(
                {
                    "label": f"Variant: {task.title}",
                    "context": GenerationContext(
                        variant_task_id=task.id, variant_revision_id=revision.id
                    ).model_dump(exclude_none=True),
                }
            )
    if not tasks:
        return options
    pairs = session.execute(
        select(SubmissionAttempt, FeedbackRecord)
        .join(
            FeedbackRecord,
            FeedbackRecord.submission_id == SubmissionAttempt.id,
        )
        .where(
            SubmissionAttempt.task_id.in_([task.id for task in tasks]),
            FeedbackRecord.status == FeedbackStatus.ACCEPTED,
            SubmissionAttempt.assessment_work_start_id.is_(None),
        )
        .order_by(SubmissionAttempt.submitted_at.desc())
        .limit(100)
    ).all()
    titles = {task.id: task.title for task in tasks}
    for attempt, feedback in pairs:
        context = GenerationContext(response_version_id=attempt.id, feedback_id=feedback.id)
        try:
            resolve_generation_context(
                session,
                SimpleNamespace(
                    generation_context=context, course_id=course_id, learning_outcome_id=outcome_id
                ),
            )
        except ValueError:
            continue
        options.append(
            {
                "label": f"Feedback: {titles[attempt.task_id]} · attempt {attempt.attempt_number} · {attempt.submitted_at.isoformat()}",
                "context": context.model_dump(exclude_none=True),
            }
        )
    return options
