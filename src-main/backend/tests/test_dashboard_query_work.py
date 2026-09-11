"""Dashboard reads must not recalculate every other learner's progress."""

from sqlalchemy import event
from support.curriculum import setup_curriculum

from app.models import Enrollment, StudentProfile, User, UserRole
from app.services.curriculum import CurriculumService
from app.services.lms import LmsService


def test_dashboard_query_work_does_not_grow_with_unrelated_enrollments(
    db_session, synthetic_material_scanning
):
    _, _, student, _, tasks, _, _ = setup_curriculum(db_session)
    course_id = tasks[0].course_id
    engine = db_session.get_bind()

    def read():
        queries = []

        def capture(*args):
            queries.append(args[2])

        db_session.expire_all()
        event.listen(engine, "before_cursor_execute", capture)
        try:
            result = LmsService(db_session).student_dashboard(student)
        finally:
            event.remove(engine, "before_cursor_execute", capture)
        return result, len(queries)

    before, initial_queries = read()
    for index in range(20):
        user = User(
            email=f"classmate-{index}@example.com",
            full_name="Classmate",
            role=UserRole.STUDENT,
            password_hash=student.password_hash,
        )
        db_session.add(user)
        db_session.flush()
        db_session.add(Enrollment(course_id=course_id, student_id=user.id))
    db_session.commit()
    after, expanded_queries = read()
    assert after.summary == before.summary
    assert after.courses == before.courses
    assert [(task.id, task.access_status) for task in after.tasks] == [
        (task.id, task.access_status) for task in before.tasks
    ]
    assert expanded_queries <= initial_queries + 2, (initial_queries, expanded_queries)


def test_dashboard_batches_one_pathway_but_refreshes_evidence_and_learner_scope(
    db_session, synthetic_material_scanning, monkeypatch
):
    from test_curriculum import confirmation, start_and_submit

    context = setup_curriculum(db_session)
    curriculum, teacher, student, course, tasks, publish, _ = context
    lms = LmsService(db_session)
    checks = []
    original = CurriculumService._current

    def checked(service, path):
        checks.append(path.id)
        return original(service, path)

    monkeypatch.setattr(CurriculumService, "_current", checked)

    def status(learner):
        return {task.id: task.access_status for task in lms.student_dashboard(learner).tasks}

    assert status(student)[tasks[-1].id] == "locked"
    assert len(checks) == 1
    response, _, _ = start_and_submit(context)
    curriculum.confirm(teacher, response.id, confirmation())
    assert status(student)[tasks[-1].id] == "available"

    other = User(
        email="other-dashboard@example.com",
        full_name="Other",
        role=UserRole.STUDENT,
        password_hash=student.password_hash,
    )
    db_session.add(other)
    db_session.flush()
    db_session.add_all(
        [
            StudentProfile(user_id=other.id, display_name="Other"),
            Enrollment(course_id=course.id, student_id=other.id),
        ]
    )
    db_session.commit()
    assert status(other)[tasks[-1].id] == "locked"

    curriculum.publish(
        teacher,
        tasks[0].learning_outcome_id,
        publish.model_copy(update={"expected_version": 1, "request_key": "new-dashboard-path"}),
    )
    assert status(student)[tasks[-1].id] == "locked"
