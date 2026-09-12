"""Start-work validation reuse stays inside its transaction's read phases."""

import copy
from collections import Counter

import pytest
from sqlalchemy import event, select
from support.learning_loop import seed_learning_loop

from app.models import LearningTask, User
from app.models.assessment_work import AssessmentWorkStart
from app.models.lms import SubmissionDraft
from app.models.source_history import SourcePassage, SourceRevision
from app.services.lms import LmsService
from app.services.rag.source_history import record_approval
from app.services.task_review import TaskReviewError, TaskReviewService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


@pytest.fixture
def start_context(db_session):
    fixture = seed_learning_loop(db_session)
    student = db_session.get(User, fixture["student_id"])
    task = db_session.get(LearningTask, fixture["task_id"])
    return LmsService(db_session), student, task, fixture


def revoke_source(session, task, teacher_id):
    passage = session.get(SourcePassage, task.source_references[0])
    revision = session.get(SourceRevision, passage.revision_id)
    return record_approval(
        session,
        course_id=task.course_id,
        material_id=revision.material_id,
        revision_id=revision.id,
        actor_id=str(teacher_id),
        state="REVOKED",
        reason="Synthetic source revoked to test start-work validation freshness.",
    )


def test_start_reuses_repeated_review_reads_but_rechecks_after_course_write(
    db_session, start_context
):
    service, student, task, fixture = start_context
    phases = [Counter()]
    writes = []
    course_write_phase = None

    def capture(_connection, _cursor, statement, parameters, _context, _many):
        nonlocal course_write_phase
        sql = " ".join(statement.lower().split())
        command = sql.split()[0]
        if command in {"insert", "update", "delete"}:
            writes.append(sql)
            phases.append(Counter())
            if sql.startswith("update courses "):
                course_write_phase = len(phases) - 1
            return
        if command != "select":
            return
        if "from task_revisions " in sql and "order by task_revisions.version desc" in sql:
            kind = "latest_revision"
        elif (
            "from task_review_events " in sql and "order by task_review_events.version desc" in sql
        ):
            kind = "latest_review"
        elif "from source_passages " in sql and "source_passages.id in" in sql:
            kind = "source_bindings"
        else:
            return
        phases[-1][(kind, repr(parameters))] += 1

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        started = service.start_assessment_work(student, task.id, fixture["form_id"])
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert started.assessment_work_start_id
    assert phases[0], "The real pre-write publication checks must run"
    repeated = {
        (phase, kind, parameters): count
        for phase, counts in enumerate(phases)
        for (kind, parameters), count in counts.items()
        # Source resolution has two legitimate scan-policy variants; the latest
        # revision and review lookups have one argument contract per read phase.
        if count > (2 if kind == "source_bindings" else 1)
    }
    assert repeated == {}, (
        f"Repeated publication reads inside unchanged start-work phases: {repeated}"
    )
    assert any(sql.startswith("insert into submission_drafts ") for sql in writes)
    assert course_write_phase is not None
    assert any(
        kind == "latest_revision" and count > 0
        for counts in phases[course_write_phase:]
        for (kind, _), count in counts.items()
    ), "The Course write must invalidate reuse before the final frozen-standard declaration"
    work = db_session.get(AssessmentWorkStart, started.assessment_work_start_id)
    assert work.task_form_version_id == fixture["form_id"]
    assert work.source_references == task.source_references


def test_start_rechecks_source_revocation_between_operations(db_session, start_context):
    service, student, task, fixture = start_context
    started = service.start_assessment_work(student, task.id, fixture["form_id"])
    original = copy.deepcopy(
        dict(
            db_session.execute(
                select(AssessmentWorkStart.__table__).where(
                    AssessmentWorkStart.id == started.assessment_work_start_id
                )
            )
            .mappings()
            .one()
        )
    )
    revoke_source(db_session, task, fixture["teacher_id"])
    db_session.commit()
    with pytest.raises(TaskReviewError):
        service.start_assessment_work(student, task.id, fixture["form_id"])
    db_session.rollback()
    preserved = dict(
        db_session.execute(
            select(AssessmentWorkStart.__table__).where(
                AssessmentWorkStart.id == started.assessment_work_start_id
            )
        )
        .mappings()
        .one()
    )
    assert preserved == original


def test_start_draft_flush_and_later_source_write_invalidate_publication_reuse(
    db_session, start_context, monkeypatch
):
    service, student, task, fixture = start_context
    create_draft = service._get_or_create_draft
    changed = []

    def revoke_after_draft_flush(student_id, task_id):
        draft = create_draft(student_id, task_id)
        # Fill a successful read after the new draft's flush, then append a real
        # synthetic source revocation before the final start_work declaration.
        assert TaskReviewService(db_session).source_approvals(
            task, required=True, require_scan=False
        )
        changed.append(revoke_source(db_session, task, fixture["teacher_id"]))
        return draft

    monkeypatch.setattr(service, "_get_or_create_draft", revoke_after_draft_flush)
    with pytest.raises(TaskReviewError):
        service.start_assessment_work(student, task.id, fixture["form_id"])
    db_session.rollback()
    assert len(changed) == 1
    assert (
        db_session.scalar(
            select(AssessmentWorkStart.id).where(AssessmentWorkStart.student_id == student.id)
        )
        is None
    )
    assert (
        db_session.scalar(
            select(SubmissionDraft.id).where(SubmissionDraft.student_id == student.id)
        )
        is None
    )
    # The rejected command must not leave its uncommitted source change behind.
    assert TaskReviewService(db_session).source_approvals(task, required=True)
