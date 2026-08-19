"""Tests for Person B's trusted protected-evidence capture boundary."""

from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session
from test_evidence_repository import NOW, _artifact, _record, _seed_scope

from app.domain.platform_enums import EvidenceType
from app.schemas.learning_events import TrustedEvidenceAnalyticsMetadata
from app.services.evidence.adapters import (
    EvidenceAnalyticsState,
    TrustedEvidenceCaptureAdapter,
    TrustedEvidenceCaptureCommand,
)
from app.services.evidence.repository import EvidenceCapture, SqlAlchemyEvidenceRepository
from app.services.evidence.safety import (
    EvidenceAccessScope,
    EvidenceAuditEvent,
    EvidenceConflictError,
    EvidencePersistenceError,
)
from app.services.evidence.service import EvidenceCaptureState, EvidenceService


class _AllowPolicy:
    def can_write(self, _: EvidenceAccessScope) -> bool:
        return True

    def can_read_timeline(self, _: EvidenceAccessScope) -> bool:
        return True

    def can_read_artifact(self, _: EvidenceAccessScope) -> bool:
        return True


class _AuditSink:
    def record(self, _: EvidenceAuditEvent) -> None:
        return None


class _RecordingAnalyticsSink:
    def __init__(self) -> None:
        self.events: list[object] = []

    def record(self, event: object) -> None:
        self.events.append(event)


def _access_scope(scope: dict[str, str]) -> EvidenceAccessScope:
    return EvidenceAccessScope(
        actor_reference=scope["actor_reference"],
        role="student",
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
    )


def test_trusted_adapters_store_a_complete_episode_and_emit_only_opaque_metadata(
    db_session: Session,
) -> None:
    scope = _seed_scope(db_session)
    analytics = _RecordingAnalyticsSink()
    service = EvidenceService(
        SqlAlchemyEvidenceRepository(db_session), _AllowPolicy(), _AuditSink()
    )
    adapter = TrustedEvidenceCaptureAdapter(service, analytics)  # type: ignore[arg-type]
    evidence_types = (
        EvidenceType.PREDICTION,
        EvidenceType.RESPONSE,
        EvidenceType.REASONING,
        EvidenceType.CONFIDENCE,
        EvidenceType.HINT,
        EvidenceType.REVISION,
        EvidenceType.SCAFFOLD,
        EvidenceType.REFLECTION,
        EvidenceType.SIMULATION,
        EvidenceType.TRANSFER,
        EvidenceType.MISCONCEPTION_CHECK,
    )

    for position, evidence_type in enumerate(evidence_types):
        evidence_id = f"episode-{position}"
        artifact_id = f"episode-artifact-{position}" if position == 1 else None
        capture = EvidenceCapture(
            record=_record(
                scope,
                evidence_id=evidence_id,
                evidence_type=evidence_type,
                artifact_id=artifact_id,
                source_interaction_id=f"episode-source-{position}",
                idempotency_key=f"episode-key-{position}",
                occurred_at=NOW + timedelta(minutes=position),
            ),
            artifact=(
                _artifact(
                    scope,
                    artifact_id=artifact_id,
                    content="PRIVATE_EPISODE_RESPONSE",
                )
                if artifact_id is not None
                else None
            ),
        )

        result = adapter.capture(TrustedEvidenceCaptureCommand(_access_scope(scope), capture))

        assert result.evidence.state is EvidenceCaptureState.STORED
        assert result.analytics_state is EvidenceAnalyticsState.RECORDED

    timeline = service.timeline(_access_scope(scope))
    assert [item.reference.evidence_type for item in timeline] == list(evidence_types)
    assert len(analytics.events) == len(evidence_types)
    serialized = repr(analytics.events)
    assert "PRIVATE_EPISODE_RESPONSE" not in serialized
    assert "learner_id" not in serialized
    assert "score" not in serialized
    first_event = analytics.events[0]
    assert getattr(first_event, "metadata").event_schema_version == (
        "learnlens.trusted-evidence-event.v1"
    )
    assert getattr(first_event, "event_id") == "episode-0"
    assert service.artifact(_access_scope(scope), "episode-artifact-1").content == (
        "PRIVATE_EPISODE_RESPONSE"
    )


def test_replay_does_not_emit_a_second_analytics_event_and_unsupported_types_are_rejected(
    db_session: Session,
) -> None:
    scope = _seed_scope(db_session)
    analytics = _RecordingAnalyticsSink()
    service = EvidenceService(
        SqlAlchemyEvidenceRepository(db_session), _AllowPolicy(), _AuditSink()
    )
    adapter = TrustedEvidenceCaptureAdapter(service, analytics)  # type: ignore[arg-type]
    capture = EvidenceCapture(record=_record(scope, artifact_id=None))
    command = TrustedEvidenceCaptureCommand(_access_scope(scope), capture)

    assert adapter.capture(command).analytics_state is EvidenceAnalyticsState.RECORDED
    assert adapter.capture(command).analytics_state is EvidenceAnalyticsState.NOT_EMITTED_REPLAY
    assert len(analytics.events) == 1

    conflicting = EvidenceCapture(
        record=_record(
            scope,
            evidence_id="conflicting-event",
            activity_id="different-activity",
            artifact_id=None,
        )
    )
    with pytest.raises(EvidenceConflictError, match="idempotency"):
        adapter.capture(TrustedEvidenceCaptureCommand(_access_scope(scope), conflicting))

    unsupported = EvidenceCapture(
        record=_record(
            scope,
            evidence_id="diagnostic-event",
            evidence_type=EvidenceType.DIAGNOSTIC,
            artifact_id=None,
            idempotency_key="diagnostic-key",
        )
    )
    with pytest.raises(ValueError, match="not supported"):
        adapter.capture(TrustedEvidenceCaptureCommand(_access_scope(scope), unsupported))


def test_persistence_reconciliation_skips_analytics_and_analytics_failure_keeps_evidence(
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _FailingRepository:
        def capture(self, _: EvidenceCapture) -> None:
            raise EvidencePersistenceError("PRIVATE_DATABASE_FAILURE")

    class _FailingAnalyticsSink:
        def record(self, _: object) -> None:
            raise RuntimeError("PRIVATE_ANALYTICS_FAILURE")

    scope = _seed_scope(db_session)
    capture = EvidenceCapture(record=_record(scope, artifact_id=None))
    analytics = _RecordingAnalyticsSink()
    reconciliation = TrustedEvidenceCaptureAdapter(
        EvidenceService(_FailingRepository(), _AllowPolicy(), _AuditSink()),  # type: ignore[arg-type]
        analytics,  # type: ignore[arg-type]
    )
    pending = reconciliation.capture(TrustedEvidenceCaptureCommand(_access_scope(scope), capture))
    assert pending.evidence.state is EvidenceCaptureState.PENDING_RECONCILIATION
    assert pending.analytics_state is EvidenceAnalyticsState.NOT_ATTEMPTED_RECONCILIATION
    assert analytics.events == []

    accepted = TrustedEvidenceCaptureAdapter(
        EvidenceService(SqlAlchemyEvidenceRepository(db_session), _AllowPolicy(), _AuditSink()),
        _FailingAnalyticsSink(),  # type: ignore[arg-type]
    ).capture(TrustedEvidenceCaptureCommand(_access_scope(scope), capture))
    assert accepted.evidence.state is EvidenceCaptureState.STORED
    assert accepted.analytics_state is EvidenceAnalyticsState.UNAVAILABLE
    assert "PRIVATE_ANALYTICS_FAILURE" not in caplog.text
    assert "PRIVATE_DATABASE_FAILURE" not in caplog.text


def test_trusted_analytics_metadata_rejects_scores_private_fields_and_oversized_versions() -> None:
    values: dict[str, object] = {
        "evidence_id": "evidence-1",
        "evidence_type": EvidenceType.PREDICTION,
        "evidence_schema_version": "evidence-record.v1",
        "evidence_record_version": 1,
        "content_digest": f"sha256:{'a' * 64}",
    }

    for forbidden in (
        {"score": 100},
        {"learner_id": "private-learner"},
        {"source_version": "x" * 101},
    ):
        with pytest.raises(ValidationError):
            TrustedEvidenceAnalyticsMetadata.model_validate({**values, **forbidden})
