"""Exact feedback/context bindings shared by generation, release and persistence."""

from app.schemas.category_review import CategoryReviewRequest, OutputCategory, ReviewEvidence
from app.schemas.feedback import (
    FR17_QUALITY_POLICY_VERSION,
    STRUCTURAL_QUALITY_POLICY_VERSION,
    FeedbackContext,
    FeedbackStructuralReview,
    GeneratedFeedback,
    JudgeEvaluationOutcome,
    quality_policy_passes,
)
from app.services.category_review import require_approved, review_digest
from app.services.feedback.prompt import feedback_context_payload


def feedback_output(feedback: GeneratedFeedback) -> dict:
    # Usage accounting is measured independently; it is not reviewed teaching content.
    return feedback.model_dump(
        mode="json", exclude={"token_usage", "estimated_cost", "usage_complete"}
    )


def context_digest(context: FeedbackContext) -> str:
    return review_digest(context.model_dump(mode="json", exclude={"correlation_id"}))


def feedback_review_request(
    context: FeedbackContext, feedback: GeneratedFeedback
) -> CategoryReviewRequest:
    return CategoryReviewRequest(
        category=OutputCategory.FEEDBACK,
        course_id=context.task.course_id,
        subject_id=context.submission.submission_id,
        output=feedback_output(feedback),
        evidence=(
            ReviewEvidence(
                reference="feedback-context",
                version=context_digest(context),
                kind="observation",
                content=feedback_context_payload(context),
            ),
        ),
        versions={
            "quality_policy": FR17_QUALITY_POLICY_VERSION,
            "context": context_digest(context),
            "task": context.task.task_id,
        },
    )


def structural_review(
    context: FeedbackContext, feedback: GeneratedFeedback, *, assessed: bool, passed: bool
) -> FeedbackStructuralReview:
    return FeedbackStructuralReview(
        scope="approved_assessment_selection" if assessed else "local_template",
        context_digest=context_digest(context),
        output_digest=review_digest(feedback_output(feedback)),
        passed=passed,
        reason=(
            "Exact selection from the frozen approved assessment, verified source quotations, "
            "and authorised hints; no new assessment decision or semantic review."
            if assessed
            else "Exact non-evaluative local teaching template and supplied reference identifiers."
        ),
        limitations=(
            "Structural identity and inherited approved content only. These numeric gates do not "
            "establish a fresh ten-dimension semantic review, empirical validity, or learner ability."
        ),
    )


def require_current_review(
    context: FeedbackContext, feedback: GeneratedFeedback, evaluation: JudgeEvaluationOutcome
) -> None:
    """Legacy judgements may replay, but never authorise a new release."""
    if evaluation.judge_result is None or not quality_policy_passes(
        evaluation.reported_decision,
        evaluation.judge_result,
        evaluation.quality_policy_version,
        evaluation.quality_review,
    ):
        raise ValueError("Feedback fails the numeric or review quality gates")
    receipt = evaluation.quality_review
    if evaluation.quality_policy_version == FR17_QUALITY_POLICY_VERSION:
        if receipt is None or isinstance(receipt, FeedbackStructuralReview):
            raise ValueError("Complete FR17 feedback review required")
        require_approved(receipt, feedback_review_request(context, feedback))
        reviewer = receipt.assessment.reviewer
        if (
            reviewer.kind != "model"
            or reviewer.reference != evaluation.provider
            or reviewer.model_version != evaluation.model
            or reviewer.prompt_version != evaluation.prompt_version
        ):
            raise ValueError("Feedback reviewer provenance differs")
        return
    if evaluation.quality_policy_version == STRUCTURAL_QUALITY_POLICY_VERSION:
        if not isinstance(receipt, FeedbackStructuralReview) or not receipt.passed:
            raise ValueError("Bounded structural receipt required")
        assessed = receipt.scope == "approved_assessment_selection"
        if assessed:
            from app.services.feedback.assessed import MODEL_VERSION, PROMPT_VERSION

            expected_identity = ("local", MODEL_VERSION, PROMPT_VERSION)
        else:
            expected_identity = ("local-deterministic", "quantumlearn-rules-v1", "feedback-v2")
        if (
            (feedback.provider, feedback.model, feedback.prompt_version) != expected_identity
            or receipt.context_digest != context_digest(context)
            or receipt.output_digest != review_digest(feedback_output(feedback))
            or assessed != bool(context.task.assessed or context.assessment_context is not None)
        ):
            raise ValueError("Structural feedback review is stale or outside its scope")
        return
    raise ValueError("A current feedback quality policy is required for new release")
