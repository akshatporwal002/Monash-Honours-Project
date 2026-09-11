"""Progress must preserve UTC instants through SQLite reload and HTTP serialization."""

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from test_misconceptions import context, finish, review_command

from app.db.session import get_db
from app.main import create_app
from app.models.activity_continuation import ActivityChoice, ActivityProgress, ActivitySuggestion
from app.models.learner_model import LearnerModelSnapshot
from app.models.learning_evidence import LearningEvidence
from app.models.lms import SubmissionAttempt
from app.models.misconceptions import MisconceptionReviewRecord
from app.models.persistence import WorkflowRun
from app.models.user import User
from app.schemas.progress import LearningProgressPage
from app.services.learning_progress import LearningProgressService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")

RECORDED = datetime(2026, 9, 10, 3, 33, 21, 486860, tzinfo=UTC)


def timestamp_values(value):
    """Find actual timestamp fields, including choices nested inside adaptations."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"occurred_at", "created_at", "generated_at"}:
                yield key, item
            else:
                yield from timestamp_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from timestamp_values(item)


@pytest.fixture
def saved_progress(db_session):
    # Fix insertion time, before any immutable history is written. Never rewrite it.
    def timestamp_new_records(session, *_):
        for row in session.new:
            if isinstance(row, (LearningEvidence, LearnerModelSnapshot)):
                row.occurred_at = RECORDED
            elif isinstance(row, SubmissionAttempt):
                row.submitted_at = RECORDED
            elif isinstance(row, MisconceptionReviewRecord):
                row.created_at = RECORDED

    event.listen(db_session, "before_flush", timestamp_new_records)
    try:
        fixture, _, educator, _, student, checks, _, saved = context(db_session)
        completed = finish(checks, student, saved)
        checks.review(educator, saved.id, review_command(completed))
    finally:
        event.remove(db_session, "before_flush", timestamp_new_records)

    workflow = db_session.scalar(
        select(WorkflowRun).where(WorkflowRun.submission_id == fixture["response_id"])
    )
    snapshot = db_session.scalar(select(LearnerModelSnapshot))
    evidence = list(db_session.scalars(select(LearningEvidence.id)))
    db_session.add(
        ActivityProgress(
            workflow_id=workflow.id,
            learner_id=student.id,
            course_id=saved.course_id,
            outcome_id=saved.outcome_id,
            snapshot_id=snapshot.id,
            state="recorded",
            evidence_ids=evidence,
            created_at=RECORDED,
        )
    )
    db_session.flush()
    db_session.add(
        ActivitySuggestion(
            workflow_id=workflow.id,
            decision={"state": "suggested", "reason": "Preserved suggestion", "uncertainty": 1},
            created_at=RECORDED,
        )
    )
    db_session.flush()
    db_session.add(
        ActivityChoice(
            workflow_id=workflow.id,
            actor_id=student.id,
            version=1,
            request_key="timezone-choice",
            payload={"action": "defer", "reason": "Revisit later"},
            created_at=RECORDED,
        )
    )
    db_session.commit()
    return fixture, student.id, educator.id, saved.course_id


def test_sqlite_reload_and_all_progress_http_timestamps_preserve_the_instant(
    db_session, saved_progress
):
    fixture, student_id, educator_id, course_id = saved_progress
    # A new session ensures neither the service nor HTTP reads use pre-flush objects.
    with Session(db_session.get_bind()) as reloaded:
        stored = reloaded.get(SubmissionAttempt, fixture["response_id"])
        assert stored.submitted_at == RECORDED.replace(tzinfo=None)
        tables = (
            "submission_attempts",
            "learning_evidence",
            "learner_model_snapshots",
            "assessment_decisions",
            "misconception_reviews",
            "activity_progress_receipts",
            "activity_suggestions",
            "activity_choices",
        )

        def history():
            return {
                table: reloaded.connection().exec_driver_sql(f'SELECT * FROM "{table}"').all()
                for table in tables
            }

        before = history()
        student = reloaded.get(User, student_id)
        page = LearningProgressService(reloaded).read(student, course_id)
        assert page.items
        row = next(item for item in page.items if item.results)
        assert row.recent_evidence and row.estimates and row.adaptations[0].choices
        for name, stamp in timestamp_values(page.model_dump()):
            assert stamp.utcoffset() == timedelta(0), (name, stamp)
            if name != "generated_at":
                assert stamp == RECORDED
        assert all(result.result is None for result in row.results)
        assert (
            LearningProgressService(reloaded).read(reloaded.get(User, educator_id), course_id).items
            == page.items
        )

        app = create_app()
        app.dependency_overrides[get_db] = lambda: reloaded
        with TestClient(app) as client:
            path = f"/api/v1/progress/{course_id}"
            assert client.get(path).status_code == 401
            login = client.post(
                "/api/v1/auth/login",
                json={"email": fixture["student_email"], "password": fixture["student_password"]},
            )
            assert login.status_code == 200
            response = client.get(path)
            assert response.status_code == 200, response.text
            payload = response.json()
            assert response.headers["cache-control"] == "no-store"
            assert client.get(path, params={"learner_id": student_id + 100}).status_code == 404
            bodies = [payload]
            evidence_id = row.recent_evidence[0].evidence_id
            detail = client.get(f"{path}/evidence/{evidence_id}")
            assert detail.status_code == 200, detail.text
            bodies.append(detail.json())
            # Exercise the union-query serialization for every populated record kind.
            kinds = {kind for counts in page.cohort_weekly_trends.values() for kind in counts}
            assert {kind.split(":")[0] for kind in kinds} >= {
                "observation",
                "response",
                "estimate",
                "misconception",
                "adaptation",
                "choice",
                "result",
            }
            for kind in kinds:
                records = client.get(f"{path}/records", params={"kind": kind})
                assert records.status_code == 200, records.text
                assert records.json()["items"]
                bodies.append(records.json())
            for body in bodies:
                for name, stamp in timestamp_values(body):
                    parsed = datetime.fromisoformat(stamp)
                    assert parsed.utcoffset() == timedelta(0), (name, stamp)
                    if name != "generated_at":
                        assert parsed == RECORDED
                        assert parsed.astimezone(ZoneInfo("Australia/Sydney")).isoformat() == (
                            "2026-09-10T13:33:21.486860+10:00"
                        )
            assert LearningProgressPage.model_validate(payload).items == page.items
        assert history() == before
        assert stored.submitted_at.tzinfo is None  # Response normalization never mutates the ORM.


@pytest.mark.parametrize(
    ("stamp", "expected_local"),
    [
        ("2026-09-10T03:33:21.486860", "2026-09-10T13:33:21.486860+10:00"),
        ("2026-01-15T03:33:21.486860", "2026-01-15T14:33:21.486860+11:00"),
        ("2026-09-10T14:30:00", "2026-09-11T00:30:00+10:00"),
        ("2026-12-31T13:30:00", "2027-01-01T00:30:00+11:00"),
        ("2026-10-03T15:59:59", "2026-10-04T01:59:59+10:00"),
        ("2026-10-03T16:00:00", "2026-10-04T03:00:00+11:00"),
        ("2026-04-04T15:59:59", "2026-04-05T02:59:59+11:00"),
        ("2026-04-04T16:00:00", "2026-04-05T02:00:00+10:00"),
    ],
)
def test_progress_response_preserves_utc_and_offset_instants_across_sydney_boundaries(
    stamp, expected_local
):
    from app.schemas.progress import ProgressResult

    naive = datetime.fromisoformat(stamp)
    expected = naive.replace(tzinfo=UTC)
    # An already-aware timestamp must be converted, never relabelled as UTC.
    for value in (
        naive,
        expected,
        expected.astimezone(ZoneInfo("Australia/Sydney")),
        expected.astimezone(timezone(timedelta(hours=-7))),
    ):
        result = ProgressResult(
            response_id="response",
            task_id="task",
            result=None,
            status="pending",
            occurred_at=value,
        )
        wire = result.model_dump(mode="json")["occurred_at"]
        parsed = datetime.fromisoformat(wire)
        assert parsed.utcoffset() == timedelta(0)
        assert parsed == expected
        assert parsed.astimezone(ZoneInfo("Australia/Sydney")).isoformat() == expected_local
