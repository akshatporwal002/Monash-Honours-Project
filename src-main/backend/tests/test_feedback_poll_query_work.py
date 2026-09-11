"""Status-only polling must not repeatedly collect unreleased assessment content."""

import asyncio

import pytest

from app.models import WorkflowStage
from app.services.feedback.application import FeedbackWorkflowApplication, workflow_response
from app.services.feedback.contracts import WorkflowClaim
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository
from app.services.feedback.runtime import LmsSubmissionProvider


@pytest.mark.parametrize(
    "stage", [stage for stage in WorkflowStage if stage is not WorkflowStage.COMPLETED]
)
def test_status_only_poll_preserves_response_without_collecting_content(
    db_session, monkeypatch, stage
):
    claim = WorkflowClaim(
        workflow_run_id="22222222-2222-4222-8222-222222222222",
        submission_id="status-only-submission",
        stage=stage,
        should_start=False,
        retryable=stage is WorkflowStage.FAILED,
        failure_category="synthetic-infrastructure-failure"
        if stage is WorkflowStage.FAILED
        else None,
    )

    async def unexpected_content_read(*args, **kwargs):
        pytest.fail("A status-only response must not collect submission or assessment content")

    monkeypatch.setattr(LmsSubmissionProvider, "get_submission", unexpected_content_read)
    application = FeedbackWorkflowApplication(SqlAlchemyFeedbackWorkflowRepository(db_session))
    response = asyncio.run(application.response(claim))
    assert response == workflow_response(claim)
    assert response.feedback is None
    if stage is WorkflowStage.FAILED:
        assert response.error is not None and response.error.retryable
    else:
        assert response.processing_stage is stage and response.error is None
