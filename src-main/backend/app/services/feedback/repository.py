from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models import (
    FeedbackRecord,
    FeedbackStatus,
    JudgeEvaluation,
    JudgeEvaluationStatus,
    WorkflowOutcome,
    WorkflowRun,
    WorkflowStage,
)
from app.schemas.feedback import (
    FeedbackPipelineResult,
    FeedbackPipelineStatus,
    GeneratedFeedback,
    JudgeResult,
    TokenUsage,
)
from app.services.feedback.contracts import PipelinePersistenceRequest
from app.services.feedback.errors import PipelinePersistenceError


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SqlAlchemyFeedbackWorkflowRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_submission(self, submission_id: str) -> FeedbackPipelineResult | None:
        statement = (
            select(WorkflowRun)
            .where(WorkflowRun.submission_id == submission_id)
            .options(
                selectinload(WorkflowRun.feedback_records).selectinload(
                    FeedbackRecord.judge_evaluation
                )
            )
        )
        try:
            workflow = self._session.scalar(statement)
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PipelinePersistenceError(submission_id) from error

        if workflow is None:
            return None
        if not workflow.feedback_records:
            raise PipelinePersistenceError(submission_id)

        feedback = max(
            workflow.feedback_records,
            key=lambda record: record.generation_attempt or 0,
        )
        judge = feedback.judge_evaluation
        if judge is None or judge.decision is None:
            raise PipelinePersistenceError(submission_id)
        if workflow.completed_at is None:
            raise PipelinePersistenceError(submission_id)

        judge_result = JudgeResult(
            decision=judge.decision,
            correctness_score=judge.correctness_score,
            relevance_score=judge.relevance_score,
            grounding_score=judge.grounding_score,
            actionability_score=judge.actionability_score,
            safety_score=judge.safety_score,
            reason=judge.reason,
            unsupported_claims=judge.unsupported_claims,
            regeneration_instructions=judge.regeneration_instructions,
        )
        token_usage = TokenUsage(
            input_tokens=feedback.input_tokens,
            output_tokens=feedback.output_tokens,
            total_tokens=feedback.total_tokens,
        )
        generated_feedback = None
        if feedback.status is FeedbackStatus.ACCEPTED:
            if (
                feedback.provider is None
                or feedback.model is None
                or feedback.prompt_version is None
            ):
                raise PipelinePersistenceError(submission_id)
            generated_feedback = GeneratedFeedback(
                feedback_content=feedback.feedback_content,
                provider=feedback.provider,
                model=feedback.model,
                prompt_version=feedback.prompt_version,
                source_references=feedback.source_references,
                simulation_references=feedback.simulation_references,
                token_usage=token_usage,
                estimated_cost=feedback.estimated_cost,
            )
            pipeline_status = FeedbackPipelineStatus.VALIDATED
        elif feedback.status is FeedbackStatus.REJECTED:
            pipeline_status = FeedbackPipelineStatus.REJECTED
        else:
            raise PipelinePersistenceError(submission_id)

        latency = _as_utc(workflow.completed_at) - _as_utc(workflow.started_at)
        return FeedbackPipelineResult(
            workflow_run_id=workflow.id,
            feedback_id=feedback.id,
            submission_id=workflow.submission_id,
            status=pipeline_status,
            validated_feedback=generated_feedback,
            judge_result=judge_result,
            regeneration_count=workflow.regeneration_count,
            fallback_used=False,
            latency_ms=max(0, int(latency.total_seconds() * 1000)),
            token_usage=token_usage,
            estimated_cost=feedback.estimated_cost,
            source_references=feedback.source_references,
            idempotent_replay=True,
        )

    def save_result(self, request: PipelinePersistenceRequest) -> FeedbackPipelineResult:
        result = request.result
        accepted = result.status is FeedbackPipelineStatus.VALIDATED
        workflow = WorkflowRun(
            id=result.workflow_run_id,
            submission_id=result.submission_id,
            current_stage=WorkflowStage.COMPLETED if accepted else WorkflowStage.FAILED,
            regeneration_count=0,
            final_outcome=(
                WorkflowOutcome.FIRST_PASS if accepted else WorkflowOutcome.WORKFLOW_FAILED
            ),
            started_at=request.started_at,
            completed_at=request.completed_at,
        )
        feedback = FeedbackRecord(
            id=result.feedback_id,
            submission_id=result.submission_id,
            workflow_run_id=result.workflow_run_id,
            feedback_content=request.generated_feedback.feedback_content,
            status=FeedbackStatus.ACCEPTED if accepted else FeedbackStatus.REJECTED,
            generation_attempt=1,
            provider=request.generated_feedback.provider,
            model=request.generated_feedback.model,
            prompt_version=request.generated_feedback.prompt_version,
            source_references=request.generated_feedback.source_references,
            simulation_references=request.generated_feedback.simulation_references,
            input_tokens=request.generated_feedback.token_usage.input_tokens,
            output_tokens=request.generated_feedback.token_usage.output_tokens,
            total_tokens=request.generated_feedback.token_usage.total_tokens,
            estimated_cost=request.generated_feedback.estimated_cost,
        )
        judge_result = result.judge_result
        judge = JudgeEvaluation(
            feedback_id=result.feedback_id,
            evaluation_status=JudgeEvaluationStatus.VALID,
            decision=judge_result.decision,
            correctness_score=judge_result.correctness_score,
            relevance_score=judge_result.relevance_score,
            grounding_score=judge_result.grounding_score,
            actionability_score=judge_result.actionability_score,
            safety_score=judge_result.safety_score,
            reason=judge_result.reason,
            unsupported_claims=judge_result.unsupported_claims,
            regeneration_instructions=judge_result.regeneration_instructions,
        )
        self._session.add_all([workflow, feedback, judge])

        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            existing = self.get_by_submission(result.submission_id)
            if existing is not None:
                return existing
            raise PipelinePersistenceError(result.submission_id) from error
        except SQLAlchemyError as error:
            self._session.rollback()
            raise PipelinePersistenceError(result.submission_id) from error

        return result
