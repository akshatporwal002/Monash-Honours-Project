"""Task 13: work opening pins the approved standard before any response exists."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from support.alignment import next_action_contract
from support.task_review import bootstrap_reviewed_demo
from test_assessment_definitions import _draft, _service, _setup

from app.db.session import get_db
from app.main import create_app
from app.models.assessment import (
    AssessmentAttempt,
    AssessmentDefinitionVersion,
    CriterionVersion,
    PassRuleVersion,
    TaskFormVersion,
)
from app.models.assessment_work import AssessmentWorkStart
from app.models.lms import Course, CourseState, Enrollment, SubmissionAttempt, SubmissionDraft
from app.models.persistence import LearningTask
from app.models.user import User, UserRole
from app.schemas.lms import DraftWrite, SubmissionCreate
from app.services.lms import DEMO_PASSWORD, LmsService
from app.services.task_review import TaskReviewError, TaskReviewService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def setup_work(session):
    course_id, outcome_id, owner_id, outcome_version_id = _setup(session)
    task = session.scalar(select(LearningTask).where(LearningTask.course_id == course_id))
    draft = replace(
        _draft(outcome_version_id=outcome_version_id, task_id=task.id),
        formal_result_eligible=True,
        instructional_support={"supported_stage": "unlimited approved conceptual hints"},
        transfer_rule={"required": True, "new_context": "fresh unaided circuit"},
    )
    service = _service(session)
    definition = service.create_draft(
        course_id=course_id, learning_outcome_id=outcome_id, actor_user_id=owner_id, draft=draft
    )
    service.approve(
        course_id=course_id,
        assessment_definition_id=definition.assessment_definition_id,
        expected_version=1,
        actor_user_id=owner_id,
        approval_reason="Synthetic approved assessment standard",
    )
    form = session.scalar(
        select(TaskFormVersion).where(
            TaskFormVersion.assessment_definition_version_id == definition.id
        )
    )
    users, _ = bootstrap_reviewed_demo(session)
    student = next(u for u in users if u.role is UserRole.STUDENT)
    session.get(Course, course_id).state = CourseState.PUBLISHED
    session.add(Enrollment(course_id=course_id, student_id=student.id))
    session.commit()
    return student, task, form, definition, draft, owner_id


def republish(session, context):
    _, _, _, definition, draft, owner_id = context
    service = _service(session)
    changed = replace(draft, task_conditions={"response_mode": "written after a new rule review"})
    new = service.update_draft(
        course_id=definition.course_id,
        assessment_definition_id=definition.assessment_definition_id,
        expected_version=definition.version,
        actor_user_id=owner_id,
        draft=changed,
    )
    service.approve(
        course_id=definition.course_id,
        assessment_definition_id=definition.assessment_definition_id,
        expected_version=definition.version + 1,
        actor_user_id=owner_id,
        approval_reason="Synthetic replacement standard and rule",
    )
    return session.scalar(
        select(TaskFormVersion).where(TaskFormVersion.assessment_definition_version_id == new.id)
    )


def test_start_save_reload_submit_keeps_exact_standard(db_session):
    student, task, form, definition, _, _ = setup_work(db_session)
    lms = LmsService(db_session)
    assert lms.get_student_task(student, task.id).assessment.task_form_version_id == form.id
    assert db_session.scalar(select(func.count()).select_from(AssessmentWorkStart)) == 0
    started = lms.start_assessment_work(student, task.id, form.id)
    work_id = started.assessment_work_start_id
    assert work_id
    assert lms.start_assessment_work(student, task.id, form.id).assessment_work_start_id == work_id
    saved = lms.save_draft(
        student,
        task.id,
        DraftWrite(answer="Independent reasoning", assessment_work_start_id=work_id),
    )
    assert (
        saved.assessment_work_start_id
        == lms.get_draft(student, task.id).assessment_work_start_id
        == work_id
    )
    response = lms.submit(
        student,
        task.id,
        SubmissionCreate(
            answer=saved.answer, assessment_work_start_id=work_id, idempotency_key="work-response"
        ),
    )
    work = db_session.get(AssessmentWorkStart, work_id)
    formal = db_session.scalar(
        select(AssessmentAttempt).where(AssessmentAttempt.response_version_id == response.id)
    )
    assert response.assessment_work_start_id == work_id
    assert formal.pass_rule_version_id == work.pass_rule_version_id
    assert formal.assessment_definition_version_id == definition.id
    assert work.source_references == task.source_references
    assert work.declared_conditions["instructional_support"] == {
        "supported_stage": "unlimited approved conceptual hints"
    }
    assert (
        db_session.get(SubmissionAttempt, response.id).declared_conditions["transfer_rule"]
        == work.declared_conditions["transfer_rule"]
    )
    assert not hasattr(response, "score") and response.formal_assessment.result is None


def test_new_rule_during_open_draft_conflicts_and_keeps_original(db_session):
    context = setup_work(db_session)
    student, task, form, _, _, _ = context
    lms = LmsService(db_session)
    started = lms.start_assessment_work(student, task.id, form.id)
    lms.save_draft(
        student,
        task.id,
        DraftWrite(
            answer="Original draft", assessment_work_start_id=started.assessment_work_start_id
        ),
    )
    old_rule = db_session.get(
        AssessmentWorkStart, started.assessment_work_start_id
    ).pass_rule_version_id
    new_form = republish(db_session, context)
    new_rule = db_session.scalar(
        select(PassRuleVersion).where(
            PassRuleVersion.assessment_definition_version_id
            == new_form.assessment_definition_version_id
        )
    )
    assert old_rule != new_rule.id
    for operation in (
        lambda: lms.start_assessment_work(student, task.id, new_form.id),
        lambda: lms.save_draft(student, task.id, DraftWrite(answer="Do not overwrite")),
        lambda: lms.submit(
            student, task.id, SubmissionCreate(answer="Do not submit", idempotency_key="changed")
        ),
    ):
        with pytest.raises(TaskReviewError, match="conditions changed") as error:
            operation()
        assert error.value.status_code == 409
        db_session.rollback()
    assert lms.get_draft(student, task.id).answer == "Original draft"
    assert (
        db_session.get(AssessmentWorkStart, started.assessment_work_start_id).pass_rule_version_id
        == old_rule
    )
    assert db_session.scalar(select(func.count()).select_from(SubmissionAttempt)) == 0


def test_submission_retry_after_republication_returns_original(db_session):
    context = setup_work(db_session)
    student, task, _, _, _, _ = context
    lms = LmsService(db_session)
    payload = SubmissionCreate(answer="Saved response", idempotency_key="stable-response")
    first = lms.submit(student, task.id, payload)
    republish(db_session, context)
    replay = lms.submit(student, task.id, payload)
    assert replay.id == first.id
    assert replay.assessment_work_start_id == first.assessment_work_start_id
    assert db_session.scalar(select(func.count()).select_from(SubmissionAttempt)) == 1


def test_legacy_draft_is_not_rebound_to_formal_assessment(db_session):
    student, task, form, _, _, _ = setup_work(db_session)
    db_session.add(
        SubmissionDraft(student_id=student.id, task_id=task.id, answer="Earlier unversioned work")
    )
    db_session.commit()
    with pytest.raises(TaskReviewError, match="predates"):
        LmsService(db_session).start_assessment_work(student, task.id, form.id)
    db_session.rollback()
    assert LmsService(db_session).get_draft(student, task.id).answer == "Earlier unversioned work"
    assert db_session.scalar(select(func.count()).select_from(AssessmentWorkStart)) == 0


def test_foreign_work_reference_and_private_history_are_rejected(db_session):
    student, task, form, _, _, _ = setup_work(db_session)
    lms = LmsService(db_session)
    started = lms.start_assessment_work(student, task.id, form.id)
    other = User(
        email="other-start@example.edu",
        full_name="Other",
        password_hash=student.password_hash,
        role=UserRole.STUDENT,
    )
    db_session.add(other)
    db_session.flush()
    db_session.add(Enrollment(course_id=task.course_id, student_id=other.id))
    db_session.commit()
    assert lms.get_draft(other, task.id) is None
    with pytest.raises(TaskReviewError, match="does not match"):
        lms.save_draft(
            other,
            task.id,
            DraftWrite(
                answer="Injected", assessment_work_start_id=started.assessment_work_start_id
            ),
        )
    db_session.rollback()
    assert lms.get_draft(other, task.id) is None


def test_task_withdrawal_blocks_new_work_but_keeps_private_draft(db_session):
    student, task, form, _, _, owner_id = setup_work(db_session)
    lms = LmsService(db_session)
    started = lms.start_assessment_work(student, task.id, form.id)
    lms.save_draft(student, task.id, DraftWrite(answer="Preserved"))
    review = TaskReviewService(db_session)
    summary = review.summary(task)
    review.record(
        db_session.get(User, owner_id),
        task.id,
        state="WITHDRAWN",
        reason="Source review due",
        expected_revision_id=summary["revision_id"],
        expected_review_version=summary["review_version"],
    )
    with pytest.raises((TaskReviewError, HTTPException)):
        lms.submit(
            student, task.id, SubmissionCreate(answer="Blocked", idempotency_key="withdrawn")
        )
    db_session.rollback()
    assert (
        lms.get_draft(student, task.id).assessment_work_start_id == started.assessment_work_start_id
    )
    assert lms.get_draft(student, task.id).answer == "Preserved"


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE assessment_work_starts SET declared_conditions = '{}' WHERE id = :id",
        "DELETE FROM assessment_work_starts WHERE id = :id",
        "INSERT OR REPLACE INTO assessment_work_starts SELECT * FROM assessment_work_starts WHERE id = :id",
        "UPDATE submission_drafts SET assessment_work_start_id = NULL WHERE assessment_work_start_id = :id",
    ],
)
def test_work_history_rejects_sql_mutation(db_session, statement):
    student, task, form, _, _, _ = setup_work(db_session)
    started = LmsService(db_session).start_assessment_work(student, task.id, form.id)
    with pytest.raises(IntegrityError, match="protected"):
        db_session.execute(text(statement), {"id": started.assessment_work_start_id})
    db_session.rollback()
    assert db_session.get(AssessmentWorkStart, started.assessment_work_start_id)


def test_concurrent_start_requests_return_one_work_reference(db_session):
    student, task, form, _, _, _ = setup_work(db_session)
    student_id, task_id, form_id = student.id, task.id, form.id
    engine = db_session.get_bind()
    db_session.rollback()
    barrier = Barrier(2)

    def start():
        with Session(engine) as session:
            learner = session.get(User, student_id)
            barrier.wait(timeout=10)
            return (
                LmsService(session)
                .start_assessment_work(learner, task_id, form_id)
                .assessment_work_start_id
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        refs = list(pool.map(lambda _: start(), range(2)))
    assert refs[0] == refs[1]
    assert db_session.scalar(select(func.count()).select_from(AssessmentWorkStart)) == 1


def test_start_api_rejects_stale_loaded_declaration_without_creating_work(db_session):
    student, task, _, _, _, _ = setup_work(db_session)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": student.email, "password": DEMO_PASSWORD}
            ).status_code
            == 200
        )
        csrf = client.cookies.get("ql_csrf")
        response = client.post(
            f"/api/v1/students/me/tasks/{task.id}/start",
            json={"task_form_version_id": "stale-form"},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 409, response.text
        assert "conditions changed" in response.json()["detail"]
    db_session.rollback()
    assert db_session.scalar(select(func.count()).select_from(AssessmentWorkStart)) == 0


def test_work_migration_replay_scope_and_protected_downgrade(tmp_path):
    from alembic import command
    from sqlalchemy import create_engine, inspect
    from test_migrations import migration_config

    url = f"sqlite:///{(tmp_path / 'work-migration.db').as_posix()}"
    config = migration_config(url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    with Session(engine) as session:
        student, task, form, _, _, _ = setup_work(session)
        started = LmsService(session).start_assessment_work(student, task.id, form.id)
        work_id = started.assessment_work_start_id
        before = dict(
            session.execute(text("SELECT * FROM assessment_work_starts")).mappings().one()
        )
        definition = session.get(AssessmentDefinitionVersion, form.assessment_definition_version_id)
        original = replace(
            _draft(outcome_version_id=definition.outcome_version_id, task_id=task.id),
            formal_result_eligible=True,
        )
        new_form = republish(
            session, (student, task, form, definition, original, definition.owner_user_id)
        )
        assert new_form.task_form_id == form.task_form_id
        assert new_form.version == 2
        # A new criterion starts at one, even when added to definition three.
        extra = replace(
            original.criteria[0],
            stable_key="fresh_evidence",
            learner_description="Explain fresh evidence.",
        )
        extended = replace(
            original,
            criteria=[*original.criteria, extra],
            next_action_contract=next_action_contract("evidence_to_claim", "fresh_evidence"),
            pass_rule_expression={
                "operator": "ALL_OF",
                "clauses": [{"criterion": "evidence_to_claim"}, {"criterion": "fresh_evidence"}],
            },
        )
        current_definition = session.get(
            AssessmentDefinitionVersion, new_form.assessment_definition_version_id
        )
        third = republish(
            session,
            (student, task, new_form, current_definition, extended, definition.owner_user_id),
        )
        added = session.scalar(
            select(CriterionVersion).where(
                CriterionVersion.assessment_definition_version_id
                == third.assessment_definition_version_id,
                CriterionVersion.learner_description == "Explain fresh evidence.",
            )
        )
        assert added.version == 1
        fourth_definition = session.get(
            AssessmentDefinitionVersion, third.assessment_definition_version_id
        )
        fourth = republish(
            session, (student, task, third, fourth_definition, original, definition.owner_user_id)
        )
        fifth_definition = session.get(
            AssessmentDefinitionVersion, fourth.assessment_definition_version_id
        )
        fifth = republish(
            session, (student, task, fourth, fifth_definition, extended, definition.owner_user_id)
        )
        restored = session.scalar(
            select(CriterionVersion).where(
                CriterionVersion.assessment_definition_version_id
                == fifth.assessment_definition_version_id,
                CriterionVersion.learner_description == "Explain fresh evidence.",
            )
        )
        assert restored.criterion_id == added.criterion_id
        assert restored.version == 2
        with pytest.raises(TaskReviewError, match="conditions changed"):
            LmsService(session).start_assessment_work(student, task.id, new_form.id)
        session.rollback()
    command.stamp(config, "20260907_0028")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert (
            dict(connection.execute(text("SELECT * FROM assessment_work_starts")).mappings().one())
            == before
        )
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    for statement in (
        "UPDATE assessment_work_starts SET source_references = '[]' WHERE id = :id",
        "DELETE FROM assessment_work_starts WHERE id = :id",
        "INSERT OR REPLACE INTO assessment_work_starts SELECT * FROM assessment_work_starts WHERE id = :id",
    ):
        with pytest.raises(IntegrityError, match="protected"):
            with engine.begin() as connection:
                connection.execute(text(statement), {"id": work_id})
    with pytest.raises(RuntimeError, match="protected|cannot downgrade"):
        command.downgrade(config, "20260907_0028")
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "20260911_0055"
        )
        assert inspect(connection).has_table("assessment_work_starts")
    engine.dispose()


def test_start_racing_republication_never_adopts_unseen_standard(db_session):
    student, task, form, definition, draft, owner_id = setup_work(db_session)
    learner_id, task_id, form_id, definition_id = student.id, task.id, form.id, definition.id
    engine = db_session.get_bind()
    db_session.rollback()
    barrier = Barrier(2)

    def start():
        with Session(engine) as session:
            learner = session.get(User, learner_id)
            barrier.wait(timeout=10)
            try:
                return (
                    LmsService(session)
                    .start_assessment_work(learner, task_id, form_id)
                    .assessment_work_start_id
                )
            except TaskReviewError as error:
                assert error.status_code == 409
                return None

    def publish():
        with Session(engine) as session:
            local_definition = session.get(AssessmentDefinitionVersion, definition_id)
            barrier.wait(timeout=10)
            return republish(session, (None, None, None, local_definition, draft, owner_id)).id

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(start)
        second = pool.submit(publish)
        reference, replacement = first.result(timeout=20), second.result(timeout=20)
    assert replacement != form_id
    work = db_session.scalar(select(AssessmentWorkStart))
    if reference:
        assert work.id == reference
        assert work.task_form_version_id == form_id
    else:
        assert work is None


def test_busy_start_reports_retryable_code_and_can_retry_without_rebinding(db_session):
    student, task, form, _, _, _ = setup_work(db_session)
    task_id, form_id = task.id, form.id
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": student.email, "password": DEMO_PASSWORD}
            ).status_code
            == 200
        )
        csrf = client.cookies.get("ql_csrf")
        db_session.connection().exec_driver_sql("PRAGMA busy_timeout = 1")
        with db_session.get_bind().connect() as blocker:
            blocker.exec_driver_sql("BEGIN IMMEDIATE")
            response = client.post(
                f"/api/v1/students/me/tasks/{task_id}/start",
                json={"task_form_version_id": form_id},
                headers={"X-CSRF-Token": csrf},
            )
            assert response.status_code == 409, response.text
            assert response.json()["detail"]["code"] == "assessment_write_busy"
            assert "retry this request" in response.json()["detail"]["message"]
            blocker.rollback()
        assert db_session.scalar(select(func.count()).select_from(AssessmentWorkStart)) == 0
        response = client.post(
            f"/api/v1/students/me/tasks/{task_id}/start",
            json={"task_form_version_id": form_id},
            headers={"X-CSRF-Token": csrf},
        )
        assert response.status_code == 200, response.text
        reference = response.json()["assessment_work_start_id"]
        assert db_session.get(AssessmentWorkStart, reference).task_form_version_id == form_id
