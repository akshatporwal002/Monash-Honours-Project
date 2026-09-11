"""Dashboard reads must not recalculate every other learner's progress."""

from sqlalchemy import event, select
from support.curriculum import setup_curriculum
from support.learning_loop import seed_learning_loop

from app.models import Enrollment, StudentProfile, User, UserRole
from app.services.curriculum import CurriculumService
from app.services.lms import LmsService


def test_dashboard_does_not_repeat_source_validation_for_each_read_layer(
    db_session, synthetic_material_scanning
):
    fixture = seed_learning_loop(db_session)
    student = db_session.scalar(select(User).where(User.email == fixture["student_email"]))
    reads = []

    def capture(connection, cursor, statement, parameters, context, many):
        if "FROM source_approvals" in statement:
            reads.append(parameters)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        result = LmsService(db_session).student_dashboard(student)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(result.tasks) == 3
    # Optional/required checks remain distinct, as does each formal publication
    # source check. Repeated graph/read layers must not multiply identical work.
    assert len(reads) <= 2 * len(result.tasks) + sum(
        task.assessment is not None for task in result.tasks
    ), len(reads)


def test_dashboard_source_reuse_ends_at_request_and_mutation_boundaries(
    db_session, synthetic_material_scanning
):
    from datetime import UTC, datetime

    import pytest

    from app.models import LearningMaterial, LearningTask
    from app.models.source_history import SourcePassage, SourceRevision
    from app.services.task_review import TaskReviewError, TaskReviewService
    from app.services.validation_reads import validation_read_scope

    fixture = seed_learning_loop(db_session)
    student = db_session.scalar(select(User).where(User.email == fixture["student_email"]))
    task = db_session.get(LearningTask, fixture["task_id"])
    passage = db_session.get(SourcePassage, task.source_references[0])
    revision = db_session.get(SourceRevision, passage.revision_id)
    material = db_session.get(LearningMaterial, revision.material_id)
    lms = LmsService(db_session)
    assert task.id in {row.id for row in lms.student_dashboard(student).tasks}

    class ChangedRead:
        session = db_session

        @validation_read_scope
        def run(self):
            review = TaskReviewService(self.session)
            assert review.source_approvals(task, required=True)
            material.retired_at = datetime.now(UTC)
            self.session.flush()
            review.source_approvals(task, required=True)

    with pytest.raises(TaskReviewError):
        ChangedRead().run()
    db_session.commit()
    # A new dashboard operation cannot retain the earlier successful read.
    with pytest.raises(TaskReviewError, match="current approval"):
        lms.student_dashboard(student)


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
