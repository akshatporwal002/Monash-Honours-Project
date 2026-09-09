"""Transactional repository for append-only Person B learner-model snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.platform_enums import (
    EvidenceLinkRelation,
    EvidenceType,
    InferenceStatus,
    LearnerModelDimension,
    ModelSource,
)
from app.models.learner_model import (
    LearnerModelCorrectionReview,
    LearnerModelCorrectionSnapshotLink,
)
from app.models.learner_model import (
    LearnerModelEvidenceLink as LearnerModelEvidenceLinkModel,
)
from app.models.learner_model import LearnerModelSnapshot as LearnerModelSnapshotModel
from app.models.learner_model import LearnerOutcomeEstimate as LearnerOutcomeEstimateModel
from app.models.learning_evidence import LearningEvidence
from app.services.learner_model.contracts import (
    LearnerModelBuildCommand,
    LearnerModelSnapshotPayload,
)
from app.services.learner_model.safety import (
    LearnerModelConflictError,
    LearnerModelPersistenceError,
    LearnerModelSafetyError,
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
    estimate_id: str
    dimension: LearnerModelDimension
    inference_status: InferenceStatus
    uncertainty: float
    reason_code: str
    evidence_observed_at: datetime
    evidence_links: tuple[tuple[str, EvidenceLinkRelation], ...]

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        """Compatibility projection; teaching consumers use relation-bearing links."""

        return tuple(evidence_id for evidence_id, _ in self.evidence_links)


@dataclass(frozen=True, slots=True)
class LearnerModelSnapshotView:
    snapshot_id: str
    prior_snapshot_id: str | None
    course_id: str
    learner_id: str
    outcome_id: str
    record_version: int
    model_source: ModelSource
    schema_version: str
    model_version: str
    rule_version: str
    occurred_at: datetime
    validated: bool
    validation_classification: str
    estimates: tuple[LearnerOutcomeEstimateView, ...]


class SqlAlchemyLearnerModelRepository:
    """Persist snapshots without importing assessment results or LMS services."""

    def __init__(self, session: Session, *, caller_transaction: bool = False) -> None:
        self._session = session
        self._caller_transaction = caller_transaction

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

    def store(
        self,
        snapshot: LearnerModelSnapshotPayload,
        *,
        accepted_review_ids: tuple[str, ...] = (),
    ) -> LearnerModelSnapshotWriteResult:
        """Store one complete snapshot atomically, or return its exact replay."""

        learner_id = _learner_id(snapshot.learner_id)
        try:
            # SQLite has no row-level `FOR UPDATE`.  Acquire its single writer lock
            # before reading the head so competing successors are serialized.
            if (
                not self._caller_transaction
                and self._session.bind
                and self._session.bind.dialect.name == "sqlite"
            ):
                self._session.commit()
                self._session.execute(text("BEGIN IMMEDIATE"))
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
                    if not self._caller_transaction:
                        self._session.rollback()
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
            self._session.flush()
            self._store_correction_links(snapshot, model, accepted_review_ids)
            if self._caller_transaction:
                self._session.flush()
            else:
                self._session.commit()
            return LearnerModelSnapshotWriteResult(
                snapshot_id=model.id,
                created=True,
                occurred_at=_as_utc(model.occurred_at),
            )
        except LearnerModelSafetyError:
            self._session.rollback()
            raise
        except IntegrityError:
            self._session.rollback()
            if self._caller_transaction:
                raise LearnerModelPersistenceError(
                    "The caller-owned model transaction was rolled back"
                ) from None
            winner = self._session.get(LearnerModelSnapshotModel, snapshot.snapshot_id)
            if winner is not None and self._is_exact_replay(winner, snapshot, learner_id):
                return LearnerModelSnapshotWriteResult(
                    snapshot_id=winner.id,
                    created=False,
                    occurred_at=_as_utc(winner.occurred_at),
                )
            raise LearnerModelConflictError(
                "learner-model snapshot conflicts with immutable history"
            ) from None
        except SQLAlchemyError:
            self._session.rollback()
            raise LearnerModelPersistenceError(
                "learner-model snapshot could not be stored"
            ) from None

    def _store_correction_links(
        self,
        snapshot: LearnerModelSnapshotPayload,
        model: LearnerModelSnapshotModel,
        review_ids: tuple[str, ...],
    ) -> None:
        """Verify accepted reviews are still current and link them atomically."""
        for review_id in sorted(set(review_ids)):
            review = self._session.get(LearnerModelCorrectionReview, review_id)
            if review is None or review.action.value != "ACCEPTED":
                raise LearnerModelConflictError(
                    "accepted correction changed during snapshot construction"
                )
            latest = self._session.scalar(
                select(LearnerModelCorrectionReview)
                .where(LearnerModelCorrectionReview.annotation_id == review.annotation_id)
                .order_by(LearnerModelCorrectionReview.review_version.desc())
                .limit(1)
            )
            if (
                latest is None
                or latest.id != review.id
                or (
                    review.course_id,
                    review.learner_id,
                    review.outcome_id,
                )
                != (snapshot.course_id, model.learner_id, snapshot.outcome_id)
            ):
                raise LearnerModelConflictError(
                    "accepted correction changed during snapshot construction"
                )
            link_id = str(
                uuid5(
                    UUID("70c3b36a-7f3a-4915-a7eb-85be33c54ddb"),
                    f"{snapshot.snapshot_id}:{review_id}",
                )
            )
            self._session.add(
                LearnerModelCorrectionSnapshotLink(
                    id=link_id,
                    review_id=review.id,
                    snapshot_id=model.id,
                    course_id=snapshot.course_id,
                    learner_id=model.learner_id,
                    outcome_id=snapshot.outcome_id,
                    schema_version="learnlens.correction-snapshot-link.v1",
                    record_version=1,
                    actor_reference=snapshot.agent_reference or snapshot.actor_reference,
                    correlation_id=snapshot.correlation_id,
                    idempotency_key=f"correction-link:{link_id}",
                    occurred_at=_as_utc(snapshot.occurred_at),
                )
            )

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
        links_by_estimate: dict[str, list[tuple[str, EvidenceLinkRelation]]] = {}
        for link in links:
            links_by_estimate.setdefault(link.estimate_id, []).append(
                (link.evidence_id, link.relation)
            )

        stored = {
            estimate.id: (
                estimate.dimension,
                estimate.inference_status,
                estimate.uncertainty,
                estimate.reason_code,
                _as_utc(estimate.evidence_observed_at),
                tuple(sorted(links_by_estimate.get(estimate.id, ()))),
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
                tuple(
                    sorted(
                        (signal.evidence_id, signal.relation)
                        for signal in estimate.evidence_signals
                    )
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
        except SQLAlchemyError:
            self._session.rollback()
            raise LearnerModelPersistenceError("learner-model history could not be read") from None
        return self._hydrate(snapshots)

    def current(
        self,
        *,
        course_id: str,
        learner_id: str,
        outcome_id: str,
    ) -> LearnerModelSnapshotView | None:
        """Return the complete current teaching view for exactly one model scope."""

        try:
            snapshot = self._session.scalar(
                select(LearnerModelSnapshotModel)
                .where(
                    LearnerModelSnapshotModel.course_id == course_id,
                    LearnerModelSnapshotModel.learner_id == _learner_id(learner_id),
                    LearnerModelSnapshotModel.outcome_id == outcome_id,
                )
                .order_by(
                    LearnerModelSnapshotModel.record_version.desc(),
                    LearnerModelSnapshotModel.occurred_at.desc(),
                    LearnerModelSnapshotModel.created_at.desc(),
                    LearnerModelSnapshotModel.id.desc(),
                )
            )
        except SQLAlchemyError:
            self._session.rollback()
            raise LearnerModelPersistenceError(
                "learner-model current state could not be read"
            ) from None
        if snapshot is None:
            return None
        return self._hydrate((snapshot,))[0]

    def _hydrate(
        self,
        snapshots: tuple[LearnerModelSnapshotModel, ...] | list[LearnerModelSnapshotModel],
    ) -> tuple[LearnerModelSnapshotView, ...]:
        """Build complete immutable views and fail closed on malformed persisted state."""

        if not snapshots:
            return ()
        snapshot_ids = [snapshot.id for snapshot in snapshots]
        try:
            scope = snapshots[0]
            if any(
                (item.course_id, item.learner_id, item.outcome_id)
                != (scope.course_id, scope.learner_id, scope.outcome_id)
                for item in snapshots
            ):
                raise LearnerModelSafetyError("learner-model hydration scope is inconsistent")
            chain = self._session.scalars(
                select(LearnerModelSnapshotModel)
                .where(
                    LearnerModelSnapshotModel.course_id == scope.course_id,
                    LearnerModelSnapshotModel.learner_id == scope.learner_id,
                    LearnerModelSnapshotModel.outcome_id == scope.outcome_id,
                )
                .order_by(LearnerModelSnapshotModel.record_version)
            ).all()
            estimates = self._session.scalars(
                select(LearnerOutcomeEstimateModel)
                .where(LearnerOutcomeEstimateModel.snapshot_id.in_(snapshot_ids))
                .order_by(
                    LearnerOutcomeEstimateModel.snapshot_id,
                    LearnerOutcomeEstimateModel.dimension,
                    LearnerOutcomeEstimateModel.id,
                )
            ).all()
            estimate_ids = [estimate.id for estimate in estimates]
            links = self._session.scalars(
                select(LearnerModelEvidenceLinkModel)
                .where(LearnerModelEvidenceLinkModel.estimate_id.in_(estimate_ids))
                .order_by(
                    LearnerModelEvidenceLinkModel.estimate_id,
                    LearnerModelEvidenceLinkModel.evidence_id,
                )
            ).all()
            evidence = self._session.scalars(
                select(LearningEvidence).where(
                    LearningEvidence.id.in_([link.evidence_id for link in links])
                )
            ).all()
        except SQLAlchemyError:
            self._session.rollback()
            raise LearnerModelPersistenceError("learner-model history could not be read") from None

        for position, item in enumerate(chain, start=1):
            predecessor = chain[position - 2].id if position > 1 else None
            if item.record_version != position or item.prior_snapshot_id != predecessor:
                raise LearnerModelSafetyError(
                    "stored learner-model predecessor chain is inconsistent"
                )

        evidence_by_id = {item.id: item for item in evidence}
        snapshots_by_id = {item.id: item for item in snapshots}
        estimate_snapshots = {estimate.id: estimate.snapshot_id for estimate in estimates}

        links_by_estimate: dict[str, list[tuple[str, EvidenceLinkRelation]]] = {}
        for link in links:
            snapshot = snapshots_by_id[estimate_snapshots[link.estimate_id]]
            linked_evidence = evidence_by_id.get(link.evidence_id)
            if linked_evidence is None or (
                linked_evidence.course_id,
                linked_evidence.learner_id,
                linked_evidence.outcome_id,
            ) != (snapshot.course_id, snapshot.learner_id, snapshot.outcome_id):
                raise LearnerModelSafetyError("stored learner-model evidence link is out of scope")
            links_by_estimate.setdefault(link.estimate_id, []).append(
                (link.evidence_id, link.relation)
            )
        estimates_by_snapshot: dict[str, list[LearnerOutcomeEstimateView]] = {}
        for estimate in estimates:
            estimate_links = tuple(links_by_estimate.get(estimate.id, ()))
            if not estimate_links or not 0 <= estimate.uncertainty <= 1:
                raise LearnerModelSafetyError("stored learner-model estimate is incomplete")
            estimates_by_snapshot.setdefault(estimate.snapshot_id, []).append(
                LearnerOutcomeEstimateView(
                    estimate_id=estimate.id,
                    dimension=estimate.dimension,
                    inference_status=estimate.inference_status,
                    uncertainty=estimate.uncertainty,
                    reason_code=estimate.reason_code,
                    evidence_observed_at=_as_utc(estimate.evidence_observed_at),
                    evidence_links=estimate_links,
                )
            )

        views: list[LearnerModelSnapshotView] = []
        for snapshot in snapshots:
            if not all(
                (
                    snapshot.course_id,
                    snapshot.learner_id,
                    snapshot.outcome_id,
                    snapshot.schema_version,
                    snapshot.model_version,
                    snapshot.rule_version,
                )
            ):
                raise LearnerModelSafetyError("stored learner-model snapshot is incomplete")
            snapshot_estimates = tuple(estimates_by_snapshot.get(snapshot.id, ()))
            if not snapshot_estimates or len(
                {estimate.dimension for estimate in snapshot_estimates}
            ) != len(snapshot_estimates):
                raise LearnerModelSafetyError("stored learner-model snapshot has invalid estimates")
            validated = False
            classification = (
                "UNVALIDATED_RULE_ESTIMATE"
                if snapshot.model_source is ModelSource.RULE_BASED
                else "UNVALIDATED_MODEL_ESTIMATE"
            )
            views.append(
                LearnerModelSnapshotView(
                    snapshot_id=snapshot.id,
                    prior_snapshot_id=snapshot.prior_snapshot_id,
                    course_id=snapshot.course_id,
                    learner_id=str(snapshot.learner_id),
                    outcome_id=snapshot.outcome_id,
                    record_version=snapshot.record_version,
                    model_source=snapshot.model_source,
                    schema_version=snapshot.schema_version,
                    model_version=snapshot.model_version,
                    rule_version=snapshot.rule_version,
                    occurred_at=_as_utc(snapshot.occurred_at),
                    validated=validated,
                    validation_classification=classification,
                    estimates=tuple(
                        sorted(snapshot_estimates, key=lambda estimate: estimate.dimension.value)
                    ),
                )
            )
        return tuple(views)

    def _validate_prior_snapshot(
        self,
        snapshot: LearnerModelSnapshotPayload,
        learner_id: int,
    ) -> None:
        query = (
            select(LearnerModelSnapshotModel)
            .where(
                LearnerModelSnapshotModel.course_id == snapshot.course_id,
                LearnerModelSnapshotModel.learner_id == learner_id,
                LearnerModelSnapshotModel.outcome_id == snapshot.outcome_id,
            )
            .order_by(
                LearnerModelSnapshotModel.record_version.desc(),
                LearnerModelSnapshotModel.occurred_at.desc(),
                LearnerModelSnapshotModel.created_at.desc(),
                LearnerModelSnapshotModel.id.desc(),
            )
        )
        if self._session.bind and self._session.bind.dialect.name != "sqlite":
            query = query.with_for_update()
        current = self._session.scalar(query)
        if current is None:
            if snapshot.prior_snapshot_id is not None or snapshot.record_version != 1:
                raise LearnerModelConflictError(
                    "learner-model first snapshot must have no predecessor and record version 1"
                )
            return
        if snapshot.prior_snapshot_id != current.id:
            raise LearnerModelConflictError("learner-model predecessor is not the current head")
        if snapshot.record_version != current.record_version + 1:
            raise LearnerModelConflictError(
                "learner-model record version does not follow current head"
            )

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
    "LearnerEvidenceObservation",
    "LearnerModelSnapshotView",
    "LearnerModelSnapshotWriteResult",
    "LearnerOutcomeEstimateView",
    "SqlAlchemyLearnerModelRepository",
]
