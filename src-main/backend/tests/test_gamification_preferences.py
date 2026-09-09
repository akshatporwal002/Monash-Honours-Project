"""Rewards remain optional and independent of marks, pacing and access."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from support.task_review import bootstrap_reviewed_demo

from app.domain.platform_enums import EvidenceType
from app.models.gamification import GamificationPreference, ParticipationRecognition
from app.models.lms import TaskPointAward
from app.models.persistence import Achievement, LearningTask, StudentAchievement, StudentProfile
from app.models.user import UserRole
from app.schemas.gamification import GamificationPreferenceWrite
from app.schemas.lms import SubmissionCreate
from app.services.evidence.live import LiveEvidenceCapture
from app.services.gamification import GamificationService
from app.services.lms import LmsService


def context(session):
    users, _ = bootstrap_reviewed_demo(session)
    student = next(user for user in users if user.role is UserRole.STUDENT)
    task = session.scalar(select(LearningTask).order_by(LearningTask.position))
    return student, task, GamificationService(session), LmsService(session)


def test_opt_out_persists_and_does_not_change_learning_access(db_session):
    student, task, gamification, lms = context(db_session)
    before = lms.student_dashboard(student)
    command = GamificationPreferenceWrite(enabled=False, expected_revision=0, idempotency_key="off")
    assert gamification.save_preference(student.id, command).revision == 1
    assert not gamification.save_preference(student.id, command).enabled
    with pytest.raises(ValueError, match="different details"):
        gamification.save_preference(student.id, command.model_copy(update={"enabled": True}))
    db_session.rollback()
    with pytest.raises(ValueError, match="changed"):
        gamification.save_preference(
            student.id, command.model_copy(update={"idempotency_key": "stale"})
        )
    db_session.rollback()
    db_session.expire_all()
    after = lms.student_dashboard(student)
    assert not after.gamification_enabled
    assert after.summary.points == after.summary.level == 0
    assert after.achievements == []
    assert [(row.id, row.access_status) for row in after.tasks] == [
        (row.id, row.access_status) for row in before.tasks
    ]
    response = lms.submit(
        student, task.id, SubmissionCreate(answer=task.expected_answer, idempotency_key="opted-out")
    )
    assert response.points_awarded == 0
    assert list(db_session.scalars(select(TaskPointAward))) == []
    assert len(list(db_session.scalars(select(GamificationPreference)))) == 1
    gamification.save_preference(
        student.id,
        GamificationPreferenceWrite(enabled=True, expected_revision=1, idempotency_key="on"),
    )
    assert gamification.preference(student.id).enabled
    with pytest.raises(IntegrityError, match="immutable"):
        db_session.execute(text("DELETE FROM gamification_preferences"))
    db_session.rollback()


def test_participation_is_score_independent_and_retries_do_not_duplicate_awards(db_session):
    student, task, _, lms = context(db_session)
    wrong = "b" if task.expected_answer != "b" else "a"
    command = SubmissionCreate(answer=wrong, idempotency_key="participated")
    first = lms.submit(student, task.id, command)
    assert first.status.value == "submitted"
    assert first.points_awarded == task.points
    assert lms.submit(student, task.id, command).id == first.id
    second = lms.submit(
        student, task.id, SubmissionCreate(answer=task.expected_answer, idempotency_key="revised")
    )
    assert second.points_awarded == 0
    profile = db_session.scalar(select(StudentProfile).where(StudentProfile.user_id == student.id))
    assert profile.points == task.points
    assert len(list(db_session.scalars(select(TaskPointAward)))) == 1
    assert "perfect-score" not in {
        item.code for item in lms.student_dashboard(student).achievements
    }


@pytest.mark.parametrize(
    "kind,code",
    [
        (EvidenceType.REFLECTION, "reflection"),
        (EvidenceType.REVISION, "revision"),
        (EvidenceType.FEEDBACK_INTERACTION, "feedback-use"),
    ],
)
def test_reflection_revision_and_feedback_recognition_keeps_evidence_and_no_extra_points(
    db_session, kind, code
):
    student, task, gamification, _ = context(db_session)
    capture = LiveEvidenceCapture(db_session)

    def record(source, evidence_kind=kind):
        return capture._write(
            task=task,
            learner_id=student.id,
            source=source,
            field=evidence_kind.value,
            kind=evidence_kind,
            value={"recorded": "A learner observation"},
            occurred_at=datetime.now(UTC),
        )

    evidence = record("one")
    record("one")
    record("two")
    db_session.commit()
    recognition = db_session.scalar(select(ParticipationRecognition))
    assert recognition.evidence_id == evidence
    assert recognition.kind == kind.value
    assert len(list(db_session.scalars(select(ParticipationRecognition)))) == 1
    profile = db_session.scalar(select(StudentProfile).where(StudentProfile.user_id == student.id))
    earned = (
        select(Achievement.code)
        .join(StudentAchievement)
        .where(StudentAchievement.student_id == profile.id)
    )
    assert set(db_session.scalars(earned)) == {code}
    assert profile.points == 0
    gamification.save_preference(
        student.id,
        GamificationPreferenceWrite(enabled=False, expected_revision=0, idempotency_key="off"),
    )
    record("three")
    other_kind = (
        EvidenceType.REVISION if kind is EvidenceType.REFLECTION else EvidenceType.REFLECTION
    )
    record("new-kind-while-off", other_kind)
    db_session.commit()
    assert len(list(db_session.scalars(select(ParticipationRecognition)))) == 1
    assert set(db_session.scalars(earned)) == {code}
