"""Transactional repository for append-only Person B learner-model snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.platform_enums import (
    CorrectionAction,
    CorrectionTargetKind,
    EvidenceLinkRelation,
    EvidenceType,
    InferenceStatus,
    LearnerModelDimension,
    ModelSource,
)
from app.models.learner_model import (
    LearnerModelAnnotation,
    LearnerModelCorrectionReview,
)
from app.models.learner_model import (
    LearnerModelEvidenceLink as LearnerModelEvidenceLinkModel,
)
from app.models.learner_model import LearnerModelSnapshot as LearnerModelSnapshotModel
from app.models.learner_model import LearnerOutcomeEstimate as LearnerOutcomeEstimateModel
from app.models.learning_evidence import LearningEvidence
from app.models.lms import Course, Enrollment, EnrollmentStatus
from app.models.user import User, UserRole
from app.services.learner_model.contracts import (
    LearnerModelBuildCommand,
    LearnerModelSnapshotPayload,
)
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
    LearnerModelSafetyError,
    LearnerModelStaleReviewError,
)


@dataclass(frozen=True, slots=True)
class LearnerEvidenceObservation:
    """Metadata-only evidence input to a deterministic learner-model rule."""

    evidence_id: str
    evidence_type: EvidenceType
    instructional_support_level: int
    occurred_at: datetime
    relation: EvidenceLinkRelation


@dataclass(frozen=True, slots=True)
class LearnerModelSnapshotWriteResult:
    snapshot_id: str
    created: bool
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class LearnerOutcomeEstimateView:
    dimension: LearnerModelDimension
    inference_status: InferenceStatus
    uncertainty: float
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LearnerModelSnapshotView:
    snapshot_id: str
    prior_snapshot_id: str | None
    model_source: ModelSource
    schema_version: str
    model_version: str
    rule_version: str
    occurred_at: datetime
    estimates: tuple[LearnerOutcomeEstimateView, ...]


@dataclass(frozen=True, slots=True)
class LearnerAnnotationWriteResult:
    annotation: LearnerAnnotationPayload
    created: bool


@dataclass(frozen=True, slots=True)
class LearnerModelCorrectionReviewWriteResult:
    review: EducatorCorrectionReviewPayload
    created: bool


@dataclass(frozen=True, slots=True)
class LearnerModelCorrectionHistory:
    annotation: LearnerAnnotationPayload
    reviews: tuple[EducatorCorrectionReviewPayload, ...]


@dataclass(frozen=True, slots=True)
class AcceptedLearnerModelCorrection:
    annotation: LearnerAnnotationPayload
    review: EducatorCorrectionReviewPayload


class SqlAlchemyLearnerModelRepository:
    """Persist snapshots without importing assessment results or LMS services."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_annotation(
        self,
        command: LearnerAnnotationCommand,
    ) -> LearnerAnnotationWriteResult:
        """Store learner-authored context after rechecking actor and target scope."""

        learner_id = _correction_learner_id(command.learner_id)
        try:
            self._require_learner_annotation_scope(command, learner_id)
            existing = self._annotation_by_idempotency(command, learner_id)
            if existing is not None:
                return self._annotation_replay(existing, command, learner_id)
            self._require_correction_target(
                command.target,
                course_id=command.course_id,
                learner_id=learner_id,
                outcome_id=command.outcome_id,
            )
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
                occurred_at=_as_utc(command.occurred_at),
            )
            self._session.add(row)
            self._session.commit()
            return LearnerAnnotationWriteResult(
                annotation=_annotation_payload(row),
                created=True,
            )
        except (LearnerModelCorrectionNotFoundError, LearnerModelConflictError):
            raise
        except IntegrityError:
            self._session.rollback()
            existing = self._annotation_by_idempotency(command, learner_id)
            if existing is not None:
                return self._annotation_replay(existing, command, learner_id)
            raise LearnerModelConflictError(
                "learner annotation conflicts with immutable correction history"
            ) from None
        except SQLAlchemyError:
            self._session.rollback()
            raise LearnerModelPersistenceError("learner annotation could not be stored") from None

    def create_correction_review(
        self,
        command: EducatorCorrectionReviewCommand,
    ) -> LearnerModelCorrectionReviewWriteResult:
        """Append one educator decision using optimistic review ordering."""

        learner_id = _correction_learner_id(command.learner_id)
        try:
            self._require_educator_review_scope(command)
            existing = self._review_by_idempotency(command, learner_id)
            if existing is not None:
                return self._review_replay(existing, command, learner_id)
            annotation = self._require_annotation_target(command, learner_id)
            latest = self._latest_review_row(annotation.id)
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
                occurred_at=_as_utc(command.occurred_at),
            )
            self._session.add(row)
            self._session.commit()
            return LearnerModelCorrectionReviewWriteResult(
                review=_review_payload(row, _annotation_target(annotation)),
                created=True,
            )
        except (
            LearnerModelCorrectionNotFoundError,
            LearnerModelConflictError,
        ):
            raise
        except IntegrityError:
            self._session.rollback()
            existing = self._review_by_idempotency(command, learner_id)
            if existing is not None:
                return self._review_replay(existing, command, learner_id)
            latest = self._latest_review_row(command.annotation_id)
            if latest is not None and latest.review_version >= command.review_version:
                raise LearnerModelStaleReviewError(
                    "correction review is based on a stale latest-review version"
                ) from None
            raise LearnerModelConflictError(
                "educator review conflicts with immutable correction history"
            ) from None
        except SQLAlchemyError:
            self._session.rollback()
            raise LearnerModelPersistenceError(
                "educator correction review could not be stored"
            ) from None

    def correction_history(
        self,
        *,
        actor_reference: str,
        course_id: str,
        learner_id: str,
        outcome_id: str,
    ) -> tuple[LearnerModelCorrectionHistory, ...]:
        """Return scoped annotation histories without revealing inaccessible scopes."""

        learner_key = _correction_learner_id(learner_id)
        try:
            self._require_history_scope(
                actor_reference=actor_reference,
                course_id=course_id,
                learner_id=learner_key,
            )
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
            annotation_ids = [annotation.id for annotation in annotations]
            reviews = self._session.scalars(
                select(LearnerModelCorrectionReview)
                .where(LearnerModelCorrectionReview.annotation_id.in_(annotation_ids))
                .order_by(
                    LearnerModelCorrectionReview.annotation_id,
                    LearnerModelCorrectionReview.review_version,
                )
            ).all()
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
            LearnerModelCorrectionHistory(
                annotation=_annotation_payload(annotation),
                reviews=tuple(
                    _review_payload(review, _annotation_target(annotation))
                    for review in by_annotation.get(annotation.id, ())
                ),
            )
            for annotation in annotations
        )

    def latest_correction_review(
        self,
        *,
        annotation_id: str,
        course_id: str,
        learner_id: str,
        outcome_id: str,
    ) -> EducatorCorrectionReviewPayload | None:
        """Return the current review only when its annotation matches the full scope."""

        learner_key = _correction_learner_id(learner_id)
        annotation = self._session.scalar(
            select(LearnerModelAnnotation).where(
                LearnerModelAnnotation.id == annotation_id,
                LearnerModelAnnotation.course_id == course_id,
                LearnerModelAnnotation.learner_id == learner_key,
                LearnerModelAnnotation.outcome_id == outcome_id,
            )
        )
        if annotation is None:
            return None
        review = self._latest_review_row(annotation.id)
        return None if review is None else _review_payload(review, _annotation_target(annotation))

    def accepted_corrections(
        self,
        *,
        course_id: str,
        learner_id: str,
        outcome_id: str,
    ) -> tuple[AcceptedLearnerModelCorrection, ...]:
        """Return annotations whose latest educator decision is accepted."""

        learner_key = _correction_learner_id(learner_id)
        try:
            annotations = self._session.scalars(
                select(LearnerModelAnnotation).where(
                    LearnerModelAnnotation.course_id == course_id,
                    LearnerModelAnnotation.learner_id == learner_key,
                    LearnerModelAnnotation.outcome_id == outcome_id,
                )
            ).all()
            accepted: list[AcceptedLearnerModelCorrection] = []
            for annotation in annotations:
                review = self._latest_review_row(annotation.id)
                if review is not None and review.action is CorrectionAction.ACCEPTED:
                    accepted.append(
                        AcceptedLearnerModelCorrection(
                            annotation=_annotation_payload(annotation),
                            review=_review_payload(review, _annotation_target(annotation)),
                        )
                    )
            return tuple(accepted)
        except SQLAlchemyError:
            self._session.rollback()
            raise LearnerModelPersistenceError(
                "accepted learner-model corrections could not be read"
            ) from None

    def _annotation_by_idempotency(
        self,
        command: LearnerAnnotationCommand,
        learner_id: int,
    ) -> LearnerModelAnnotation | None:
        return self._session.scalar(
            select(LearnerModelAnnotation).where(
                LearnerModelAnnotation.course_id == command.course_id,
                LearnerModelAnnotation.learner_id == learner_id,
                LearnerModelAnnotation.idempotency_key == command.idempotency_key,
            )
        )

    def _annotation_replay(
        self,
        existing: LearnerModelAnnotation,
        command: LearnerAnnotationCommand,
        learner_id: int,
    ) -> LearnerAnnotationWriteResult:
        if not _annotation_is_exact(existing, command, learner_id):
            raise LearnerModelConflictError(
                "learner annotation idempotency key was reused for different content"
            )
        return LearnerAnnotationWriteResult(
            annotation=_annotation_payload(existing),
            created=False,
        )

    def _review_by_idempotency(
        self,
        command: EducatorCorrectionReviewCommand,
        learner_id: int,
    ) -> LearnerModelCorrectionReview | None:
        return self._session.scalar(
            select(LearnerModelCorrectionReview).where(
                LearnerModelCorrectionReview.course_id == command.course_id,
                LearnerModelCorrectionReview.learner_id == learner_id,
                LearnerModelCorrectionReview.idempotency_key == command.idempotency_key,
            )
        )

    def _review_replay(
        self,
        existing: LearnerModelCorrectionReview,
        command: EducatorCorrectionReviewCommand,
        learner_id: int,
    ) -> LearnerModelCorrectionReviewWriteResult:
        annotation = self._session.get(LearnerModelAnnotation, existing.annotation_id)
        if annotation is None or not _review_is_exact(existing, annotation, command, learner_id):
            raise LearnerModelConflictError(
                "educator review idempotency key was reused for different content"
            )
        return LearnerModelCorrectionReviewWriteResult(
            review=_review_payload(existing, _annotation_target(annotation)),
            created=False,
        )

    def _require_learner_annotation_scope(
        self,
        command: LearnerAnnotationCommand,
        learner_id: int,
    ) -> None:
        if command.actor_reference != command.learner_id:
            raise LearnerModelCorrectionNotFoundError("correction target is unavailable")
        user = self._session.get(User, learner_id)
        enrollment = self._session.scalar(
            select(Enrollment.id).where(
                Enrollment.course_id == command.course_id,
                Enrollment.student_id == learner_id,
                Enrollment.status == EnrollmentStatus.ACTIVE,
            )
        )
        if (
            user is None
            or not user.is_active
            or user.role is not UserRole.STUDENT
            or enrollment is None
        ):
            raise LearnerModelCorrectionNotFoundError("correction target is unavailable")

    def _require_educator_review_scope(
        self,
        command: EducatorCorrectionReviewCommand,
    ) -> None:
        actor_id = _actor_id(command.actor_reference)
        educator_course = self._session.scalar(
            select(Course.id)
            .join(User, User.id == Course.educator_id)
            .where(
                Course.id == command.course_id,
                User.id == actor_id,
                User.role == UserRole.EDUCATOR,
                User.is_active.is_(True),
            )
        )
        if educator_course is None:
            raise LearnerModelCorrectionNotFoundError("correction target is unavailable")

    def _require_history_scope(
        self,
        *,
        actor_reference: str,
        course_id: str,
        learner_id: int,
    ) -> None:
        actor_id = _actor_id(actor_reference)
        if actor_id == learner_id:
            learner = self._session.get(User, learner_id)
            enrollment = self._session.scalar(
                select(Enrollment.id).where(
                    Enrollment.course_id == course_id,
                    Enrollment.student_id == learner_id,
                    Enrollment.status == EnrollmentStatus.ACTIVE,
                )
            )
            if (
                learner is not None
                and learner.is_active
                and learner.role is UserRole.STUDENT
                and enrollment is not None
            ):
                return
        educator_course = self._session.scalar(
            select(Course.id)
            .join(User, User.id == Course.educator_id)
            .where(
                Course.id == course_id,
                User.id == actor_id,
                User.role == UserRole.EDUCATOR,
                User.is_active.is_(True),
            )
        )
        if educator_course is None:
            raise LearnerModelCorrectionNotFoundError("correction history is unavailable")

    def _require_correction_target(
        self,
        target: CorrectionTarget,
        *,
        course_id: str,
        learner_id: int,
        outcome_id: str,
    ) -> None:
        if target.target_kind is CorrectionTargetKind.EVIDENCE:
            target_id = self._session.scalar(
                select(LearningEvidence.id).where(
                    LearningEvidence.id == target.evidence_id,
                    LearningEvidence.course_id == course_id,
                    LearningEvidence.learner_id == learner_id,
                    LearningEvidence.outcome_id == outcome_id,
                )
            )
        else:
            target_id = self._session.scalar(
                select(LearnerOutcomeEstimateModel.id)
                .join(
                    LearnerModelSnapshotModel,
                    LearnerModelSnapshotModel.id == LearnerOutcomeEstimateModel.snapshot_id,
                )
                .where(
                    LearnerOutcomeEstimateModel.id == target.estimate_id,
                    LearnerModelSnapshotModel.course_id == course_id,
                    LearnerModelSnapshotModel.learner_id == learner_id,
                    LearnerModelSnapshotModel.outcome_id == outcome_id,
                )
            )
        if target_id is None:
            raise LearnerModelCorrectionNotFoundError("correction target is unavailable")

    def _require_annotation_target(
        self,
        command: EducatorCorrectionReviewCommand,
        learner_id: int,
    ) -> LearnerModelAnnotation:
        annotation = self._session.scalar(
            select(LearnerModelAnnotation).where(
                LearnerModelAnnotation.id == command.annotation_id,
                LearnerModelAnnotation.course_id == command.course_id,
                LearnerModelAnnotation.learner_id == learner_id,
                LearnerModelAnnotation.outcome_id == command.outcome_id,
            )
        )
        if annotation is None or _annotation_target(annotation) != command.target:
            raise LearnerModelCorrectionNotFoundError("correction target is unavailable")
        self._require_correction_target(
            command.target,
            course_id=command.course_id,
            learner_id=learner_id,
            outcome_id=command.outcome_id,
        )
        return annotation

    def _latest_review_row(self, annotation_id: str) -> LearnerModelCorrectionReview | None:
        return self._session.scalar(
            select(LearnerModelCorrectionReview)
            .where(LearnerModelCorrectionReview.annotation_id == annotation_id)
            .order_by(LearnerModelCorrectionReview.review_version.desc())
            .limit(1)
        )

    def observations(
        self,
        command: LearnerModelBuildCommand,
    ) -> tuple[LearnerEvidenceObservation, ...]:
        """Load only requested evidence from the same learner/course/outcome scope."""

        learner_id = _learner_id(command.learner_id)
        requested = tuple(signal.evidence_id for signal in command.evidence_signals)
        if len(set(requested)) != len(requested):
            raise LearnerModelSafetyError("learner-model evidence signals must be distinct")
        try:
            rows = self._session.scalars(
                select(LearningEvidence).where(
                    LearningEvidence.id.in_(requested),
                    LearningEvidence.course_id == command.course_id,
                    LearningEvidence.learner_id == learner_id,
                    LearningEvidence.outcome_id == command.outcome_id,
                )
            ).all()
        except SQLAlchemyError:
            self._session.rollback()
            raise LearnerModelPersistenceError("learner-model evidence could not be read") from None
        by_id = {row.id: row for row in rows}
        if len(by_id) != len(requested):
            raise LearnerModelSafetyError(
                "learner-model evidence must exist in the requested learner/course/outcome scope"
            )
        relations = {signal.evidence_id: signal.relation for signal in command.evidence_signals}
        return tuple(
            LearnerEvidenceObservation(
                evidence_id=evidence_id,
                evidence_type=by_id[evidence_id].evidence_type,
                instructional_support_level=int(by_id[evidence_id].instructional_support_level),
                occurred_at=_as_utc(by_id[evidence_id].occurred_at),
                relation=relations[evidence_id],
            )
            for evidence_id in requested
        )

    def store(self, snapshot: LearnerModelSnapshotPayload) -> LearnerModelSnapshotWriteResult:
        """Store one complete snapshot atomically, or return its exact replay."""

        learner_id = _learner_id(snapshot.learner_id)
        try:
            existing = self._session.scalar(
                select(LearnerModelSnapshotModel).where(
                    LearnerModelSnapshotModel.course_id == snapshot.course_id,
                    LearnerModelSnapshotModel.learner_id == learner_id,
                    LearnerModelSnapshotModel.outcome_id == snapshot.outcome_id,
                    LearnerModelSnapshotModel.idempotency_key == snapshot.idempotency_key,
                )
            )
            if existing is not None:
                if self._is_exact_replay(existing, snapshot, learner_id):
                    return LearnerModelSnapshotWriteResult(
                        snapshot_id=existing.id,
                        created=False,
                        occurred_at=_as_utc(existing.occurred_at),
                    )
                raise LearnerModelConflictError(
                    "learner-model idempotency key was reused for a different snapshot"
                )

            self._validate_prior_snapshot(snapshot, learner_id)
            self._validate_estimates(snapshot, learner_id)
            model = LearnerModelSnapshotModel(
                id=snapshot.snapshot_id,
                course_id=snapshot.course_id,
                learner_id=learner_id,
                outcome_id=snapshot.outcome_id,
                prior_snapshot_id=snapshot.prior_snapshot_id,
                model_source=snapshot.model_source,
                schema_version=snapshot.contract_version,
                model_version=snapshot.model_version,
                rule_version=snapshot.rule_version,
                record_version=snapshot.record_version,
                actor_reference=snapshot.actor_reference,
                agent_reference=snapshot.agent_reference,
                correlation_id=snapshot.correlation_id,
                idempotency_key=snapshot.idempotency_key,
                occurred_at=_as_utc(snapshot.occurred_at),
            )
            self._session.add(model)
            self._session.flush()
            estimates: list[LearnerOutcomeEstimateModel] = []
            for estimate in snapshot.estimates:
                row = LearnerOutcomeEstimateModel(
                    id=estimate.estimate_id,
                    snapshot_id=model.id,
                    dimension=estimate.dimension,
                    inference_status=estimate.inference_status,
                    uncertainty=estimate.uncertainty,
                    reason_code=estimate.reason_code,
                    evidence_observed_at=_as_utc(estimate.evidence_observed_at),
                )
                estimates.append(row)
            self._session.add_all(estimates)
            self._session.flush()
            estimate_ids = {
                estimate.id: payload for estimate, payload in zip(estimates, snapshot.estimates)
            }
            self._session.add_all(
                LearnerModelEvidenceLinkModel(
                    estimate_id=estimate_id,
                    evidence_id=signal.evidence_id,
                    relation=signal.relation,
                )
                for estimate_id, payload in estimate_ids.items()
                for signal in payload.evidence_signals
            )
            self._session.commit()
            return LearnerModelSnapshotWriteResult(
                snapshot_id=model.id,
                created=True,
                occurred_at=_as_utc(model.occurred_at),
            )
        except LearnerModelSafetyError:
            raise
        except IntegrityError:
            self._session.rollback()
            raise LearnerModelConflictError(
                "learner-model snapshot conflicts with immutable history"
            ) from None
        except SQLAlchemyError:
            self._session.rollback()
            raise LearnerModelPersistenceError(
                "learner-model snapshot could not be stored"
            ) from None

    def _is_exact_replay(
        self,
        existing: LearnerModelSnapshotModel,
        snapshot: LearnerModelSnapshotPayload,
        learner_id: int,
    ) -> bool:
        if (
            existing.id,
            existing.course_id,
            existing.learner_id,
            existing.outcome_id,
            existing.prior_snapshot_id,
            existing.model_source,
            existing.schema_version,
            existing.model_version,
            existing.rule_version,
            existing.record_version,
            existing.actor_reference,
            existing.agent_reference,
            existing.correlation_id,
            existing.idempotency_key,
            _as_utc(existing.occurred_at),
        ) != (
            snapshot.snapshot_id,
            snapshot.course_id,
            learner_id,
            snapshot.outcome_id,
            snapshot.prior_snapshot_id,
            snapshot.model_source,
            snapshot.contract_version,
            snapshot.model_version,
            snapshot.rule_version,
            snapshot.record_version,
            snapshot.actor_reference,
            snapshot.agent_reference,
            snapshot.correlation_id,
            snapshot.idempotency_key,
            _as_utc(snapshot.occurred_at),
        ):
            return False

        estimates = self._session.scalars(
            select(LearnerOutcomeEstimateModel).where(
                LearnerOutcomeEstimateModel.snapshot_id == existing.id
            )
        ).all()
        estimate_ids = [estimate.id for estimate in estimates]
        links = self._session.scalars(
            select(LearnerModelEvidenceLinkModel).where(
                LearnerModelEvidenceLinkModel.estimate_id.in_(estimate_ids)
            )
        ).all()
        links_by_estimate: dict[str, set[tuple[str, EvidenceLinkRelation]]] = {}
        for link in links:
            links_by_estimate.setdefault(link.estimate_id, set()).add(
                (link.evidence_id, link.relation)
            )

        stored = {
            estimate.id: (
                estimate.dimension,
                estimate.inference_status,
                estimate.uncertainty,
                estimate.reason_code,
                _as_utc(estimate.evidence_observed_at),
                frozenset(links_by_estimate.get(estimate.id, set())),
            )
            for estimate in estimates
        }
        requested = {
            estimate.estimate_id: (
                estimate.dimension,
                estimate.inference_status,
                estimate.uncertainty,
                estimate.reason_code,
                _as_utc(estimate.evidence_observed_at),
                frozenset(
                    (signal.evidence_id, signal.relation) for signal in estimate.evidence_signals
                ),
            )
            for estimate in snapshot.estimates
        }
        return stored == requested

    def timeline(
        self,
        *,
        course_id: str,
        learner_id: str,
        outcome_id: str,
    ) -> tuple[LearnerModelSnapshotView, ...]:
        """Return old and new snapshots in their stable append-only order."""

        try:
            snapshots = self._session.scalars(
                select(LearnerModelSnapshotModel)
                .where(
                    LearnerModelSnapshotModel.course_id == course_id,
                    LearnerModelSnapshotModel.learner_id == _learner_id(learner_id),
                    LearnerModelSnapshotModel.outcome_id == outcome_id,
                )
                .order_by(
                    LearnerModelSnapshotModel.occurred_at,
                    LearnerModelSnapshotModel.created_at,
                    LearnerModelSnapshotModel.id,
                )
            ).all()
            snapshot_ids = [snapshot.id for snapshot in snapshots]
            estimates = self._session.scalars(
                select(LearnerOutcomeEstimateModel)
                .where(LearnerOutcomeEstimateModel.snapshot_id.in_(snapshot_ids))
                .order_by(LearnerOutcomeEstimateModel.dimension, LearnerOutcomeEstimateModel.id)
            ).all()
            estimate_ids = [estimate.id for estimate in estimates]
            links = self._session.scalars(
                select(LearnerModelEvidenceLinkModel)
                .where(LearnerModelEvidenceLinkModel.estimate_id.in_(estimate_ids))
                .order_by(LearnerModelEvidenceLinkModel.evidence_id)
            ).all()
        except SQLAlchemyError:
            self._session.rollback()
            raise LearnerModelPersistenceError("learner-model history could not be read") from None
        links_by_estimate: dict[str, list[str]] = {}
        for link in links:
            links_by_estimate.setdefault(link.estimate_id, []).append(link.evidence_id)
        estimates_by_snapshot: dict[str, list[LearnerOutcomeEstimateView]] = {}
        for estimate in estimates:
            estimates_by_snapshot.setdefault(estimate.snapshot_id, []).append(
                LearnerOutcomeEstimateView(
                    dimension=estimate.dimension,
                    inference_status=estimate.inference_status,
                    uncertainty=estimate.uncertainty,
                    evidence_ids=tuple(links_by_estimate.get(estimate.id, ())),
                )
            )
        return tuple(
            LearnerModelSnapshotView(
                snapshot_id=snapshot.id,
                prior_snapshot_id=snapshot.prior_snapshot_id,
                model_source=snapshot.model_source,
                schema_version=snapshot.schema_version,
                model_version=snapshot.model_version,
                rule_version=snapshot.rule_version,
                occurred_at=_as_utc(snapshot.occurred_at),
                estimates=tuple(estimates_by_snapshot.get(snapshot.id, ())),
            )
            for snapshot in snapshots
        )

    def _validate_prior_snapshot(
        self,
        snapshot: LearnerModelSnapshotPayload,
        learner_id: int,
    ) -> None:
        if snapshot.prior_snapshot_id is None:
            return
        prior = self._session.scalar(
            select(LearnerModelSnapshotModel).where(
                LearnerModelSnapshotModel.id == snapshot.prior_snapshot_id,
                LearnerModelSnapshotModel.course_id == snapshot.course_id,
                LearnerModelSnapshotModel.learner_id == learner_id,
                LearnerModelSnapshotModel.outcome_id == snapshot.outcome_id,
            )
        )
        if prior is None:
            raise LearnerModelSafetyError("prior snapshot is unavailable in the requested scope")

    def _validate_estimates(self, snapshot: LearnerModelSnapshotPayload, learner_id: int) -> None:
        dimensions = [estimate.dimension for estimate in snapshot.estimates]
        estimate_ids = [estimate.estimate_id for estimate in snapshot.estimates]
        if len(set(dimensions)) != len(dimensions) or len(set(estimate_ids)) != len(estimate_ids):
            raise LearnerModelSafetyError(
                "snapshot estimate dimensions and identifiers must be distinct"
            )
        requested_evidence = {
            signal.evidence_id
            for estimate in snapshot.estimates
            for signal in estimate.evidence_signals
        }
        rows = self._session.scalars(
            select(LearningEvidence.id).where(
                LearningEvidence.id.in_(requested_evidence),
                LearningEvidence.course_id == snapshot.course_id,
                LearningEvidence.learner_id == learner_id,
                LearningEvidence.outcome_id == snapshot.outcome_id,
            )
        ).all()
        if set(rows) != requested_evidence:
            raise LearnerModelSafetyError(
                "every learner-model estimate must link in-scope immutable evidence"
            )


def _annotation_target(annotation: LearnerModelAnnotation) -> CorrectionTarget:
    return CorrectionTarget(
        target_kind=annotation.target_kind,
        evidence_id=annotation.evidence_id,
        estimate_id=annotation.estimate_id,
    )


def _annotation_payload(annotation: LearnerModelAnnotation) -> LearnerAnnotationPayload:
    return LearnerAnnotationPayload(
        annotation_id=annotation.id,
        course_id=annotation.course_id,
        learner_id=str(annotation.learner_id),
        outcome_id=annotation.outcome_id,
        target=_annotation_target(annotation),
        record_version=annotation.record_version,
        action=annotation.action,
        note=annotation.note,
        actor_reference=annotation.actor_reference,
        correlation_id=annotation.correlation_id,
        idempotency_key=annotation.idempotency_key,
        occurred_at=_as_utc(annotation.occurred_at),
    )


def _review_payload(
    review: LearnerModelCorrectionReview,
    target: CorrectionTarget,
) -> EducatorCorrectionReviewPayload:
    return EducatorCorrectionReviewPayload(
        review_id=review.id,
        annotation_id=review.annotation_id,
        course_id=review.course_id,
        learner_id=str(review.learner_id),
        outcome_id=review.outcome_id,
        target=target,
        review_version=review.review_version,
        expected_latest_review_version=review.expected_latest_review_version,
        action=review.action,
        reason=review.reason,
        actor_reference=review.actor_reference,
        correlation_id=review.correlation_id,
        idempotency_key=review.idempotency_key,
        occurred_at=_as_utc(review.occurred_at),
    )


def _annotation_is_exact(
    annotation: LearnerModelAnnotation,
    command: LearnerAnnotationCommand,
    learner_id: int,
) -> bool:
    return (
        annotation.id,
        annotation.course_id,
        annotation.learner_id,
        annotation.outcome_id,
        _annotation_target(annotation),
        annotation.action,
        annotation.note,
        annotation.schema_version,
        annotation.record_version,
        annotation.actor_reference,
        annotation.correlation_id,
        annotation.idempotency_key,
        _as_utc(annotation.occurred_at),
    ) == (
        command.annotation_id,
        command.course_id,
        learner_id,
        command.outcome_id,
        command.target,
        command.action,
        command.note,
        "learnlens.learner-annotation.v1",
        command.record_version,
        command.actor_reference,
        command.correlation_id,
        command.idempotency_key,
        _as_utc(command.occurred_at),
    )


def _review_is_exact(
    review: LearnerModelCorrectionReview,
    annotation: LearnerModelAnnotation,
    command: EducatorCorrectionReviewCommand,
    learner_id: int,
) -> bool:
    return (
        review.id,
        review.annotation_id,
        review.course_id,
        review.learner_id,
        review.outcome_id,
        _annotation_target(annotation),
        review.review_version,
        review.expected_latest_review_version,
        review.action,
        review.reason,
        review.schema_version,
        review.actor_reference,
        review.correlation_id,
        review.idempotency_key,
        _as_utc(review.occurred_at),
    ) == (
        command.review_id,
        command.annotation_id,
        command.course_id,
        learner_id,
        command.outcome_id,
        command.target,
        command.review_version,
        command.expected_latest_review_version,
        command.action,
        command.reason,
        "learnlens.educator-correction-review.v1",
        command.actor_reference,
        command.correlation_id,
        command.idempotency_key,
        _as_utc(command.occurred_at),
    )


def _correction_learner_id(value: str) -> int:
    try:
        return _learner_id(value)
    except LearnerModelSafetyError:
        raise LearnerModelCorrectionNotFoundError("correction target is unavailable") from None


def _actor_id(value: str) -> int:
    try:
        actor_id = int(value)
    except ValueError:
        raise LearnerModelCorrectionNotFoundError("correction target is unavailable") from None
    if actor_id < 1:
        raise LearnerModelCorrectionNotFoundError("correction target is unavailable")
    return actor_id


def _learner_id(value: str) -> int:
    try:
        learner_id = int(value)
    except ValueError:
        raise LearnerModelSafetyError("learner reference is unavailable") from None
    if learner_id < 1:
        raise LearnerModelSafetyError("learner reference is unavailable")
    return learner_id


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "AcceptedLearnerModelCorrection",
    "LearnerEvidenceObservation",
    "LearnerAnnotationWriteResult",
    "LearnerModelCorrectionHistory",
    "LearnerModelCorrectionReviewWriteResult",
    "LearnerModelSnapshotView",
    "LearnerModelSnapshotWriteResult",
    "LearnerOutcomeEstimateView",
    "SqlAlchemyLearnerModelRepository",
]
