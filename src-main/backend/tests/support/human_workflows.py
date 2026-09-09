"""Isolated learners, fresh forms and queue owners for browser journeys."""

from uuid import uuid4

from sqlalchemy import select

from app.domain.assessment import AssessmentResult, AssessorReviewAction, ResultState
from app.models.enums import FeedbackStatus
from app.models.persistence import FeedbackRecord, StudentProfile, WorkflowRun
from app.models.user import User
from app.services.assessment.access import RoleAssignmentService
from app.services.assessment.review import AssessmentReviewActionRequest, AssessmentReviewService
from support.assessment import assign_assessor
from support.assessment_review import seed_review_context


def seed_human_workflows(session):
    fixture = seed_review_context(session, reassessment=True)
    owner = session.scalar(select(User).where(User.email == fixture["educator_email"]))
    student = session.scalar(select(User).where(User.email == fixture["student_email"]))
    session.add(StudentProfile(user_id=student.id, display_name=student.full_name))
    backup = User(
        email=f"backup-{uuid4().hex}@example.edu",
        full_name="Backup reviewer",
        role=owner.role,
        password_hash=owner.password_hash,
    )
    session.add(backup)
    session.commit()
    assign_assessor(session, backup, fixture["course_id"], owner)
    AssessmentReviewService(session, assignments=RoleAssignmentService(session)).act(
        owner,
        decision_id=fixture["decision_id"],
        request=AssessmentReviewActionRequest(
            action=AssessorReviewAction.OVERRIDE,
            expected_result_state=ResultState.PROVISIONAL,
            expected_review_revision=0,
            new_result=AssessmentResult.INCOMPLETE,
            reason="PRIVATE: fixture assessor requires fresh evidence.",
        ),
    )
    workflow = session.scalar(
        select(WorkflowRun).where(WorkflowRun.submission_id == fixture["response_id"])
    )
    feedback = FeedbackRecord(
        id=str(uuid4()),
        submission_id=fixture["response_id"],
        workflow_run_id=workflow.id,
        status=FeedbackStatus.ACCEPTED,
        generation_attempt=1,
        provider="test",
        model="test",
        prompt_version="test.v1",
        feedback_content={"explanation": "Synthetic accepted explanation for human sampling."},
    )
    session.add(feedback)
    session.commit()
    return {
        **fixture,
        "owner_name": owner.full_name,
        "backup_name": backup.full_name,
        "feedback_id": feedback.id,
    }
