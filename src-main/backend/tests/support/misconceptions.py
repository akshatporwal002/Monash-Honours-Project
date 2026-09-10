"""Independent synthetic work for the misconception teaching and review browser flow."""

from uuid import uuid4

from sqlalchemy import select

from app.models.enums import FeedbackStatus
from app.models.persistence import FeedbackRecord, StudentProfile, WorkflowRun
from app.models.user import User
from support.assessment_review import seed_review_context


def seed_misconception_context(session):
    fixture = seed_review_context(session)
    student = session.scalar(select(User).where(User.email == fixture["student_email"]))
    session.add(StudentProfile(user_id=student.id, display_name=student.full_name))
    workflow = session.scalar(
        select(WorkflowRun).where(WorkflowRun.submission_id == fixture["response_id"])
    )
    feedback = FeedbackRecord(
        id=str(uuid4()),
        submission_id=fixture["response_id"],
        workflow_run_id=workflow.id,
        status=FeedbackStatus.ACCEPTED,
        generation_attempt=1,
        provider="synthetic-test-record",
        model="synthetic-test-record",
        prompt_version="misconception-fixture.v1",
        feedback_content={
            "explanation": "Compare the observation with the predicted distribution."
        },
    )
    session.add(feedback)
    session.commit()
    return {**fixture, "feedback_id": feedback.id}
