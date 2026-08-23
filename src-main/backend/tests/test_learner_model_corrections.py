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
    EvidenceLinkRelation,
    InferenceStatus,
    LearnerModelDimension,
    ModelSource,
)
from app.models.enums import TaskType
from app.models.learner_model import (
    LearnerModelAnnotation,
    LearnerModelCorrectionReview,
    LearnerModelCorrectionSnapshotLink,
    LearnerModelEvidenceLink,
    LearnerModelSnapshot,
    LearnerOutcomeEstimate,
)
from app.models.lms import (
    Course,
    CourseModule,
    Enrollment,
    EnrollmentStatus,
    LearningOutcome,
    OutcomeKind,
)
from app.models.persistence import LearningTask
from app.models.user import User, UserRole
from app.services.evidence.repository import EvidenceCapture, SqlAlchemyEvidenceRepository
from app.services.learner_model.builder import (
    DeterministicLearnerModelBuilder,
    LearnerModelBuildService,
    LearnerModelBuildState,
)
from app.services.learner_model.contracts import (
    LearnerModelBuildCommand,
    LearnerModelEvidenceSignal,
    LearnerModelSnapshotPayload,
)
from app.services.learner_model.correction_contracts import (
    EducatorCorrectionReviewCommand,
    LearnerAnnotationCommand,
)
from app.services.learner_model.corrections import LearnerModelCorrectionService
from app.services.learner_model.repository import SqlAlchemyLearnerModelRepository
from app.services.learner_model.safety import (
    LearnerModelConflictError,
    LearnerModelCorrectionNotFoundError,
    LearnerModelStaleReviewError,
)

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
    scope = {
        "learner_id": str(learner.id),
        "educator_id": str(educator.id),
        "actor_reference": str(learner.id),
    }
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
        if suffix == "one":
            session.add(
                Enrollment(
                    course_id=course.id,
                    student_id=learner.id,
                    status=EnrollmentStatus.ACTIVE,
                )
            )
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
    evidence_link = LearnerModelEvidenceLink(
        id="link-before-correction",
        estimate_id=estimate.id,
        evidence_id="evidence-record-1",
        relation=EvidenceLinkRelation.SUPPORTS,
    )
    session.add_all((snapshot, estimate))
    session.flush()
    session.add(evidence_link)
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


def _annotation_command(
    scope: dict[str, str],
    **overrides: object,
) -> LearnerAnnotationCommand:
    values: dict[str, object] = {
        "annotation_id": "service-annotation-1",
        "course_id": scope["course_one"],
        "learner_id": scope["learner_id"],
        "outcome_id": scope["outcome_one"],
        "target": {
            "target_kind": CorrectionTargetKind.EVIDENCE,
            "evidence_id": "evidence-record-1",
        },
        "record_version": 1,
        "actor_reference": scope["learner_id"],
        "correlation_id": "service-correlation-1",
        "idempotency_key": "service-annotation-key-1",
        "occurred_at": NOW + timedelta(minutes=2),
        "note": "The response needs my additional context.",
    }
    values.update(overrides)
    return LearnerAnnotationCommand.model_validate(values)


def _review_command(
    scope: dict[str, str],
    **overrides: object,
) -> EducatorCorrectionReviewCommand:
    values: dict[str, object] = {
        "review_id": "service-review-1",
        "annotation_id": "service-annotation-1",
        "course_id": scope["course_one"],
        "learner_id": scope["learner_id"],
        "outcome_id": scope["outcome_one"],
        "target": {
            "target_kind": CorrectionTargetKind.EVIDENCE,
            "evidence_id": "evidence-record-1",
        },
        "review_version": 1,
        "expected_latest_review_version": 0,
        "action": CorrectionAction.NEEDS_REVIEW,
        "reason": "The learner context requires educator review.",
        "actor_reference": scope["educator_id"],
        "correlation_id": "service-correlation-1",
        "idempotency_key": "service-review-key-1",
        "occurred_at": NOW + timedelta(minutes=3),
    }
    values.update(overrides)
    return EducatorCorrectionReviewCommand.model_validate(values)


def _build_command(
    scope: dict[str, str],
    **overrides: object,
) -> LearnerModelBuildCommand:
    values: dict[str, object] = {
        "snapshot_id": "snapshot-after-correction",
        "course_id": scope["course_one"],
        "learner_id": scope["learner_id"],
        "outcome_id": scope["outcome_one"],
        "prior_snapshot_id": "snapshot-before-correction",
        "model_source": ModelSource.RULE_BASED,
        "model_version": "learner-model-rules.v1",
        "rule_version": "learner-rules.v1",
        "record_version": 2,
        "actor_reference": scope["learner_id"],
        "agent_reference": "learner-model-agent.v1",
        "correlation_id": "build-after-correction-correlation",
        "idempotency_key": "build-after-correction-key",
        "occurred_at": NOW + timedelta(minutes=10),
        "evidence_signals": (
            LearnerModelEvidenceSignal(
                evidence_id="evidence-record-1",
                relation=EvidenceLinkRelation.SUPPORTS,
            ),
        ),
    }
    values.update(overrides)
    return LearnerModelBuildCommand.model_validate(values)


def _accept_correction(
    service: LearnerModelCorrectionService,
    scope: dict[str, str],
    target: dict[str, object],
) -> None:
    service.annotate(_annotation_command(scope, target=target))
    service.review(
        _review_command(
            scope,
            target=target,
            action=CorrectionAction.ACCEPTED,
            reason="The correction is supported and must inform the next snapshot.",
        )
    )


class _PermissiveCorrectionPolicy:
    def can_annotate(self, _: LearnerAnnotationCommand) -> bool:
        return True

    def can_review(self, _: EducatorCorrectionReviewCommand) -> bool:
        return True

    def can_read_history(self, **_: str) -> bool:
        return True


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


def test_correction_service_supports_exact_replay_history_and_accepted_lookup(
    db_session: Session,
) -> None:
    scope = _seed_target_history(db_session)
    repository = SqlAlchemyLearnerModelRepository(db_session)
    service = LearnerModelCorrectionService(repository)

    created = service.annotate(_annotation_command(scope))
    replayed = service.annotate(_annotation_command(scope))
    estimate_annotation = service.annotate(
        _annotation_command(
            scope,
            annotation_id="service-annotation-2",
            target={
                "target_kind": CorrectionTargetKind.ESTIMATE,
                "estimate_id": "estimate-before-correction",
            },
            idempotency_key="service-annotation-key-2",
            occurred_at=NOW + timedelta(minutes=3),
        )
    )
    first_review = service.review(_review_command(scope))
    replayed_review = service.review(_review_command(scope))

    assert created.created is True
    assert replayed.created is False
    assert replayed.annotation == created.annotation
    assert estimate_annotation.created is True
    assert first_review.created is True
    assert replayed_review.created is False
    assert (
        repository.accepted_corrections(
            course_id=scope["course_one"],
            learner_id=scope["learner_id"],
            outcome_id=scope["outcome_one"],
        )
        == ()
    )

    accepted = service.review(
        _review_command(
            scope,
            review_id="service-review-2",
            review_version=2,
            expected_latest_review_version=1,
            action=CorrectionAction.ACCEPTED,
            reason="The learner context is supported by the immutable evidence.",
            idempotency_key="service-review-key-2",
            occurred_at=NOW + timedelta(minutes=4),
        )
    )
    learner_history = service.history(
        actor_reference=scope["learner_id"],
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )
    educator_history = service.history(
        actor_reference=scope["educator_id"],
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )
    latest = repository.latest_correction_review(
        annotation_id="service-annotation-1",
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )
    accepted_corrections = repository.accepted_corrections(
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )

    assert accepted.created is True
    assert learner_history == educator_history
    assert len(learner_history) == 2
    evidence_history = next(
        item for item in learner_history if item.annotation.annotation_id == "service-annotation-1"
    )
    assert [review.review_version for review in evidence_history.reviews] == [1, 2]
    assert latest == accepted.review
    assert len(accepted_corrections) == 1
    assert accepted_corrections[0].review == accepted.review


def test_repository_scope_checks_override_a_permissive_caller_policy(
    db_session: Session,
) -> None:
    scope = _seed_target_history(db_session)
    other_learner = User(
        email="other-correction-learner@example.edu",
        password_hash="hash",
        full_name="Other Correction Learner",
        role=UserRole.STUDENT,
        is_active=True,
    )
    db_session.add(other_learner)
    db_session.flush()
    db_session.add(
        Enrollment(
            course_id=scope["course_one"],
            student_id=other_learner.id,
            status=EnrollmentStatus.ACTIVE,
        )
    )
    db_session.commit()
    service = LearnerModelCorrectionService(
        SqlAlchemyLearnerModelRepository(db_session),
        _PermissiveCorrectionPolicy(),
    )
    unavailable_commands = (
        _annotation_command(
            scope,
            target={
                "target_kind": CorrectionTargetKind.EVIDENCE,
                "evidence_id": "missing-evidence",
            },
        ),
        _annotation_command(
            scope,
            course_id=scope["course_two"],
            outcome_id=scope["outcome_two"],
        ),
        _annotation_command(scope, actor_reference=scope["educator_id"]),
        _annotation_command(
            scope,
            learner_id=str(other_learner.id),
            actor_reference=str(other_learner.id),
        ),
    )

    messages: list[str] = []
    for unavailable in unavailable_commands:
        with pytest.raises(LearnerModelCorrectionNotFoundError) as error:
            service.annotate(unavailable)
        messages.append(str(error.value))
    assert messages == ["correction target is unavailable"] * len(unavailable_commands)
    assert db_session.scalar(select(func.count()).select_from(LearnerModelAnnotation)) == 0

    service.annotate(_annotation_command(scope))
    outsider = User(
        email="outside-correction-educator@example.edu",
        password_hash="hash",
        full_name="Outside Correction Educator",
        role=UserRole.EDUCATOR,
        is_active=True,
    )
    db_session.add(outsider)
    db_session.commit()
    review_commands = (
        _review_command(scope, actor_reference=str(outsider.id)),
        _review_command(
            scope,
            target={
                "target_kind": CorrectionTargetKind.ESTIMATE,
                "estimate_id": "estimate-before-correction",
            },
        ),
    )
    for unavailable in review_commands:
        with pytest.raises(
            LearnerModelCorrectionNotFoundError,
            match="correction target is unavailable",
        ):
            service.review(unavailable)
    with pytest.raises(
        LearnerModelCorrectionNotFoundError,
        match="correction history is unavailable",
    ):
        service.history(
            actor_reference=str(outsider.id),
            course_id=scope["course_one"],
            learner_id=scope["learner_id"],
            outcome_id=scope["outcome_one"],
        )
    assert db_session.scalar(select(func.count()).select_from(LearnerModelCorrectionReview)) == 0


def test_conflicting_stale_and_inactive_commands_leave_history_atomic(
    db_session: Session,
) -> None:
    scope = _seed_target_history(db_session)
    service = LearnerModelCorrectionService(SqlAlchemyLearnerModelRepository(db_session))
    service.annotate(_annotation_command(scope))

    with pytest.raises(LearnerModelConflictError, match="idempotency"):
        service.annotate(_annotation_command(scope, note="Conflicting replay content."))
    service.review(_review_command(scope))
    with pytest.raises(LearnerModelConflictError, match="idempotency"):
        service.review(_review_command(scope, reason="Conflicting replay reason."))
    with pytest.raises(LearnerModelStaleReviewError, match="stale"):
        service.review(
            _review_command(
                scope,
                review_id="stale-review",
                idempotency_key="stale-review-key",
            )
        )

    educator = db_session.get(User, int(scope["educator_id"]))
    assert educator is not None
    educator.is_active = False
    db_session.commit()
    with pytest.raises(LearnerModelCorrectionNotFoundError):
        service.review(_review_command(scope))
    with pytest.raises(LearnerModelCorrectionNotFoundError):
        service.review(
            _review_command(
                scope,
                review_id="inactive-educator-review",
                review_version=2,
                expected_latest_review_version=1,
                idempotency_key="inactive-educator-review-key",
            )
        )

    learner = db_session.get(User, int(scope["learner_id"]))
    assert learner is not None
    learner.is_active = False
    db_session.commit()
    with pytest.raises(LearnerModelCorrectionNotFoundError):
        service.annotate(_annotation_command(scope))
    with pytest.raises(LearnerModelCorrectionNotFoundError):
        service.annotate(
            _annotation_command(
                scope,
                annotation_id="inactive-learner-annotation",
                idempotency_key="inactive-learner-annotation-key",
            )
        )
    learner.is_active = True
    enrollment = db_session.scalar(
        select(Enrollment).where(
            Enrollment.course_id == scope["course_one"],
            Enrollment.student_id == learner.id,
        )
    )
    assert enrollment is not None
    enrollment.status = EnrollmentStatus.WITHDRAWN
    db_session.commit()
    with pytest.raises(LearnerModelCorrectionNotFoundError):
        service.annotate(
            _annotation_command(
                scope,
                annotation_id="withdrawn-learner-annotation",
                idempotency_key="withdrawn-learner-annotation-key",
            )
        )

    assert db_session.scalar(select(func.count()).select_from(LearnerModelAnnotation)) == 1
    assert db_session.scalar(select(func.count()).select_from(LearnerModelCorrectionReview)) == 1


def test_concurrent_exact_duplicates_resolve_to_replay_without_partial_rows(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = _seed_target_history(db_session)
    repository = SqlAlchemyLearnerModelRepository(db_session)
    service = LearnerModelCorrectionService(repository)
    service.annotate(_annotation_command(scope))

    original_annotation_lookup = repository._annotation_by_idempotency
    annotation_lookups = 0

    def delayed_annotation_lookup(command, learner_id):
        nonlocal annotation_lookups
        annotation_lookups += 1
        if annotation_lookups == 1:
            return None
        return original_annotation_lookup(command, learner_id)

    monkeypatch.setattr(repository, "_annotation_by_idempotency", delayed_annotation_lookup)
    collided_annotation = service.annotate(_annotation_command(scope))
    monkeypatch.setattr(repository, "_annotation_by_idempotency", original_annotation_lookup)
    service.review(_review_command(scope))

    original_review_lookup = repository._review_by_idempotency
    original_latest_review = repository._latest_review_row
    review_lookups = 0
    latest_review_lookups = 0

    def delayed_review_lookup(command, learner_id):
        nonlocal review_lookups
        review_lookups += 1
        if review_lookups == 1:
            return None
        return original_review_lookup(command, learner_id)

    def delayed_latest_review(annotation_id):
        nonlocal latest_review_lookups
        latest_review_lookups += 1
        if latest_review_lookups == 1:
            return None
        return original_latest_review(annotation_id)

    monkeypatch.setattr(repository, "_review_by_idempotency", delayed_review_lookup)
    monkeypatch.setattr(repository, "_latest_review_row", delayed_latest_review)
    collided_review = service.review(_review_command(scope))

    assert collided_annotation.created is False
    assert collided_review.created is False
    assert db_session.scalar(select(func.count()).select_from(LearnerModelAnnotation)) == 1
    assert db_session.scalar(select(func.count()).select_from(LearnerModelCorrectionReview)) == 1


@pytest.mark.parametrize(
    "target",
    (
        {
            "target_kind": CorrectionTargetKind.EVIDENCE,
            "evidence_id": "evidence-record-1",
        },
        {
            "target_kind": CorrectionTargetKind.ESTIMATE,
            "estimate_id": "estimate-before-correction",
        },
    ),
)
def test_accepted_correction_marks_only_later_snapshot_for_review_and_links_it(
    db_session: Session,
    target: dict[str, object],
) -> None:
    scope = _seed_target_history(db_session)
    repository = SqlAlchemyLearnerModelRepository(db_session)
    correction_service = LearnerModelCorrectionService(repository)
    before = repository.timeline(
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )
    _accept_correction(correction_service, scope, target)

    result = LearnerModelBuildService(
        repository,
        DeterministicLearnerModelBuilder(),
    ).build(_build_command(scope))
    after = repository.timeline(
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )
    correction_links = db_session.scalars(select(LearnerModelCorrectionSnapshotLink)).all()
    stored_estimate = db_session.scalar(
        select(LearnerOutcomeEstimate).where(
            LearnerOutcomeEstimate.snapshot_id == "snapshot-after-correction"
        )
    )

    assert result.state is LearnerModelBuildState.STORED
    assert len(before) == 1 and len(after) == 2
    assert after[0] == before[0]
    assert before[0].estimates[0].inference_status is InferenceStatus.SUPPORTED
    assert after[1].estimates[0].inference_status is InferenceStatus.NEEDS_REVIEW
    assert after[1].estimates[0].evidence_ids == before[0].estimates[0].evidence_ids
    assert stored_estimate is not None
    assert stored_estimate.reason_code == "correction.accepted-review.v1"
    assert stored_estimate.uncertainty == 0.8
    assert len(correction_links) == 1
    assert correction_links[0].review_id == "service-review-1"
    assert correction_links[0].snapshot_id == "snapshot-after-correction"


@pytest.mark.parametrize(
    "action",
    (CorrectionAction.REJECTED, CorrectionAction.NEEDS_REVIEW),
)
def test_rejected_and_pending_corrections_leave_deterministic_output_unchanged(
    db_session: Session,
    action: CorrectionAction,
) -> None:
    scope = _seed_target_history(db_session)
    repository = SqlAlchemyLearnerModelRepository(db_session)
    correction_service = LearnerModelCorrectionService(repository)
    correction_service.annotate(_annotation_command(scope))
    correction_service.review(_review_command(scope, action=action))
    before = repository.timeline(
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )

    result = LearnerModelBuildService(
        repository,
        DeterministicLearnerModelBuilder(),
    ).build(_build_command(scope))
    after = repository.timeline(
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )

    assert result.state is LearnerModelBuildState.STORED
    assert after[0] == before[0]
    assert after[1].estimates[0].inference_status is InferenceStatus.SUPPORTED
    assert (
        db_session.scalar(select(func.count()).select_from(LearnerModelCorrectionSnapshotLink)) == 0
    )


def test_provider_failure_preserves_accepted_correction_and_existing_snapshot(
    db_session: Session,
) -> None:
    class _FailingBuilder:
        model_version = "learner-model-rules.v1"

        def build(self, *_: object) -> LearnerModelSnapshotPayload | None:
            raise RuntimeError("provider failed")

    scope = _seed_target_history(db_session)
    repository = SqlAlchemyLearnerModelRepository(db_session)
    correction_service = LearnerModelCorrectionService(repository)
    _accept_correction(
        correction_service,
        scope,
        {
            "target_kind": CorrectionTargetKind.EVIDENCE,
            "evidence_id": "evidence-record-1",
        },
    )
    before = repository.timeline(
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )

    result = LearnerModelBuildService(repository, _FailingBuilder()).build(_build_command(scope))

    assert result.state is LearnerModelBuildState.PROVIDER_UNAVAILABLE
    assert (
        repository.timeline(
            course_id=scope["course_one"],
            learner_id=scope["learner_id"],
            outcome_id=scope["outcome_one"],
        )
        == before
    )
    assert db_session.scalar(select(func.count()).select_from(LearnerModelAnnotation)) == 1
    assert db_session.scalar(select(func.count()).select_from(LearnerModelCorrectionReview)) == 1
    assert (
        db_session.scalar(select(func.count()).select_from(LearnerModelCorrectionSnapshotLink)) == 0
    )


def test_correction_accepted_during_build_causes_stale_conflict_without_snapshot(
    db_session: Session,
) -> None:
    scope = _seed_target_history(db_session)
    repository = SqlAlchemyLearnerModelRepository(db_session)
    correction_service = LearnerModelCorrectionService(repository)
    correction_service.annotate(_annotation_command(scope))
    correction_service.review(_review_command(scope))

    class _AcceptDuringBuild:
        model_version = "learner-model-rules.v1"

        def __init__(self) -> None:
            self._delegate = DeterministicLearnerModelBuilder()

        def build(self, command, observations):
            correction_service.review(
                _review_command(
                    scope,
                    review_id="service-review-2",
                    review_version=2,
                    expected_latest_review_version=1,
                    action=CorrectionAction.ACCEPTED,
                    idempotency_key="service-review-key-2",
                    occurred_at=NOW + timedelta(minutes=4),
                )
            )
            return self._delegate.build(command, observations)

    with pytest.raises(LearnerModelStaleReviewError, match="changed during"):
        LearnerModelBuildService(repository, _AcceptDuringBuild()).build(_build_command(scope))

    assert db_session.scalar(select(func.count()).select_from(LearnerModelSnapshot)) == 1
    assert db_session.scalar(select(func.count()).select_from(LearnerModelCorrectionReview)) == 2
    assert (
        db_session.scalar(select(func.count()).select_from(LearnerModelCorrectionSnapshotLink)) == 0
    )


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
