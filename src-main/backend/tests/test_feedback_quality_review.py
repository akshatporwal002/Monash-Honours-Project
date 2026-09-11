"""Live FR17 gates, exact bindings and append-only receipt persistence."""

import json

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from test_feedback_pipeline import build_pipeline, judge_outcome
from test_quality_judge import assessment_payload, context, feedback, output, response, run

from app.models import JudgeDecision, JudgeEvaluation, JudgeEvaluationStatus
from app.schemas.category_review import ReviewDimension
from app.schemas.feedback import FeedbackPipelineStatus
from app.services.feedback import LlmFeedbackJudge, RecordingStructuredLlmClient
from app.services.feedback.application import workflow_response
from app.services.feedback.contracts import WorkflowClaim
from app.services.feedback.quality_review import require_current_review
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository
from app.services.local_ai import LocalFeedbackGenerator, LocalFeedbackJudge


@pytest.mark.parametrize("missing", ["assessment", "dimension"])
def test_missing_complete_review_cannot_pass(missing):
    candidate = output()
    if missing == "assessment":
        candidate.pop("category_assessment")
    else:
        candidate["category_assessment"]["findings"].pop()
    evaluation = run(
        LlmFeedbackJudge(RecordingStructuredLlmClient(response(candidate))).evaluate(
            context(), feedback()
        )
    )
    assert evaluation.evaluation_status is JudgeEvaluationStatus.MALFORMED
    assert evaluation.quality_review.decision.value == "REJECTED"
    assert len(evaluation.quality_review.unresolved_dimensions) == 10


@pytest.mark.parametrize("dimension", list(ReviewDimension))
def test_each_unverified_dimension_blocks_an_otherwise_numeric_pass(dimension):
    assessment = assessment_payload()
    for finding in assessment["findings"]:
        if finding["dimension"] == dimension.value:
            finding["outcome"] = "UNVERIFIED"
    evaluation = run(
        LlmFeedbackJudge(
            RecordingStructuredLlmClient(response(output(category_assessment=assessment)))
        ).evaluate(context(), feedback())
    )
    assert evaluation.reported_decision is JudgeDecision.PASS
    assert evaluation.judge_result.correctness_score == 100
    assert evaluation.judge_result.decision is JudgeDecision.FAIL
    assert evaluation.quality_review.unresolved_dimensions == (dimension,)
    assert dimension.value in " ".join(evaluation.judge_result.regeneration_instructions)


@pytest.mark.parametrize("change", ["output", "source", "learner", "answer", "model"])
def test_review_is_bound_to_exact_candidate_and_private_context(change):
    supplied, candidate = context(), feedback()
    evaluation = run(
        LlmFeedbackJudge(RecordingStructuredLlmClient(response(output()))).evaluate(
            supplied, candidate
        )
    )
    require_current_review(supplied, candidate, evaluation)
    assert evaluation.quality_review.assessment.reviewer.reference == "judge-provider"
    if change == "output":
        candidate = candidate.model_copy(update={"feedback_content": {"summary": "Changed."}})
    elif change == "model":
        candidate = candidate.model_copy(update={"model": "different-model"})
    elif change == "source":
        supplied = supplied.model_copy(
            update={
                "retrieval_context": [
                    supplied.retrieval_context[0].model_copy(
                        update={"chunk_text": "Changed evidence."}
                    )
                ]
            }
        )
    else:
        field = "student_id" if change == "learner" else "submitted_answer"
        supplied = supplied.model_copy(
            update={
                "submission": supplied.submission.model_copy(
                    update={field: "changed-private-value"}
                )
            }
        )
    with pytest.raises(ValueError):
        require_current_review(supplied, candidate, evaluation)
    stale = run(
        LlmFeedbackJudge(RecordingStructuredLlmClient(response(output()))).evaluate(
            supplied, candidate
        )
    )
    assert stale.judge_result.decision is JudgeDecision.FAIL
    assert stale.quality_review.reason == "review_invalid_or_failed"


class ReviewingClient:
    def __init__(self, *, unverified=False):
        self.calls = 0
        self.unverified = unverified

    async def generate_structured(self, request):
        self.calls += 1
        candidate = output()
        candidate["category_assessment"]["request_digest"] = json.loads(request.user_prompt)[
            "category_review"
        ]["request_digest"]
        if self.unverified:
            candidate["category_assessment"]["findings"][0]["outcome"] = "UNVERIFIED"
        return response(candidate)


def reviewed_pipeline(db_session, *, unverified=False):
    pipeline, _, _, generator, _ = build_pipeline(db_session)
    client = ReviewingClient(unverified=unverified)
    pipeline._judge = LlmFeedbackJudge(client)
    return pipeline, generator, client


def test_receipt_persists_with_feedback_and_replays_without_leaking_to_learner(db_session):
    pipeline, generator, client = reviewed_pipeline(db_session)
    result = run(pipeline.run("submission-1"))
    assert result.status is FeedbackPipelineStatus.VALIDATED
    row = db_session.scalar(select(JudgeEvaluation))
    assert row.feedback_id == result.feedback_id
    from app.schemas.persistence import JudgeEvaluationRead

    assert JudgeEvaluationRead.model_validate(row).quality_review is not None
    receipt = result.judge_evaluations[-1].quality_review
    assert row.quality_review == receipt.model_dump(mode="json")
    assert receipt.subject_id == result.submission_id
    assert receipt.course_id == generator.contexts[0].task.course_id
    replay = run(pipeline.run("submission-1"))
    assert replay.judge_evaluations[-1].quality_review == receipt
    assert client.calls == 1
    from app.models import WorkflowStage

    view = workflow_response(
        WorkflowClaim(
            workflow_run_id=result.workflow_run_id,
            submission_id=result.submission_id,
            stage=WorkflowStage.COMPLETED,
            should_start=False,
            terminal_result=replay,
        )
    ).model_dump_json()
    assert "quality_review" not in view
    assert "findings" not in view
    assert receipt.request_digest not in view


def test_unverified_review_retains_two_receipts_then_safe_fallback(db_session):
    pipeline, generator, client = reviewed_pipeline(db_session, unverified=True)
    result = run(pipeline.run("submission-1"))
    assert result.status is FeedbackPipelineStatus.FALLBACK
    assert result.regeneration_count == 1
    assert client.calls == generator.call_count == 2
    rows = db_session.scalars(select(JudgeEvaluation)).all()
    assert len(rows) == 2
    assert all(row.quality_review["decision"] == "REJECTED" for row in rows)
    assert all(row.decision is JudgeDecision.FAIL for row in rows)


@pytest.mark.parametrize("table", ["judge_evaluations", "feedback_records"])
@pytest.mark.parametrize("mutation", ["update", "delete", "replace"])
def test_reviewed_output_and_receipt_are_immutable_in_sql(db_session, table, mutation):
    pipeline, _, _ = reviewed_pipeline(db_session)
    run(pipeline.run("submission-1"))
    sql = {
        "update": f"UPDATE {table} SET id=id",
        "delete": f"DELETE FROM {table}",
        "replace": f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}",
    }[mutation]
    with pytest.raises(IntegrityError, match="history is immutable"):
        db_session.execute(text(sql))
    db_session.rollback()
    assert SqlAlchemyFeedbackWorkflowRepository(db_session).get_by_submission("submission-1")


def test_no_receipt_uses_sql_null_and_cannot_gain_forged_review_by_update(db_session):
    pipeline, _, _, _, _ = build_pipeline(
        db_session,
        judge_error_on_calls={1: RuntimeError("unavailable"), 2: RuntimeError("unavailable")},
    )
    run(pipeline.run("submission-1"))
    assert (
        db_session.scalar(
            text("SELECT count(*) FROM judge_evaluations WHERE quality_review IS NULL")
        )
        == 2
    )
    with pytest.raises(IntegrityError, match="history is immutable"):
        db_session.execute(text("UPDATE judge_evaluations SET quality_review='{}'"))
    db_session.rollback()


@pytest.mark.parametrize("status", ["accepted", "safe_fallback"])
def test_replacement_using_different_id_cannot_destroy_reviewed_history(db_session, status):
    from uuid import uuid4

    pipeline, _, _ = reviewed_pipeline(db_session)
    result = run(pipeline.run("submission-1"))
    with pytest.raises(IntegrityError, match="Reviewed feedback history is immutable"):
        db_session.execute(
            text(
                "INSERT OR REPLACE INTO feedback_records "
                "(id,submission_id,workflow_run_id,feedback_content,status,generation_attempt,"
                "provider,model,prompt_version) VALUES (:id,:submission,:workflow,'{}',:status,"
                "1,'replacement','replacement','replacement')"
            ),
            {
                "id": str(uuid4()),
                "submission": result.submission_id,
                "workflow": result.workflow_run_id,
                "status": status,
            },
        )
    db_session.rollback()


def test_legacy_v1_remains_readable_but_cannot_authorise_new_release(db_session):
    legacy = judge_outcome(JudgeDecision.PASS, input_tokens=0, output_tokens=0, cost="0")
    # A durable pre-migration row has no receipt; read compatibility is intentional.
    row = JudgeEvaluation(
        evaluation_status=legacy.evaluation_status,
        reported_decision=legacy.reported_decision,
        decision=JudgeDecision.PASS,
        correctness_score=90,
        relevance_score=91,
        grounding_score=92,
        actionability_score=93,
        safety_score=100,
        reason=legacy.reason,
        unsupported_claims=[],
        regeneration_instructions=[],
        provider=legacy.provider,
        model=legacy.model,
        prompt_version=legacy.prompt_version,
        quality_policy_version="quality-policy-v1",
        quality_review=None,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        estimated_cost=legacy.estimated_cost,
        usage_complete=True,
    )
    stored = SqlAlchemyFeedbackWorkflowRepository._judge_outcome(row, "submission-1")
    assert stored.judge_result.decision is JudgeDecision.PASS
    with pytest.raises(ValueError, match="current feedback quality policy"):
        require_current_review(context(), feedback(), stored)

    class LegacyJudge:
        async def evaluate(self, context, feedback):
            return legacy

    pipeline, _, _, generator, _ = build_pipeline(db_session)
    pipeline._judge = LegacyJudge()
    result = run(pipeline.run("submission-1"))
    assert result.status is FeedbackPipelineStatus.FALLBACK
    assert generator.call_count == 2


def test_local_template_has_honest_structural_receipt_and_rejects_extra_claims():
    supplied = context()
    candidate = run(LocalFeedbackGenerator().generate(supplied))
    evaluation = run(LocalFeedbackJudge().evaluate(supplied, candidate))
    require_current_review(supplied, candidate, evaluation)
    assert evaluation.quality_review.scope == "local_template"
    assert "not a semantic review" in evaluation.reason
    assert not hasattr(evaluation.quality_review, "assessment")
    changed = candidate.model_copy(
        update={
            "feedback_content": {**candidate.feedback_content, "summary": "Your answer is correct."}
        }
    )
    rejected = run(LocalFeedbackJudge().evaluate(supplied, changed))
    assert rejected.judge_result.decision is JudgeDecision.FAIL
    assert rejected.quality_review.passed is False


def test_new_persistence_rechecks_receipt_and_context_even_if_pipeline_is_bypassed(db_session):
    from dataclasses import replace

    from app.services.feedback.errors import PipelinePersistenceError

    class CaptureRepository(SqlAlchemyFeedbackWorkflowRepository):
        def save_result(self, request):
            self.request = request
            return super().save_result(request)

    repository = CaptureRepository(db_session)
    pipeline, _, _, _, _ = build_pipeline(db_session, repository=repository)
    run(pipeline.run("submission-1"))
    original = repository.request
    legacy = original.attempts[-1].judge_evaluation.model_copy(
        update={
            "quality_policy_version": "quality-policy-v1",
            "quality_review": None,
        }
    )
    forged = replace(
        original,
        result=original.result.model_copy(update={"judge_evaluations": [legacy]}),
        attempts=(replace(original.attempts[-1], judge_evaluation=legacy),),
    )
    with pytest.raises(PipelinePersistenceError):
        repository._validate_persistence_request(forged)
    invalid_scores = original.attempts[-1].judge_evaluation.model_copy(
        update={
            "judge_result": original.attempts[-1].judge_evaluation.judge_result.model_copy(
                update={"safety_score": 99}
            )
        }
    )
    with pytest.raises(PipelinePersistenceError):
        repository._validate_persistence_request(
            replace(
                original,
                result=original.result.model_copy(update={"judge_evaluations": [invalid_scores]}),
                attempts=(replace(original.attempts[-1], judge_evaluation=invalid_scores),),
            )
        )
    changed_context = original.feedback_context.model_copy(
        update={
            "submission": original.feedback_context.submission.model_copy(
                update={"submitted_answer": "Changed after the judge approved the candidate."}
            )
        }
    )
    with pytest.raises(PipelinePersistenceError):
        repository._validate_persistence_request(
            replace(original, feedback_context=changed_context)
        )
