"""Reviewed teaching remains visible in evidence without changing earlier observations."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from test_misconceptions import answer, context, finish, review_command
from test_task14_lifecycle import complete, setup_episode

from app.domain.platform_enums import EvidenceType, InstructionalSupportLevel
from app.models.learning_evidence import LearningEvidence
from app.models.lms import Course, CourseState, SubmissionAttempt
from app.schemas.lms import SubmissionCreate
from app.schemas.misconceptions import MisconceptionExit
from app.services.evidence.live import LiveEvidenceCapture
from app.services.lms import LmsServiceError
from app.services.misconception_state import active_assessed_transfer


def test_teaching_is_retained_for_future_work_and_extra_help_cannot_be_downgraded(db_session):
    fixture, _, educator, _, student, service, opened, saved = context(db_session)
    original = db_session.get(SubmissionAttempt, fixture["response_id"])
    capture = LiveEvidenceCapture(db_session)
    before = capture._support_for(original.assessment_work_start_id, original.submitted_at)
    first, _ = answer(service, student, saved)
    teaching = db_session.scalar(
        select(LearningEvidence).where(
            LearningEvidence.evidence_type == EvidenceType.SCAFFOLD,
        )
    )
    assert teaching.instructional_support_level == InstructionalSupportLevel.CONCEPT_CUE
    assert capture._support_for(original.assessment_work_start_id, original.submitted_at) == before
    level, _, parents = capture._support_for(original.assessment_work_start_id, datetime.now(UTC))
    assert level == InstructionalSupportLevel.CONCEPT_CUE and teaching.id in parents
    second, _ = answer(service, student, first, helped=True)
    assert second.initial_evidence == []
    educator_view = service.read(educator, saved.id)
    revision = db_session.get(LearningEvidence, educator_view.responses[-1].evidence_id)
    assert revision.instructional_support_level == InstructionalSupportLevel.DIRECT_ANSWER
    assert educator_view.initial_evidence[0].id == opened.evidence_ids[0]
    assert educator_view.initial_evidence[0].content
    third, _ = answer(service, student, second)
    transfer = db_session.get(LearningEvidence, third.responses[-1].evidence_id)
    assert transfer.instructional_support_level == InstructionalSupportLevel.INDEPENDENT


def test_actual_assessed_transfer_is_active_until_submission(db_session):
    lms, student, task, started = setup_episode(db_session)
    assert active_assessed_transfer(db_session, student.id, task.id) is None
    payload = complete(lms, student, task, started)
    assert active_assessed_transfer(db_session, student.id, task.id)
    lms.submit(
        student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="transfer")
    )
    assert active_assessed_transfer(db_session, student.id, task.id) is None


def test_educator_approved_persistence_stages_control_the_claim(db_session):
    _, _, educator, _, student, service, opened, saved = context(db_session)
    service.exit(
        student,
        saved.id,
        MisconceptionExit(
            request_key="leave",
            expected_version=0,
            disposition="DEFERRED",
            reason="Use a new check.",
        ),
    )
    saved = service.open(
        educator,
        opened.model_copy(
            update={
                "request_key": "approved-rule",
                "persistence_stages": ["PROBE", "TRANSFER"],
                "fresh_question": "Interpret a different sampling result using the same model.",
            }
        ),
    )
    done = finish(service, student, saved)
    with pytest.raises(LmsServiceError, match="approved for this cycle"):
        service.review(
            educator,
            done.id,
            review_command(
                done,
                "PERSISTED",
                supports=[item.evidence_id for item in done.responses[:2]],
                contradicts=[],
            ),
        )
    db_session.rollback()
    reviewed = service.review(
        educator,
        done.id,
        review_command(
            done,
            "PERSISTED",
            supports=[done.responses[0].evidence_id, done.responses[2].evidence_id],
            contradicts=[],
        ),
    )
    assert reviewed.state == "PERSISTED"
    db_session.get(Course, saved.course_id).state = CourseState.ARCHIVED
    db_session.commit()
    assert service.list_owned(student) == []
