"""Durable Task 16 regeneration and fixed fallback through the real pipeline."""

import asyncio
from copy import deepcopy

import pytest
from sqlalchemy import select
from test_task16_grounding import NoDelegate
from test_task16_grounding import grounded_context as grounded_context

from app.models import FeedbackRecord
from app.models.lms import SubmissionAttempt
from app.schemas.feedback import FeedbackPipelineStatus
from app.services.feedback.assessed import AssessedFeedbackGenerator, AssessedFeedbackJudge
from app.services.feedback.fallback import ASSESSED_SAFE_FALLBACK_CONTENT
from app.services.feedback.pipeline import FeedbackPipeline
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository
from app.services.feedback.runtime import LmsSubmissionProvider


class PreservedContextCollector:
    def __init__(self, context):
        self.context = context

    async def collect(self, submission, correlation_id):
        assert submission.submission_id == self.context.submission.submission_id
        return self.context.model_copy(update={"correlation_id": correlation_id})


class TamperedCandidates:
    def __init__(self, *, repair=False, provider_error=False):
        self.real = AssessedFeedbackGenerator(NoDelegate())
        self.calls = []
        self.repair = repair
        self.provider_error = provider_error

    async def generate(self, context, regeneration=None):
        self.calls.append(regeneration)
        if self.provider_error:
            raise RuntimeError("Synthetic provider failure")
        good = await self.real.generate(context, regeneration)
        if regeneration is not None and self.repair:
            return good
        content = deepcopy(good.feedback_content)
        content["assessed"]["source_claims"][0]["claim"] = "Unsupported factual claim"
        return good.model_copy(update={"feedback_content": content})


def run_pipeline(session, context, generator=None):
    repository = SqlAlchemyFeedbackWorkflowRepository(session)
    claim = repository.get_workflow_claim(context.submission.submission_id)
    pipeline = FeedbackPipeline(
        LmsSubmissionProvider(session),
        PreservedContextCollector(context),
        generator or AssessedFeedbackGenerator(NoDelegate()),
        AssessedFeedbackJudge(NoDelegate()),
        repository,
    )
    result = asyncio.run(
        pipeline.run(
            context.submission.submission_id,
            claim.workflow_run_id if claim else None,
            execution_token=claim.execution_token if claim else None,
        )
    )
    return result, repository


@pytest.mark.parametrize("repair", [False, True])
def test_one_regeneration_preserves_rejections_versions_and_submission(
    db_session, grounded_context, repair
):
    response = db_session.get(SubmissionAttempt, grounded_context.submission.submission_id)
    original = (
        response.answer,
        response.code,
        response.circuit,
        response.content_digest,
        response.score,
    )
    generator = TamperedCandidates(repair=repair)
    result, repository = run_pipeline(db_session, grounded_context, generator)
    assert len(generator.calls) == 2
    assert generator.calls[0] is None
    assert generator.calls[1].judge_evaluation.reason
    assert result.regeneration_count == 1
    assert len(result.judge_evaluations) == 2
    assert all(
        item.reason and item.model and item.prompt_version for item in result.judge_evaluations
    )
    assert result.status is (
        FeedbackPipelineStatus.VALIDATED if repair else FeedbackPipelineStatus.FALLBACK
    )
    if not repair:
        assert result.safe_fallback.feedback_content == ASSESSED_SAFE_FALLBACK_CONTENT
        assert all(item.judge_result.unsupported_claims for item in result.judge_evaluations)
    db_session.expire_all()
    recovered = repository.get_by_submission(response.id)
    assert recovered.judge_evaluations == result.judge_evaluations
    assert recovered.feedback_id == result.feedback_id
    records = list(
        db_session.scalars(
            select(FeedbackRecord).where(FeedbackRecord.submission_id == response.id)
        )
    )
    assert len(records) == (2 if repair else 3)
    replay, _ = run_pipeline(db_session, grounded_context, generator)
    assert replay.idempotent_replay
    assert len(generator.calls) == 2
    assert (
        response.answer,
        response.code,
        response.circuit,
        response.content_digest,
        response.score,
    ) == original


def test_provider_failure_uses_durable_assessed_fallback(db_session, grounded_context):
    generator = TamperedCandidates(provider_error=True)
    result, repository = run_pipeline(db_session, grounded_context, generator)
    assert result.status is FeedbackPipelineStatus.FALLBACK
    assert result.safe_fallback.feedback_content == ASSESSED_SAFE_FALLBACK_CONTENT
    assert len(generator.calls) == 2
    assert result.regeneration_count == 1
    assert len(result.judge_evaluations) == 2
    assert all(item.reason for item in result.judge_evaluations)
    assert repository.get_by_submission(result.submission_id).safe_fallback == result.safe_fallback
