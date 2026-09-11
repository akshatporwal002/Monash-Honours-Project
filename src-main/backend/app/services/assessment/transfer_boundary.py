"""Shared learner/course boundary for unfinished unaided transfer work."""

from sqlalchemy import exists, select

from app.models.episode import EpisodeStageStart
from app.models.lms import SubmissionAttempt
from app.models.persistence import LearningTask


def active_course_transfer(session, student_id, course_id):
    """A started transfer stays active until its exact work has a submission."""
    return (
        session.scalar(
            select(EpisodeStageStart.id)
            .where(
                EpisodeStageStart.student_id == student_id,
                EpisodeStageStart.task_id.in_(
                    select(LearningTask.id).where(LearningTask.course_id == course_id)
                ),
                ~exists(
                    select(SubmissionAttempt.id).where(
                        SubmissionAttempt.assessment_work_start_id
                        == EpisodeStageStart.assessment_work_start_id
                    )
                ),
            )
            .limit(1)
        )
        is not None
    )
