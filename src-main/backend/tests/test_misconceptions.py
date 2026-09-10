"""A possible misconception needs scoped observations and human review, never a grade."""

from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from test_escalation import setup

from app.models.assessment import AssessmentDecision
from app.models.learning_evidence import LearningEvidence
from app.models.misconceptions import MisconceptionReviewRecord
from app.models.user import User, UserRole
from app.schemas.misconceptions import MisconceptionAnswer, MisconceptionOpen, MisconceptionReview
from app.schemas.tutor import TutorTurnWrite
from app.services.learner_model.repository import SqlAlchemyLearnerModelRepository
from app.services.lms import LmsServiceError
from app.services.misconceptions import MisconceptionService
from app.services.tutor import TutorService


def context(session, *, support_level=2):
    fixture, queue, educator, backup, student, feedback, _ = setup(session)
    evidence = list(
        session.scalars(
            select(LearningEvidence.id).where(
                LearningEvidence.response_version_id == fixture["response_id"],
            )
        )
    )
    assert evidence
    command = MisconceptionOpen(
        request_key="open",
        feedback_id=feedback.id,
        hypothesis="The learner may be treating each sampled count as an exact probability.",
        confidence=0.5,
        evidence_ids=evidence[:1],
        probe="How would you interpret a different count on the next run?",
        explanation="Sampling varies between runs. Compare that with the predicted distribution.",
        explanation_support_level=support_level,
        fresh_question="PRIVATE fresh question: explain what changes with more samples.",
        selection_reason="The saved explanation does not distinguish sampled counts from probabilities.",
        content_approval_reason="Synthetic educator reviewed these prompts against the approved course source.",
        persistence_stages=["PROBE", "REVISION"],
    )
    service = MisconceptionService(session)
    saved = service.open(educator, command)
    return fixture, queue, educator, backup, student, service, command, saved


def answer(service, student, saved, *, helped=False):
    command = MisconceptionAnswer(
        request_key=str(uuid4()),
        expected_version=saved.version,
        stage=saved.next_stage,
        answer="Counts can change while the predicted probability remains fixed.",
        reasoning="The number of samples affects the observed proportions.",
        confidence=0.6,
        help_used=helped,
        start_fresh_check=saved.next_stage == "REVISION",
    )
    return service.answer(student, saved.id, command), command


def finish(service, student, saved, *, helped=False):
    for _ in range(3):
        saved, _ = answer(service, student, saved, helped=helped)
    return saved


def review_command(saved, state="UNCERTAIN", **changes):
    payload = dict(
        request_key=str(uuid4()),
        expected_version=saved.version,
        state=state,
        confidence=0.6,
        supports=[saved.responses[0].evidence_id],
        contradicts=[saved.responses[-1].evidence_id],
        reason="The fresh response challenges the original hypothesis; retain both observations.",
        next_action="Compare the observed and predicted distributions on another approved activity.",
    )
    payload.update(changes)
    return MisconceptionReview(**payload)


def test_full_cycle_hides_help_preserves_corrections_and_routes_unresolved_case(db_session):
    fixture, queue, educator, _, student, service, opened, saved = context(db_session)
    decision = db_session.get(AssessmentDecision, fixture["decision_id"])
    original = (decision.result, decision.result_state)
    assert service.open(educator, opened).id == saved.id
    read = service.read(student, saved.id)
    assert read.state == "UNCERTAIN"
    assert read.fresh_question is None and read.explanation is None
    first, command = answer(service, student, read)
    assert first.explanation and first.fresh_question is None
    assert service.answer(student, first.id, command).version == 1
    second, _ = answer(service, student, first)
    assert second.next_stage == "TRANSFER" and second.fresh_question
    assert second.explanation is None and second.probe is None and second.responses == []
    tutor = TutorService(db_session)
    state = tutor.read(student, saved.task_id)
    assert not state.instructional_help_available and state.turns == []
    with pytest.raises(LmsServiceError, match="unavailable"):
        tutor.send(
            student,
            saved.task_id,
            TutorTurnWrite(
                message="Explain this step",
                expected_revision=state.revision,
                idempotency_key="help",
                context_token=state.context_token,
            ),
        )
    db_session.rollback()
    complete, _ = answer(service, student, second)
    assert len(complete.responses) == 3
    first_review = review_command(complete)
    reviewed = service.review(educator, complete.id, first_review)
    assert reviewed.state == "UNCERTAIN" and reviewed.reviews[0].escalation_id
    assert service.review(educator, complete.id, first_review).version == 4
    corrected = service.review(educator, complete.id, review_command(reviewed, "CORRECTED"))
    assert corrected.state == "CORRECTED"
    assert [item.state for item in corrected.reviews] == ["UNCERTAIN", "CORRECTED"]
    cases = queue.queue(educator, fixture["course_id"], "ASSESSOR")
    assert len(cases) == 1 and cases[0].trigger == "UNRESOLVED_MISCONCEPTION"
    head = SqlAlchemyLearnerModelRepository(db_session).current(
        course_id=saved.course_id,
        learner_id=str(student.id),
        outcome_id=saved.outcome_id,
    )
    assert head.prior_snapshot_id == reviewed.reviews[0].snapshot_id
    assert all(item.uncertainty == 1 for item in head.estimates)
    assert (decision.result, decision.result_state) == original
    evidence = db_session.get(LearningEvidence, corrected.reviews[-1].evidence_id)
    assert evidence.actor_reference == str(educator.id)
    assert evidence.learner_id == student.id
    for table in ("misconception_hypotheses", "misconception_responses", "misconception_reviews"):
        with pytest.raises(IntegrityError, match="immutable"):
            db_session.execute(text(f"DELETE FROM {table}"))
        db_session.rollback()


@pytest.mark.parametrize("state", ["UNCERTAIN", "PERSISTED", "WEAKENED", "CORRECTED"])
def test_review_states_require_retained_evidence_and_remain_uncertain(db_session, state):
    _, _, educator, _, student, service, _, saved = context(db_session)
    complete = finish(service, student, saved)
    command = review_command(
        complete, state, supports=[item.evidence_id for item in complete.responses[:2]]
    )
    result = service.review(educator, saved.id, command)
    assert result.state == state
    assert result.reviews[0].confidence < 1
    assert result.reviews[0].supports == command.supports
    assert result.reviews[0].contradicts == command.contradicts


def test_one_answer_and_supported_transfer_cannot_create_persisted_or_corrected_claim(db_session):
    _, _, educator, _, student, service, _, saved = context(db_session)
    one, _ = answer(service, student, saved)
    with pytest.raises(LmsServiceError, match="before recording a state"):
        service.review(educator, saved.id, review_command(one, contradicts=[]))
    db_session.rollback()
    two, _ = answer(service, student, one)
    three, _ = answer(service, student, two, helped=True)
    for command in (review_command(three, "PERSISTED"), review_command(three, "CORRECTED")):
        with pytest.raises(LmsServiceError):
            service.review(educator, saved.id, command)
        db_session.rollback()
    assert list(db_session.scalars(select(MisconceptionReviewRecord))) == []


def test_scope_replay_stale_and_stage_guards(db_session):
    _, _, educator, _, student, service, opened, saved = context(db_session)
    other = User(
        email=f"other-{uuid4().hex}@example.edu",
        full_name="Other",
        password_hash="unused",
        role=UserRole.STUDENT,
    )
    db_session.add(other)
    db_session.commit()
    with pytest.raises(Exception) as error:
        service.read(other, saved.id)
    assert error.value.status_code == 404
    with pytest.raises(LmsServiceError, match="different details"):
        service.open(educator, opened.model_copy(update={"probe": "Different"}))
    db_session.rollback()
    skipped = MisconceptionAnswer(
        request_key="skip",
        expected_version=0,
        stage="TRANSFER",
        answer="Answer",
        reasoning="Reason",
        confidence=0.5,
        help_used=False,
    )
    with pytest.raises(LmsServiceError, match="in order"):
        service.answer(student, saved.id, skipped)
    db_session.rollback()
    first, command = answer(service, student, saved)
    with pytest.raises(LmsServiceError, match="different details"):
        service.answer(student, saved.id, command.model_copy(update={"answer": "Different"}))
    db_session.rollback()
    with pytest.raises(LmsServiceError, match="changed"):
        service.answer(student, saved.id, command.model_copy(update={"request_key": "stale"}))
    db_session.rollback()
    assert service.read(student, saved.id).version == first.version
