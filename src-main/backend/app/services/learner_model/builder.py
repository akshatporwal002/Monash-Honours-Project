"""Deterministic, review-gated construction of learner-model snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol
from uuid import UUID, uuid5

from app.domain.platform_enums import (
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
    LearnerModelUpdateCommand,
    LearnerOutcomeEstimatePayload,
)
from app.services.learner_model.correction_repository import (
    SqlAlchemyLearnerModelCorrectionRepository,
)
from app.services.learner_model.repository import (
    LearnerEvidenceObservation,
    LearnerModelSnapshotView,
    LearnerModelSnapshotWriteResult,
    SqlAlchemyLearnerModelRepository,
)
from app.services.learner_model.safety import (
    LearnerModelConflictError,
    LearnerModelProviderError,
    LearnerModelReviewRequiredError,
    require_human_review_for_model_source,
    require_trusted_adjudication,
)

_ESTIMATE_NAMESPACE = UUID("98a5d0b4-b902-43db-a232-ceafb7a60de1")
_SNAPSHOT_NAMESPACE = UUID("d8c8293e-2a9b-43a5-a8a6-64d3d7aa5ca0")


@dataclass(frozen=True, slots=True)
class EvidenceRule:
    """Versioned, non-diagnostic meaning assigned to one evidence type."""

    evidence_type: EvidenceType
    dimension: LearnerModelDimension
    minimum_supporting_signals: int = 1
    required_context_types: frozenset[EvidenceType] = frozenset()


# Evidence is an observation, not a teaching decision.  In particular, acknowledgement
# and transfer events remain excluded until a trusted adjudication can establish the
# required revision/response behaviour.  Access support is deliberately not a rule input.
_RULE_TABLE = (
    EvidenceRule(EvidenceType.PREDICTION, LearnerModelDimension.PRIOR_KNOWLEDGE),
    EvidenceRule(EvidenceType.REASONING, LearnerModelDimension.REASONING_STRENGTH),
    EvidenceRule(EvidenceType.CONFIDENCE, LearnerModelDimension.CONFIDENCE_CALIBRATION),
    EvidenceRule(EvidenceType.HINT, LearnerModelDimension.SCAFFOLD_DEPENDENCE),
    EvidenceRule(EvidenceType.SCAFFOLD, LearnerModelDimension.SCAFFOLD_DEPENDENCE),
    EvidenceRule(
        EvidenceType.FEEDBACK_INTERACTION,
        LearnerModelDimension.FEEDBACK_USE,
        required_context_types=frozenset({EvidenceType.REVISION}),
    ),
    EvidenceRule(
        EvidenceType.TRANSFER,
        LearnerModelDimension.TRANSFER,
        required_context_types=frozenset({EvidenceType.REASONING}),
    ),
    EvidenceRule(
        EvidenceType.MISCONCEPTION_CHECK,
        LearnerModelDimension.POSSIBLE_MISCONCEPTION,
        minimum_supporting_signals=2,
    ),
    EvidenceRule(
        EvidenceType.RESPONSE,
        LearnerModelDimension.INDEPENDENCE,
        minimum_supporting_signals=2,
    ),
    EvidenceRule(
        EvidenceType.REVISION,
        LearnerModelDimension.INDEPENDENCE,
        minimum_supporting_signals=2,
    ),
    EvidenceRule(
        EvidenceType.REASONING,
        LearnerModelDimension.INDEPENDENCE,
        minimum_supporting_signals=2,
    ),
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
    view: LearnerModelSnapshotView | None = None


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
        corrections: SqlAlchemyLearnerModelCorrectionRepository | None = None,
    ) -> None:
        self._repository = repository
        self._builder = builder
        self._corrections = corrections

    def _build(self, command: LearnerModelBuildCommand) -> LearnerModelBuildResult:
        """Internal payload seam retained for focused repository/provider tests only."""
        try:
            require_human_review_for_model_source(
                command.model_source,
                command.reviewed_by_reference,
            )
        except LearnerModelReviewRequiredError:
            return LearnerModelBuildResult(LearnerModelBuildState.REVIEW_REQUIRED)
        observations = self._repository.observations(command)
        try:
            payload = self._builder.build(command, observations)
        except Exception:
            # Provider exceptions are never allowed to create a partial inference;
            # the caller can surface this bounded state while evidence remains durable.
            return LearnerModelBuildResult(LearnerModelBuildState.PROVIDER_UNAVAILABLE)
        if payload is None:
            return LearnerModelBuildResult(LearnerModelBuildState.NO_INFERENCE)
        return LearnerModelBuildResult(
            LearnerModelBuildState.STORED,
            snapshot=self._repository.store(payload),
        )

    def update(
        self, command: LearnerModelUpdateCommand, *, include_view: bool = True
    ) -> LearnerModelBuildResult:
        """Append cumulative state, optionally omitting the caller's unused teaching view."""

        if not isinstance(command, LearnerModelUpdateCommand):
            raise TypeError("learner-model updates require the scoped update command")
        for attempt in range(2):
            try:
                return self._update_once(command, include_view=include_view)
            except LearnerModelConflictError as error:
                if attempt or not _is_retryable_head_conflict(error):
                    raise
        raise AssertionError("bounded learner-model retry must return or raise")

    def _update_once(
        self, command: LearnerModelUpdateCommand, *, include_view: bool = True
    ) -> LearnerModelBuildResult:
        require_trusted_adjudication(
            command.model_source,
            command.adjudicator_reference,
            command.adjudication_rule_version,
            command.rule_version,
        )
        try:
            require_human_review_for_model_source(
                command.model_source,
                command.reviewed_by_reference,
            )
        except LearnerModelReviewRequiredError:
            return LearnerModelBuildResult(LearnerModelBuildState.REVIEW_REQUIRED)
        incoming = self._repository.observations(command)
        head = self._repository.current(
            course_id=command.course_id,
            learner_id=command.learner_id,
            outcome_id=command.outcome_id,
        )
        relations = _merge_relations(head, incoming)
        accepted = (
            ()
            if self._corrections is None
            else self._corrections.accepted_targets(
                course_id=command.course_id,
                learner_id=command.learner_id,
                outcome_id=command.outcome_id,
                evidence_ids=tuple(evidence_id for evidence_id, _ in relations),
                snapshot_id=None if head is None else head.snapshot_id,
            )
        )
        if head is not None and relations == _view_relations(head) and not accepted:
            return LearnerModelBuildResult(
                LearnerModelBuildState.STORED,
                snapshot=LearnerModelSnapshotWriteResult(
                    snapshot_id=head.snapshot_id,
                    created=False,
                    occurred_at=head.occurred_at,
                ),
                view=head if include_view else None,
            )
        cumulative_signals = tuple(
            LearnerModelEvidenceSignal(evidence_id=evidence_id, relation=relation)
            for evidence_id, relation in relations
        )
        snapshot_id = _snapshot_identity(
            command,
            head,
            relations,
            accepted_review_ids=tuple(item.review_id for item in accepted),
        )
        observations = self._repository.observations(
            LearnerModelBuildCommand(
                snapshot_id=snapshot_id,
                course_id=command.course_id,
                learner_id=command.learner_id,
                outcome_id=command.outcome_id,
                prior_snapshot_id=head.snapshot_id if head else None,
                model_source=command.model_source,
                model_version=command.model_version,
                rule_version=command.rule_version,
                record_version=(head.record_version + 1) if head else 1,
                actor_reference=command.actor_reference,
                agent_reference=command.agent_reference,
                correlation_id=command.correlation_id,
                idempotency_key=snapshot_id,
                occurred_at=max(item.occurred_at for item in incoming),
                evidence_signals=cumulative_signals,
            )
        )
        cumulative_command = LearnerModelBuildCommand(
            snapshot_id=snapshot_id,
            course_id=command.course_id,
            learner_id=command.learner_id,
            outcome_id=command.outcome_id,
            prior_snapshot_id=head.snapshot_id if head else None,
            model_source=command.model_source,
            model_version=command.model_version,
            rule_version=command.rule_version,
            record_version=(head.record_version + 1) if head else 1,
            actor_reference=command.actor_reference,
            agent_reference=command.agent_reference,
            correlation_id=command.correlation_id,
            idempotency_key=snapshot_id,
            occurred_at=max(item.occurred_at for item in observations),
            evidence_signals=cumulative_signals,
        )
        try:
            reviewed_ids = {
                key
                for item in (head.estimates if head else ())
                if item.reason_code.startswith("reviewed-profile.")
                for key, _ in item.evidence_links
            }
            rule_ids = {item.evidence_id for item in incoming} | {
                key
                for item in (head.estimates if head else ())
                if not item.reason_code.startswith("reviewed-profile.")
                for key, _ in item.evidence_links
            }
            # A human relation about one dimension is not a rule adjudication of
            # every other dimension that happens to consume that evidence type.
            rule_observations = tuple(
                item for item in observations if item.evidence_id not in reviewed_ids - rule_ids
            )
            payload = self._builder.build(cumulative_command, rule_observations)
        except Exception:
            return LearnerModelBuildResult(LearnerModelBuildState.PROVIDER_UNAVAILABLE)
        if payload is None:
            return LearnerModelBuildResult(LearnerModelBuildState.NO_INFERENCE)
        if head:
            # New rule observations cannot silently replace an educator's scoped
            # interpretation. Retain its evidence time and uncertainty; the prior
            # snapshot chain preserves who made that review.
            reviewed = [
                item for item in head.estimates if item.reason_code.startswith("reviewed-profile.")
            ]
            dimensions = {item.dimension for item in reviewed}
            retained = tuple(
                LearnerOutcomeEstimatePayload(
                    estimate_id=str(
                        uuid5(_ESTIMATE_NAMESPACE, f"{payload.snapshot_id}:{item.dimension.value}")
                    ),
                    dimension=item.dimension,
                    inference_status=item.inference_status,
                    uncertainty=item.uncertainty,
                    reason_code=item.reason_code,
                    evidence_observed_at=item.evidence_observed_at,
                    evidence_signals=tuple(
                        LearnerModelEvidenceSignal(evidence_id=key, relation=relation)
                        for key, relation in item.evidence_links
                    ),
                )
                for item in reviewed
            )
            payload = payload.model_copy(
                update={
                    "estimates": tuple(
                        item for item in payload.estimates if item.dimension not in dimensions
                    )
                    + retained,
                    "occurred_at": max(payload.occurred_at, head.occurred_at),
                }
            )
        if accepted:
            affected = {item.dimension for item in accepted if item.dimension is not None}
            payload = payload.model_copy(
                update={
                    "estimates": tuple(
                        estimate.model_copy(
                            update={"inference_status": InferenceStatus.NEEDS_REVIEW}
                        )
                        if estimate.dimension.value in affected
                        else estimate
                        for estimate in payload.estimates
                    )
                }
            )
        _require_dimension_continuity(head, payload)
        stored = (
            self._repository.store(
                payload,
                accepted_review_ids=tuple(item.review_id for item in accepted),
            )
            if accepted
            else self._repository.store(payload)
        )
        return LearnerModelBuildResult(
            LearnerModelBuildState.STORED,
            snapshot=stored,
            view=(
                self._repository.current(
                    course_id=command.course_id,
                    learner_id=command.learner_id,
                    outcome_id=command.outcome_id,
                )
                if include_view
                else None
            ),
        )


def _view_relations(head) -> tuple[tuple[str, EvidenceLinkRelation], ...]:
    relations: dict[str, EvidenceLinkRelation] = {}
    for estimate in head.estimates:
        for evidence_id, relation in estimate.evidence_links:
            previous = relations.setdefault(evidence_id, relation)
            if previous is not relation:
                raise LearnerModelProviderError(
                    "stored evidence has conflicting learner-model relations"
                )
    return tuple(sorted(relations.items()))


def _merge_relations(
    head,
    incoming: tuple[LearnerEvidenceObservation, ...],
) -> tuple[tuple[str, EvidenceLinkRelation], ...]:
    relations = dict(_view_relations(head)) if head is not None else {}
    for observation in incoming:
        previous = relations.setdefault(observation.evidence_id, observation.relation)
        if previous is not observation.relation:
            raise LearnerModelProviderError(
                "evidence cannot be reclassified in learner-model history"
            )
    return tuple(sorted(relations.items()))


def _snapshot_identity(
    command,
    head,
    relations: tuple[tuple[str, EvidenceLinkRelation], ...],
    *,
    accepted_review_ids: tuple[str, ...] = (),
) -> str:
    predecessor = head.snapshot_id if head else "first"
    logical_input = "|".join(
        (
            command.course_id,
            command.learner_id,
            command.outcome_id,
            predecessor,
            command.model_source.value,
            command.model_version,
            command.rule_version,
            *(
                f"{dimension.value}:{evidence_id}:{relation.value}"
                for dimension, evidence_id, relation in _view_dimension_relations(head)
            ),
            *(f"{evidence_id}:{relation.value}" for evidence_id, relation in relations),
            *(f"accepted-review:{review_id}" for review_id in sorted(set(accepted_review_ids))),
        )
    )
    return str(uuid5(_SNAPSHOT_NAMESPACE, logical_input))


def _view_dimension_relations(
    head,
) -> tuple[tuple[LearnerModelDimension, str, EvidenceLinkRelation], ...]:
    if head is None:
        return ()
    return tuple(
        sorted(
            (
                (estimate.dimension, evidence_id, relation)
                for estimate in head.estimates
                for evidence_id, relation in estimate.evidence_links
            ),
            key=lambda item: (item[0].value, item[1], item[2].value),
        )
    )


def _require_dimension_continuity(head, payload: LearnerModelSnapshotPayload) -> None:
    """Never silently rewrite an inherited evidence item's dimension meaning."""

    if head is None:
        return
    historical: dict[str, set[LearnerModelDimension]] = {}
    for dimension, evidence_id, _ in _view_dimension_relations(head):
        historical.setdefault(evidence_id, set()).add(dimension)
    candidate: dict[str, set[LearnerModelDimension]] = {}
    for estimate in payload.estimates:
        for signal in estimate.evidence_signals:
            candidate.setdefault(signal.evidence_id, set()).add(estimate.dimension)
    for evidence_id, previous_dimensions in historical.items():
        next_dimensions = candidate.get(evidence_id, set())
        if not previous_dimensions <= next_dimensions:
            raise LearnerModelConflictError(
                "learner-model evidence cannot be reassigned to an incompatible dimension"
            )


def _is_retryable_head_conflict(error: LearnerModelConflictError) -> bool:
    """Only a concurrent head transition merits rebuilding the deterministic proposal."""

    return str(error).startswith(
        (
            "learner-model predecessor is not the current head",
            "learner-model record version does not follow current head",
            "learner-model first snapshot must have no predecessor",
        )
    )


def _estimates(
    command: LearnerModelBuildCommand,
    observations: tuple[LearnerEvidenceObservation, ...],
) -> list[LearnerOutcomeEstimatePayload]:
    estimates: list[LearnerOutcomeEstimatePayload] = []
    for dimension in sorted({rule.dimension for rule in _RULE_TABLE}, key=lambda item: item.value):
        rules = tuple(rule for rule in _RULE_TABLE if rule.dimension is dimension)
        eligible_types = {rule.evidence_type for rule in rules}
        observed_types = {observation.evidence_type for observation in observations}
        context_types = frozenset().union(*(rule.required_context_types for rule in rules))
        if context_types and not context_types <= observed_types:
            continue
        eligible = tuple(
            observation
            for observation in observations
            if observation.evidence_type in eligible_types | context_types
            and (
                dimension is not LearnerModelDimension.INDEPENDENCE
                or observation.instructional_support_level == 0
            )
        )
        if eligible:
            _append_estimate(
                estimates,
                command,
                dimension,
                eligible,
                minimum_supporting_signals=max(rule.minimum_supporting_signals for rule in rules),
            )
    return estimates


def _append_estimate(
    estimates: list[LearnerOutcomeEstimatePayload],
    command: LearnerModelBuildCommand,
    dimension: LearnerModelDimension,
    observations: tuple[LearnerEvidenceObservation, ...] | list[LearnerEvidenceObservation],
    *,
    minimum_supporting_signals: int = 1,
) -> None:
    if not observations:
        return
    evidence_signals = tuple(
        LearnerModelEvidenceSignal(evidence_id=item.evidence_id, relation=item.relation)
        for item in observations
    )
    supporting = sum(item.relation is EvidenceLinkRelation.SUPPORTS for item in observations)
    contradicting = sum(item.relation is EvidenceLinkRelation.CONTRADICTS for item in observations)
    if supporting and supporting < minimum_supporting_signals:
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
