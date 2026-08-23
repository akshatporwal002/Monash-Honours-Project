"""Deterministic, review-gated construction of learner-model snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol
from uuid import UUID, uuid5

from app.domain.platform_enums import (
    CorrectionTargetKind,
    EvidenceLinkRelation,
    EvidenceType,
    InferenceStatus,
    LearnerModelDimension,
    ModelSource,
)
from app.services.learner_model.contracts import (
    LearnerModelBuildCommand,
    LearnerModelEvidenceSignal,
    LearnerModelSnapshotPayload,
    LearnerOutcomeEstimatePayload,
)
from app.services.learner_model.repository import (
    AcceptedLearnerModelCorrection,
    LearnerEvidenceObservation,
    LearnerModelSnapshotWriteResult,
    SqlAlchemyLearnerModelRepository,
)
from app.services.learner_model.safety import (
    LearnerModelProviderError,
    LearnerModelReviewRequiredError,
    require_human_review_for_model_source,
)

_ESTIMATE_NAMESPACE = UUID("98a5d0b4-b902-43db-a232-ceafb7a60de1")
_INDEPENDENCE_TYPES = frozenset(
    {EvidenceType.RESPONSE, EvidenceType.REVISION, EvidenceType.REASONING, EvidenceType.TRANSFER}
)


class LearnerModelBuildState(str, Enum):
    STORED = "stored"
    NO_INFERENCE = "no_inference"
    REVIEW_REQUIRED = "review_required"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


@dataclass(frozen=True, slots=True)
class LearnerModelBuildResult:
    state: LearnerModelBuildState
    snapshot: LearnerModelSnapshotWriteResult | None = None


class LearnerModelAdapter(Protocol):
    """Versioned provider boundary; non-rule implementations require review."""

    model_version: str

    def build(
        self,
        command: LearnerModelBuildCommand,
        observations: tuple[LearnerEvidenceObservation, ...],
    ) -> LearnerModelSnapshotPayload | None: ...


class DeterministicLearnerModelBuilder:
    """Rules that require linked evidence and retain uncertainty by construction."""

    model_version = "learner-model-rules.v1"

    def build(
        self,
        command: LearnerModelBuildCommand,
        observations: tuple[LearnerEvidenceObservation, ...],
    ) -> LearnerModelSnapshotPayload | None:
        if command.model_source is not ModelSource.RULE_BASED:
            raise LearnerModelProviderError("deterministic builder cannot serve a non-rule source")
        if command.model_version != self.model_version:
            raise LearnerModelProviderError(
                "deterministic builder version does not match the command"
            )
        estimates = tuple(_estimates(command, observations))
        if not estimates:
            return None
        return LearnerModelSnapshotPayload(
            snapshot_id=command.snapshot_id,
            course_id=command.course_id,
            learner_id=command.learner_id,
            outcome_id=command.outcome_id,
            prior_snapshot_id=command.prior_snapshot_id,
            model_source=command.model_source,
            model_version=command.model_version,
            rule_version=command.rule_version,
            record_version=command.record_version,
            actor_reference=command.actor_reference,
            agent_reference=command.agent_reference,
            correlation_id=command.correlation_id,
            idempotency_key=command.idempotency_key,
            occurred_at=command.occurred_at,
            estimates=estimates,
        )


class LearnerModelBuildService:
    """Ensure a provider failure cannot mutate accepted evidence or old snapshots."""

    def __init__(
        self,
        repository: SqlAlchemyLearnerModelRepository,
        builder: LearnerModelAdapter,
    ) -> None:
        self._repository = repository
        self._builder = builder

    def build(self, command: LearnerModelBuildCommand) -> LearnerModelBuildResult:
        try:
            require_human_review_for_model_source(
                command.model_source,
                command.reviewed_by_reference,
            )
        except LearnerModelReviewRequiredError:
            return LearnerModelBuildResult(LearnerModelBuildState.REVIEW_REQUIRED)
        observations = self._repository.observations(command)
        correction_state = self._repository.correction_state(command)
        try:
            payload = self._builder.build(command, observations)
        except Exception:
            # Provider exceptions are never allowed to create a partial inference;
            # the caller can surface this bounded state while evidence remains durable.
            return LearnerModelBuildResult(LearnerModelBuildState.PROVIDER_UNAVAILABLE)
        if payload is None:
            return LearnerModelBuildResult(LearnerModelBuildState.NO_INFERENCE)
        corrected_payload, applied_review_ids = _apply_accepted_corrections(
            payload,
            correction_state.accepted,
        )
        return LearnerModelBuildResult(
            LearnerModelBuildState.STORED,
            snapshot=self._repository.store(
                corrected_payload,
                correction_state=correction_state,
                applied_correction_review_ids=applied_review_ids,
            ),
        )


def _apply_accepted_corrections(
    payload: LearnerModelSnapshotPayload,
    corrections: tuple[AcceptedLearnerModelCorrection, ...],
) -> tuple[LearnerModelSnapshotPayload, frozenset[str]]:
    """Mark affected new estimates for review without mutating source evidence or history."""

    estimates: list[LearnerOutcomeEstimatePayload] = []
    applied_review_ids: set[str] = set()
    for estimate in payload.estimates:
        evidence_ids = {signal.evidence_id for signal in estimate.evidence_signals}
        affecting = tuple(
            correction
            for correction in corrections
            if (
                correction.annotation.target.target_kind is CorrectionTargetKind.EVIDENCE
                and correction.annotation.target.evidence_id in evidence_ids
            )
            or (
                correction.annotation.target.target_kind is CorrectionTargetKind.ESTIMATE
                and correction.target_dimension is estimate.dimension
            )
        )
        if not affecting:
            estimates.append(estimate)
            continue
        applied_review_ids.update(correction.review.review_id for correction in affecting)
        estimates.append(
            LearnerOutcomeEstimatePayload(
                estimate_id=estimate.estimate_id,
                dimension=estimate.dimension,
                inference_status=InferenceStatus.NEEDS_REVIEW,
                uncertainty=max(estimate.uncertainty, 0.8),
                reason_code="correction.accepted-review.v1",
                evidence_observed_at=estimate.evidence_observed_at,
                evidence_signals=estimate.evidence_signals,
            )
        )
    return (
        payload.model_copy(update={"estimates": tuple(estimates)}),
        frozenset(applied_review_ids),
    )


def _estimates(
    command: LearnerModelBuildCommand,
    observations: tuple[LearnerEvidenceObservation, ...],
) -> list[LearnerOutcomeEstimatePayload]:
    estimates: list[LearnerOutcomeEstimatePayload] = []
    by_type: dict[EvidenceType, list[LearnerEvidenceObservation]] = {}
    for observation in observations:
        by_type.setdefault(observation.evidence_type, []).append(observation)

    _append_estimate(
        estimates,
        command,
        LearnerModelDimension.PRIOR_KNOWLEDGE,
        by_type.get(EvidenceType.PREDICTION, ()),
    )
    reasoning = by_type.get(EvidenceType.REASONING, ())
    if reasoning:
        dimension = (
            LearnerModelDimension.REASONING_STRENGTH
            if any(item.relation is EvidenceLinkRelation.SUPPORTS for item in reasoning)
            else LearnerModelDimension.REASONING_GAP
        )
        _append_estimate(estimates, command, dimension, reasoning)
    _append_estimate(
        estimates,
        command,
        LearnerModelDimension.CONFIDENCE_CALIBRATION,
        by_type.get(EvidenceType.CONFIDENCE, ()),
    )
    _append_estimate(
        estimates,
        command,
        LearnerModelDimension.FEEDBACK_USE,
        by_type.get(EvidenceType.FEEDBACK_INTERACTION, ()),
    )
    _append_estimate(
        estimates,
        command,
        LearnerModelDimension.SCAFFOLD_DEPENDENCE,
        tuple(by_type.get(EvidenceType.HINT, ())) + tuple(by_type.get(EvidenceType.SCAFFOLD, ())),
    )
    _append_estimate(
        estimates,
        command,
        LearnerModelDimension.TRANSFER,
        by_type.get(EvidenceType.TRANSFER, ()),
    )
    _append_estimate(
        estimates,
        command,
        LearnerModelDimension.POSSIBLE_MISCONCEPTION,
        by_type.get(EvidenceType.MISCONCEPTION_CHECK, ()),
        require_two_supporting_signals=True,
    )
    independent = tuple(
        observation
        for evidence_type in _INDEPENDENCE_TYPES
        for observation in by_type.get(evidence_type, ())
        if observation.instructional_support_level == 0
    )
    _append_estimate(
        estimates,
        command,
        LearnerModelDimension.INDEPENDENCE,
        independent,
        require_two_supporting_signals=True,
    )
    return estimates


def _append_estimate(
    estimates: list[LearnerOutcomeEstimatePayload],
    command: LearnerModelBuildCommand,
    dimension: LearnerModelDimension,
    observations: tuple[LearnerEvidenceObservation, ...] | list[LearnerEvidenceObservation],
    *,
    require_two_supporting_signals: bool = False,
) -> None:
    if not observations:
        return
    evidence_signals = tuple(
        LearnerModelEvidenceSignal(evidence_id=item.evidence_id, relation=item.relation)
        for item in observations
    )
    supporting = sum(item.relation is EvidenceLinkRelation.SUPPORTS for item in observations)
    contradicting = sum(item.relation is EvidenceLinkRelation.CONTRADICTS for item in observations)
    if require_two_supporting_signals and supporting < 2:
        status, uncertainty = InferenceStatus.UNCERTAIN, 0.8
    elif supporting and not contradicting:
        status, uncertainty = InferenceStatus.SUPPORTED, (0.4 if supporting > 1 else 0.7)
    elif contradicting and not supporting:
        status, uncertainty = InferenceStatus.CONTRADICTED, (0.4 if contradicting > 1 else 0.7)
    else:
        status, uncertainty = InferenceStatus.UNCERTAIN, 0.8
    estimates.append(
        LearnerOutcomeEstimatePayload(
            estimate_id=str(uuid5(_ESTIMATE_NAMESPACE, f"{command.snapshot_id}:{dimension.value}")),
            dimension=dimension,
            inference_status=status,
            uncertainty=uncertainty,
            reason_code=f"rule.{dimension.value.casefold()}.v1",
            evidence_observed_at=max(item.occurred_at for item in observations),
            evidence_signals=evidence_signals,
        )
    )


__all__ = [
    "DeterministicLearnerModelBuilder",
    "LearnerModelAdapter",
    "LearnerModelBuildResult",
    "LearnerModelBuildService",
    "LearnerModelBuildState",
]
