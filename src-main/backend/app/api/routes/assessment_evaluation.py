"""Reject the retired direct learner evaluation path."""

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies.roles import CurrentStudent

router = APIRouter(prefix="/assessment")


@router.post(
    "/attempts/{assessment_attempt_id}/evaluate",
    status_code=status.HTTP_403_FORBIDDEN,
    response_model=None,
    deprecated=True,
)
def evaluate_assessment_attempt(
    assessment_attempt_id: str,
    _: CurrentStudent,
) -> None:
    """Submission jobs own evaluation; D-01 does not permit learner result visibility."""
    # Deny without resolving the attempt or constructing an evaluator. Existing,
    # missing, foreign, and replayed identifiers receive the same response.
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Direct assessment evaluation is unavailable. Use the task submission workflow.",
    )
