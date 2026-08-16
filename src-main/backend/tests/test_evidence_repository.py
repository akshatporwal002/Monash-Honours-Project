"""Repository proof for transactional Person B evidence capture."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import create_db_engine, create_session_factory
from app.domain.platform_enums import (
    AccessSupportState,
    EvidenceLinkRelation,
    EvidenceProvenance,
    EvidenceType,
    InstructionalSupportLevel,
    ObservationType,
)
from app.models.enums import TaskType
from app.models.learning_evidence import EvidenceArtifact as EvidenceArtifactModel
from app.models.learning_evidence import EvidenceLink as EvidenceLinkModel
from app.models.learning_evidence import LearningEvidence
from app.models.lms import Course, CourseModule, LearningOutcome, OutcomeKind
from app.models.persistence import LearningTask
from app.models.user import User, UserRole
from app.schemas.evidence import EvidenceArtifact, EvidenceLink, EvidenceRecord
from app.services.evidence.repository import EvidenceCapture, SqlAlchemyEvidenceRepository
from app.services.evidence.safety import EvidenceConflictError, EvidenceScopeError

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


def _seed_scope(session: Session) -> dict[str, str]:
    educator = User(
        email="evidence-educator@example.edu",
        password_hash="hash",
        full_name="Evidence Educator",
        role=UserRole.EDUCATOR,
        is_active=True,
    )
    learner = User(
        email="evidence-learner@example.edu",
        password_hash="hash",
        full_name="Evidence Learner",
        role=UserRole.STUDENT,
        is_active=True,
    )
    session.add_all((educator, learner))
    session.flush()
    values = {"learner_id": str(learner.id), "actor_reference": str(learner.id)}
    for suffix in ("one", "two"):
        course = Course(
            id=f"evidence-course-{suffix}",
            educator_id=educator.id,
            code=f"EVD-{suffix}",
            title=f"Evidence {suffix}",
            description="",
        )
        module = CourseModule(
            id=f"evidence-module-{suffix}",
            course_id=course.id,
            title=f"Evidence module {suffix}",
            description="",
            position=1,
        )
        outcome = LearningOutcome(
            id=f"evidence-outcome-{suffix}",
            module_id=module.id,
            title=f"Evidence outcome {suffix}",
            statement="Explain the evidence.",
            kind=OutcomeKind.WEEKLY,
            week_number=1,
            position=1,
        )
        task = LearningTask(
            id=f"evidence-task-{suffix}",
            slug=f"evidence-task-{suffix}",
            title=f"Evidence task {suffix}",
            module=f"Evidence module {suffix}",
            description="",
            instructions="",
            task_type=TaskType.SHORT_ANSWER,
            difficulty="introductory",
            points=0,
            position=1,
            course_id=course.id,
            module_id=module.id,
            learning_outcome_id=outcome.id,
        )
        session.add_all((course, module, outcome, task))
        values.update(
            {
                f"course_{suffix}": course.id,
                f"outcome_{suffix}": outcome.id,
                f"task_{suffix}": task.id,
            }
        )
    session.commit()
    return values


def _artifact(scope: dict[str, str], **overrides: object) -> EvidenceArtifact:
    values: dict[str, object] = {
        "artifact_id": "evidence-artifact-1",
        "course_id": scope["course_one"],
        "learner_id": scope["learner_id"],
        "content": "PRIVATE_LEARNER_ANSWER",
        "content_digest": f"sha256:{'a' * 64}",
        "content_format": "plain-text.v1",
        "record_version": 1,
        "occurred_at": NOW,
    }
    values.update(overrides)
    return EvidenceArtifact.model_validate(values)


def _record(scope: dict[str, str], **overrides: object) -> EvidenceRecord:
    values: dict[str, object] = {
        "evidence_id": "evidence-record-1",
        "course_id": scope["course_one"],
        "learner_id": scope["learner_id"],
        "outcome_id": scope["outcome_one"],
        "activity_id": "activity-1",
        "task_id": scope["task_one"],
        "response_version_id": "response-version-1",
        "source_interaction_id": "source-interaction-1",
        "source_version": "source.v1",
        "task_conditions_version": 1,
        "evidence_type": EvidenceType.REASONING,
        "provenance": EvidenceProvenance.LEARNER,
        "observation_type": ObservationType.DIRECT,
        "instructional_support_level": InstructionalSupportLevel.CONCEPT_CUE,
        "access_support_state": AccessSupportState.PROVIDED,
        "artifact_id": "evidence-artifact-1",
        "content_digest": f"sha256:{'a' * 64}",
        "actor_reference": scope["actor_reference"],
        "agent_reference": "evidence-agent.v1",
        "correlation_id": "correlation-1",
        "schema_version": "evidence-record.v1",
        "record_version": 1,
        "idempotency_key": "evidence-key-1",
        "occurred_at": NOW,
    }
    values.update(overrides)
    return EvidenceRecord.model_validate(values)


def test_capture_is_transactional_and_returns_only_an_opaque_reference(db_session: Session) -> None:
    scope = _seed_scope(db_session)
    repository = SqlAlchemyEvidenceRepository(db_session)
    result = repository.capture(EvidenceCapture(record=_record(scope), artifact=_artifact(scope)))

    assert result.created is True
    assert result.reference.evidence_id == "evidence-record-1"
    assert "PRIVATE_LEARNER_ANSWER" not in result.reference.model_dump_json()
    assert "learner_id" not in result.reference.model_dump()
    assert db_session.scalar(select(func.count()).select_from(EvidenceArtifactModel)) == 1
    assert db_session.scalar(select(func.count()).select_from(LearningEvidence)) == 1


def test_exact_replay_and_conflict_are_distinguished(db_session: Session) -> None:
    scope = _seed_scope(db_session)
    repository = SqlAlchemyEvidenceRepository(db_session)
    capture = EvidenceCapture(record=_record(scope), artifact=_artifact(scope))

    created = repository.capture(capture)
    replayed = repository.capture(capture)

    assert created.created is True
    assert replayed.created is False
    assert replayed.reference == created.reference
    with pytest.raises(EvidenceConflictError, match="idempotency"):
        repository.capture(
            EvidenceCapture(
                record=_record(scope, activity_id="different-activity"),
                artifact=_artifact(scope),
            )
        )


def test_timeline_sorts_out_of_order_captures_stably(db_session: Session) -> None:
    scope = _seed_scope(db_session)
    repository = SqlAlchemyEvidenceRepository(db_session)
    repository.capture(
        EvidenceCapture(
            record=_record(
                scope,
                evidence_id="evidence-late",
                artifact_id=None,
                idempotency_key="evidence-key-late",
                occurred_at=NOW + timedelta(minutes=5),
            )
        )
    )
    repository.capture(
        EvidenceCapture(
            record=_record(
                scope,
                evidence_id="evidence-early",
                artifact_id=None,
                idempotency_key="evidence-key-early",
                occurred_at=NOW - timedelta(minutes=5),
            )
        )
    )

    history = repository.timeline(course_id=scope["course_one"], learner_id=scope["learner_id"])

    assert [item.reference.evidence_id for item in history] == ["evidence-early", "evidence-late"]


def test_cross_course_and_dangling_links_are_rejected(db_session: Session) -> None:
    scope = _seed_scope(db_session)
    repository = SqlAlchemyEvidenceRepository(db_session)
    repository.capture(
        EvidenceCapture(
            record=_record(
                scope,
                evidence_id="evidence-course-two",
                course_id=scope["course_two"],
                outcome_id=scope["outcome_two"],
                task_id=scope["task_two"],
                artifact_id=None,
                idempotency_key="evidence-key-two",
            )
        )
    )
    link = EvidenceLink(
        evidence_id="evidence-record-1",
        linked_evidence_id="evidence-course-two",
        relation=EvidenceLinkRelation.SUPPORTS,
        actor_reference=scope["actor_reference"],
        correlation_id="correlation-1",
        occurred_at=NOW,
    )

    with pytest.raises(EvidenceScopeError, match="same course"):
        repository.capture(
            EvidenceCapture(record=_record(scope), artifact=_artifact(scope), links=(link,))
        )
    with pytest.raises(EvidenceScopeError, match="valid course"):
        repository.capture(
            EvidenceCapture(record=_record(scope, task_id=scope["task_two"], artifact_id=None))
        )


def test_link_must_include_the_record_captured_by_its_transaction(db_session: Session) -> None:
    scope = _seed_scope(db_session)
    repository = SqlAlchemyEvidenceRepository(db_session)
    repository.capture(
        EvidenceCapture(
            record=_record(
                scope,
                evidence_id="evidence-existing-one",
                artifact_id=None,
                idempotency_key="evidence-key-existing-one",
            )
        )
    )
    repository.capture(
        EvidenceCapture(
            record=_record(
                scope,
                evidence_id="evidence-existing-two",
                artifact_id=None,
                idempotency_key="evidence-key-existing-two",
            )
        )
    )
    unrelated_link = EvidenceLink(
        evidence_id="evidence-existing-one",
        linked_evidence_id="evidence-existing-two",
        relation=EvidenceLinkRelation.SUPPORTS,
        actor_reference=scope["actor_reference"],
        correlation_id="correlation-1",
        occurred_at=NOW,
    )

    with pytest.raises(EvidenceScopeError, match="captured evidence"):
        repository.capture(
            EvidenceCapture(
                record=_record(
                    scope,
                    evidence_id="evidence-unrelated",
                    artifact_id=None,
                    idempotency_key="evidence-key-unrelated",
                ),
                links=(unrelated_link,),
            )
        )


def test_concurrent_exact_replay_creates_one_row(tmp_path) -> None:
    engine = create_db_engine(f"sqlite:///{(tmp_path / 'evidence-concurrency.db').as_posix()}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        scope = _seed_scope(session)
    capture = EvidenceCapture(record=_record(scope), artifact=_artifact(scope))
    barrier = Barrier(2)

    def store() -> bool:
        with session_factory() as session:
            barrier.wait()
            return SqlAlchemyEvidenceRepository(session).capture(capture).created

    with ThreadPoolExecutor(max_workers=2) as executor:
        created = list(executor.map(lambda _: store(), range(2)))
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(LearningEvidence)) == 1
    assert sorted(created) == [False, True]
    engine.dispose()


def test_valid_same_course_link_is_persisted(db_session: Session) -> None:
    scope = _seed_scope(db_session)
    repository = SqlAlchemyEvidenceRepository(db_session)
    repository.capture(
        EvidenceCapture(
            record=_record(
                scope,
                evidence_id="evidence-record-base",
                artifact_id=None,
                idempotency_key="evidence-key-base",
            )
        )
    )
    link = EvidenceLink(
        evidence_id="evidence-record-2",
        linked_evidence_id="evidence-record-base",
        relation=EvidenceLinkRelation.CONTRADICTS,
        actor_reference=scope["actor_reference"],
        correlation_id="correlation-2",
        occurred_at=NOW,
    )
    repository.capture(
        EvidenceCapture(
            record=_record(
                scope,
                evidence_id="evidence-record-2",
                artifact_id=None,
                correlation_id="correlation-2",
                idempotency_key="evidence-key-2",
            ),
            links=(link,),
        )
    )

    assert db_session.scalar(select(func.count()).select_from(EvidenceLinkModel)) == 1


def test_later_append_only_link_does_not_break_an_earlier_exact_replay(db_session: Session) -> None:
    scope = _seed_scope(db_session)
    repository = SqlAlchemyEvidenceRepository(db_session)
    original = EvidenceCapture(
        record=_record(
            scope,
            evidence_id="evidence-record-base",
            artifact_id=None,
            idempotency_key="evidence-key-base",
        )
    )
    repository.capture(original)
    link = EvidenceLink(
        evidence_id="evidence-record-next",
        linked_evidence_id="evidence-record-base",
        relation=EvidenceLinkRelation.SUPPORTS,
        actor_reference=scope["actor_reference"],
        correlation_id="correlation-next",
        occurred_at=NOW,
    )
    repository.capture(
        EvidenceCapture(
            record=_record(
                scope,
                evidence_id="evidence-record-next",
                artifact_id=None,
                correlation_id="correlation-next",
                idempotency_key="evidence-key-next",
            ),
            links=(link,),
        )
    )

    replay = repository.capture(original)

    assert replay.created is False
