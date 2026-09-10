"""Read-only stage checks shared by instructional-help services."""

from sqlalchemy import select

from app.models.episode import EpisodeStageStart
from app.models.lms import SubmissionAttempt, SubmissionDraft
from app.models.misconceptions import (
    MisconceptionClosure,
    MisconceptionHypothesis,
    MisconceptionResponse,
)


def active_fresh_check(session, student_id, task_id):
    closed = (
        select(MisconceptionClosure.id)
        .where(
            MisconceptionClosure.hypothesis_id == MisconceptionHypothesis.id,
        )
        .exists()
    )
    revision = (
        select(MisconceptionResponse.id)
        .where(
            MisconceptionResponse.hypothesis_id == MisconceptionHypothesis.id,
            MisconceptionResponse.stage == "REVISION",
        )
        .exists()
    )
    transfer = (
        select(MisconceptionResponse.id)
        .where(
            MisconceptionResponse.hypothesis_id == MisconceptionHypothesis.id,
            MisconceptionResponse.stage == "TRANSFER",
        )
        .exists()
    )
    return session.scalar(
        select(MisconceptionHypothesis.id)
        .where(
            MisconceptionHypothesis.student_id == student_id,
            MisconceptionHypothesis.task_id == task_id,
            revision,
            ~transfer,
            ~closed,
        )
        .limit(1)
    )


def active_assessed_transfer(session, student_id, task_id):
    submitted = (
        select(SubmissionAttempt.id)
        .where(
            SubmissionAttempt.assessment_work_start_id == SubmissionDraft.assessment_work_start_id,
        )
        .exists()
    )
    return session.scalar(
        select(EpisodeStageStart.id)
        .join(
            SubmissionDraft,
            SubmissionDraft.assessment_work_start_id == EpisodeStageStart.assessment_work_start_id,
        )
        .where(
            SubmissionDraft.student_id == student_id, SubmissionDraft.task_id == task_id, ~submitted
        )
        .limit(1)
    )
