"""Fresh authoring records for each browser test, in its disposable database."""

from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import TaskType
from app.models.lms import Course, CourseModule, LearningOutcome, OutcomeKind
from app.models.persistence import LearningTask
from app.models.user import User, UserRole
from support.assessment import assign_assessor


def seed_authoring_context(session: Session) -> dict[str, str]:
    suffix = uuid4().hex
    password = "assessment-authoring-test-password"
    educator = User(
        email=f"author-{suffix}@example.edu",
        password_hash=hash_password(password),
        full_name="Assessment Author",
        role=UserRole.EDUCATOR,
    )
    session.add(educator)
    session.flush()
    course = Course(educator_id=educator.id, code=f"R-{suffix[:8]}", title="Recall rule authoring")
    session.add(course)
    session.flush()
    module = CourseModule(course_id=course.id, title="Recall", position=1)
    session.add(module)
    session.flush()
    outcome = LearningOutcome(
        module_id=module.id,
        title="Recall the gate name",
        statement="Name the Hadamard gate.",
        kind=OutcomeKind.TOPIC,
        position=1,
    )
    session.add(outcome)
    session.flush()
    task = LearningTask(
        slug=f"recall-{suffix}",
        title="Name the gate",
        module="Recall",
        description="Recall one name.",
        instructions="Name the gate.",
        task_type=TaskType.SHORT_ANSWER,
        difficulty="beginner",
        points=0,
        position=1,
        course_id=course.id,
        module_id=module.id,
        learning_outcome_id=outcome.id,
    )
    session.add(task)
    session.commit()
    assign_assessor(session, educator, course.id, educator)
    return {
        "course_id": course.id,
        "outcome_id": outcome.id,
        "task_id": task.id,
        "educator_email": educator.email,
        "educator_password": password,
    }
