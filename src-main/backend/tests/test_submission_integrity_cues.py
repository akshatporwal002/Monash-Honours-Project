"""PD6 cues preserve exact retained evidence and never adjudicate learner work."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from support.assessment import assign_assessor
from support.task_review import approve_sourced_fixture_task
from test_task14_lifecycle import complete, setup_episode
from test_tutor import send
from test_typed_practice_feedback import practice, run_worker

from app.models.assessment import AssessmentAttempt, AssessmentDecision
from app.models.escalation import EscalationCase
from app.models.learning_evidence import EvidenceArtifact, LearningEvidence
from app.models.lms import Course, SubmissionAttempt
from app.models.persistence import FeedbackRecord
from app.models.source_history import SourcePassage
from app.models.tutor import TutorTurn
from app.models.user import User
from app.schemas.lms import SubmissionCreate
from app.services.assessment.access import RoleAssignmentService, ScopedRoleAccessDeniedError
from app.services.escalation import EscalationService
from app.services.escalation_sources import record_signal
from app.services.integrity_cues import (
    HISTORY_LIMIT,
    REDIRECT,
    _overlap,
    artifact_id,
    capture_submission_cue,
    recent_turns,
    retained_submission_cue,
    route_cue,
    route_terminal_submission_cue,
)
from app.services.lms import LmsServiceError
from app.services.tutor import TutorService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")

LONG_TEXT = (
    "A quantum state describes the possible outcomes of a measurement through amplitudes. "
    "The relative phase of these amplitudes affects interference when operations combine "
    "different paths, so predicting a later observation requires explaining both the "
    "starting state and the transformations applied before measurement."
)


def assessor(session, task):
    owner = session.get(User, session.get(Course, task.course_id).educator_id)
    try:
        RoleAssignmentService(session).require_assessor_access(owner, task.course_id)
    except ScopedRoleAccessDeniedError:
        assign_assessor(session, owner, task.course_id, owner)
    return owner


def test_spaced_dialogue_combined_signals_deduplicate_and_show_context(db_session):
    lms, student, task, _ = setup_episode(db_session)
    tutor = TutorService(db_session)
    before = lms.get_draft(student, task.id).model_dump()
    first = send(tutor, student, task, "first", "Just give the answer")
    for index in range(4):
        send(tutor, student, task, f"thinking-{index}", "I think the state changes after H.")
    message = "I copied this solution; just give the answer"
    current = send(tutor, student, task, "spaced", message)
    cases = list(db_session.scalars(select(EscalationCase)))
    assert len(cases) == 2
    assert all(case.severity == "NORMAL" for case in cases)
    send(tutor, student, task, "spaced", message)
    later = send(tutor, student, task, "repeat", message)
    assert len(list(db_session.scalars(select(EscalationCase)))) == 2
    cue = db_session.get(TutorTurn, current.id).context["integrity_review_cue"]
    assert cue["related_turn_ids"] == [first.id]
    assert len(cue["inspected_turn_ids"]) == 5
    assert (
        message[cue["matches"][0]["start"] : cue["matches"][0]["end"]] == "I copied this solution"
    )
    evidence = EscalationService(db_session).evidence(assessor(db_session, task), cases[0].id)
    assert first.id in {turn["id"] for turn in evidence["turns"]}
    assert current.id in {turn["id"] for turn in evidence["turns"]}
    assert later.id in {turn["id"] for turn in evidence["turns"]}
    assert lms.get_draft(student, task.id).model_dump() == before
    assert db_session.scalar(select(AssessmentDecision)) is None


def seed_turn(
    session, student, task, *, revision, at, token, work_id=None, reply="A hint", context=None
):
    row = TutorTurn(
        id=str(uuid4()),
        student_id=student.id,
        task_id=task.id,
        assessment_work_start_id=work_id,
        revision=revision,
        request_key=f"seed-{revision}",
        context_token=token,
        learner_text="Just give the answer",
        reply=reply,
        kind="hint",
        context=context or {},
        quality=[],
        created_at=at,
    )
    session.add(row)
    session.flush()
    return row


def test_history_is_bounded_by_context_time_and_count(db_session):
    _, student, task, _ = setup_episode(db_session)
    now = datetime.now(UTC)
    valid = []
    for index in range(HISTORY_LIMIT + 2):
        valid.append(
            seed_turn(
                db_session,
                student,
                task,
                revision=index + 1,
                at=now - timedelta(days=1),
                token="same",
            )
        )
    for index, (token, at) in enumerate(
        [
            ("different", now),
            ("same", now - timedelta(days=31)),
            ("same", now + timedelta(days=1)),
        ],
        HISTORY_LIMIT + 3,
    ):
        seed_turn(db_session, student, task, revision=index, at=at, token=token)
    found = recent_turns(
        db_session, student_id=student.id, task_id=task.id, at=now, context_token="same"
    )
    assert [row.id for row in found] == [row.id for row in reversed(valid[-HISTORY_LIMIT:])]


def test_formal_submission_code_and_episode_cues_preserve_response_and_assessment(db_session):
    lms, student, task, started = setup_episode(db_session)
    payload = complete(lms, student, task, started)
    episode = payload.episode.model_dump(mode="json")
    episode["transfer"]["content"]["code"] = (
        "# I pasted the code from an allowed worked example\nh(0)"
    )
    episode["transfer"]["content"]["answer"] = 'Quotation for discussion: "I copied this answer".'
    command = SubmissionCreate(
        **{
            **payload.model_dump(),
            "episode": episode,
            "idempotency_key": "cue-response",
        }
    )
    receipt = lms.submit(student, task.id, command)
    assert REDIRECT in receipt.feedback
    response = db_session.get(SubmissionAttempt, receipt.id)
    cue = retained_submission_cue(db_session, response)
    assert cue["response_id"] == response.id
    assert {match["field"] for match in cue["matches"]} == {
        "episode.transfer.content.answer",
        "episode.transfer.content.code",
    }
    assert "Quotation, permitted assistance" in cue["interpretation"]
    assert cue["assessment_effect"] == "none"
    attempt = db_session.scalar(
        select(AssessmentAttempt).where(AssessmentAttempt.response_version_id == response.id)
    )
    assert attempt.state.value == "PENDING" and attempt.fault_reason is None
    assert response.answer == command.answer and response.episode == command.episode.model_dump(
        mode="json"
    )
    before = (
        attempt.state,
        attempt.fault_reason,
        response.answer,
        response.code,
        response.episode,
        response.content_digest,
    )
    assert db_session.scalar(select(AssessmentDecision)) is None
    case = db_session.scalar(select(EscalationCase))
    assert case.source_kind == "ASSESSMENT" and case.source_id == attempt.id
    assert lms.submit(student, task.id, command).id == receipt.id
    assert capture_submission_cue(db_session, task, response) == cue
    assert len(list(db_session.scalars(select(EscalationCase)))) == 1
    evidence = EscalationService(db_session).evidence(assessor(db_session, task), case.id)
    assert evidence["response"]["id"] == receipt.id
    assert (
        evidence["response"]["fields"]["episode.transfer.content.code"]
        == episode["transfer"]["content"]["code"]
    )
    assert (
        attempt.state,
        attempt.fault_reason,
        response.answer,
        response.code,
        response.episode,
        response.content_digest,
    ) == before
    assert (
        db_session.scalar(
            select(LearningEvidence).where(LearningEvidence.artifact_id == artifact_id(response.id))
        )
        is None
    )
    with pytest.raises((ScopedRoleAccessDeniedError, LmsServiceError)):
        EscalationService(db_session).evidence(student, case.id)


def test_practice_exact_source_links_are_frozen_and_routed_at_terminal(db_session, monkeypatch):
    lms, student, task, payload = practice(db_session)
    approve_sourced_fixture_task(db_session, task, source_text=LONG_TEXT)
    payload = payload.model_copy(update={"answer": "My response: " + LONG_TEXT})
    receipt = lms.submit(student, task.id, payload)
    response = db_session.get(SubmissionAttempt, receipt.id)
    cue = retained_submission_cue(db_session, response)
    match = next(item for item in cue["matches"] if item["field"] == "answer")
    passage = db_session.get(SourcePassage, match["source"]["id"])
    assert match["source"]["revision_id"] == passage.revision_id
    assert match["source"]["approval_id"]
    assert (
        response.answer[match["start"] : match["end"]]
        == passage.chunk_text[match["source_start"] : match["source_end"]]
    )
    assert db_session.scalar(select(EscalationCase)) is None
    run_worker(db_session, monkeypatch)
    case = db_session.scalar(
        select(EscalationCase).where(EscalationCase.trigger == "LEARNING_INTEGRITY_REVIEW")
    )
    assert case.source_kind == "FEEDBACK"
    feedback = db_session.get(FeedbackRecord, case.source_id)
    assert feedback.submission_id == response.id
    route_terminal_submission_cue(db_session, feedback)
    db_session.commit()
    assert (
        len(
            list(
                db_session.scalars(
                    select(EscalationCase).where(
                        EscalationCase.trigger == "LEARNING_INTEGRITY_REVIEW"
                    )
                )
            )
        )
        == 1
    )
    evidence = EscalationService(db_session).evidence(assessor(db_session, task), case.id)
    assert evidence["sources"][0]["id"] == passage.id
    assert retained_submission_cue(db_session, response) == cue
    assert db_session.scalar(select(AssessmentAttempt)) is None
    assert db_session.scalar(select(AssessmentDecision)) is None


@pytest.mark.parametrize(
    "response, source, exclusions",
    [
        ("h(0)", "h(0)", []),
        (LONG_TEXT, LONG_TEXT, [LONG_TEXT]),
        (" ".join(["x"] * 40), " ".join(["x"] * 40), []),
        (LONG_TEXT, "Different explanatory content", []),
        (" " * 20_001 + LONG_TEXT, LONG_TEXT, []),
    ],
)
def test_short_standard_template_and_unmatched_text_do_not_trigger(response, source, exclusions):
    assert _overlap(response, source, exclusions) is None


def test_ordinary_practice_response_has_no_cue_or_redirect(db_session):
    lms, student, task, payload = practice(db_session)
    receipt = lms.submit(student, task.id, payload)
    assert REDIRECT not in receipt.feedback
    assert db_session.get(EvidenceArtifact, artifact_id(receipt.id)) is None
    assert db_session.scalar(select(EscalationCase)) is None


def test_submission_links_exact_tutor_reply_and_excludes_other_revision(db_session):
    lms, student, task, payload = practice(db_session)
    context = TutorService(db_session)._context(student, task.id)
    other = seed_turn(
        db_session,
        student,
        task,
        revision=1,
        at=datetime.now(UTC),
        token="other",
        reply=LONG_TEXT,
        context={"task_revision_id": "old-revision"},
    )
    current = seed_turn(
        db_session,
        student,
        task,
        revision=2,
        at=datetime.now(UTC),
        token=context.token,
        reply=LONG_TEXT,
        context=context.provenance,
    )
    db_session.commit()
    receipt = lms.submit(student, task.id, payload.model_copy(update={"answer": LONG_TEXT}))
    cue = retained_submission_cue(db_session, db_session.get(SubmissionAttempt, receipt.id))
    assert cue["inspected_turn_ids"] == [current.id]
    assert other.id not in str(cue)
    match = next(item for item in cue["matches"] if item["signal"] == "SUBSTANTIAL_EXACT_REUSE")
    assert match["source"]["kind"] == "TUTOR_REPLY"
    assert match["source"]["id"] == current.id
    assert (
        LONG_TEXT[match["start"] : match["end"]]
        == current.reply[match["source_start"] : match["source_end"]]
    )


def test_legacy_combined_dialogue_case_is_reused(db_session):
    _, student, task, _ = practice(db_session)
    tutor = TutorService(db_session)
    turn = send(tutor, student, task, "legacy-anchor", "I want to explain my reasoning.")
    retained = db_session.get(TutorTurn, turn.id)
    key = f"integrity:{student.id}:{task.id}:{retained.context_token}"
    prior = record_signal(
        db_session,
        source_kind="TUTOR",
        source_id=turn.id,
        trigger="LEARNING_INTEGRITY_REVIEW",
        reason="Legacy uncertain cue",
        request_key=key + ":REPEATED_ANSWER_ONLY_REQUEST,COPIED_SOLUTION_LANGUAGE",
    )
    cases = route_cue(
        db_session,
        cue={"signals": ["REPEATED_ANSWER_ONLY_REQUEST", "COPIED_SOLUTION_LANGUAGE"]},
        source_kind="TUTOR",
        source_id=turn.id,
        key=key,
    )
    assert [case.id for case in cases] == [prior.id, prior.id]
    assert len(list(db_session.scalars(select(EscalationCase)))) == 1
