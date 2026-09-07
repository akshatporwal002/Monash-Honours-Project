from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Course,
    CourseModule,
    LearningMaterial,
    LearningOutcome,
    LearningTask,
    OutcomeKind,
    PlatformAuditEvent,
    TaskType,
    User,
    UserRole,
)
from app.models.source_history import SourcePassage, SourceRevision
from app.models.task_review import TaskReviewEvent, TaskRevision
from app.services.quantum import QuantumSimulationError, validate_circuit
from app.services.rag.source_history import record_approval
from app.services.task_review import TaskReviewError, TaskReviewService


@pytest.fixture
def review_context(db_session):
    actors = {}
    for name, role in (
        ("lead", UserRole.EDUCATOR),
        ("outsider", UserRole.EDUCATOR),
        ("admin", UserRole.ADMINISTRATOR),
        ("student", UserRole.STUDENT),
    ):
        actors[name] = User(
            email=f"{name}@task-review.test", password_hash="unused", full_name=name, role=role
        )
    db_session.add_all(actors.values())
    db_session.flush()
    course = Course(educator_id=actors["lead"].id, code="REVIEW-1", title="Review course")
    db_session.add(course)
    db_session.flush()
    module = CourseModule(course_id=course.id, title="Gates", position=1)
    db_session.add(module)
    db_session.flush()
    outcome = LearningOutcome(
        module_id=module.id,
        title="Hadamard",
        statement="Predict a Hadamard outcome",
        kind=OutcomeKind.TOPIC,
        position=1,
    )
    db_session.add(outcome)
    db_session.flush()
    task = LearningTask(
        slug="teacher-authored",
        title="Predict",
        module=module.title,
        description="Predict H applied to zero",
        instructions="Explain your prediction",
        task_type=TaskType.SHORT_ANSWER,
        difficulty="beginner",
        points=100,
        position=1,
        course_id=course.id,
        module_id=module.id,
        learning_outcome_id=outcome.id,
        expected_answer="Equal measurement probabilities",
    )
    db_session.add(task)
    db_session.commit()
    return TaskReviewService(db_session), actors, task


def _record(context, state, **overrides):
    service, actors, task = context
    summary = service.summary(task)
    return service.record(
        actors["lead"],
        task.id,
        **{
            "expected_revision_id": summary["revision_id"],
            "expected_review_version": summary["review_version"],
            "state": state,
            "reason": "Reviewed exact teaching content",
            **overrides,
        },
    )


def _approve(context):
    service, actors, task = context
    service.capture(task, actors["lead"].id)
    _record(context, "SUBMITTED")
    return _record(context, "APPROVED")


def test_review_requires_explicit_submission_and_approval(db_session, review_context):
    service, actors, task = review_context
    revision = service.capture(task, actors["lead"].id)
    assert not service.summary(task)["available"]
    with pytest.raises(TaskReviewError, match="current state"):
        _record(review_context, "APPROVED")
    # Failed review rolls back any uncommitted authoring work.
    service.capture(task, actors["lead"].id)
    _record(review_context, "SUBMITTED")
    approved = _record(review_context, "APPROVED")
    assert service.summary(task)["available"]
    assert approved.source_approvals == {}
    assert service.latest_revision(task.id).snapshot["expected_answer"] == task.expected_answer
    assert db_session.scalar(select(func.count()).select_from(PlatformAuditEvent)) == 2
    assert revision.provenance == "AUTHORED"


def test_capture_flushes_edits_and_preserves_previous_approved_revision(db_session, review_context):
    service, actors, task = review_context
    approval = _approve(review_context)
    original = service.latest_revision(task.id)
    task.instructions = "Predict then explain without running a circuit"
    task.due_at = datetime(2026, 10, 1, tzinfo=UTC)
    revised = service.capture(task, actors["lead"].id)
    db_session.commit()
    assert revised.version == 2
    assert revised.snapshot["instructions"] == task.instructions
    assert revised.snapshot["due_at"] == "2026-10-01T00:00:00+00:00"
    assert original.snapshot["instructions"] == "Explain your prediction"
    assert service.latest_event(original.id).id == approval.id
    assert service.summary(task)["state"] == "DRAFT"
    assert not service.summary(task)["available"]
    assert service.capture(task).id == revised.id
    assert len(service.history(actors["lead"], task.id)) == 2


def test_out_of_band_task_or_outcome_edit_invalidates_review(db_session, review_context):
    service, _, task = review_context
    _approve(review_context)
    outcome = db_session.get(LearningOutcome, task.learning_outcome_id)
    outcome.statement = "Apply a different standard"
    db_session.commit()
    assert not service.summary(task)["available"]
    with pytest.raises(TaskReviewError, match="content changed"):
        _record(review_context, "WITHDRAWN")


@pytest.mark.parametrize("actor", ["student", "outsider", "admin"])
def test_only_course_owner_can_change_task_review(db_session, review_context, actor):
    service, actors, task = review_context
    revision = service.capture(task)
    db_session.commit()
    with pytest.raises(TaskReviewError) as caught:
        service.record(
            actors[actor],
            task.id,
            expected_revision_id=revision.id,
            expected_review_version=0,
            state="SUBMITTED",
            reason="Attempted review",
        )
    assert caught.value.status_code == 403
    assert service.latest_event(revision.id) is None
    if actor != "admin":
        with pytest.raises(TaskReviewError) as caught:
            service.history(actors[actor], task.id)
        assert caught.value.status_code == 403
    else:
        assert len(service.history(actors[actor], task.id)) == 1


def test_stale_action_and_rejection_preserve_review_history(review_context):
    service, actors, task = review_context
    service.capture(task)
    submitted = _record(review_context, "SUBMITTED")
    with pytest.raises(TaskReviewError, match="review changed"):
        _record(review_context, "REJECTED", expected_review_version=0)
    rejected = _record(review_context, "REJECTED")
    assert not service.summary(task)["available"]
    _record(review_context, "SUBMITTED")
    _record(review_context, "APPROVED")
    _record(review_context, "WITHDRAWN")
    events = service.history(actors["lead"], task.id)[0]["events"]
    assert [event.state for event in events] == [
        "SUBMITTED",
        "REJECTED",
        "SUBMITTED",
        "APPROVED",
        "WITHDRAWN",
    ]
    assert [event.id for event in events[:2]] == [submitted.id, rejected.id]
    assert not service.summary(task)["available"]


def test_concurrent_review_requests_cannot_create_duplicate_events(db_session, review_context):
    service, actors, task = review_context
    revision = service.capture(task)
    db_session.commit()
    task_id, actor_id, revision_id = task.id, actors["lead"].id, revision.id
    barrier = Barrier(2)

    def submit():
        with Session(db_session.get_bind(), autoflush=False) as session:
            actor = session.get(User, actor_id)
            barrier.wait(timeout=10)
            try:
                return (
                    TaskReviewService(session)
                    .record(
                        actor,
                        task_id,
                        expected_revision_id=revision_id,
                        expected_review_version=0,
                        state="SUBMITTED",
                        reason="Review requested",
                    )
                    .state
                )
            except TaskReviewError as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(), range(2)))
    assert results.count("SUBMITTED") == 1
    assert results.count(409) == 1
    assert db_session.scalar(select(func.count()).select_from(TaskReviewEvent)) == 1


def test_assessor_can_read_history_only_while_course_grant_is_current(db_session, review_context):
    from app.models import ScopedRole
    from app.services.assessment.access import RoleAssignmentService
    from app.services.assessment.eligibility import AssessorEligibilityService

    service, actors, task = review_context
    _approve(review_context)
    eligibility = AssessorEligibilityService(db_session)
    eligibility.record(
        actors["lead"],
        course_id=task.course_id,
        subject_user_id=actors["outsider"].id,
        expected_version=0,
        state="APPROVED",
        reason="Teaching appointment confirmed",
    )
    RoleAssignmentService(db_session, assignment_eligibility=lambda *_: True).assign(
        actors["admin"],
        course_id=task.course_id,
        subject_user_id=actors["outsider"].id,
        role=ScopedRole.ASSESSOR,
        reason="Course-specific appointment",
    )
    assert len(service.history(actors["outsider"], task.id)) == 1
    eligibility.record(
        actors["lead"],
        course_id=task.course_id,
        subject_user_id=actors["outsider"].id,
        expected_version=1,
        state="WITHDRAWN",
        reason="Teaching duties ended",
    )
    with pytest.raises(TaskReviewError) as caught:
        service.review_summary(actors["outsider"], task.id)
    assert caught.value.status_code == 403


def _source(db_session, task):
    material = LearningMaterial(
        course_id=task.course_id,
        original_filename="lesson.txt",
        content_hash="a" * 64,
        mime_type="text/plain",
    )
    db_session.add(material)
    db_session.flush()
    revision = SourceRevision(
        material_id=material.id,
        course_id=task.course_id,
        version=1,
        source_label="Teacher lesson",
        mime_type="text/plain",
        content_hash="a" * 64,
        extracted_blocks=[],
        extraction_version="fixture-v1",
        provenance="EXTRACTED",
    )
    db_session.add(revision)
    db_session.flush()
    passage = SourcePassage(
        id="review-passage",
        revision_id=revision.id,
        course_id=task.course_id,
        chunk_index=0,
        chunk_text="H on zero gives equal probabilities",
        chunk_hash="b" * 64,
    )
    db_session.add(passage)
    db_session.flush()
    task.source_references = [passage.id]
    db_session.commit()
    return material, revision


def test_sources_need_current_approval_and_reapproval_needs_fresh_review(
    db_session, review_context
):
    service, actors, task = review_context
    material, revision = _source(db_session, task)
    service.capture(task)
    _record(review_context, "SUBMITTED")
    with pytest.raises(TaskReviewError, match="current approval"):
        _record(review_context, "APPROVED")
    source_args = dict(
        course_id=task.course_id,
        material_id=material.id,
        revision_id=revision.id,
        actor_id=str(actors["lead"].id),
        reason="Read source",
    )
    source_approval = record_approval(db_session, state="APPROVED", **source_args)
    db_session.commit()
    event = _record(review_context, "APPROVED")
    assert event.source_approvals == {"review-passage": source_approval.id}
    assert service.summary(task)["available"]
    record_approval(db_session, state="REVOKED", **source_args)
    db_session.commit()
    assert not service.summary(task)["available"]
    record_approval(db_session, state="APPROVED", **source_args)
    db_session.commit()
    assert not service.summary(task)["available"]
    _record(review_context, "WITHDRAWN")
    _record(review_context, "SUBMITTED")
    _record(review_context, "APPROVED")
    assert service.summary(task)["available"]
    material.retired_at = datetime.now(UTC)
    db_session.commit()
    assert not service.summary(task)["available"]


def test_generated_and_formal_tasks_require_external_sources(db_session, review_context):
    service, _, task = review_context
    with pytest.raises(TaskReviewError, match="source passages"):
        service.validate_ready(task, require_sources=True)
    task.slug = "generated-without-sources"
    db_session.commit()
    service.capture(task)
    _record(review_context, "SUBMITTED")
    with pytest.raises(TaskReviewError, match="source passages"):
        _record(review_context, "APPROVED")


@pytest.mark.parametrize(
    "criteria",
    [
        {},
        {"starter_circuit": {"qubits": 1, "operations": {}}},
        {"starter_circuit": {"qubits": 1, "operations": [], "noise": "custom"}},
        {"starter_circuit": {"qubits": 6, "operations": []}},
        {"starter_circuit": {"qubits": 1, "operations": [{"gate": "z", "targets": [0]}]}},
        {"starter_circuit": {"qubits": 1, "operations": []}, "required_gates": ["z"]},
        {"starter_circuit": {"qubits": 1, "operations": []}, "expected_circuit": "bad"},
    ],
)
def test_unsupported_circuit_content_cannot_be_approved(db_session, review_context, criteria):
    service, _, task = review_context
    task.task_type = TaskType.QUANTUM_CIRCUIT
    task.marking_criteria = criteria
    db_session.commit()
    service.capture(task)
    _record(review_context, "SUBMITTED")
    with pytest.raises(TaskReviewError) as caught:
        _record(review_context, "APPROVED")
    assert caught.value.status_code == 422
    assert not service.summary(task)["available"]


def test_empty_starter_allowed_but_empty_execution_still_rejected(db_session, review_context):
    service, _, task = review_context
    task.task_type = TaskType.QUANTUM_CIRCUIT
    task.marking_criteria = {"starter_circuit": {"qubits": 1, "operations": []}}
    db_session.commit()
    _approve(review_context)
    assert service.summary(task)["available"]
    with pytest.raises(QuantumSimulationError, match="at least one gate"):
        validate_circuit(qubits=1, operations=[])


@pytest.mark.parametrize("table", ["task_revisions", "task_review_events"])
@pytest.mark.parametrize("action", ["update", "delete", "replace", "unique_replace"])
def test_sql_history_mutations_fail(db_session, review_context, table, action):
    _approve(review_context)
    statements = {
        "update": f"UPDATE {table} SET version = version + 10",
        "delete": f"DELETE FROM {table}",
        "replace": f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}",
    }
    if action == "unique_replace":
        model = TaskRevision if table == "task_revisions" else TaskReviewEvent
        columns = ", ".join(column.name for column in model.__table__.columns)
        selected = ", ".join(
            "'replacement-id'" if col.name == "id" else col.name for col in model.__table__.columns
        )
        statement = (
            f"INSERT OR REPLACE INTO {table} ({columns}) SELECT {selected} FROM {table} LIMIT 1"
        )
    else:
        statement = statements[action]
    with pytest.raises(IntegrityError, match="append-only"):
        db_session.execute(text(statement))
    db_session.rollback()
    assert review_context[0].summary(review_context[2])["available"]
