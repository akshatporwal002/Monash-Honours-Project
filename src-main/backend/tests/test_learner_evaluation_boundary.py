"""Mounted learner API checks for the direct evaluation restriction."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from support.assessment import build_assessment_blueprint
from support.task_review import (
    approve_fixture_task,
    bind_reviewed_fixture_form,
    bootstrap_reviewed_demo,
)

from app.api.assessment_dependencies import (
    get_assessment_evaluation_executor,
    get_assessment_evaluation_service,
)
from app.api.feedback_dependencies import get_feedback_executor
from app.core.security import hash_password
from app.db.session import get_db
from app.domain.assessment import BloomProcess, ResultState
from app.main import create_app
from app.models.assessment import (
    AssessmentApprovalState,
    AssessmentAttempt,
    AssessmentDecision,
    AssessmentEvaluationFailureCategory,
    AssessmentEvaluationJob,
    AssessmentEvaluationJobState,
    CriterionEvaluation,
    TaskApproval,
)
from app.models.lms import (
    Course,
    CourseState,
    Enrollment,
    EnrollmentStatus,
    PlatformAuditEvent,
    SubmissionAttempt,
)
from app.models.persistence import LearningTask
from app.models.user import User, UserRole
from app.schemas.lms import SubmissionCreate
from app.services.assessment.evaluation import AssessmentEvaluationService
from app.services.assessment.jobs import (
    AssessmentEvaluationApplication,
    AssessmentEvaluationExecutor,
    AssessmentEvaluationRecoveryWorker,
    SqlAlchemyAssessmentEvaluationJobRepository,
)
from app.services.assessment.runtime import build_assessment_evaluation_service
from app.services.lms import DEMO_PASSWORD, LmsService


def _published_task(session: Session):
    users, _ = bootstrap_reviewed_demo(session)
    student = next(user for user in users if user.role is UserRole.STUDENT)
    definition, bloom, criterion, _, form, owner = build_assessment_blueprint(session)
    course = session.get(Course, definition.course_id)
    assert course is not None
    course.state = CourseState.PUBLISHED
    session.add(Enrollment(course_id=course.id, student_id=student.id))
    bloom.bloom_process = BloomProcess.REMEMBER
    criterion.approved_anchors = {"all_of": ["Hadamard"]}
    criterion.critical_error_rules = {}
    definition.formal_result_eligible = True
    definition.result_eligibility_declared_at = datetime(2026, 8, 16, tzinfo=UTC)
    session.commit()
    review_event = bind_reviewed_fixture_form(session, form)
    form.approval_state = AssessmentApprovalState.APPROVED
    form.approved_at = datetime(2026, 8, 16, tzinfo=UTC)
    form.approved_by_user_id = owner.id
    definition.approval_state = AssessmentApprovalState.APPROVED
    definition.approved_at = datetime(2026, 8, 16, tzinfo=UTC)
    definition.approved_by_user_id = owner.id
    session.add(
        TaskApproval(
            course_id=course.id,
            assessment_definition_version_id=definition.id,
            task_form_version_id=form.id,
            task_review_event_id=review_event.id,
            actor_user_id=owner.id,
            approval_reason="Approved test phrase rule.",
            approval_state=AssessmentApprovalState.APPROVED,
            approved_at=definition.approved_at,
            approved_by_user_id=owner.id,
        )
    )
    session.commit()
    approve_fixture_task(session, session.get(LearningTask, form.learning_task_id))
    return student, course, form.learning_task_id


def _login(client: TestClient, email: str = "student@quantumlearn.demo") -> None:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text


def test_direct_evaluation_is_denied_before_creating_a_decision(db_session: Session) -> None:
    student, _, task_id = _published_task(db_session)
    LmsService(db_session).submit(
        student, task_id, SubmissionCreate(answer="Hadamard", idempotency_key="submission")
    )
    attempt = db_session.scalar(select(AssessmentAttempt))
    assert attempt is not None
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        _login(client)
        response = client.post(
            f"/api/v1/assessment/attempts/{attempt.id}/evaluate",
            json={"evaluation_idempotency_key": "direct-request"},
        )
    decisions = db_session.scalars(select(AssessmentDecision)).all()
    job = db_session.get(AssessmentEvaluationJob, attempt.id)
    assert response.status_code == 403, (
        response.text,
        f"decisions={len(decisions)}",
        f"durable_job={job.state.value if job else None}",
    )
    assert decisions == []
    factory = sessionmaker(bind=db_session.get_bind())
    worker = AssessmentEvaluationRecoveryWorker(
        factory, AssessmentEvaluationExecutor(factory, build_assessment_evaluation_service)
    )
    assert asyncio.run(worker.run_once()) is True
    assert asyncio.run(worker.run_once()) is False
    db_session.expire_all()
    assert len(db_session.scalars(select(AssessmentDecision)).all()) == 1
    assert job is not None and job.state is AssessmentEvaluationJobState.COMPLETED


def _evaluation_snapshot(session: Session) -> list:
    session.expire_all()
    tables = (AssessmentAttempt, AssessmentEvaluationJob, AssessmentDecision, CriterionEvaluation)
    rows = [list(session.execute(select(model.__table__))) for model in tables]
    rows.append(
        list(
            session.execute(
                select(PlatformAuditEvent.__table__).where(
                    PlatformAuditEvent.action.like("assessment_evaluation.%")
                )
            )
        )
    )
    return rows


@pytest.mark.parametrize(
    "actor", ("owner", "other_student", "withdrawn", "archived", "educator", "anonymous")
)
@pytest.mark.parametrize(
    "job_state", ("pending", "running", "retry_scheduled", "review_required", "completed")
)
def test_direct_denials_have_no_evaluation_side_effects(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, actor: str, job_state: str
) -> None:
    student, course, task_id = _published_task(db_session)
    LmsService(db_session).submit(
        student, task_id, SubmissionCreate(answer="Hadamard", idempotency_key="submission")
    )
    attempt = db_session.scalar(select(AssessmentAttempt))
    assert attempt is not None
    job = db_session.get(AssessmentEvaluationJob, attempt.id)
    assert job is not None
    repository = SqlAlchemyAssessmentEvaluationJobRepository(db_session)
    if job_state != "pending":
        claim = AssessmentEvaluationApplication(repository).start(attempt.response_version_id)
        assert claim is not None
        if job_state == "completed":
            build_assessment_evaluation_service(db_session, attempt.id).evaluate(
                assessment_attempt_id=attempt.id,
                evaluation_idempotency_key=job.evaluation_idempotency_key,
            )
            assert repository.complete(claim, completed_at=datetime.now(UTC))
        elif job_state != "running":
            assert repository.fail(
                claim,
                AssessmentEvaluationFailureCategory.PROVIDER_UNAVAILABLE,
                failed_at=datetime.now(UTC),
                retryable=job_state == "retry_scheduled",
            )
    if actor == "other_student":
        other = User(
            email="other-student@example.edu",
            password_hash=hash_password(DEMO_PASSWORD),
            full_name="Other Student",
            role=UserRole.STUDENT,
        )
        db_session.add(other)
    elif actor == "withdrawn":
        enrollment = db_session.scalar(select(Enrollment).where(Enrollment.course_id == course.id))
        assert enrollment is not None
        enrollment.status = EnrollmentStatus.WITHDRAWN
    elif actor == "archived":
        course.state = CourseState.ARCHIVED
    db_session.commit()

    def unexpected_evaluation(*args, **kwargs):
        pytest.fail("Denied requests must not construct or call an evaluator")

    monkeypatch.setattr(AssessmentEvaluationService, "evaluate", unexpected_evaluation)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_assessment_evaluation_service] = unexpected_evaluation
    with TestClient(app) as client:
        if actor != "anonymous":
            email = {
                "other_student": "other-student@example.edu",
                "educator": "educator@quantumlearn.demo",
            }.get(actor, student.email)
            _login(client, email)
        before = _evaluation_snapshot(db_session)
        target_bodies = []
        for target in (attempt.id, "00000000-0000-4000-8000-000000000099"):
            bodies = []
            for key in (job.evaluation_idempotency_key, job.evaluation_idempotency_key, "new-key"):
                response = client.post(
                    f"/api/v1/assessment/attempts/{target}/evaluate",
                    json={"evaluation_idempotency_key": key},
                )
                assert response.status_code == (401 if actor == "anonymous" else 403)
                bodies.append(response.json())
            assert bodies[0] == bodies[1] == bodies[2]
            assert set(bodies[0]) == {"detail"}
            target_bodies.append(bodies[0])
        assert target_bodies[0] == target_bodies[1]
        assert _evaluation_snapshot(db_session) == before


def test_normal_submission_uses_one_durable_job_and_withholds_the_decision(
    db_session: Session,
) -> None:
    _, _, task_id = _published_task(db_session)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    # Feedback is independent of this boundary. Evaluation uses the real executor
    # and production rule adapter, with separate sessions in the disposable DB.
    app.dependency_overrides[get_feedback_executor] = lambda: AsyncMock()
    executor = AssessmentEvaluationExecutor(
        sessionmaker(bind=db_session.get_bind()), build_assessment_evaluation_service
    )
    app.dependency_overrides[get_assessment_evaluation_executor] = lambda: executor
    with TestClient(app) as client:
        _login(client)
        endpoint = f"/api/v1/students/me/tasks/{task_id}/submissions"
        payload = {"answer": "Hadamard", "idempotency_key": "durable-submission"}
        first = client.post(endpoint, json=payload)
        replay = client.post(endpoint, json=payload)
        assert first.status_code == replay.status_code == 201, (first.text, replay.text)
        assert first.json()["id"] == replay.json()["id"]
        for response in (first, replay):
            assert response.json()["formal_assessment"] == {
                "result": None,
                "visibility": "withheld",
            }
        before = _evaluation_snapshot(db_session)
        conflict = client.post(endpoint, json={**payload, "answer": "Changed evidence"})
        assert conflict.status_code == 409
        assert _evaluation_snapshot(db_session) == before
        history = client.get(endpoint)
        task = client.get(f"/api/v1/students/me/tasks/{task_id}")
        assert history.status_code == task.status_code == 200
        assert len(history.json()) == 1
        for summary in (history.json()[0], task.json()["latest_attempt"]):
            assert "score" not in summary
            assert summary["formal_assessment"] == {"result": None, "visibility": "withheld"}
    db_session.expire_all()
    assert len(db_session.scalars(select(SubmissionAttempt)).all()) == 1
    assert len(db_session.scalars(select(AssessmentAttempt)).all()) == 1
    jobs = db_session.scalars(select(AssessmentEvaluationJob)).all()
    decisions = db_session.scalars(select(AssessmentDecision)).all()
    assert len(jobs) == len(decisions) == 1
    assert jobs[0].state is AssessmentEvaluationJobState.COMPLETED
    assert jobs[0].processing_attempts == 1
    assert decisions[0].result_state is ResultState.PROVISIONAL
    assert decisions[0].result.value == "PASS"
    assert len(db_session.scalars(select(CriterionEvaluation)).all()) == 1
    worker = AssessmentEvaluationRecoveryWorker(sessionmaker(bind=db_session.get_bind()), executor)
    assert asyncio.run(worker.run_once()) is False


@pytest.mark.parametrize("scope", ("other_course", "withdrawn", "archived"))
def test_submission_replay_and_history_require_current_course_access(
    db_session: Session, scope: str
) -> None:
    student, course, task_id = _published_task(db_session)
    payload = {"answer": "Hadamard", "idempotency_key": "submission"}
    LmsService(db_session).submit(student, task_id, SubmissionCreate(**payload))
    if scope == "other_course":
        other = User(
            email="other-student@example.edu",
            password_hash=hash_password(DEMO_PASSWORD),
            full_name="Other Course Student",
            role=UserRole.STUDENT,
        )
        db_session.add(other)
        db_session.flush()
        other_course = db_session.scalar(select(Course).where(Course.id != course.id))
        assert other_course is not None
        db_session.add(Enrollment(course_id=other_course.id, student_id=other.id))
    elif scope == "withdrawn":
        enrollment = db_session.scalar(select(Enrollment).where(Enrollment.course_id == course.id))
        assert enrollment is not None
        enrollment.status = EnrollmentStatus.WITHDRAWN
    else:
        course.state = CourseState.ARCHIVED
    db_session.commit()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        _login(client, "other-student@example.edu" if scope == "other_course" else student.email)
        before = _evaluation_snapshot(db_session)
        endpoint = f"/api/v1/students/me/tasks/{task_id}/submissions"
        replay = client.post(endpoint, json=payload)
        history = client.get(endpoint)
        assert replay.status_code == history.status_code == 403, (replay.text, history.text)
        assert _evaluation_snapshot(db_session) == before
        assert len(db_session.scalars(select(SubmissionAttempt)).all()) == 1
