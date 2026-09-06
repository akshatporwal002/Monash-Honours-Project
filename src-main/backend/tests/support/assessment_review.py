"""A private course and provisional decision for one browser test execution."""

from uuid import uuid4

from sqlalchemy.orm import Session

from support.assessment import assign_assessor, seed_review_decision


def seed_review_context(session: Session) -> dict[str, str]:
    attempt, response, decision, assessor = seed_review_decision(session, suffix=uuid4().hex)
    assign_assessor(session, assessor, attempt.course_id, assessor)
    return {
        "educator_email": assessor.email,
        "educator_password": "assessment-model-test-password",
        "course_id": attempt.course_id,
        "attempt_id": attempt.id,
        "response_id": response.id,
        "decision_id": decision.id,
    }
