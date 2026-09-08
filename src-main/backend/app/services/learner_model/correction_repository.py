"""Transactional, non-enumerating persistence for learner-model corrections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.platform_enums import CorrectionTargetKind
from app.models.learner_model import (
    LearnerModelAnnotation,
    LearnerModelCorrectionReview,
    LearnerModelCorrectionSnapshotLink,
    LearnerModelEvidenceLink,
    LearnerModelSnapshot,
    LearnerOutcomeEstimate,
)
from app.models.learning_evidence import LearningEvidence
from app.models.lms import Course, Enrollment, EnrollmentStatus
from app.models.user import User, UserRole
from app.services.learner_model.correction_contracts import (
    CorrectionTarget,
    EducatorCorrectionReviewCommand,
    EducatorCorrectionReviewPayload,
    LearnerAnnotationCommand,
    LearnerAnnotationPayload,
)
from app.services.learner_model.safety import (
    LearnerModelConflictError,
    LearnerModelCorrectionNotFoundError,
    LearnerModelPersistenceError,
    LearnerModelStaleReviewError,
)


@dataclass(frozen=True, slots=True)
class AnnotationWrite:
    annotation: LearnerAnnotationPayload
    created: bool


@dataclass(frozen=True, slots=True)
class ReviewWrite:
    review: EducatorCorrectionReviewPayload
    created: bool


@dataclass(frozen=True, slots=True)
class CorrectionHistory:
    annotation: LearnerAnnotationPayload
    reviews: tuple[EducatorCorrectionReviewPayload, ...]


@dataclass(frozen=True, slots=True)
class AcceptedCorrectionTarget:
    review_id: str
    dimension: str | None


class SqlAlchemyLearnerModelCorrectionRepository:
    """Own correction scope, replay, ancestry and protected-history persistence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def annotate(self, command: LearnerAnnotationCommand) -> AnnotationWrite:
        learner_id = _learner_id(command.learner_id)
        try:
            self._require_learner_scope(command, learner_id)
            existing = self._annotation_by_key(
                command.course_id, learner_id, command.idempotency_key
            )
            if existing is not None:
                return self._annotation_replay(existing, command, learner_id)
            self._require_target(command.target, command.course_id, learner_id, command.outcome_id)
            row = LearnerModelAnnotation(
                id=command.annotation_id,
                course_id=command.course_id,
                learner_id=learner_id,
                outcome_id=command.outcome_id,
                target_kind=command.target.target_kind,
                evidence_id=command.target.evidence_id,
                estimate_id=command.target.estimate_id,
                action=command.action,
                note=command.note,
                schema_version="learnlens.learner-annotation.v1",
                record_version=command.record_version,
                actor_reference=command.actor_reference,
                correlation_id=command.correlation_id,
                idempotency_key=command.idempotency_key,
                occurred_at=_utc(command.occurred_at),
            )
            self._session.add(row)
            self._session.commit()
            return AnnotationWrite(_annotation_payload(row), True)
        except (LearnerModelCorrectionNotFoundError, LearnerModelConflictError):
            self._session.rollback()
            raise
        except IntegrityError:
            self._session.rollback()
            existing = self._annotation_by_key(
                command.course_id, learner_id, command.idempotency_key
            )
            if existing is not None:
                return self._annotation_replay(existing, command, learner_id)
            raise LearnerModelConflictError(
                "learner annotation conflicts with immutable history"
            ) from None
        except SQLAlchemyError:
            self._session.rollback()
            raise LearnerModelPersistenceError("learner annotation could not be stored") from None

    def review(self, command: EducatorCorrectionReviewCommand) -> ReviewWrite:
        learner_id = _learner_id(command.learner_id)
        try:
            self._require_educator_scope(command.course_id, command.actor_reference)
            existing = self._review_by_key(command.course_id, learner_id, command.idempotency_key)
            if existing is not None:
                return self._review_replay(existing, command, learner_id)
            annotation = self._annotation(command, learner_id)
            latest = self._latest_review(annotation.id)
            latest_version = 0 if latest is None else latest.review_version
            if latest_version != command.expected_latest_review_version:
                raise LearnerModelStaleReviewError(
                    "correction review is based on a stale latest-review version"
                )
            row = LearnerModelCorrectionReview(
                id=command.review_id,
                annotation_id=annotation.id,
                course_id=command.course_id,
                learner_id=learner_id,
                outcome_id=command.outcome_id,
                prior_review_id=None if latest is None else latest.id,
                review_version=command.review_version,
                expected_latest_review_version=command.expected_latest_review_version,
                action=command.action,
                reason=command.reason,
                schema_version="learnlens.educator-correction-review.v1",
                actor_reference=command.actor_reference,
                correlation_id=command.correlation_id,
                idempotency_key=command.idempotency_key,
                occurred_at=_utc(command.occurred_at),
            )
            self._session.add(row)
            self._session.commit()
            return ReviewWrite(_review_payload(row, _target(annotation)), True)
        except (LearnerModelCorrectionNotFoundError, LearnerModelConflictError):
            self._session.rollback()
            raise
        except IntegrityError:
            self._session.rollback()
            existing = self._review_by_key(command.course_id, learner_id, command.idempotency_key)
            if existing is not None:
                return self._review_replay(existing, command, learner_id)
            raise LearnerModelStaleReviewError(
                "correction review is based on a stale latest-review version"
            ) from None
        except SQLAlchemyError:
            self._session.rollback()
            raise LearnerModelPersistenceError(
                "educator correction review could not be stored"
            ) from None

    def history(
        self, *, actor_reference: str, course_id: str, learner_id: str, outcome_id: str
    ) -> tuple[CorrectionHistory, ...]:
        learner_key = _learner_id(learner_id)
        try:
            self._require_history_scope(actor_reference, course_id, learner_key)
            annotations = self._session.scalars(
                select(LearnerModelAnnotation)
                .where(
                    LearnerModelAnnotation.course_id == course_id,
                    LearnerModelAnnotation.learner_id == learner_key,
                    LearnerModelAnnotation.outcome_id == outcome_id,
                )
                .order_by(
                    LearnerModelAnnotation.occurred_at,
                    LearnerModelAnnotation.created_at,
                    LearnerModelAnnotation.id,
                )
            ).all()
            reviews = (
                self._session.scalars(
                    select(LearnerModelCorrectionReview)
                    .where(
                        LearnerModelCorrectionReview.annotation_id.in_(
                            [row.id for row in annotations]
                        )
                    )
                    .order_by(
                        LearnerModelCorrectionReview.annotation_id,
                        LearnerModelCorrectionReview.review_version,
                        LearnerModelCorrectionReview.occurred_at,
                        LearnerModelCorrectionReview.id,
                    )
                ).all()
                if annotations
                else []
            )
        except LearnerModelCorrectionNotFoundError:
            raise
        except SQLAlchemyError:
            self._session.rollback()
            raise LearnerModelPersistenceError(
                "learner-model correction history could not be read"
            ) from None
        by_annotation: dict[str, list[LearnerModelCorrectionReview]] = {}
        for review in reviews:
            by_annotation.setdefault(review.annotation_id, []).append(review)
        return tuple(
            CorrectionHistory(
                _annotation_payload(row),
                tuple(
                    _review_payload(review, _target(row))
                    for review in by_annotation.get(row.id, ())
                ),
            )
            for row in annotations
        )

    def accepted_targets(
        self,
        *,
        course_id: str,
        learner_id: str,
        outcome_id: str,
        evidence_ids: tuple[str, ...],
        snapshot_id: str | None,
    ) -> tuple[AcceptedCorrectionTarget, ...]:
        """Resolve latest accepted decisions applicable to a proposed successor."""
        learner_key = _learner_id(learner_id)
        estimates = (
            self._session.scalars(
                select(LearnerOutcomeEstimate).where(
                    LearnerOutcomeEstimate.snapshot_id == snapshot_id
                )
            ).all()
            if snapshot_id
            else []
        )
        # An annotation may identify either a previous estimate or one of its
        # immutable evidence links.  Both target forms need to carry the
        # accepted review into the corresponding successor dimension.
        dimensions = {estimate.id: estimate.dimension.value for estimate in estimates}
        evidence_dimensions: dict[str, set[str]] = {}
        if estimates:
            for evidence_id, dimension in self._session.execute(
                select(LearnerModelEvidenceLink.evidence_id, LearnerOutcomeEstimate.dimension)
                .join(
                    LearnerOutcomeEstimate,
                    LearnerModelEvidenceLink.estimate_id == LearnerOutcomeEstimate.id,
                )
                .where(LearnerOutcomeEstimate.snapshot_id == snapshot_id)
            ):
                evidence_dimensions.setdefault(evidence_id, set()).add(dimension.value)
        linked_review_ids = set(
            self._session.scalars(select(LearnerModelCorrectionSnapshotLink.review_id)).all()
        )
        annotations = self._session.scalars(
            select(LearnerModelAnnotation).where(
                LearnerModelAnnotation.course_id == course_id,
                LearnerModelAnnotation.learner_id == learner_key,
                LearnerModelAnnotation.outcome_id == outcome_id,
            )
        ).all()
        accepted: list[AcceptedCorrectionTarget] = []
        for annotation in annotations:
            if (
                annotation.evidence_id not in evidence_ids
                and annotation.estimate_id not in dimensions
            ):
                continue
            review = self._latest_review(annotation.id)
            if (
                review is not None
                and review.action.value == "ACCEPTED"
                and review.id not in linked_review_ids
            ):
                target_dimensions = (
                    {dimensions[annotation.estimate_id]}
                    if annotation.estimate_id in dimensions
                    else evidence_dimensions.get(annotation.evidence_id, set())
                )
                accepted.extend(
                    AcceptedCorrectionTarget(review.id, dimension)
                    for dimension in sorted(target_dimensions)
                )
        return tuple(sorted(accepted, key=lambda item: item.review_id))

    def _require_learner_scope(self, command: LearnerAnnotationCommand, learner_id: int) -> None:
        if command.actor_reference != command.learner_id:
            raise LearnerModelCorrectionNotFoundError("correction target is unavailable")
        enrolled = self._session.scalar(
            select(Enrollment.id).where(
                Enrollment.course_id == command.course_id,
                Enrollment.student_id == learner_id,
                Enrollment.status == EnrollmentStatus.ACTIVE,
            )
        )
        user = self._session.get(User, learner_id)
        if (
            user is None
            or not user.is_active
            or user.role is not UserRole.STUDENT
            or enrolled is None
        ):
            raise LearnerModelCorrectionNotFoundError("correction target is unavailable")

    def _require_educator_scope(self, course_id: str, actor_reference: str) -> None:
        actor_id = _learner_id(actor_reference)
        course = self._session.scalar(
            select(Course.id)
            .join(User, Course.educator_id == User.id)
            .where(
                Course.id == course_id,
                User.id == actor_id,
                User.role == UserRole.EDUCATOR,
                User.is_active.is_(True),
            )
        )
        if course is None:
            raise LearnerModelCorrectionNotFoundError("correction target is unavailable")

    def _require_history_scope(self, actor_reference: str, course_id: str, learner_id: int) -> None:
        if str(learner_id) == actor_reference:
            self._require_learner_scope_for_history(course_id, learner_id)
            return
        self._require_educator_scope(course_id, actor_reference)
        # Do not let an educator distinguish an arbitrary user ID from a
        # learner with no history in this course.
        self._require_learner_scope_for_history(course_id, learner_id)

    def _require_learner_scope_for_history(self, course_id: str, learner_id: int) -> None:
        user = self._session.get(User, learner_id)
        enrolled = self._session.scalar(
            select(Enrollment.id).where(
                Enrollment.course_id == course_id,
                Enrollment.student_id == learner_id,
                Enrollment.status.in_((EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED)),
            )
        )
        if (
            user is None
            or not user.is_active
            or user.role is not UserRole.STUDENT
            or enrolled is None
        ):
            raise LearnerModelCorrectionNotFoundError("correction history is unavailable")

    def _require_target(
        self, target: CorrectionTarget, course_id: str, learner_id: int, outcome_id: str
    ) -> None:
        if target.target_kind is CorrectionTargetKind.EVIDENCE:
            found = self._session.scalar(
                select(LearningEvidence.id).where(
                    LearningEvidence.id == target.evidence_id,
                    LearningEvidence.course_id == course_id,
                    LearningEvidence.learner_id == learner_id,
                    LearningEvidence.outcome_id == outcome_id,
                )
            )
        else:
            found = self._session.scalar(
                select(LearnerOutcomeEstimate.id)
                .join(LearnerModelSnapshot)
                .where(
                    LearnerOutcomeEstimate.id == target.estimate_id,
                    LearnerModelSnapshot.course_id == course_id,
                    LearnerModelSnapshot.learner_id == learner_id,
                    LearnerModelSnapshot.outcome_id == outcome_id,
                )
            )
        if found is None:
            raise LearnerModelCorrectionNotFoundError("correction target is unavailable")

    def _annotation(
        self, command: EducatorCorrectionReviewCommand, learner_id: int
    ) -> LearnerModelAnnotation:
        annotation = self._session.scalar(
            select(LearnerModelAnnotation).where(
                LearnerModelAnnotation.id == command.annotation_id,
                LearnerModelAnnotation.course_id == command.course_id,
                LearnerModelAnnotation.learner_id == learner_id,
                LearnerModelAnnotation.outcome_id == command.outcome_id,
            )
        )
        if annotation is None or _target(annotation) != command.target:
            raise LearnerModelCorrectionNotFoundError("correction target is unavailable")
        self._require_target(command.target, command.course_id, learner_id, command.outcome_id)
        return annotation

    def _annotation_by_key(
        self, course_id: str, learner_id: int, key: str
    ) -> LearnerModelAnnotation | None:
        return self._session.scalar(
            select(LearnerModelAnnotation).where(
                LearnerModelAnnotation.course_id == course_id,
                LearnerModelAnnotation.learner_id == learner_id,
                LearnerModelAnnotation.idempotency_key == key,
            )
        )

    def _review_by_key(
        self, course_id: str, learner_id: int, key: str
    ) -> LearnerModelCorrectionReview | None:
        return self._session.scalar(
            select(LearnerModelCorrectionReview).where(
                LearnerModelCorrectionReview.course_id == course_id,
                LearnerModelCorrectionReview.learner_id == learner_id,
                LearnerModelCorrectionReview.idempotency_key == key,
            )
        )

    def _latest_review(self, annotation_id: str) -> LearnerModelCorrectionReview | None:
        return self._session.scalar(
            select(LearnerModelCorrectionReview)
            .where(LearnerModelCorrectionReview.annotation_id == annotation_id)
            .order_by(
                LearnerModelCorrectionReview.review_version.desc(),
                LearnerModelCorrectionReview.id.desc(),
            )
            .limit(1)
        )

    def _annotation_replay(
        self, row: LearnerModelAnnotation, command: LearnerAnnotationCommand, learner_id: int
    ) -> AnnotationWrite:
        if (
            row.id,
            row.course_id,
            row.learner_id,
            row.outcome_id,
            _target(row),
            row.action,
            row.note,
            row.record_version,
            row.actor_reference,
            row.correlation_id,
            row.idempotency_key,
            _utc(row.occurred_at),
        ) != (
            command.annotation_id,
            command.course_id,
            learner_id,
            command.outcome_id,
            command.target,
            command.action,
            command.note,
            command.record_version,
            command.actor_reference,
            command.correlation_id,
            command.idempotency_key,
            _utc(command.occurred_at),
        ):
            raise LearnerModelConflictError(
                "learner annotation idempotency key was reused for different content"
            )
        return AnnotationWrite(_annotation_payload(row), False)

    def _review_replay(
        self,
        row: LearnerModelCorrectionReview,
        command: EducatorCorrectionReviewCommand,
        learner_id: int,
    ) -> ReviewWrite:
        annotation = self._session.get(LearnerModelAnnotation, row.annotation_id)
        if annotation is None or (
            row.id,
            row.annotation_id,
            row.course_id,
            row.learner_id,
            row.outcome_id,
            _target(annotation),
            row.prior_review_id,
            row.review_version,
            row.expected_latest_review_version,
            row.action,
            row.reason,
            row.actor_reference,
            row.correlation_id,
            row.idempotency_key,
            _utc(row.occurred_at),
        ) != (
            command.review_id,
            command.annotation_id,
            command.course_id,
            learner_id,
            command.outcome_id,
            command.target,
            command.prior_review_id,
            command.review_version,
            command.expected_latest_review_version,
            command.action,
            command.reason,
            command.actor_reference,
            command.correlation_id,
            command.idempotency_key,
            _utc(command.occurred_at),
        ):
            raise LearnerModelConflictError(
                "educator review idempotency key was reused for different content"
            )
        return ReviewWrite(_review_payload(row, _target(annotation)), False)


def _learner_id(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise LearnerModelCorrectionNotFoundError("correction target is unavailable") from None


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _target(row: LearnerModelAnnotation) -> CorrectionTarget:
    return CorrectionTarget(
        target_kind=row.target_kind, evidence_id=row.evidence_id, estimate_id=row.estimate_id
    )


def _annotation_payload(row: LearnerModelAnnotation) -> LearnerAnnotationPayload:
    return LearnerAnnotationPayload(
        annotation_id=row.id,
        course_id=row.course_id,
        learner_id=str(row.learner_id),
        outcome_id=row.outcome_id,
        target=_target(row),
        actor_reference=row.actor_reference,
        correlation_id=row.correlation_id,
        idempotency_key=row.idempotency_key,
        occurred_at=_utc(row.occurred_at),
        record_version=row.record_version,
        action=row.action,
        note=row.note,
    )


def _review_payload(
    row: LearnerModelCorrectionReview, target: CorrectionTarget
) -> EducatorCorrectionReviewPayload:
    return EducatorCorrectionReviewPayload(
        review_id=row.id,
        annotation_id=row.annotation_id,
        course_id=row.course_id,
        learner_id=str(row.learner_id),
        outcome_id=row.outcome_id,
        target=target,
        actor_reference=row.actor_reference,
        correlation_id=row.correlation_id,
        idempotency_key=row.idempotency_key,
        occurred_at=_utc(row.occurred_at),
        prior_review_id=row.prior_review_id,
        review_version=row.review_version,
        expected_latest_review_version=row.expected_latest_review_version,
        action=row.action,
        reason=row.reason,
    )


__all__ = [
    "AcceptedCorrectionTarget",
    "AnnotationWrite",
    "CorrectionHistory",
    "ReviewWrite",
    "SqlAlchemyLearnerModelCorrectionRepository",
]
