"""Transactional and privacy-boundary tests for learner-model corrections."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session
from test_evidence_repository import NOW, _record, _seed_scope

from app.domain.platform_enums import (
    CorrectionAction,
    CorrectionTargetKind,
    EvidenceType,
)
from app.models.lms import Course, Enrollment, EnrollmentStatus
from app.services.evidence.repository import EvidenceCapture, SqlAlchemyEvidenceRepository
from app.services.learner_model.correction_contracts import (
    CorrectionTarget,
    EducatorCorrectionReviewCommand,
    LearnerAnnotationCommand,
)
from app.services.learner_model.correction_repository import (
    SqlAlchemyLearnerModelCorrectionRepository,
)
from app.services.learner_model.corrections import LearnerModelCorrectionService
from app.services.learner_model.safety import (
    LearnerModelConflictError,
    LearnerModelCorrectionNotFoundError,
    LearnerModelStaleReviewError,
)


def _enrol(session: Session, scope: dict[str, str]) -> str:
    course = session.get(Course, scope["course_one"])
    assert course is not None
    session.add(
        Enrollment(
            course_id=course.id,
            student_id=int(scope["learner_id"]),
            status=EnrollmentStatus.ACTIVE,
        )
    )
    session.commit()
    return str(course.educator_id)


def _command(scope: dict[str, str], **overrides: object) -> LearnerAnnotationCommand:
    values: dict[str, object] = {
        "annotation_id": "annotation-1",
        "course_id": scope["course_one"],
        "learner_id": scope["learner_id"],
        "outcome_id": scope["outcome_one"],
        "target": CorrectionTarget(
            target_kind=CorrectionTargetKind.EVIDENCE, evidence_id="evidence-1"
        ),
        "actor_reference": scope["learner_id"],
        "correlation_id": "correction-correlation-1",
        "idempotency_key": "annotation-key-1",
        "occurred_at": NOW,
        "record_version": 1,
        "note": "The recorded context is incomplete.",
    }
    values.update(overrides)
    return LearnerAnnotationCommand.model_validate(values)


def _seed_annotation(session: Session) -> tuple[dict[str, str], str, LearnerAnnotationCommand]:
    scope = _seed_scope(session)
    educator_id = _enrol(session, scope)
    SqlAlchemyEvidenceRepository(session).capture(
        EvidenceCapture(
            record=_record(
                scope,
                evidence_id="evidence-1",
                evidence_type=EvidenceType.REASONING,
                artifact_id=None,
                idempotency_key="evidence-key-1",
            )
        )
    )
    command = _command(scope)
    return scope, educator_id, command


def test_annotation_replays_exactly_and_conflicting_key_preserves_history(
    db_session: Session,
) -> None:
    scope, _, command = _seed_annotation(db_session)
    service = LearnerModelCorrectionService(SqlAlchemyLearnerModelCorrectionRepository(db_session))

    first = service.annotate(command)
    replay = service.annotate(command)

    assert first.created is True
    assert replay.created is False
    with pytest.raises(LearnerModelConflictError):
        service.annotate(_command(scope, note="Different protected note."))
    history = service.history(
        actor_reference=scope["learner_id"],
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )
    assert [item.annotation.annotation_id for item in history] == ["annotation-1"]


def test_review_is_ordered_and_stale_or_cross_scope_requests_do_not_write(
    db_session: Session,
) -> None:
    scope, educator_id, annotation = _seed_annotation(db_session)
    service = LearnerModelCorrectionService(SqlAlchemyLearnerModelCorrectionRepository(db_session))
    service.annotate(annotation)
    review = EducatorCorrectionReviewCommand.model_validate(
        {
            "review_id": "review-1",
            "annotation_id": "annotation-1",
            "course_id": scope["course_one"],
            "learner_id": scope["learner_id"],
            "outcome_id": scope["outcome_one"],
            "target": annotation.target,
            "actor_reference": educator_id,
            "correlation_id": "review-correlation-1",
            "idempotency_key": "review-key-1",
            "occurred_at": NOW + timedelta(minutes=1),
            "review_version": 1,
            "expected_latest_review_version": 0,
            "action": CorrectionAction.NEEDS_REVIEW,
            "reason": "A controlled follow-up is required.",
        }
    )
    assert service.review(review).created is True
    with pytest.raises(LearnerModelStaleReviewError):
        service.review(
            review.model_copy(update={"review_id": "review-2", "idempotency_key": "review-key-2"})
        )
    with pytest.raises(LearnerModelCorrectionNotFoundError):
        service.history(
            actor_reference="99999",
            course_id=scope["course_one"],
            learner_id=scope["learner_id"],
            outcome_id=scope["outcome_one"],
        )
    assert (
        len(
            service.history(
                actor_reference=educator_id,
                course_id=scope["course_one"],
                learner_id=scope["learner_id"],
                outcome_id=scope["outcome_one"],
            )[0].reviews
        )
        == 1
    )


class _FailingAudit:
    def record(self, _event) -> None:
        raise RuntimeError("protected note must never leave persistence")


def test_audit_failure_does_not_undo_durable_annotation(db_session: Session) -> None:
    scope, _, command = _seed_annotation(db_session)
    service = LearnerModelCorrectionService(
        SqlAlchemyLearnerModelCorrectionRepository(db_session), _FailingAudit()
    )
    result = service.annotate(command)
    assert result.audit_recorded is False
    assert result.audit_failure_category == "audit_unavailable"
    assert (
        service.history(
            actor_reference=scope["learner_id"],
            course_id=scope["course_one"],
            learner_id=scope["learner_id"],
            outcome_id=scope["outcome_one"],
        )[0].annotation.note
        == command.note
    )
