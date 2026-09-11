"""Real task approval and continuation receipts, with synthetic human findings."""

import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from test_activity_continuation import context as _activity_context
from test_activity_continuation import run_worker
from test_task_review import _record, _source
from test_task_review import review_context as review_context

from app.api.dependencies.authentication import get_current_user
from app.api.routes.task_review import router
from app.db.session import get_db
from app.models.activity_continuation import ActivitySuggestion
from app.models.source_history import SourceRevision
from app.models.task_review import CategoryQualityReview, TaskReviewEvent
from app.schemas.category_review import ReviewDimension
from app.services.category_review import review_output
from app.services.continuation.activity import ActivityService
from app.services.rag.source_history import record_approval
from app.services.task_review import TaskReviewError

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")
activity_context = _activity_context


@pytest.fixture
def generated(review_context, db_session):
    service, actors, task = review_context
    _, source = _source(db_session, task)
    record_approval(
        db_session,
        course_id=task.course_id,
        material_id=source.material_id,
        revision_id=source.id,
        actor_id=str(actors["lead"].id),
        state="APPROVED",
        reason="Synthetic source review",
    )
    task.generation_provider = "synthetic-generator"
    task.generation_model = "synthetic-v1"
    task.generation_prompt_version = "synthetic-prompt-v1"
    service.capture(task)
    db_session.commit()
    _record(review_context, "SUBMITTED")
    return review_context


def findings(context):
    request = context["request"]
    return {
        "request_digest": context["request_digest"],
        "findings": [
            {
                "dimension": dimension.value,
                "outcome": "SATISFIED",
                "basis": "human",
                "reason": f"Synthetic reviewer checked {dimension.value} against this exact passage",
                "evidence_references": [request.evidence[0].reference],
            }
            for dimension in ReviewDimension
        ],
    }


@pytest.mark.parametrize("storage", ["metadata", "migration_ddl"])
def test_generated_approval_requires_complete_review_and_retains_protected_receipt(
    generated, db_session, storage
):
    if storage == "migration_ddl":
        db_session.execute(text("DROP TABLE category_quality_reviews"))
        path = (
            Path(__file__).parents[1]
            / "migrations/versions/20260911_0054_category_quality_reviews.py"
        )
        spec = importlib.util.spec_from_file_location("category_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        for statement in migration._STATEMENTS:
            db_session.execute(text(statement))
        db_session.commit()
        with pytest.raises(RuntimeError, match="protected"):
            migration.downgrade()
    service, actors, task = generated
    with pytest.raises(TaskReviewError, match="every generated-content"):
        _record(generated, "APPROVED")
    assert service.summary(task)["state"] == "SUBMITTED"
    context = service.quality_context(actors["lead"], task.id)
    assert context["required"]
    payload = findings(context)
    event = _record(generated, "APPROVED", quality_review=payload)
    saved = db_session.scalar(select(CategoryQualityReview))
    assert saved.task_review_event_id == event.id
    assert saved.task_revision_id == context["request"].subject_id
    assert saved.reviewer_id == actors["lead"].id
    assert saved.receipt["assessment"]["reviewer"]["reference"] == f"user:{actors['lead'].id}"
    assert len(saved.receipt["assessment"]["findings"]) == 10
    assert service.summary(task)["available"]
    assert service.history(actors["lead"], task.id)[0]["quality_reviews"] == [saved]
    for operation in (
        "UPDATE category_quality_reviews SET reviewer_id=reviewer_id",
        "DELETE FROM category_quality_reviews",
        "INSERT OR REPLACE INTO category_quality_reviews SELECT * FROM category_quality_reviews",
    ):
        with pytest.raises(IntegrityError):
            db_session.execute(text(operation))
        db_session.rollback()
    assert db_session.scalar(select(CategoryQualityReview)).id == saved.id


def test_source_change_and_unverified_dimension_cannot_approve(generated, db_session):
    service, actors, task = generated
    context = service.quality_context(actors["lead"], task.id)
    payload = findings(context)
    payload["findings"][0]["outcome"] = "UNVERIFIED"
    with pytest.raises(TaskReviewError, match="unresolved"):
        _record(generated, "APPROVED", quality_review=payload)
    payload = findings(context)
    source_id = context["request"].evidence[0].version
    record_approval(
        db_session,
        course_id=task.course_id,
        material_id=db_session.get(SourceRevision, source_id).material_id,
        revision_id=source_id,
        actor_id=str(actors["lead"].id),
        state="APPROVED",
        reason="New synthetic source review",
    )
    db_session.commit()
    with pytest.raises(TaskReviewError, match="stale"):
        _record(generated, "APPROVED", quality_review=payload)
    assert db_session.scalar(select(CategoryQualityReview)) is None


def test_rejected_dimensions_are_retained_with_rejection_event(generated, db_session):
    service, actors, task = generated
    payload = findings(service.quality_context(actors["lead"], task.id))
    payload["findings"][0].update(
        outcome="VIOLATED", reason="Source does not support the proposed answer"
    )
    event = _record(generated, "REJECTED", quality_review=payload)
    saved = db_session.scalar(select(CategoryQualityReview))
    assert event.state == saved.decision == "REJECTED"
    assert (
        saved.receipt["assessment"]["findings"][0]["reason"]
        == "Source does not support the proposed answer"
    )
    assert not service.summary(task)["available"]


def test_quality_routes_enforce_scope_and_bind_actual_reviewer(generated, db_session):
    service, actors, task = generated
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: actors["student"]
    with TestClient(app) as client:
        assert client.get(f"/tasks/{task.id}/review/quality").status_code == 403
        app.dependency_overrides[get_current_user] = lambda: actors["outsider"]
        assert client.get(f"/tasks/{task.id}/review/quality").status_code == 403
        app.dependency_overrides[get_current_user] = lambda: actors["lead"]
        context = client.get(f"/tasks/{task.id}/review/quality")
        assert context.status_code == 200
        assert "H on zero" in context.text
        payload = findings(service.quality_context(actors["lead"], task.id))
        summary = service.summary(task)
        body = {
            "expected_revision_id": summary["revision_id"],
            "expected_review_version": summary["review_version"],
            "state": "APPROVED",
            "reason": "Synthetic complete content review",
            "quality_review": payload,
        }
        payload["reviewer"] = {"reference": "forged-other-educator"}
        assert client.post(f"/tasks/{task.id}/review", json=body).status_code == 422
        del payload["reviewer"]
        assert client.post(f"/tasks/{task.id}/review", json=body).status_code == 200
        app.dependency_overrides[get_current_user] = lambda: actors["student"]
        assert client.get(f"/tasks/{task.id}/review/history").status_code == 403


def test_historical_generated_approval_stays_frozen_but_new_revision_requires_review(
    generated, db_session
):
    service, actors, task = generated
    revision = service.latest_revision(task.id)
    # A pre-FR17 approval, as retained by the forward migration; no backfilled finding.
    historic = TaskReviewEvent(
        task_revision_id=revision.id,
        course_id=task.course_id,
        version=2,
        state="APPROVED",
        actor_user_id=actors["lead"].id,
        reason="Historical synthetic approval",
        source_approvals=service.source_approvals(task),
        policy_version="educator-task-review-v1",
    )
    db_session.add(historic)
    db_session.commit()
    assert service.summary(task)["available"]
    assert db_session.scalar(select(CategoryQualityReview)) is None
    task.title = "Changed generated task"
    service.capture(task, actors["lead"].id)
    db_session.commit()
    _record(generated, "SUBMITTED")
    with pytest.raises(TaskReviewError, match="every generated-content"):
        _record(generated, "APPROVED")
    db_session.refresh(historic)
    assert historic.state == "APPROVED" and historic.reason == "Historical synthetic approval"


def test_continuation_retains_limited_selection_review_and_replay(activity_context, db_session):
    curriculum, identity, factory, _ = activity_context
    assert run_worker(factory).state.value == "completed"
    assert not run_worker(factory).processed
    saved = db_session.get(ActivitySuggestion, identity)
    quality = saved.decision["quality_review"]
    assert quality["decision"] == "APPROVED" and quality["scope"] == "reviewed_selection"
    factual = next(
        row for row in quality["assessment"]["findings"] if row["dimension"] == "factual_accuracy"
    )
    assert factual["outcome"] == "NOT_APPLICABLE" and "not remeasured" in factual["reason"]
    assert any(item["approval_reference"] for item in quality["evidence"])
    assert (
        ActivityService(db_session).read(curriculum[2], identity).next_task_id
        == curriculum[4][1].id
    )


def test_unavailable_selection_review_withholds_suggestion_without_losing_work(
    activity_context, db_session, monkeypatch
):
    from app.services.continuation import activity

    original = activity.review_selection

    def unavailable(*args):
        context, _ = original(*args)
        return context, review_output(context)

    monkeypatch.setattr(activity, "review_selection", unavailable)
    curriculum, identity, factory, _ = activity_context
    assert run_worker(factory).state.value == "completed"
    saved = db_session.get(ActivitySuggestion, identity)
    assert saved.task_id is None and saved.decision["quality_review"]["decision"] == "REJECTED"
    view = ActivityService(db_session).read(curriculum[2], identity)
    assert (
        view.state == "quality_review_required" and not view.options and view.next_task_id is None
    )
