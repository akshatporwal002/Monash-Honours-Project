from datetime import timedelta

from sqlalchemy import select
from support.assessment_review import seed_review_context
from test_assessor_review_api import _request
from test_reassessment import context, publish_equivalent
from test_reminder_controls import NOW

from app.domain.assessment import AssessorReviewAction, ResultState
from app.models.user import User
from app.schemas.reassessment import OutcomePolicyWrite
from app.services.assessment.reassessment import ReassessmentService
from app.services.reminders import ReminderService


def test_reminders_require_current_reassessment_authorisation(db_session):
    fixture, owner, student, reviews, reassessments, command = context(db_session)
    form = publish_equivalent(db_session, fixture, owner, reassessments)
    command = command.model_copy(update={"task_form_version_id": form.id})
    reminders = ReminderService(db_session, now=NOW)
    assert reminders.send(student.id, form.task_id) is None
    db_session.rollback()
    reassessments.authorise(owner, fixture["decision_id"], command)
    assert reminders.send(student.id, form.task_id) is not None
    db_session.commit()
    reviews.act(
        owner,
        decision_id=fixture["decision_id"],
        request=_request(
            AssessorReviewAction.VOID,
            expected_revision=1,
            expected_state=ResultState.OVERRIDDEN,
        ),
    )
    assert (
        ReminderService(db_session, now=NOW + timedelta(days=2)).send(student.id, form.task_id)
        is None
    )


def test_independently_required_equivalent_form_does_not_need_reassessment_grant(db_session):
    fixture = seed_review_context(db_session)
    owner = db_session.scalar(select(User).where(User.email == fixture["educator_email"]))
    student = db_session.scalar(select(User).where(User.email == fixture["student_email"]))
    reassessments = ReassessmentService(db_session)
    form = publish_equivalent(db_session, fixture, owner, reassessments)
    forms = reassessments.setup(owner, fixture["decision_id"]).policy_forms
    reassessments.publish_policy(
        owner,
        fixture["definition_id"],
        OutcomePolicyWrite(
            selection_rule="ALL_REQUIRED_FORMS",
            required_form_ids=[item.id for item in forms],
            reason="Every listed form is independently required evidence.",
        ),
    )
    assert ReminderService(db_session, now=NOW).send(student.id, form.task_id) is not None
