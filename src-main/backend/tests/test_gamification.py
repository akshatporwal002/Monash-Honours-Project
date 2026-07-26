from sqlalchemy import select

from app.models import (
    Achievement,
    AttemptStatus,
    Course,
    CourseModule,
    CourseState,
    Enrollment,
    EnrollmentStatus,
    LearningOutcome,
    LearningTask,
    OutcomeKind,
    StudentProfile,
    SubmissionAttempt,
    SubmissionDraft,
    TaskType,
    User,
    UserRole,
    WorkflowRun,
    WorkflowStage,
)
from app.schemas.lms import SubmissionCreate
from app.services.gamification import GamificationService
from app.services.lms import LmsService, bootstrap_demo


def test_gamification_awards_each_task_once_and_recalculates_level(db_session) -> None:
    users, _ = bootstrap_demo(db_session)
    student = next(user for user in users if user.role is UserRole.STUDENT)
    profile = db_session.scalar(select(StudentProfile).where(StudentProfile.user_id == student.id))
    task = db_session.scalar(select(LearningTask).order_by(LearningTask.position))
    assert profile is not None
    assert task is not None
    draft = SubmissionDraft(student_id=student.id, task_id=task.id)
    db_session.add(draft)
    db_session.flush()
    attempt = SubmissionAttempt(
        draft_id=draft.id,
        student_id=student.id,
        task_id=task.id,
        attempt_number=1,
        status=AttemptStatus.COMPLETED,
        score=100,
        feedback="Validated feedback is pending.",
        feedback_reference="attempt-1",
    )
    db_session.add(attempt)
    db_session.flush()
    gamification = GamificationService(db_session)

    first = gamification.award_completion(profile, task, attempt)
    repeated = gamification.award_completion(profile, task, attempt)
    db_session.commit()

    assert first.points_awarded == task.points
    assert repeated.points_awarded == 0
    assert profile.points == task.points
    assert {"first-step", "perfect-score"} <= set(first.achievement_codes)
    assert gamification.level(0, 500) == 1
    assert gamification.level(500, 500) == 2


def test_production_achievement_defaults_award_and_display_for_non_demo_student(
    db_session,
) -> None:
    session = db_session
    assert list(session.scalars(select(Achievement.code)).all()) == []
    educator = User(
        email="educator@example.edu",
        full_name="Production Educator",
        password_hash="not-used",
        role=UserRole.EDUCATOR,
    )
    student = User(
        email="student@example.edu",
        full_name="Production Student",
        password_hash="not-used",
        role=UserRole.STUDENT,
    )
    session.add_all([educator, student])
    session.flush()
    profile = StudentProfile(
        user_id=student.id,
        display_name=student.full_name,
    )
    course = Course(
        educator_id=educator.id,
        code="PROD-101",
        title="Production course",
        state=CourseState.PUBLISHED,
    )
    session.add_all([profile, course])
    session.flush()
    module = CourseModule(
        course_id=course.id,
        title="Production module",
        position=1,
    )
    session.add(module)
    session.flush()
    outcome = LearningOutcome(
        module_id=module.id,
        title="Production outcome",
        statement="Identify a grounded learning concept.",
        kind=OutcomeKind.TOPIC,
        position=1,
    )
    session.add(outcome)
    session.flush()
    task = LearningTask(
        slug="production-first-task",
        title="First production task",
        module=module.title,
        description="Choose the correct response.",
        instructions="Select one answer.",
        task_type=TaskType.MULTIPLE_CHOICE,
        difficulty="beginner",
        points=125,
        position=1,
        expected_answer="b",
        course_id=course.id,
        module_id=module.id,
        learning_outcome_id=outcome.id,
        marking_criteria={
            "choices": [
                {"id": "a", "text": "Incorrect"},
                {"id": "b", "text": "Correct"},
            ]
        },
    )
    enrollment = Enrollment(
        course_id=course.id,
        student_id=student.id,
        status=EnrollmentStatus.ACTIVE,
    )
    session.add_all([task, enrollment])
    session.commit()

    service = LmsService(session)
    attempt = service.submit(
        student,
        task.id,
        SubmissionCreate(answer="b"),
    )
    workflow = session.scalar(select(WorkflowRun).where(WorkflowRun.submission_id == attempt.id))
    assert workflow is not None
    assert workflow.current_stage is WorkflowStage.PENDING
    assert workflow.execution_attempt_count == 0
    assert workflow.execution_token is None
    assert workflow.lease_expires_at is None
    assert workflow.course_id == course.id
    assert workflow.task_id == task.id
    dashboard = service.student_dashboard(student)

    assert set(session.scalars(select(Achievement.code)).all()) == {
        "first-step",
        "circuit-maker",
        "perfect-score",
    }
    assert attempt.points_awarded == 125
    assert dashboard.summary.points == 125
    assert {achievement.code for achievement in dashboard.achievements} == {
        "first-step",
        "perfect-score",
    }
