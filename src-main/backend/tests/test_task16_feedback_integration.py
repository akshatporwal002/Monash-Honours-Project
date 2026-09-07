"""Task 16 production composition over a real frozen learning episode."""

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import Session
from support.task16 import setup_task16_episode
from test_task14_lifecycle import complete

from app.models.assessment import AssessmentDecision, CriterionEvaluation
from app.models.lms import SubmissionAttempt
from app.schemas.assessment import AssessmentVersionReference
from app.schemas.feedback import FeedbackPipelineStatus
from app.schemas.lms import SubmissionCreate
from app.services.episode_responses import SqlAlchemyFrozenResponseReader
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository
from app.services.feedback.runtime import build_feedback_pipeline


def test_task16_real_episode_feedback_preserves_response_and_never_scores(db_session: Session):
    lms, student, task, started = setup_task16_episode(db_session)
    payload = complete(lms, student, task, started)
    submitted = lms.submit(
        student,
        task.id,
        SubmissionCreate(**payload.model_dump(), idempotency_key="task16-grounded-feedback"),
    )
    stored = db_session.get(SubmissionAttempt, submitted.id)
    frozen_digest = stored.content_digest
    original_answer = stored.answer
    decisions_before = list(db_session.scalars(select(AssessmentDecision.id)))
    criteria_before = list(db_session.scalars(select(CriterionEvaluation.id)))
    repository = SqlAlchemyFeedbackWorkflowRepository(db_session)
    claim = repository.get_workflow_claim(submitted.id)
    result = asyncio.run(
        build_feedback_pipeline(db_session, repository).run(
            submitted.id, claim.workflow_run_id, execution_token=claim.execution_token
        )
    )
    assert result.status is FeedbackPipelineStatus.VALIDATED
    assert result.source_references
    assert set(result.source_references).issubset(set(task.source_references))
    assert (
        result.validated_feedback.feedback_content["assessed"]["response_version_id"]
        == submitted.id
    )
    replay = asyncio.run(build_feedback_pipeline(db_session, repository).run(submitted.id))
    assert replay.idempotent_replay
    assert replay.feedback_id == result.feedback_id
    assert replay.workflow_run_id == result.workflow_run_id
    assert replay.source_references == result.source_references
    assert stored.content_digest == frozen_digest
    assert stored.answer == original_answer == payload.answer
    assert stored.score is None
    reference = AssessmentVersionReference.model_validate(
        result.validated_feedback.feedback_content["assessed"]["assessment"]
    )
    frozen = SqlAlchemyFrozenResponseReader(db_session).read(assessment=reference)
    assert frozen.reference.content_digest == frozen_digest
    assert list(db_session.scalars(select(AssessmentDecision.id))) == decisions_before
    assert list(db_session.scalars(select(CriterionEvaluation.id))) == criteria_before
