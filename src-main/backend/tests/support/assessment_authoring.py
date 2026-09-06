"""Fresh authoring records for each browser test, in its disposable database."""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import TaskType
from app.models.lms import Course, CourseModule, LearningOutcome, OutcomeKind
from app.models.persistence import LearningTask
from app.models.user import User
from support.assessment import assign_assessor


def seed_authoring_context(session: Session) -> dict[str, str]:
    educator = session.scalar(select(User).where(User.email == "educator@quantumlearn.demo"))
    assert educator is not None
    suffix = uuid4().hex
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
    return {"course_id": course.id, "outcome_id": outcome.id, "task_id": task.id}
