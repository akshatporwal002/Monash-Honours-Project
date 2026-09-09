"""Synthetic approved pathway used only in tests and localhost fixtures."""

from sqlalchemy import select

from app.models import Course, LearningTask, ScopedRole, User, UserRole
from app.schemas.curriculum import PathwayPublish
from app.services.assessment.access import RoleAssignmentService
from app.services.assessment.eligibility import AssessorEligibilityService
from app.services.curriculum import CurriculumService
from support.task_review import approve_sourced_fixture_task, bootstrap_reviewed_demo


def setup_curriculum(session):
    bootstrap_reviewed_demo(session)
    course = session.scalar(select(Course))
    teacher = session.get(User, course.educator_id)
    student = session.scalar(select(User).where(User.role == UserRole.STUDENT))
    admin = session.scalar(select(User).where(User.role == UserRole.ADMINISTRATOR))
    tasks = list(session.scalars(select(LearningTask).order_by(LearningTask.position)).all())[:3]
    for position, task in enumerate(tasks):
        task.learning_outcome_id = tasks[0].learning_outcome_id
        task.module_id = tasks[0].module_id
        task.prerequisite_task_ids = [tasks[position - 1].id] if position else []
        session.commit()
        approve_sourced_fixture_task(session, task)
    AssessorEligibilityService(session).record(
        teacher,
        course_id=course.id,
        subject_user_id=teacher.id,
        expected_version=0,
        state="APPROVED",
        reason="Synthetic course assessor eligibility",
    )
    RoleAssignmentService(
        session, assignment_eligibility=lambda actor, role: actor.role == UserRole.EDUCATOR
    ).assign(
        admin,
        subject_user_id=teacher.id,
        course_id=course.id,
        role=ScopedRole.ASSESSOR,
        reason="Synthetic assessor grant",
    )
    payload = PathwayPublish(
        expected_version=0,
        request_key="publish",
        title="Three approved activities",
        steps=[
            dict(
                task_id=task.id,
                concept="Hadamard",
                prerequisites=[tasks[i - 1].id] if i else [],
                support_level="guided",
                faded_support_level="independent",
                evidence_rule="An accepted response is required",
            )
            for i, task in enumerate(tasks)
        ],
        diagnostic_prompt="Explain how applying H twice changes a single qubit.",
        diagnostic_task_id=tasks[0].id,
        independent_conditions="Respond without instructional help. Approved access support remains allowed.",
        reason="Reviewed teaching pathway",
    )
    service = CurriculumService(session)
    path = service.publish(teacher, tasks[0].learning_outcome_id, payload)
    return service, teacher, student, course, tasks, payload, path
