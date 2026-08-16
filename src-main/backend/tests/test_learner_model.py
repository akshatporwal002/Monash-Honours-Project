"""Deterministic and append-only proof for Person B learner-model snapshots."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from test_evidence_repository import NOW, _record, _seed_scope

from app.domain.platform_enums import (
    EvidenceLinkRelation,
    EvidenceType,
    InferenceStatus,
    LearnerModelDimension,
    ModelSource,
)
from app.models.learner_model import LearnerModelSnapshot
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
)
from app.services.learner_model.repository import SqlAlchemyLearnerModelRepository
from app.services.learner_model.safety import (
    LearnerModelConflictError,
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


def _service(session: Session, builder=None) -> LearnerModelBuildService:
    return LearnerModelBuildService(
        SqlAlchemyLearnerModelRepository(session),
        builder or DeterministicLearnerModelBuilder(),
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

    created = _service(db_session).build(_command(scope, signals))
    replayed = _service(db_session).build(_command(scope, signals))

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
    _service(db_session).build(_command(scope, first_signal))
    _store_evidence(
        db_session,
        scope,
        evidence_id="misconception-2",
        evidence_type=EvidenceType.MISCONCEPTION_CHECK,
        occurred_at=NOW + timedelta(minutes=1),
    )
    second = _service(db_session).build(
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
    result = _service(db_session).build(
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
    service.build(_command(scope, signals))
    with pytest.raises(LearnerModelConflictError, match="idempotency"):
        service.build(
            _command(
                scope,
                signals,
                snapshot_id="different-snapshot",
            )
        )
    with pytest.raises(ValueError, match="requested learner/course/outcome scope"):
        service.build(
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
    no_review = _service(db_session, _FailingProvider()).build(
        _command(
            scope,
            signals,
            model_source=ModelSource.ADVISORY_MODEL,
        )
    )
    provider_failure = _service(db_session, _FailingProvider()).build(
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

    command.upgrade(config, "head")
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
