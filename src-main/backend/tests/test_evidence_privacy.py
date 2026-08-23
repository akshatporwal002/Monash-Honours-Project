"""Privacy and access proof for the Person B evidence service."""

from __future__ import annotations

from dataclasses import fields

import pytest
from sqlalchemy.orm import Session
from test_evidence_repository import _artifact, _record, _seed_scope

from app.services.evidence.repository import EvidenceCapture, SqlAlchemyEvidenceRepository
from app.services.evidence.safety import (
    EvidenceAccessScope,
    EvidenceAuditAction,
    EvidenceAuditEvent,
    EvidenceNotFoundError,
    EvidencePersistenceError,
    opaque_fingerprint,
)
from app.services.evidence.service import EvidenceCaptureState, EvidenceService


class _Policy:
    def __init__(self, *, write: bool = True, timeline: bool = True, artifact: bool = True) -> None:
        self.write = write
        self.timeline = timeline
        self.artifact = artifact

    def can_write(self, _: EvidenceAccessScope) -> bool:
        return self.write

    def can_read_timeline(self, _: EvidenceAccessScope) -> bool:
        return self.timeline

    def can_read_artifact(self, _: EvidenceAccessScope) -> bool:
        return self.artifact


class _AuditSink:
    def __init__(self) -> None:
        self.events: list[EvidenceAuditEvent] = []

    def record(self, event: EvidenceAuditEvent) -> None:
        self.events.append(event)


def _access_scope(scope: dict[str, str]) -> EvidenceAccessScope:
    return EvidenceAccessScope(
        actor_reference=scope["actor_reference"],
        role="student",
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
    )


def test_access_denial_is_non_enumerating_and_artifacts_need_separate_permission(
    db_session: Session,
) -> None:
    scope = _seed_scope(db_session)
    repository = SqlAlchemyEvidenceRepository(db_session)
    repository.capture(EvidenceCapture(record=_record(scope), artifact=_artifact(scope)))
    authorized = EvidenceService(repository, _Policy(), _AuditSink())
    denied = EvidenceService(
        repository, _Policy(write=False, timeline=False, artifact=False), _AuditSink()
    )

    with pytest.raises(EvidenceNotFoundError, match="unavailable"):
        denied.timeline(_access_scope(scope))
    with pytest.raises(EvidenceNotFoundError, match="unavailable"):
        denied.artifact(_access_scope(scope), "evidence-artifact-1")
    with pytest.raises(EvidenceNotFoundError, match="unavailable"):
        authorized.artifact(_access_scope(scope), "not-an-artifact")
    assert authorized.artifact(_access_scope(scope), "evidence-artifact-1").content == (
        "PRIVATE_LEARNER_ANSWER"
    )


@pytest.mark.parametrize(
    "action",
    (
        EvidenceAuditAction.EVIDENCE_CREATED,
        EvidenceAuditAction.LEARNER_ANNOTATION,
        EvidenceAuditAction.EDUCATOR_CORRECTION,
        EvidenceAuditAction.RETRY,
        EvidenceAuditAction.FALLBACK,
    ),
)
def test_audit_events_are_bounded_and_exclude_private_content(
    db_session: Session,
    action: EvidenceAuditAction,
) -> None:
    scope = _seed_scope(db_session)
    audit = _AuditSink()
    service = EvidenceService(SqlAlchemyEvidenceRepository(db_session), _Policy(), audit)
    capture = EvidenceCapture(
        record=_record(scope, artifact_id=None, idempotency_key=f"evidence-key-{action.value}"),
    )

    result = service.capture(_access_scope(scope), capture, action=action)

    assert result.state is EvidenceCaptureState.STORED
    assert result.audit_recorded is True
    event = audit.events[-1]
    assert event.action is action
    assert event.actor_fingerprint == opaque_fingerprint(scope["actor_reference"])
    assert event.actor_fingerprint != scope["actor_reference"]
    assert event.resource_fingerprint != capture.record.evidence_id
    assert event.schema_version == "evidence-record.v1"
    assert "PRIVATE_LEARNER_ANSWER" not in repr(event)
    assert {field.name for field in fields(event)}.isdisjoint(
        {
            "content",
            "answer",
            "prompt",
            "source_chunk",
            "course_id",
            "learner_id",
            "role",
            "note",
            "reason",
            "evidence_id",
            "estimate_id",
            "annotation_id",
            "review_id",
        }
    )


def test_audit_failure_keeps_stored_evidence_and_hides_exception_text(db_session: Session) -> None:
    class _BrokenAuditSink:
        def record(self, _: EvidenceAuditEvent) -> None:
            raise RuntimeError("PRIVATE_AUDIT_EXCEPTION_TEXT")

    scope = _seed_scope(db_session)
    service = EvidenceService(
        SqlAlchemyEvidenceRepository(db_session),
        _Policy(),
        _BrokenAuditSink(),
    )

    result = service.capture(
        _access_scope(scope), EvidenceCapture(record=_record(scope), artifact=_artifact(scope))
    )

    assert result.state is EvidenceCaptureState.STORED
    assert result.audit_recorded is False
    assert result.reference is not None
    assert "PRIVATE_AUDIT_EXCEPTION_TEXT" not in repr(result)


def test_persistence_failure_returns_typed_reconciliation_state_without_private_error() -> None:
    class _FailingRepository:
        def capture(self, _: EvidenceCapture):
            raise EvidencePersistenceError("PRIVATE_DATABASE_ERROR")

    audit = _AuditSink()
    service = EvidenceService(_FailingRepository(), _Policy(), audit)  # type: ignore[arg-type]
    scope = EvidenceAccessScope("learner-1", "student", "course-1", "learner-1")
    capture = EvidenceCapture(record=_record_for_failed_write())

    result = service.capture(scope, capture)

    assert result.state is EvidenceCaptureState.PENDING_RECONCILIATION
    assert result.reference is None
    assert result.failure_category == "evidence_persistence_unavailable"
    assert result.audit_recorded is True
    assert audit.events[-1].action is EvidenceAuditAction.FALLBACK
    assert "PRIVATE_DATABASE_ERROR" not in repr(result)
    assert "PRIVATE_DATABASE_ERROR" not in repr(audit.events[-1])


def test_write_scope_must_match_the_record_even_when_policy_grants_access(
    db_session: Session,
) -> None:
    scope = _seed_scope(db_session)
    service = EvidenceService(SqlAlchemyEvidenceRepository(db_session), _Policy(), _AuditSink())
    mismatched = _record(
        scope,
        course_id=scope["course_two"],
        outcome_id=scope["outcome_two"],
        task_id=scope["task_two"],
        artifact_id=None,
    )

    with pytest.raises(EvidenceNotFoundError, match="unavailable"):
        service.capture(_access_scope(scope), EvidenceCapture(record=mismatched))


def _record_for_failed_write():
    return _record(
        {
            "course_one": "course-1",
            "outcome_one": "outcome-1",
            "task_one": "task-1",
            "learner_id": "learner-1",
            "actor_reference": "learner-1",
        },
        artifact_id=None,
    )
