"""Application service for learner annotations and educator correction reviews."""

from __future__ import annotations

from typing import Protocol

from app.services.learner_model.correction_contracts import (
    EducatorCorrectionReviewCommand,
    LearnerAnnotationCommand,
)
from app.services.learner_model.repository import (
    LearnerAnnotationWriteResult,
    LearnerModelCorrectionHistory,
    LearnerModelCorrectionReviewWriteResult,
    SqlAlchemyLearnerModelRepository,
)
from app.services.learner_model.safety import LearnerModelCorrectionNotFoundError


class CorrectionAccessPolicy(Protocol):
    """Optional caller policy that can narrow, but never widen, repository access."""

    def can_annotate(self, command: LearnerAnnotationCommand) -> bool: ...

    def can_review(self, command: EducatorCorrectionReviewCommand) -> bool: ...

    def can_read_history(
        self,
        *,
        actor_reference: str,
        course_id: str,
        learner_id: str,
        outcome_id: str,
    ) -> bool: ...


class LearnerModelCorrectionService:
    """Coordinate correction commands without exposing target existence across scopes."""

    def __init__(
        self,
        repository: SqlAlchemyLearnerModelRepository,
        access_policy: CorrectionAccessPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._access_policy = access_policy

    def annotate(self, command: LearnerAnnotationCommand) -> LearnerAnnotationWriteResult:
        if self._access_policy is not None and not self._access_policy.can_annotate(command):
            raise LearnerModelCorrectionNotFoundError("correction target is unavailable")
        return self._repository.create_annotation(command)

    def review(
        self,
        command: EducatorCorrectionReviewCommand,
    ) -> LearnerModelCorrectionReviewWriteResult:
        if self._access_policy is not None and not self._access_policy.can_review(command):
            raise LearnerModelCorrectionNotFoundError("correction target is unavailable")
        return self._repository.create_correction_review(command)

    def history(
        self,
        *,
        actor_reference: str,
        course_id: str,
        learner_id: str,
        outcome_id: str,
    ) -> tuple[LearnerModelCorrectionHistory, ...]:
        if self._access_policy is not None and not self._access_policy.can_read_history(
            actor_reference=actor_reference,
            course_id=course_id,
            learner_id=learner_id,
            outcome_id=outcome_id,
        ):
            raise LearnerModelCorrectionNotFoundError("correction history is unavailable")
        return self._repository.correction_history(
            actor_reference=actor_reference,
            course_id=course_id,
            learner_id=learner_id,
            outcome_id=outcome_id,
        )


__all__ = ["CorrectionAccessPolicy", "LearnerModelCorrectionService"]
