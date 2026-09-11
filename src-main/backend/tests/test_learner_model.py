"""Deterministic and append-only proof for Person B learner-model snapshots."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from test_evidence_repository import NOW, _record, _seed_scope

from app.db.session import create_session_factory
from app.domain.platform_enums import (
    AccessSupportState,
    EvidenceLinkRelation,
    EvidenceType,
    InferenceStatus,
    LearnerModelDimension,
    ModelSource,
)
from app.models.learner_model import (
    LearnerModelEvidenceLink,
    LearnerModelSnapshot,
    LearnerOutcomeEstimate,
)
from app.models.learning_evidence import LearningEvidence
from app.services.evidence.repository import EvidenceCapture, SqlAlchemyEvidenceRepository
from app.services.learner_model.builder import (
    DeterministicLearnerModelBuilder,
    LearnerModelBuildService,
    LearnerModelBuildState,
)
from app.services.learner_model.contracts import (
    LearnerModelBuildCommand,
    LearnerModelEvidenceSignal,
    LearnerModelUpdateCommand,
)
from app.services.learner_model.repository import SqlAlchemyLearnerModelRepository
from app.services.learner_model.safety import (
    LearnerModelConflictError,
    LearnerModelSafetyError,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _store_evidence(
    session: Session,
    scope: dict[str, str],
    *,
    evidence_id: str,
    evidence_type: EvidenceType,
    occurred_at=NOW,
    instructional_support_level: int = 0,
    access_support_state: AccessSupportState = AccessSupportState.NOT_DECLARED,
) -> None:
    SqlAlchemyEvidenceRepository(session).capture(
        EvidenceCapture(
            record=_record(
                scope,
                evidence_id=evidence_id,
                evidence_type=evidence_type,
                artifact_id=None,
                idempotency_key=f"key-{evidence_id}",
                source_interaction_id=f"source-{evidence_id}",
                occurred_at=occurred_at,
                instructional_support_level=instructional_support_level,
                access_support_state=access_support_state,
            )
        )
    )


def _command(
    scope: dict[str, str],
    signals: tuple[LearnerModelEvidenceSignal, ...],
    **overrides: object,
) -> LearnerModelBuildCommand:
    values: dict[str, object] = {
        "snapshot_id": "learner-snapshot-1",
        "course_id": scope["course_one"],
        "learner_id": scope["learner_id"],
        "outcome_id": scope["outcome_one"],
        "model_source": ModelSource.RULE_BASED,
        "model_version": "learner-model-rules.v1",
        "rule_version": "learner-rules.v1",
        "record_version": 1,
        "actor_reference": scope["actor_reference"],
        "agent_reference": "learner-model-agent.v1",
        "correlation_id": "learner-model-correlation-1",
        "idempotency_key": "learner-model-key-1",
        "occurred_at": NOW + timedelta(hours=1),
        "evidence_signals": signals,
    }
    values.update(overrides)
    return LearnerModelBuildCommand.model_validate(values)


def _update_command(
    scope: dict[str, str],
    signals: tuple[LearnerModelEvidenceSignal, ...],
    **overrides: object,
) -> LearnerModelUpdateCommand:
    values: dict[str, object] = {
        "course_id": scope["course_one"],
        "learner_id": scope["learner_id"],
        "outcome_id": scope["outcome_one"],
        "model_source": ModelSource.RULE_BASED,
        "model_version": "learner-model-rules.v1",
        "rule_version": "learner-rules.v1",
        "actor_reference": scope["actor_reference"],
        "agent_reference": "learner-model-agent.v1",
        "adjudicator_reference": "learner-model-rule-engine.v1",
        "adjudication_rule_version": "learner-rules.v1",
        "correlation_id": "learner-model-correlation-1",
        "evidence_signals": signals,
    }
    values.update(overrides)
    return LearnerModelUpdateCommand.model_validate(values)


def _service(session: Session, builder=None) -> LearnerModelBuildService:
    return LearnerModelBuildService(
        SqlAlchemyLearnerModelRepository(session),
        builder or DeterministicLearnerModelBuilder(),
    )


def test_update_command_rejects_caller_control_of_persistence_identity(
    db_session: Session,
) -> None:
    scope = _seed_scope(db_session)
    with pytest.raises(ValueError, match="Extra inputs"):
        _update_command(
            scope,
            (
                LearnerModelEvidenceSignal(
                    evidence_id="unused-evidence", relation=EvidenceLinkRelation.SUPPORTS
                ),
            ),
            snapshot_id="caller-controlled-snapshot",
        )


@pytest.mark.parametrize("missing_field", ("adjudicator_reference", "adjudication_rule_version"))
def test_update_command_requires_a_versioned_trusted_adjudication_source(
    db_session: Session,
    missing_field: str,
) -> None:
    scope = _seed_scope(db_session)
    values = _update_command(
        scope,
        (
            LearnerModelEvidenceSignal(
                evidence_id="unused-evidence", relation=EvidenceLinkRelation.SUPPORTS
            ),
        ),
    ).model_dump()
    del values[missing_field]

    with pytest.raises(ValueError, match="Field required"):
        LearnerModelUpdateCommand.model_validate(values)


def test_update_rejects_an_unregistered_adjudicator(db_session: Session) -> None:
    scope = _seed_scope(db_session)
    _store_evidence(
        db_session, scope, evidence_id="prediction-1", evidence_type=EvidenceType.PREDICTION
    )
    with pytest.raises(LearnerModelSafetyError, match="not authorized"):
        _service(db_session).update(
            _update_command(
                scope,
                (
                    LearnerModelEvidenceSignal(
                        evidence_id="prediction-1", relation=EvidenceLinkRelation.SUPPORTS
                    ),
                ),
                adjudicator_reference="untrusted-client",
            )
        )


def test_rules_build_reproducible_linked_snapshot_and_keep_single_weak_signal_uncertain(
    db_session: Session,
) -> None:
    scope = _seed_scope(db_session)
    evidence = (
        ("prediction-1", EvidenceType.PREDICTION, EvidenceLinkRelation.SUPPORTS, 0),
        ("reasoning-1", EvidenceType.REASONING, EvidenceLinkRelation.SUPPORTS, 0),
        ("confidence-1", EvidenceType.CONFIDENCE, EvidenceLinkRelation.SUPPORTS, 0),
        ("hint-1", EvidenceType.HINT, EvidenceLinkRelation.SUPPORTS, 2),
        ("response-1", EvidenceType.RESPONSE, EvidenceLinkRelation.SUPPORTS, 0),
        ("revision-1", EvidenceType.REVISION, EvidenceLinkRelation.SUPPORTS, 0),
        ("misconception-1", EvidenceType.MISCONCEPTION_CHECK, EvidenceLinkRelation.SUPPORTS, 0),
    )
    for position, (evidence_id, evidence_type, _, support_level) in enumerate(evidence):
        _store_evidence(
            db_session,
            scope,
            evidence_id=evidence_id,
            evidence_type=evidence_type,
            occurred_at=NOW + timedelta(minutes=position),
            instructional_support_level=support_level,
        )
    signals = tuple(
        LearnerModelEvidenceSignal(evidence_id=evidence_id, relation=relation)
        for evidence_id, _, relation, _ in evidence
    )

    created = _service(db_session)._build(_command(scope, signals))
    replayed = _service(db_session)._build(_command(scope, signals))

    assert created.state is LearnerModelBuildState.STORED
    assert created.snapshot is not None and created.snapshot.created is True
    assert replayed.snapshot is not None and replayed.snapshot.created is False
    timeline = SqlAlchemyLearnerModelRepository(db_session).timeline(
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )
    assert len(timeline) == 1
    assert timeline[0].schema_version == "learnlens.learner-model-snapshot.v1"
    estimates = {estimate.dimension: estimate for estimate in timeline[0].estimates}
    assert estimates[LearnerModelDimension.REASONING_STRENGTH].inference_status is (
        InferenceStatus.SUPPORTED
    )
    assert estimates[LearnerModelDimension.INDEPENDENCE].inference_status is (
        InferenceStatus.SUPPORTED
    )
    possible_misconception = estimates[LearnerModelDimension.POSSIBLE_MISCONCEPTION]
    assert possible_misconception.inference_status is InferenceStatus.UNCERTAIN
    assert possible_misconception.uncertainty == 0.8
    assert possible_misconception.evidence_ids == ("misconception-1",)


def test_current_teaching_view_exposes_complete_unvalidated_rule_snapshot(
    db_session: Session,
) -> None:
    """Teaching services consume complete provenance, never ORM rows or a status alone."""

    scope = _seed_scope(db_session)
    _store_evidence(
        db_session,
        scope,
        evidence_id="prediction-1",
        evidence_type=EvidenceType.PREDICTION,
        occurred_at=NOW,
    )
    _store_evidence(
        db_session,
        scope,
        evidence_id="reasoning-1",
        evidence_type=EvidenceType.REASONING,
        occurred_at=NOW + timedelta(minutes=1),
    )
    _service(db_session)._build(
        _command(
            scope,
            (
                LearnerModelEvidenceSignal(
                    evidence_id="prediction-1", relation=EvidenceLinkRelation.SUPPORTS
                ),
                LearnerModelEvidenceSignal(
                    evidence_id="reasoning-1", relation=EvidenceLinkRelation.CONTRADICTS
                ),
            ),
        )
    )

    view = SqlAlchemyLearnerModelRepository(db_session).current(
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )

    assert view is not None
    assert (
        view.snapshot_id,
        view.prior_snapshot_id,
        view.course_id,
        view.learner_id,
        view.outcome_id,
        view.record_version,
        view.model_source,
        view.schema_version,
        view.model_version,
        view.rule_version,
        view.occurred_at,
        view.validated,
        view.validation_classification,
    ) == (
        "learner-snapshot-1",
        None,
        scope["course_one"],
        scope["learner_id"],
        scope["outcome_one"],
        1,
        ModelSource.RULE_BASED,
        "learnlens.learner-model-snapshot.v1",
        "learner-model-rules.v1",
        "learner-rules.v1",
        NOW + timedelta(hours=1),
        False,
        "UNVALIDATED_RULE_ESTIMATE",
    )
    assert [estimate.dimension for estimate in view.estimates] == sorted(
        (estimate.dimension for estimate in view.estimates), key=lambda dimension: dimension.value
    )
    reasoning = next(
        estimate
        for estimate in view.estimates
        if estimate.dimension is LearnerModelDimension.REASONING_STRENGTH
    )
    assert (
        reasoning.estimate_id,
        reasoning.inference_status,
        reasoning.uncertainty,
        reasoning.reason_code,
        reasoning.evidence_observed_at,
        reasoning.evidence_links,
    ) == (
        "3ad1b946-011c-518b-97a3-ed09436ca3c1",
        InferenceStatus.CONTRADICTED,
        0.7,
        "rule.reasoning_strength.v1",
        NOW + timedelta(minutes=1),
        (("reasoning-1", EvidenceLinkRelation.CONTRADICTS),),
    )


def test_current_fails_closed_for_a_persisted_snapshot_without_estimates(
    db_session: Session,
) -> None:
    scope = _seed_scope(db_session)
    db_session.add(
        LearnerModelSnapshot(
            id="malformed-snapshot",
            course_id=scope["course_one"],
            learner_id=int(scope["learner_id"]),
            outcome_id=scope["outcome_one"],
            prior_snapshot_id=None,
            model_source=ModelSource.RULE_BASED,
            schema_version="learnlens.learner-model-snapshot.v1",
            model_version="learner-model-rules.v1",
            rule_version="learner-rules.v1",
            record_version=1,
            actor_reference=scope["actor_reference"],
            agent_reference="learner-model-agent.v1",
            correlation_id="malformed-correlation",
            idempotency_key="malformed-key",
            occurred_at=NOW,
        )
    )
    db_session.commit()

    with pytest.raises(LearnerModelSafetyError, match="invalid estimates"):
        SqlAlchemyLearnerModelRepository(db_session).current(
            course_id=scope["course_one"],
            learner_id=scope["learner_id"],
            outcome_id=scope["outcome_one"],
        )


def test_current_fails_closed_for_a_broken_persisted_predecessor_chain(
    db_session: Session,
) -> None:
    scope = _seed_scope(db_session)
    db_session.add(
        LearnerModelSnapshot(
            id="broken-chain-snapshot",
            course_id=scope["course_one"],
            learner_id=int(scope["learner_id"]),
            outcome_id=scope["outcome_one"],
            prior_snapshot_id="missing-predecessor",
            model_source=ModelSource.RULE_BASED,
            schema_version="learnlens.learner-model-snapshot.v1",
            model_version="learner-model-rules.v1",
            rule_version="learner-rules.v1",
            record_version=1,
            actor_reference=scope["actor_reference"],
            agent_reference="learner-model-agent.v1",
            correlation_id="broken-chain-correlation",
            idempotency_key="broken-chain-key",
            occurred_at=NOW,
        )
    )
    db_session.commit()

    with pytest.raises(LearnerModelSafetyError, match="predecessor chain"):
        SqlAlchemyLearnerModelRepository(db_session).current(
            course_id=scope["course_one"],
            learner_id=scope["learner_id"],
            outcome_id=scope["outcome_one"],
        )


def test_current_does_not_leak_a_valid_snapshot_across_course_scope(db_session: Session) -> None:
    scope = _seed_scope(db_session)
    _store_evidence(
        db_session, scope, evidence_id="prediction-1", evidence_type=EvidenceType.PREDICTION
    )
    _service(db_session).update(
        _update_command(
            scope,
            (
                LearnerModelEvidenceSignal(
                    evidence_id="prediction-1", relation=EvidenceLinkRelation.SUPPORTS
                ),
            ),
        )
    )

    assert (
        SqlAlchemyLearnerModelRepository(db_session).current(
            course_id=scope["course_two"],
            learner_id=scope["learner_id"],
            outcome_id=scope["outcome_two"],
        )
        is None
    )


@pytest.mark.parametrize(
    ("relation", "expected_status"),
    (
        (EvidenceLinkRelation.SUPPORTS, InferenceStatus.SUPPORTED),
        (EvidenceLinkRelation.CONTRADICTS, InferenceStatus.CONTRADICTED),
    ),
)
def test_reasoning_rule_keeps_one_stable_dimension_for_both_relation_directions(
    db_session: Session,
    relation: EvidenceLinkRelation,
    expected_status: InferenceStatus,
) -> None:
    scope = _seed_scope(db_session)
    _store_evidence(
        db_session,
        scope,
        evidence_id="reasoning-1",
        evidence_type=EvidenceType.REASONING,
    )

    result = _service(db_session)._build(
        _command(
            scope,
            (LearnerModelEvidenceSignal(evidence_id="reasoning-1", relation=relation),),
        )
    )

    assert result.state is LearnerModelBuildState.STORED
    view = SqlAlchemyLearnerModelRepository(db_session).current(
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )
    assert view is not None
    reasoning = next(
        estimate
        for estimate in view.estimates
        if estimate.dimension is LearnerModelDimension.REASONING_STRENGTH
    )
    assert reasoning.inference_status is expected_status
    assert reasoning.evidence_links == (("reasoning-1", relation),)


@pytest.mark.parametrize(
    "evidence_type",
    (
        EvidenceType.FEEDBACK_INTERACTION,
        EvidenceType.TRANSFER,
    ),
)
def test_event_occurrence_alone_does_not_create_feedback_or_transfer_inference(
    db_session: Session,
    evidence_type: EvidenceType,
) -> None:
    scope = _seed_scope(db_session)
    _store_evidence(
        db_session,
        scope,
        evidence_id="event-1",
        evidence_type=evidence_type,
    )

    result = _service(db_session)._build(
        _command(
            scope,
            (
                LearnerModelEvidenceSignal(
                    evidence_id="event-1", relation=EvidenceLinkRelation.SUPPORTS
                ),
            ),
        )
    )

    assert result.state is LearnerModelBuildState.NO_INFERENCE
    assert (
        SqlAlchemyLearnerModelRepository(db_session).current(
            course_id=scope["course_one"],
            learner_id=scope["learner_id"],
            outcome_id=scope["outcome_one"],
        )
        is None
    )


@pytest.mark.parametrize(
    ("primary_type", "context_type", "dimension"),
    (
        (
            EvidenceType.FEEDBACK_INTERACTION,
            EvidenceType.REVISION,
            LearnerModelDimension.FEEDBACK_USE,
        ),
        (EvidenceType.TRANSFER, EvidenceType.REASONING, LearnerModelDimension.TRANSFER),
    ),
)
def test_feedback_and_transfer_require_and_retain_their_trusted_context(
    db_session: Session,
    primary_type: EvidenceType,
    context_type: EvidenceType,
    dimension: LearnerModelDimension,
) -> None:
    scope = _seed_scope(db_session)
    _store_evidence(db_session, scope, evidence_id="primary-1", evidence_type=primary_type)
    _store_evidence(db_session, scope, evidence_id="context-1", evidence_type=context_type)

    result = _service(db_session).update(
        LearnerModelUpdateCommand(
            course_id=scope["course_one"],
            learner_id=scope["learner_id"],
            outcome_id=scope["outcome_one"],
            model_version="learner-model-rules.v1",
            rule_version="learner-rules.v1",
            actor_reference=scope["actor_reference"],
            adjudicator_reference="learner-model-rule-engine.v1",
            adjudication_rule_version="learner-rules.v1",
            correlation_id="trusted-context-1",
            evidence_signals=(
                LearnerModelEvidenceSignal(
                    evidence_id="primary-1", relation=EvidenceLinkRelation.SUPPORTS
                ),
                LearnerModelEvidenceSignal(
                    evidence_id="context-1", relation=EvidenceLinkRelation.SUPPORTS
                ),
            ),
        )
    )

    assert result.view is not None
    estimate = next(item for item in result.view.estimates if item.dimension is dimension)
    assert estimate.inference_status is InferenceStatus.SUPPORTED
    assert {evidence_id for evidence_id, _ in estimate.evidence_links} == {
        "primary-1",
        "context-1",
    }


def test_access_support_is_not_scaffold_dependence(
    db_session: Session,
) -> None:
    scope = _seed_scope(db_session)
    _store_evidence(
        db_session,
        scope,
        evidence_id="independent-reasoning-1",
        evidence_type=EvidenceType.REASONING,
        access_support_state=AccessSupportState.PROVIDED,
    )

    _service(db_session)._build(
        _command(
            scope,
            (
                LearnerModelEvidenceSignal(
                    evidence_id="independent-reasoning-1",
                    relation=EvidenceLinkRelation.SUPPORTS,
                ),
            ),
        )
    )

    view = SqlAlchemyLearnerModelRepository(db_session).current(
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )
    assert view is not None
    assert LearnerModelDimension.SCAFFOLD_DEPENDENCE not in {
        estimate.dimension for estimate in view.estimates
    }


def test_update_appends_a_complete_cumulative_snapshot_and_skips_an_unchanged_replay(
    db_session: Session,
) -> None:
    scope = _seed_scope(db_session)
    _store_evidence(
        db_session,
        scope,
        evidence_id="prediction-1",
        evidence_type=EvidenceType.PREDICTION,
        occurred_at=NOW,
    )
    service = _service(db_session)
    first = service.update(
        _update_command(
            scope,
            (
                LearnerModelEvidenceSignal(
                    evidence_id="prediction-1", relation=EvidenceLinkRelation.SUPPORTS
                ),
            ),
        )
    )
    _store_evidence(
        db_session,
        scope,
        evidence_id="prediction-2",
        evidence_type=EvidenceType.PREDICTION,
        occurred_at=NOW + timedelta(minutes=2),
    )
    second_command = _update_command(
        scope,
        (
            LearnerModelEvidenceSignal(
                evidence_id="prediction-2", relation=EvidenceLinkRelation.CONTRADICTS
            ),
        ),
    )
    second = service.update(second_command)
    replay = service.update(second_command)

    assert first.snapshot is not None and first.snapshot.created is True
    assert second.snapshot is not None and second.snapshot.created is True
    assert replay.snapshot is not None and replay.snapshot.created is False
    timeline = SqlAlchemyLearnerModelRepository(db_session).timeline(
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )
    assert len(timeline) == 2
    assert timeline[0].prior_snapshot_id is None
    assert timeline[1].prior_snapshot_id == timeline[0].snapshot_id
    assert timeline[1].record_version == 2
    estimate = next(
        item
        for item in timeline[1].estimates
        if item.dimension is LearnerModelDimension.PRIOR_KNOWLEDGE
    )
    assert estimate.inference_status is InferenceStatus.UNCERTAIN
    assert estimate.evidence_observed_at == NOW + timedelta(minutes=2)
    assert estimate.evidence_links == (
        ("prediction-1", EvidenceLinkRelation.SUPPORTS),
        ("prediction-2", EvidenceLinkRelation.CONTRADICTS),
    )
    assert timeline[0].estimates[0].evidence_links == (
        ("prediction-1", EvidenceLinkRelation.SUPPORTS),
    )
    current = SqlAlchemyLearnerModelRepository(db_session).current(
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )
    assert current is not None
    assert current.snapshot_id == timeline[1].snapshot_id
    assert current.record_version == 2


def test_update_replays_equivalent_evidence_in_a_different_input_order(
    db_session: Session,
) -> None:
    scope = _seed_scope(db_session)
    for evidence_id, evidence_type in (
        ("prediction-1", EvidenceType.PREDICTION),
        ("reasoning-1", EvidenceType.REASONING),
    ):
        _store_evidence(
            db_session,
            scope,
            evidence_id=evidence_id,
            evidence_type=evidence_type,
        )
    service = _service(db_session)
    first = service.update(
        _update_command(
            scope,
            (
                LearnerModelEvidenceSignal(
                    evidence_id="prediction-1", relation=EvidenceLinkRelation.SUPPORTS
                ),
                LearnerModelEvidenceSignal(
                    evidence_id="reasoning-1", relation=EvidenceLinkRelation.CONTRADICTS
                ),
            ),
        )
    )
    replay = service.update(
        _update_command(
            scope,
            (
                LearnerModelEvidenceSignal(
                    evidence_id="reasoning-1", relation=EvidenceLinkRelation.CONTRADICTS
                ),
                LearnerModelEvidenceSignal(
                    evidence_id="prediction-1", relation=EvidenceLinkRelation.SUPPORTS
                ),
            ),
            correlation_id="different-retry-correlation",
        )
    )

    assert first.snapshot is not None and replay.snapshot is not None
    assert replay.snapshot == first.snapshot.__class__(
        snapshot_id=first.snapshot.snapshot_id,
        created=False,
        occurred_at=first.snapshot.occurred_at,
    )


def test_teaching_consumer_changes_allowed_action_from_the_public_current_view(
    db_session: Session,
) -> None:
    def allowed_action(view) -> str:
        estimate = next(
            item
            for item in view.estimates
            if item.dimension is LearnerModelDimension.PRIOR_KNOWLEDGE
        )
        return "PROCEED" if estimate.inference_status is InferenceStatus.SUPPORTED else "REVISIT"

    scope = _seed_scope(db_session)
    _store_evidence(
        db_session,
        scope,
        evidence_id="prediction-1",
        evidence_type=EvidenceType.PREDICTION,
    )
    _store_evidence(
        db_session,
        scope,
        evidence_id="prediction-2",
        evidence_type=EvidenceType.PREDICTION,
        occurred_at=NOW + timedelta(minutes=1),
    )
    service = _service(db_session)
    service.update(
        _update_command(
            scope,
            (
                LearnerModelEvidenceSignal(
                    evidence_id="prediction-1", relation=EvidenceLinkRelation.SUPPORTS
                ),
            ),
        )
    )
    repository = SqlAlchemyLearnerModelRepository(db_session)
    supported_view = repository.current(
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )
    assert supported_view is not None
    service.update(
        _update_command(
            scope,
            (
                LearnerModelEvidenceSignal(
                    evidence_id="prediction-2", relation=EvidenceLinkRelation.CONTRADICTS
                ),
            ),
        )
    )
    uncertain_view = repository.current(
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )
    assert uncertain_view is not None

    assert allowed_action(supported_view) == "PROCEED"
    assert allowed_action(uncertain_view) == "REVISIT"


def test_store_rejects_two_different_successors_from_the_same_predecessor(
    db_session: Session,
) -> None:
    scope = _seed_scope(db_session)
    for evidence_id in ("prediction-1", "prediction-2", "prediction-3"):
        _store_evidence(
            db_session,
            scope,
            evidence_id=evidence_id,
            evidence_type=EvidenceType.PREDICTION,
        )
    service = _service(db_session)
    service._build(
        _command(
            scope,
            (
                LearnerModelEvidenceSignal(
                    evidence_id="prediction-1", relation=EvidenceLinkRelation.SUPPORTS
                ),
            ),
        )
    )
    service._build(
        _command(
            scope,
            (
                LearnerModelEvidenceSignal(
                    evidence_id="prediction-2", relation=EvidenceLinkRelation.SUPPORTS
                ),
            ),
            snapshot_id="learner-snapshot-2",
            prior_snapshot_id="learner-snapshot-1",
            record_version=2,
            idempotency_key="learner-model-key-2",
        )
    )

    with pytest.raises(LearnerModelConflictError, match="current head"):
        service._build(
            _command(
                scope,
                (
                    LearnerModelEvidenceSignal(
                        evidence_id="prediction-3", relation=EvidenceLinkRelation.SUPPORTS
                    ),
                ),
                snapshot_id="learner-snapshot-3",
                prior_snapshot_id="learner-snapshot-1",
                record_version=2,
                idempotency_key="learner-model-key-3",
            )
        )


def test_identical_updates_from_independent_sessions_create_one_complete_snapshot(
    db_session: Session,
) -> None:
    class _BarrierRepository(SqlAlchemyLearnerModelRepository):
        def __init__(self, session: Session, barrier: Barrier) -> None:
            super().__init__(session)
            self._barrier = barrier
            self._waited = False

        def store(self, snapshot):
            if not self._waited:
                self._waited = True
                self._barrier.wait()
            return super().store(snapshot)

    scope = _seed_scope(db_session)
    _store_evidence(
        db_session,
        scope,
        evidence_id="prediction-1",
        evidence_type=EvidenceType.PREDICTION,
    )
    command = _update_command(
        scope,
        (
            LearnerModelEvidenceSignal(
                evidence_id="prediction-1", relation=EvidenceLinkRelation.SUPPORTS
            ),
        ),
    )
    session_factory = create_session_factory(db_session.get_bind())
    barrier = Barrier(2)

    def update_in_own_session():
        with session_factory() as session:
            result = LearnerModelBuildService(
                _BarrierRepository(session, barrier), DeterministicLearnerModelBuilder()
            ).update(command)
            assert result.snapshot is not None
            return result.snapshot

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = tuple(executor.map(lambda _: update_in_own_session(), range(2)))

    assert {first.snapshot_id, second.snapshot_id} == {first.snapshot_id}
    assert {first.created, second.created} == {True, False}
    with session_factory() as fresh_session:
        assert fresh_session.scalar(select(func.count()).select_from(LearnerModelSnapshot)) == 1
        assert fresh_session.scalar(select(func.count()).select_from(LearnerOutcomeEstimate)) == 1
        assert fresh_session.scalar(select(func.count()).select_from(LearnerModelEvidenceLink)) == 1
        timeline = SqlAlchemyLearnerModelRepository(fresh_session).timeline(
            course_id=scope["course_one"],
            learner_id=scope["learner_id"],
            outcome_id=scope["outcome_one"],
        )
    assert [snapshot.record_version for snapshot in timeline] == [1]
    assert [snapshot.prior_snapshot_id for snapshot in timeline] == [None]


def test_distinct_concurrent_updates_rebuild_into_one_linear_cumulative_history(
    db_session: Session,
) -> None:
    class _BarrierRepository(SqlAlchemyLearnerModelRepository):
        def __init__(self, session: Session, barrier: Barrier) -> None:
            super().__init__(session)
            self._barrier = barrier
            self._waited = False

        def store(self, snapshot):
            if not self._waited:
                self._waited = True
                self._barrier.wait()
            return super().store(snapshot)

    scope = _seed_scope(db_session)
    for evidence_id in ("prediction-1", "prediction-2"):
        _store_evidence(
            db_session,
            scope,
            evidence_id=evidence_id,
            evidence_type=EvidenceType.PREDICTION,
        )
    session_factory = create_session_factory(db_session.get_bind())
    barrier = Barrier(2)

    def command(evidence_id: str) -> LearnerModelUpdateCommand:
        return LearnerModelUpdateCommand(
            course_id=scope["course_one"],
            learner_id=scope["learner_id"],
            outcome_id=scope["outcome_one"],
            model_version="learner-model-rules.v1",
            rule_version="learner-rules.v1",
            actor_reference=scope["actor_reference"],
            agent_reference="learner-model-agent.v1",
            adjudicator_reference="learner-model-rule-engine.v1",
            adjudication_rule_version="learner-rules.v1",
            correlation_id=f"concurrent-{evidence_id}",
            evidence_signals=(
                LearnerModelEvidenceSignal(
                    evidence_id=evidence_id, relation=EvidenceLinkRelation.SUPPORTS
                ),
            ),
        )

    def update_in_own_session(update_command: LearnerModelUpdateCommand):
        with session_factory() as session:
            result = LearnerModelBuildService(
                _BarrierRepository(session, barrier), DeterministicLearnerModelBuilder()
            ).update(update_command)
            assert result.snapshot is not None and result.view is not None
            return result

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(update_in_own_session, (command("prediction-1"), command("prediction-2")))
        )

    assert all(result.snapshot is not None and result.snapshot.created for result in results)
    with session_factory() as fresh_session:
        timeline = SqlAlchemyLearnerModelRepository(fresh_session).timeline(
            course_id=scope["course_one"],
            learner_id=scope["learner_id"],
            outcome_id=scope["outcome_one"],
        )
    assert [snapshot.record_version for snapshot in timeline] == [1, 2]
    assert timeline[1].prior_snapshot_id == timeline[0].snapshot_id
    estimate = next(
        item
        for item in timeline[1].estimates
        if item.dimension is LearnerModelDimension.PRIOR_KNOWLEDGE
    )
    assert {evidence_id for evidence_id, _ in estimate.evidence_links} == {
        "prediction-1",
        "prediction-2",
    }


def test_contradicting_evidence_creates_later_snapshot_without_mutating_history(
    db_session: Session,
) -> None:
    scope = _seed_scope(db_session)
    _store_evidence(
        db_session,
        scope,
        evidence_id="misconception-1",
        evidence_type=EvidenceType.MISCONCEPTION_CHECK,
    )
    first_signal = (
        LearnerModelEvidenceSignal(
            evidence_id="misconception-1", relation=EvidenceLinkRelation.SUPPORTS
        ),
    )
    _service(db_session)._build(_command(scope, first_signal))
    _store_evidence(
        db_session,
        scope,
        evidence_id="misconception-2",
        evidence_type=EvidenceType.MISCONCEPTION_CHECK,
        occurred_at=NOW + timedelta(minutes=1),
    )
    second = _service(db_session)._build(
        _command(
            scope,
            (
                *first_signal,
                LearnerModelEvidenceSignal(
                    evidence_id="misconception-2", relation=EvidenceLinkRelation.CONTRADICTS
                ),
            ),
            snapshot_id="learner-snapshot-2",
            prior_snapshot_id="learner-snapshot-1",
            record_version=2,
            idempotency_key="learner-model-key-2",
            occurred_at=NOW + timedelta(hours=2),
        )
    )

    assert second.state is LearnerModelBuildState.STORED
    timeline = SqlAlchemyLearnerModelRepository(db_session).timeline(
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )
    assert [snapshot.snapshot_id for snapshot in timeline] == [
        "learner-snapshot-1",
        "learner-snapshot-2",
    ]
    assert timeline[0].prior_snapshot_id is None
    assert timeline[1].prior_snapshot_id == "learner-snapshot-1"
    assert timeline[0].estimates[0].inference_status is InferenceStatus.UNCERTAIN
    assert timeline[1].estimates[0].inference_status is InferenceStatus.UNCERTAIN


def test_possible_misconception_requires_two_supporting_signals_before_supported(
    db_session: Session,
) -> None:
    scope = _seed_scope(db_session)
    for position in range(2):
        _store_evidence(
            db_session,
            scope,
            evidence_id=f"misconception-{position}",
            evidence_type=EvidenceType.MISCONCEPTION_CHECK,
            occurred_at=NOW + timedelta(minutes=position),
        )
    result = _service(db_session)._build(
        _command(
            scope,
            tuple(
                LearnerModelEvidenceSignal(
                    evidence_id=f"misconception-{position}",
                    relation=EvidenceLinkRelation.SUPPORTS,
                )
                for position in range(2)
            ),
        )
    )

    assert result.state is LearnerModelBuildState.STORED
    estimate = (
        SqlAlchemyLearnerModelRepository(db_session)
        .timeline(
            course_id=scope["course_one"],
            learner_id=scope["learner_id"],
            outcome_id=scope["outcome_one"],
        )[0]
        .estimates[0]
    )
    assert estimate.inference_status is InferenceStatus.SUPPORTED
    assert estimate.uncertainty == 0.4


def test_conflicting_idempotency_and_out_of_scope_evidence_are_rejected(
    db_session: Session,
) -> None:
    scope = _seed_scope(db_session)
    _store_evidence(
        db_session,
        scope,
        evidence_id="prediction-1",
        evidence_type=EvidenceType.PREDICTION,
    )
    signals = (
        LearnerModelEvidenceSignal(
            evidence_id="prediction-1", relation=EvidenceLinkRelation.SUPPORTS
        ),
    )
    service = _service(db_session)
    service._build(_command(scope, signals))
    with pytest.raises(LearnerModelConflictError, match="idempotency"):
        service._build(
            _command(
                scope,
                signals,
                rule_version="learner-rules.v2",
            )
        )
    with pytest.raises(LearnerModelConflictError, match="idempotency"):
        service._build(
            _command(
                scope,
                signals,
                snapshot_id="different-snapshot",
            )
        )
    with pytest.raises(ValueError, match="requested learner/course/outcome scope"):
        service._build(
            _command(
                scope,
                (
                    LearnerModelEvidenceSignal(
                        evidence_id="missing-evidence", relation=EvidenceLinkRelation.SUPPORTS
                    ),
                ),
                snapshot_id="scope-snapshot",
                idempotency_key="scope-key",
            )
        )


def test_provider_failure_or_missing_review_leaves_evidence_and_snapshot_history_unchanged(
    db_session: Session,
) -> None:
    class _FailingProvider:
        model_version = "failing-provider.v1"

        def build(self, *_: object):
            raise RuntimeError("private provider failure")

    scope = _seed_scope(db_session)
    _store_evidence(
        db_session,
        scope,
        evidence_id="prediction-1",
        evidence_type=EvidenceType.PREDICTION,
    )
    signals = (
        LearnerModelEvidenceSignal(
            evidence_id="prediction-1", relation=EvidenceLinkRelation.SUPPORTS
        ),
    )
    no_review = _service(db_session, _FailingProvider())._build(
        _command(
            scope,
            signals,
            model_source=ModelSource.ADVISORY_MODEL,
        )
    )
    provider_failure = _service(db_session, _FailingProvider())._build(
        _command(
            scope,
            signals,
            model_source=ModelSource.ADVISORY_MODEL,
            reviewed_by_reference="educator-1",
        )
    )

    assert no_review.state is LearnerModelBuildState.REVIEW_REQUIRED
    assert provider_failure.state is LearnerModelBuildState.PROVIDER_UNAVAILABLE
    assert db_session.scalar(select(func.count()).select_from(LearningEvidence)) == 1
    assert db_session.scalar(select(func.count()).select_from(LearnerModelSnapshot)) == 0


def test_learner_model_migration_creates_append_only_tables_and_safe_empty_downgrade(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "learner-model-migration.db"
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")

    command.upgrade(config, "20260816_0020")
    from sqlalchemy import create_engine, inspect

    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    inspector = inspect(engine)
    assert {
        "learner_model_snapshots",
        "learner_outcome_estimates",
        "learner_model_evidence_links",
    } <= set(inspector.get_table_names())
    with engine.connect() as connection:
        triggers = connection.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                "AND tbl_name IN ('learner_model_snapshots', 'learner_outcome_estimates', "
                "'learner_model_evidence_links')"
            )
        ).scalars()
        assert len(tuple(triggers)) == 6
    command.downgrade(config, "20260816_0019")
    assert "learner_model_snapshots" not in set(inspect(engine).get_table_names())
    engine.dispose()
