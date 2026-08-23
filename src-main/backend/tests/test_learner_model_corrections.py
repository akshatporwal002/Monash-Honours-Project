"""Persistence proof for append-only learner-model correction history."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_evidence_repository import NOW, _record

from app.db.session import create_db_engine
from app.domain.platform_enums import (
    CorrectionAction,
    CorrectionTargetKind,
    InferenceStatus,
    LearnerModelDimension,
    ModelSource,
)
from app.models.enums import TaskType
from app.models.learner_model import (
    LearnerModelAnnotation,
    LearnerModelCorrectionReview,
    LearnerModelCorrectionSnapshotLink,
    LearnerModelSnapshot,
    LearnerOutcomeEstimate,
)
from app.models.lms import Course, CourseModule, LearningOutcome, OutcomeKind
from app.models.persistence import LearningTask
from app.models.user import User, UserRole
from app.services.evidence.repository import EvidenceCapture, SqlAlchemyEvidenceRepository

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CORRECTION_TABLES = {
    "learner_model_annotations",
    "learner_model_correction_reviews",
    "learner_model_correction_snapshot_links",
}


def _migration_config(database_path: Path) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    return config


def _seed_target_history(session: Session) -> dict[str, str]:
    educator = User(
        email="correction-educator@example.edu",
        password_hash="hash",
        full_name="Correction Educator",
        role=UserRole.EDUCATOR,
        is_active=True,
    )
    learner = User(
        email="correction-learner@example.edu",
        password_hash="hash",
        full_name="Correction Learner",
        role=UserRole.STUDENT,
        is_active=True,
    )
    session.add_all((educator, learner))
    session.commit()
    scope = {"learner_id": str(learner.id), "actor_reference": str(learner.id)}
    for suffix in ("one", "two"):
        course = Course(
            id=f"correction-course-{suffix}",
            educator_id=educator.id,
            code=f"COR-{suffix}",
            title=f"Correction {suffix}",
            description="",
        )
        session.add(course)
        session.commit()
        module = CourseModule(
            id=f"correction-module-{suffix}",
            course_id=course.id,
            title=f"Correction module {suffix}",
            description="",
            position=1,
        )
        session.add(module)
        session.commit()
        outcome = LearningOutcome(
            id=f"correction-outcome-{suffix}",
            module_id=module.id,
            title=f"Correction outcome {suffix}",
            statement="Explain the evidence.",
            kind=OutcomeKind.WEEKLY,
            week_number=1,
            position=1,
        )
        session.add(outcome)
        session.commit()
        task = LearningTask(
            id=f"correction-task-{suffix}",
            slug=f"correction-task-{suffix}",
            title=f"Correction task {suffix}",
            module=f"Correction module {suffix}",
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
        session.add(task)
        session.commit()
        scope.update(
            {
                f"course_{suffix}": course.id,
                f"outcome_{suffix}": outcome.id,
                f"task_{suffix}": task.id,
            }
        )
    SqlAlchemyEvidenceRepository(session).capture(
        EvidenceCapture(record=_record(scope, artifact_id=None))
    )
    snapshot = LearnerModelSnapshot(
        id="snapshot-before-correction",
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
        correlation_id="snapshot-correlation-1",
        idempotency_key="snapshot-idempotency-1",
        occurred_at=NOW + timedelta(minutes=1),
    )
    estimate = LearnerOutcomeEstimate(
        id="estimate-before-correction",
        snapshot_id=snapshot.id,
        dimension=LearnerModelDimension.REASONING_STRENGTH,
        inference_status=InferenceStatus.SUPPORTED,
        uncertainty=0.2,
        reason_code="rule.reasoning-strength.v1",
        evidence_observed_at=NOW,
    )
    session.add_all((snapshot, estimate))
    session.commit()
    return scope


def _annotation(scope: dict[str, str], **overrides: object) -> LearnerModelAnnotation:
    values: dict[str, object] = {
        "id": "annotation-1",
        "course_id": scope["course_one"],
        "learner_id": int(scope["learner_id"]),
        "outcome_id": scope["outcome_one"],
        "target_kind": CorrectionTargetKind.EVIDENCE,
        "evidence_id": "evidence-record-1",
        "estimate_id": None,
        "action": CorrectionAction.ANNOTATED,
        "note": "This evidence needs learner context.",
        "schema_version": "learnlens.learner-annotation.v1",
        "record_version": 1,
        "actor_reference": scope["actor_reference"],
        "correlation_id": "correction-correlation-1",
        "idempotency_key": "annotation-idempotency-1",
        "occurred_at": NOW + timedelta(minutes=2),
    }
    values.update(overrides)
    return LearnerModelAnnotation(**values)


def _review(scope: dict[str, str], **overrides: object) -> LearnerModelCorrectionReview:
    values: dict[str, object] = {
        "id": "review-1",
        "annotation_id": "annotation-1",
        "course_id": scope["course_one"],
        "learner_id": int(scope["learner_id"]),
        "outcome_id": scope["outcome_one"],
        "prior_review_id": None,
        "review_version": 1,
        "expected_latest_review_version": 0,
        "action": CorrectionAction.NEEDS_REVIEW,
        "reason": "An educator needs to inspect the linked evidence.",
        "schema_version": "learnlens.educator-correction-review.v1",
        "actor_reference": "educator-1",
        "correlation_id": "correction-correlation-1",
        "idempotency_key": "review-idempotency-1",
        "occurred_at": NOW + timedelta(minutes=3),
    }
    values.update(overrides)
    return LearnerModelCorrectionReview(**values)


def test_model_constraints_keep_targets_actions_idempotency_and_reviews_ordered(
    db_session: Session,
) -> None:
    scope = _seed_target_history(db_session)
    db_session.add(_annotation(scope))
    db_session.add(_review(scope))
    db_session.commit()

    second_review = _review(
        scope,
        id="review-2",
        prior_review_id="review-1",
        review_version=2,
        expected_latest_review_version=1,
        action=CorrectionAction.ACCEPTED,
        idempotency_key="review-idempotency-2",
        occurred_at=NOW + timedelta(minutes=4),
    )
    db_session.add(second_review)
    db_session.commit()

    assert db_session.scalar(select(func.count()).select_from(LearnerModelAnnotation)) == 1
    assert db_session.scalars(
        select(LearnerModelCorrectionReview).order_by(LearnerModelCorrectionReview.review_version)
    ).all() == [db_session.get(LearnerModelCorrectionReview, "review-1"), second_review]

    invalid_rows = (
        _annotation(
            scope,
            id="annotation-multi-target",
            estimate_id="estimate-before-correction",
            idempotency_key="annotation-idempotency-2",
        ),
        _annotation(
            scope,
            id="annotation-invalid-action",
            action=CorrectionAction.ACCEPTED,
            idempotency_key="annotation-idempotency-3",
        ),
        _annotation(scope, id="annotation-replay-different"),
        _review(
            scope,
            id="review-skipped-version",
            prior_review_id="review-1",
            review_version=3,
            expected_latest_review_version=1,
            idempotency_key="review-idempotency-3",
        ),
        _review(
            scope,
            id="review-duplicate-version",
            prior_review_id="review-1",
            review_version=2,
            expected_latest_review_version=1,
            idempotency_key="review-idempotency-4",
        ),
        _review(
            scope,
            id="review-orphan",
            annotation_id="missing-annotation",
            idempotency_key="review-idempotency-5",
        ),
        _review(
            scope,
            id="review-cross-scope",
            course_id=scope["course_two"],
            outcome_id=scope["outcome_two"],
            idempotency_key="review-idempotency-6",
        ),
    )
    for invalid in invalid_rows:
        db_session.add(invalid)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    assert db_session.scalar(select(func.count()).select_from(LearnerModelAnnotation)) == 1
    assert db_session.scalar(select(func.count()).select_from(LearnerModelCorrectionReview)) == 2


def test_clean_migration_creates_indexes_triggers_and_supports_empty_downgrade(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "clean-corrections.db"
    config = _migration_config(database_path)

    command.upgrade(config, "head")
    engine = create_db_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        inspector = inspect(engine)
        assert CORRECTION_TABLES <= set(inspector.get_table_names())
        assert {index["name"] for index in inspector.get_indexes("learner_model_annotations")} >= {
            "ix_learner_model_annotations_timeline",
            "ix_learner_model_annotations_target",
            "ix_learner_model_annotations_correlation",
            "ix_learner_model_annotations_idempotency",
        }
        with engine.connect() as connection:
            trigger_names = set(
                connection.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                        "AND tbl_name IN ('learner_model_annotations', "
                        "'learner_model_correction_reviews', "
                        "'learner_model_correction_snapshot_links')"
                    )
                ).scalars()
            )
        assert len(trigger_names) == 9
    finally:
        engine.dispose()

    command.downgrade(config, "20260816_0021")
    downgraded = create_db_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        assert CORRECTION_TABLES.isdisjoint(inspect(downgraded).get_table_names())
    finally:
        downgraded.dispose()


def test_upgrade_from_existing_head_preserves_records_and_is_repeat_safe(tmp_path: Path) -> None:
    database_path = tmp_path / "existing-learner-model.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = _migration_config(database_path)
    command.upgrade(config, "20260816_0021")
    engine = create_db_engine(database_url)
    try:
        with Session(engine) as session:
            _seed_target_history(session)
        with engine.connect() as connection:
            before = {
                table: connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
                for table in (
                    "learning_evidence",
                    "learner_model_snapshots",
                    "learner_outcome_estimates",
                )
            }
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    rerun_engine = create_db_engine(database_url)
    try:
        with rerun_engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = '20260816_0021'"))
    finally:
        rerun_engine.dispose()
    command.upgrade(config, "head")

    upgraded = create_db_engine(database_url)
    try:
        assert CORRECTION_TABLES <= set(inspect(upgraded).get_table_names())
        with upgraded.connect() as connection:
            after = {
                table: connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
                for table in before
            }
        assert after == before
    finally:
        upgraded.dispose()


def test_migration_rejects_partial_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "partial-corrections.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = _migration_config(database_path)
    command.upgrade(config, "20260816_0021")
    engine = create_db_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE learner_model_annotations (id VARCHAR(36))"))
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="partial learner-model correction schema"):
        command.upgrade(config, "head")


def test_migrated_scope_append_only_and_populated_downgrade_guards(tmp_path: Path) -> None:
    database_path = tmp_path / "protected-corrections.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = _migration_config(database_path)
    command.upgrade(config, "head")
    engine = create_db_engine(database_url)
    try:
        with Session(engine) as session:
            scope = _seed_target_history(session)
            session.add(_annotation(scope))
            session.add(_review(scope))
            session.commit()
            later_snapshot = LearnerModelSnapshot(
                id="snapshot-after-correction",
                course_id=scope["course_one"],
                learner_id=int(scope["learner_id"]),
                outcome_id=scope["outcome_one"],
                prior_snapshot_id="snapshot-before-correction",
                model_source=ModelSource.RULE_BASED,
                schema_version="learnlens.learner-model-snapshot.v1",
                model_version="learner-model-rules.v1",
                rule_version="learner-rules.v1",
                record_version=2,
                actor_reference=scope["actor_reference"],
                agent_reference="learner-model-agent.v1",
                correlation_id="snapshot-correlation-2",
                idempotency_key="snapshot-idempotency-2",
                occurred_at=NOW + timedelta(minutes=6),
            )
            session.add(later_snapshot)
            session.commit()
            session.add(
                LearnerModelCorrectionSnapshotLink(
                    id="non-accepted-snapshot-link",
                    review_id="review-1",
                    snapshot_id=later_snapshot.id,
                    course_id=scope["course_one"],
                    learner_id=int(scope["learner_id"]),
                    outcome_id=scope["outcome_one"],
                    schema_version="learnlens.correction-snapshot-link.v1",
                    record_version=1,
                    actor_reference="learner-model-agent.v1",
                    correlation_id="correction-correlation-1",
                    idempotency_key="non-accepted-link-key",
                    occurred_at=NOW + timedelta(minutes=7),
                )
            )
            with pytest.raises(IntegrityError, match="snapshot scope or ordering"):
                session.commit()
            session.rollback()
            session.add(
                _review(
                    scope,
                    id="review-invalid-ancestry",
                    prior_review_id="missing-review",
                    review_version=2,
                    expected_latest_review_version=1,
                    action=CorrectionAction.ACCEPTED,
                    idempotency_key="invalid-ancestry-key",
                    occurred_at=NOW + timedelta(minutes=4),
                )
            )
            with pytest.raises(IntegrityError, match="review ancestry"):
                session.commit()
            session.rollback()
            session.add(
                _review(
                    scope,
                    id="review-2",
                    prior_review_id="review-1",
                    review_version=2,
                    expected_latest_review_version=1,
                    action=CorrectionAction.ACCEPTED,
                    idempotency_key="review-idempotency-2",
                    occurred_at=NOW + timedelta(minutes=4),
                )
            )
            session.commit()
            session.add(
                LearnerModelCorrectionSnapshotLink(
                    id="out-of-order-snapshot-link",
                    review_id="review-2",
                    snapshot_id="snapshot-before-correction",
                    course_id=scope["course_one"],
                    learner_id=int(scope["learner_id"]),
                    outcome_id=scope["outcome_one"],
                    schema_version="learnlens.correction-snapshot-link.v1",
                    record_version=1,
                    actor_reference="learner-model-agent.v1",
                    correlation_id="correction-correlation-1",
                    idempotency_key="out-of-order-link-key",
                    occurred_at=NOW + timedelta(minutes=5),
                )
            )
            with pytest.raises(IntegrityError, match="snapshot scope or ordering"):
                session.commit()
            session.rollback()
            session.add(
                LearnerModelCorrectionSnapshotLink(
                    id="correction-snapshot-link-1",
                    review_id="review-2",
                    snapshot_id=later_snapshot.id,
                    course_id=scope["course_one"],
                    learner_id=int(scope["learner_id"]),
                    outcome_id=scope["outcome_one"],
                    schema_version="learnlens.correction-snapshot-link.v1",
                    record_version=1,
                    actor_reference="learner-model-agent.v1",
                    correlation_id="correction-correlation-1",
                    idempotency_key="correction-link-idempotency-1",
                    occurred_at=NOW + timedelta(minutes=7),
                )
            )
            session.commit()

        with engine.begin() as connection:
            with pytest.raises(
                IntegrityError, match="invalid learner-model correction target scope"
            ):
                connection.execute(
                    text(
                        "INSERT INTO learner_model_annotations (id, course_id, learner_id, "
                        "outcome_id, target_kind, evidence_id, estimate_id, action, note, "
                        "schema_version, record_version, actor_reference, correlation_id, "
                        "idempotency_key, occurred_at) VALUES ('cross-scope-annotation', "
                        ":course, :learner, :outcome, 'EVIDENCE', 'evidence-record-1', NULL, "
                        "'ANNOTATED', 'Wrong scope.', 'learnlens.learner-annotation.v1', 1, "
                        ":actor, 'cross-scope-correlation', 'cross-scope-key', :occurred_at)"
                    ),
                    {
                        "course": scope["course_two"],
                        "learner": int(scope["learner_id"]),
                        "outcome": scope["outcome_two"],
                        "actor": scope["actor_reference"],
                        "occurred_at": NOW + timedelta(minutes=6),
                    },
                )
        with engine.begin() as connection:
            with pytest.raises(IntegrityError, match="append-only"):
                connection.execute(
                    text(
                        "UPDATE learner_model_annotations SET note = 'changed' WHERE id = 'annotation-1'"
                    )
                )
        with engine.begin() as connection:
            with pytest.raises(IntegrityError, match="append-only"):
                connection.execute(
                    text("DELETE FROM learner_model_correction_reviews WHERE id = 'review-1'")
                )
        with engine.connect() as connection:
            counts_before = {
                table: connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
                for table in CORRECTION_TABLES
            }
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="restore the verified backup"):
        command.downgrade(config, "20260816_0021")
    guarded = create_db_engine(database_url)
    try:
        with guarded.connect() as connection:
            counts_after = {
                table: connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
                for table in CORRECTION_TABLES
            }
        assert counts_after == counts_before
    finally:
        guarded.dispose()
