"""Transactional repository for append-only Person B learner-model snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
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


class SqlAlchemyLearnerModelRepository:
    """Persist snapshots without importing assessment results or LMS services."""

    def __init__(self, session: Session) -> None:
        self._session = session

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
