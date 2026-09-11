"""Scope, released-result visibility and preserved inference evidence in progress reads."""

import pytest
from fastapi import HTTPException
from sqlalchemy import inspect, select
from test_misconceptions import context, finish, review_command

from app.models.assessment import AssessmentDecision
from app.models.lms import Course, CourseState
from app.models.user import User, UserRole
from app.services.learning_progress import LearningProgressService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def test_progress_reads_preserve_states_links_and_hide_provisional_results(db_session):
    fixture, _, educator, _, student, checks, _, saved = context(db_session)
    complete = finish(checks, student, saved)
    reviewed = checks.review(educator, saved.id, review_command(complete))
    service = LearningProgressService(db_session)
    tables = inspect(db_session.connection()).get_table_names()

    def counts():
        return {
            name: db_session.connection()
            .exec_driver_sql(f'SELECT COUNT(*) FROM "{name}"')
            .scalar_one()
            for name in tables
        }

    before = counts()
    decisions_before = [
        (row.id, row.result, row.result_state)
        for row in db_session.scalars(select(AssessmentDecision))
    ]
    mine = service.read(student, saved.course_id)
    row = next(item for item in mine.items if item.outcome_id == saved.outcome_id)
    assert row.misconception_ids == [saved.id]
    assert row.estimates and row.estimates[-1].snapshot_id == reviewed.reviews[-1].snapshot_id
    assert all(item.uncertainty == 1 for item in row.estimates)
    assert {item.evidence_id for estimate in row.estimates for item in estimate.evidence}
    assert row.results and all(item.result is None for item in row.results)
    assert row.observations["MISCONCEPTION_CHECK"] == 4
    assert any(item.confidence is not None for item in row.recent_evidence)
    assert all(item.learner_id == student.id for item in mine.items)
    assert service.read(educator, saved.course_id, learner_id=student.id).items == mine.items
    assert [
        (item.id, item.result, item.result_state)
        for item in db_session.scalars(select(AssessmentDecision))
    ] == decisions_before
    assert counts() == before


def test_progress_scope_denies_other_learners_and_archived_student_access(db_session):
    _, _, educator, _, student, _, _, saved = context(db_session)
    outsider = User(
        email="outside-progress@example.test",
        full_name="Outside",
        password_hash="unused",
        role=UserRole.STUDENT,
    )
    db_session.add(outsider)
    db_session.commit()
    service = LearningProgressService(db_session)
    with pytest.raises(HTTPException):
        service.read(student, saved.course_id, learner_id=outsider.id)
    with pytest.raises(HTTPException):
        service.read(outsider, saved.course_id)
    course = db_session.get(Course, saved.course_id)
    course.state = CourseState.ARCHIVED
    db_session.commit()
    with pytest.raises(HTTPException):
        service.read(student, saved.course_id)
    assert service.read(educator, saved.course_id).course_id == saved.course_id


def test_progress_outcomes_use_published_rules_and_released_whole_decisions(db_session):
    from test_reassessment import context as reassessment_context

    from app.services.assessment.outcome_results import OutcomeResultService

    fixture, educator, student, _, _, _ = reassessment_context(db_session)
    expected = OutcomeResultService(db_session).read(student, fixture["response_id"])
    rows = LearningProgressService(db_session).read(student, fixture["course_id"]).items
    selected = next(item for row in rows for item in row.outcome_results)
    assert selected.model_dump() == expected.model_dump(exclude={"authorisations"})
    assert selected.result.value == "INCOMPLETE"
    assert selected.evidence_response_ids == [fixture["response_id"]]
    assert "PRIVATE" not in selected.model_dump_json()
    assert LearningProgressService(db_session).read(educator, fixture["course_id"]).items == rows
    course = db_session.get(Course, fixture["course_id"])
    course.state = CourseState.ARCHIVED
    db_session.commit()
    assert LearningProgressService(db_session).read(educator, fixture["course_id"]).items == rows


def test_cohort_pages_include_empty_scopes_and_exclude_inactive_learners(db_session):
    from app.models.lms import Enrollment

    _, _, educator, _, student, _, _, saved = context(db_session)
    other = User(
        email="next-progress@example.test",
        full_name="Next learner",
        password_hash="unused",
        role=UserRole.STUDENT,
    )
    db_session.add(other)
    db_session.flush()
    db_session.add(Enrollment(course_id=saved.course_id, student_id=other.id))
    db_session.commit()
    service = LearningProgressService(db_session)
    first = service.read(educator, saved.course_id, outcome_id=saved.outcome_id, limit=1)
    second = service.read(
        educator, saved.course_id, outcome_id=saved.outcome_id, limit=1, offset=first.next_offset
    )
    assert first.items[0].learner_id == student.id and first.next_offset == 1
    assert second.items[0].learner_id == other.id and second.next_offset is None
    assert second.items[0].observations == {} and second.items[0].estimates == []
    assert first.cohort_observations == second.cohort_observations
    other.is_active = False
    db_session.commit()
    assert (
        service.read(educator, saved.course_id, outcome_id=saved.outcome_id, limit=1).next_offset
        is None
    )


def test_progress_http_scope_cache_and_page_limits(db_session):
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import create_app

    fixture, _, _, _, student, _, _, saved = context(db_session)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        path = f"/api/v1/progress/{saved.course_id}"
        assert client.get(path).status_code == 401
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": fixture["student_email"], "password": fixture["student_password"]},
            ).status_code
            == 200
        )
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert all(row["learner_id"] == student.id for row in response.json()["items"])
        assert client.get(path, params={"learner_id": student.id + 100}).status_code == 404
        assert client.get(path, params={"limit": 26}).status_code == 422
        assert client.get(path, params={"offset": -1}).status_code == 422


def test_old_practice_cannot_complete_a_now_formal_task(db_session):
    from test_assessed_lms_reads import prepare_reads

    from app.services.progress_activity import completed_practice_tasks

    student, _, _, task = prepare_reads(db_session, True)
    assert task.id not in completed_practice_tasks(db_session, student.id, [task.id])


def test_evidence_detail_scope_fresh_gate_and_original_content(db_session):
    from test_misconceptions import answer

    from app.models.learning_evidence import LearningEvidence
    from app.services.progress_evidence import read_progress_evidence

    _, _, educator, outsider, student, checks, _, saved = context(db_session)
    identity = db_session.scalar(
        select(LearningEvidence.id).where(
            LearningEvidence.course_id == saved.course_id,
            LearningEvidence.evidence_type == "RESPONSE",
        )
    )
    detail = read_progress_evidence(db_session, student, saved.course_id, identity)
    assert any(item.label == "Answer" and item.text for item in detail.fields)
    assert detail == read_progress_evidence(db_session, educator, saved.course_id, identity)
    assert "declared_conditions" not in detail.model_dump_json()
    with pytest.raises(HTTPException):
        read_progress_evidence(db_session, outsider, saved.course_id, identity)
    with pytest.raises(HTTPException):
        read_progress_evidence(db_session, student, "other-course", identity)
    saved, _ = answer(checks, student, saved)
    saved, _ = answer(checks, student, saved)
    with pytest.raises(HTTPException, match="fresh check"):
        read_progress_evidence(db_session, student, saved.course_id, identity)
    assert read_progress_evidence(db_session, educator, saved.course_id, identity).fields
    saved, _ = answer(checks, student, saved)
    assert (
        read_progress_evidence(db_session, student, saved.course_id, identity).fields
        == detail.fields
    )


def test_trends_link_support_states_and_hide_provisional_results(db_session):
    from datetime import date

    from app.services.progress_trends import contributing_records, records_query

    _, _, educator, _, student, checks, _, saved = context(db_session)
    complete = finish(checks, student, saved)
    checks.review(educator, saved.id, review_command(complete))
    service = LearningProgressService(db_session)
    page = service.read(educator, saved.course_id)
    series = page.cohort_weekly_trends
    assert any("misconception:UNCERTAIN" in counts for counts in series.values())
    assert any("result:unreleased" in counts for counts in series.values())
    assert all("result:PASS" not in counts for counts in series.values())
    _, roster = service.scope(educator, saved.course_id)
    source = records_query(saved.course_id, roster)
    for week, counts in series.items():
        for kind, count in counts.items():
            records = contributing_records(
                db_session,
                source,
                course_id=saved.course_id,
                kind=kind,
                week=date.fromisoformat(week),
                limit=50,
            )
            assert len(records["items"]) == count
            assert all(row["learner_id"] == student.id for row in records["items"])
            if kind.startswith(("observation:", "misconception:", "estimate:", "response:")):
                assert all(row["evidence_ids"] for row in records["items"])


def test_stale_pathway_credit_does_not_block_unrelated_tasks(db_session):
    from support.curriculum import setup_curriculum

    from app.models.lms import LearningOutcome, OutcomeKind
    from app.models.persistence import LearningTask
    from app.schemas.lms import SubmissionCreate
    from app.services.lms import LmsService
    from app.services.progress_activity import completed_practice_tasks

    _, _, student, course, tasks, _, _ = setup_curriculum(db_session)
    service = LmsService(db_session)
    service.submit(student, tasks[0].id, SubmissionCreate(answer="a"))
    outcome = LearningOutcome(
        module_id=tasks[0].module_id,
        title="Unrelated outcome",
        statement="Independent activity",
        kind=OutcomeKind.TOPIC,
        position=2,
    )
    db_session.add(outcome)
    db_session.flush()
    unrelated = LearningTask(
        slug="unrelated-progress",
        title="Unrelated activity",
        module=tasks[0].module,
        description="Independent practice",
        instructions="Explain",
        task_type=tasks[0].task_type,
        difficulty="beginner",
        points=0,
        position=10,
        course_id=course.id,
        module_id=tasks[0].module_id,
        learning_outcome_id=outcome.id,
        prerequisite_task_ids=[],
    )
    db_session.add(unrelated)
    tasks[0].description = "A changed, no longer reviewed description"
    db_session.commit()
    assert tasks[0].id not in completed_practice_tasks(db_session, student.id, [tasks[0].id])
    service._require_unlocked(student, unrelated)
