"""Read preserved teaching against the learner, task and response time that used it."""

from datetime import UTC

from sqlalchemy import select

from app.domain.platform_enums import EvidenceType
from app.models.assessment_work import AssessmentWorkStart
from app.models.episode import EpisodeStageStart
from app.models.learning_evidence import LearningEvidence
from app.models.misconceptions import MisconceptionHypothesis, MisconceptionResponse
from app.models.persistence import LearningTask


def teaching_observations(
    session, work_id, before, *, task_id=None, student_id=None, stage_id=None
):
    query = (
        select(LearningEvidence)
        .join(
            MisconceptionResponse,
            MisconceptionResponse.id == LearningEvidence.source_interaction_id,
        )
        .join(
            MisconceptionHypothesis,
            MisconceptionHypothesis.id == MisconceptionResponse.hypothesis_id,
        )
        .where(
            LearningEvidence.evidence_type == EvidenceType.SCAFFOLD,
            LearningEvidence.course_id == MisconceptionHypothesis.course_id,
            LearningEvidence.outcome_id == MisconceptionHypothesis.outcome_id,
            LearningEvidence.learner_id == MisconceptionHypothesis.student_id,
            LearningEvidence.occurred_at <= before,
        )
    )
    if work_id:
        work = session.get(AssessmentWorkStart, work_id)
        if work is None:
            return []
        query = query.where(
            LearningEvidence.activity_id == work.id,
            MisconceptionHypothesis.task_id == work.task_id,
            MisconceptionHypothesis.student_id == work.student_id,
            MisconceptionHypothesis.course_id == work.course_id,
        )
    else:
        task = session.get(LearningTask, task_id) if task_id else None
        if task is None or student_id is None:
            return []
        query = query.where(
            LearningEvidence.activity_id == task.id,
            MisconceptionHypothesis.task_id == task.id,
            MisconceptionHypothesis.student_id == student_id,
            MisconceptionHypothesis.course_id == task.course_id,
            MisconceptionHypothesis.outcome_id == task.learning_outcome_id,
        )
    if stage_id:
        stage = session.get(EpisodeStageStart, stage_id)
        if stage is None or stage.assessment_work_start_id != work_id:
            return []
        query = query.where(LearningEvidence.occurred_at >= stage.created_at)
    return list(session.scalars(query.order_by(LearningEvidence.occurred_at, LearningEvidence.id)))


def response_teaching(session, response):
    from app.schemas.episode import RecordedTeachingRead

    stage_id = ((response.episode or {}).get("transfer") or {}).get("stage_start_id")
    stage = session.get(EpisodeStageStart, stage_id) if stage_id else None
    result = []
    for evidence in teaching_observations(
        session,
        response.assessment_work_start_id,
        response.submitted_at,
        task_id=response.task_id,
        student_id=response.student_id,
    ):
        saved = session.get(MisconceptionResponse, evidence.source_interaction_id)
        hypothesis = session.get(MisconceptionHypothesis, saved.hypothesis_id)
        after_transfer = stage is not None and _utc(evidence.occurred_at) >= _utc(stage.created_at)
        result.append(
            RecordedTeachingRead(
                evidence_id=evidence.id,
                hypothesis_id=hypothesis.id,
                instructional_support_level=evidence.instructional_support_level,
                explanation=hypothesis.payload["explanation"],
                occurred_at=evidence.occurred_at,
                during_transfer=after_transfer,
            )
        )
    return tuple(result)


def teaching_result_issue(records):
    if any(item.instructional_support_level >= 4 or item.during_transfer for item in records):
        return "This item received answer-revealing help or help after its fresh stage began. Preserve it as learning evidence and use a fresh approved task for a formal result."
    return None


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
