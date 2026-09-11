"""Task 16 context acceptance with ordinary reviewed episode fixtures."""

import asyncio

import pytest
from sqlalchemy import event, update
from test_task15_migrated_review import request, setup_human

from app.domain.assessment import CriterionDecision
from app.models.assessment import AssessmentAttempt, AssessmentDefinitionVersion
from app.models.lms import SubmissionAttempt
from app.models.persistence import LearningTask
from app.services.assessment.feedback_context import SqlAlchemyAssessmentFeedbackContextProvider
from app.services.feedback.runtime import LmsSubmissionProvider

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def resolve(session, attempt):
    submission = asyncio.run(
        LmsSubmissionProvider(session).get_submission(attempt.response_version_id)
    )
    return asyncio.run(SqlAlchemyAssessmentFeedbackContextProvider(session).resolve(submission))


def test_frozen_response_and_reviewed_prompt_survive_mutable_task_edit(db_session):
    _, _, attempt, _ = setup_human(db_session)
    before = resolve(db_session, attempt)
    assert before.context is not None, before.reason_code
    task = db_session.get(LearningTask, attempt.task_id)
    task.instructions = "MUTABLE NEW TASK: do not show this in old feedback"
    db_session.commit()
    statements = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(db_session.bind, "before_cursor_execute", observe)
    try:
        after = resolve(db_session, attempt)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", observe)
    assert after.context.task.prompt == before.context.task.prompt
    assert after.context.frozen_response.episode.transfer.content.answer == "  Fresh application\n"
    assert after.context.feedback_release_allowed
    assert all(c.evaluation is None for c in after.context.criteria)
    assert not {"INSERT", "UPDATE", "DELETE", "REPLACE"} & set(statements)


@pytest.mark.parametrize("broken", ["digest", "foreign", "missing_context"])
def test_corrupt_or_unavailable_context_fails_closed(db_session, broken):
    _, actor, attempt, _ = setup_human(db_session)
    if broken == "digest":
        db_session.execute(
            update(SubmissionAttempt)
            .where(SubmissionAttempt.id == attempt.response_version_id)
            .values(answer="tampered")
        )
    elif broken == "foreign":
        db_session.execute(
            update(AssessmentAttempt)
            .where(AssessmentAttempt.id == attempt.id)
            .values(student_id=actor.id)
        )
    else:
        db_session.execute(
            update(AssessmentDefinitionVersion)
            .where(AssessmentDefinitionVersion.id == attempt.assessment_definition_version_id)
            .values(formal_result_eligible=False)
        )
    db_session.commit()
    result = resolve(db_session, attempt)
    assert result.context is None
    assert result.reason_code


def test_latest_human_revision_replaces_earlier_judgement(db_session):
    service, actor, attempt, _ = setup_human(db_session)
    service.finalise(
        actor, assessment_attempt_id=attempt.id, request=request(service, actor, attempt.id)
    )
    first = resolve(db_session, attempt).context
    assert all(c.evaluation.decision is CriterionDecision.MET for c in first.criteria)
    service.finalise(
        actor,
        assessment_attempt_id=attempt.id,
        request=request(
            service, actor, attempt.id, key="correction", decision=CriterionDecision.NOT_MET
        ),
    )
    second = resolve(db_session, attempt).context
    assert second.current_human_action_id != first.current_human_action_id
    assert all(c.evaluation.decision is CriterionDecision.NOT_MET for c in second.criteria)
    assert all(c.evaluation.model_version is None for c in second.criteria)


@pytest.mark.parametrize(
    "timing,allowed",
    [("after_confirmation", False), ("after_submission", True), ("unknown", False)],
)
def test_explicit_approved_release_timing(db_session, timing, allowed):
    _, _, attempt, _ = setup_human(db_session)
    db_session.execute(
        update(AssessmentDefinitionVersion)
        .where(AssessmentDefinitionVersion.id == attempt.assessment_definition_version_id)
        .values(instructional_support={"feedback_timing": timing})
    )
    db_session.commit()
    assert resolve(db_session, attempt).context.feedback_release_allowed is allowed


def test_feedback_waits_while_transfer_is_active(db_session):
    from types import SimpleNamespace

    from test_task14_lifecycle import complete, setup_episode

    from app.domain.assessment import AssessmentAttemptState
    from app.services.assessment.feedback_context import feedback_release_state

    lms, student, task, started = setup_episode(db_session)
    complete(lms, student, task, started)
    attempt = SimpleNamespace(
        student_id=student.id,
        task_id=task.id,
        course_id=task.course_id,
        state=AssessmentAttemptState.PENDING,
    )
    # A saved transfer has not yet been submitted, so no feedback may be released.
    allowed, active = feedback_release_state(db_session, attempt, None, None)
    assert active
    assert not allowed


@pytest.mark.parametrize("status", ["completed", "timed_out"])
def test_recorded_simulation_provenance_is_preserved(db_session, status):
    _, _, attempt, _ = setup_human(db_session, simulation_status=status)
    context = resolve(db_session, attempt).context
    assert len(context.simulation_evidence) == 1
    run = context.simulation_evidence[0]
    assert run["status"] == status
    assert (
        run["run_id"] == context.frozen_response.episode.supported.simulation_references[0].run_id
    )
    assert run["policy_version"]
    if status == "timed_out":
        assert context.context_warnings
