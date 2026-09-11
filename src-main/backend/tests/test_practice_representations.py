"""FR35 delivery authorization and immutable provenance; approvals are synthetic."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from support.task_review import approve_fixture_task, approve_sourced_fixture_task
from test_assessment_work_starts import setup_work
from test_conditional_programming import content as content

from app.api.dependencies.authentication import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.domain.platform_enums import AccessSupportState
from app.main import create_app
from app.models import CourseState, Enrollment, LearningTask, User, UserRole
from app.models.assessment import AssessmentDecision
from app.models.learner_model import LearnerModelSnapshot
from app.models.learning_evidence import EvidenceArtifact, LearningEvidence
from app.schemas.learner_preferences import PreferenceUpdate, PreferenceValues
from app.schemas.lms import SubmissionCreate
from app.schemas.practice_representations import (
    PracticeRepresentationRequest,
    practice_representations,
)
from app.services.evidence.live import LiveEvidenceCapture, evidence_id
from app.services.learner_preferences import LearnerPreferenceService
from app.services.lms import LmsService
from app.services.practice_representations import (
    PracticeRepresentationService,
    practice_support_observations,
)
from app.services.task_review import TaskReviewError, TaskReviewService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def variant(identity, sources, **overrides):
    return dict(
        representation_id=identity,
        mode="text",
        title=identity,
        text="Check the equality case.",
        steps=[],
        circuit=None,
        source_references=sources,
        equivalence_basis="Synthetic reviewer rationale; same task response required.",
        support_kind="instructional",
        instructional_support_level=2,
        explanation_detail="brief",
        **overrides,
    )


@pytest.fixture
def context(db_session, content):
    lms, owner, learner, course, _, tasks = content
    for item in tasks:
        approve_sourced_fixture_task(db_session, db_session.get(LearningTask, item.id))
    task = db_session.get(LearningTask, tasks[0].id)
    task.marking_criteria = {
        **task.marking_criteria,
        "practice_representations": [
            variant("brief", task.source_references),
            {
                **variant("steps", task.source_references),
                "mode": "stepwise",
                "explanation_detail": "detailed",
                "steps": ["Compare with the boundary", "Trace the selected branch"],
                "instructional_support_level": 3,
            },
            {
                **variant("access", task.source_references),
                "support_kind": "accessibility",
                "instructional_support_level": 0,
            },
        ],
    }
    db_session.commit()
    approve_fixture_task(db_session, task)
    lms.set_course_state(owner, course.id, CourseState.PUBLISHED)
    db_session.add(Enrollment(student_id=learner.id, course_id=course.id))
    db_session.commit()
    return lms, owner, learner, task, PracticeRepresentationService(db_session)


def command(catalog, identity="brief", key="open", selection="preference"):
    return PracticeRepresentationRequest(
        revision_id=catalog.revision_id,
        representation_id=identity,
        preference_version=catalog.preference_version,
        request_key=key,
        selection=selection,
    )


def test_preferences_choose_actual_reviewed_content_and_keep_override(db_session, context):
    _, _, learner, task, service = context
    preferences = LearnerPreferenceService(db_session)
    preferences.save(
        learner,
        PreferenceUpdate(
            expected_version=0,
            request_key="preferences",
            values=PreferenceValues(
                format="stepwise", explanation_detail="detailed", support_amount="on_request"
            ),
        ),
    )
    catalog = service.catalog(learner, task.id)
    assert catalog.recommended_id == "steps" and catalog.on_request
    assert db_session.scalar(select(func.count()).select_from(LearningEvidence)) == 0
    assert "text" not in catalog.choices[0].model_dump()
    delivered = service.deliver(learner, task.id, command(catalog, "steps"))
    assert delivered.representation.steps == [
        "Compare with the boundary",
        "Trace the selected branch",
    ]
    override = service.deliver(learner, task.id, command(catalog, "brief", "override", "override"))
    assert service.catalog(learner, task.id).selected_id == "brief"
    assert service.catalog(learner, task.id).selection == "override"
    assert (
        service.deliver(learner, task.id, command(catalog, "brief", "override", "override"))
        == override
    )
    assert db_session.scalar(select(func.count()).select_from(LearningEvidence)) == 2
    assert db_session.scalar(select(func.count()).select_from(LearnerModelSnapshot)) == 0
    assert db_session.scalar(select(func.count()).select_from(AssessmentDecision)) == 0
    preferences.save(
        learner,
        PreferenceUpdate(
            expected_version=1,
            request_key="disable",
            values=PreferenceValues(
                personalisation_enabled=False, format="stepwise", explanation_detail="detailed"
            ),
        ),
    )
    assert service.catalog(learner, task.id).recommended_id == "brief"
    with pytest.raises(TaskReviewError, match="Preferences changed"):
        service.deliver(learner, task.id, command(catalog, "steps", "new-key"))


def test_delivery_retains_exact_revision_sources_and_support_on_response(db_session, context):
    lms, _, learner, task, service = context
    catalog = service.catalog(learner, task.id)
    when = datetime.now(UTC)
    instruction = service.deliver(
        learner, task.id, command(catalog, "steps", "instruction", "override")
    )
    access = service.deliver(learner, task.id, command(catalog, "access", "access", "override"))
    record = db_session.get(LearningEvidence, instruction.evidence_id)
    saved = json.loads(db_session.get(EvidenceArtifact, record.artifact_id).content)
    assert record.source_version == catalog.revision_id
    assert saved["receipt"]["review_event_id"] == catalog.review_event_id
    assert set(saved["source_approvals"]) == set(task.source_references)
    assert (
        practice_support_observations(db_session, task.id, learner.id, when - timedelta(seconds=1))
        == []
    )
    assert (
        practice_support_observations(db_session, task.id, learner.id + 100, datetime.now(UTC))
        == []
    )
    response = lms.submit(
        learner, task.id, SubmissionCreate(answer="cool", idempotency_key="response")
    )
    evidence = db_session.get(LearningEvidence, evidence_id(response.id, "response"))
    assert evidence.instructional_support_level == 3
    assert evidence.access_support_state == AccessSupportState.PROVIDED
    assert db_session.get(LearningEvidence, access.evidence_id).instructional_support_level == 0
    assert (
        LiveEvidenceCapture(db_session)._support_for(
            "unrelated-formal-work", datetime.now(UTC), task_id=task.id, student_id=learner.id
        )[0]
        == 0
    )


def test_changed_review_denies_replay_but_preserves_original_receipt(db_session, context):
    _, owner, learner, task, service = context
    catalog = service.catalog(learner, task.id)
    receipt = service.deliver(learner, task.id, command(catalog))
    with pytest.raises(TaskReviewError, match="request key"):
        service.deliver(learner, task.id, command(catalog, "access", selection="override"))
    task.instructions += " Reviewed revised instructions."
    db_session.commit()
    approve_fixture_task(db_session, task)
    with pytest.raises(TaskReviewError, match="reviewed task changed"):
        service.deliver(learner, task.id, command(catalog))
    assert (
        db_session.get(LearningEvidence, receipt.evidence_id).source_version == catalog.revision_id
    )
    assert practice_support_observations(db_session, task.id, learner.id, datetime.now(UTC)) == []
    current = service.catalog(learner, task.id)
    review = TaskReviewService(db_session)
    review.record(
        owner,
        task.id,
        expected_revision_id=current.revision_id,
        expected_review_version=review.latest_event(current.revision_id).version,
        state="WITHDRAWN",
        reason="Synthetic withdrawal",
    )
    with pytest.raises(TaskReviewError):
        service.deliver(learner, task.id, command(current, key="after-withdrawal"))


@pytest.mark.parametrize(
    "change",
    [
        {"support_kind": "accessibility", "instructional_support_level": 2},
        {
            "mode": "worked_example",
            "instructional_support_level": 0,
            "support_kind": "accessibility",
        },
        {"source_references": ["undeclared"]},
        {"equivalence_basis": " "},
        {"mode": "stepwise", "steps": []},
    ],
)
def test_review_rejects_false_access_or_missing_equivalence_and_sources(change):
    with pytest.raises(ValueError):
        practice_representations(
            {"practice_representations": [{**variant("one", ["source"]), **change}]}, ["source"]
        )


def test_existing_assessed_work_cannot_use_practice_route(db_session):
    learner, task, form, *_ = setup_work(db_session)
    lms = LmsService(db_session)
    lms.start_assessment_work(learner, task.id, form.id)
    with pytest.raises(TaskReviewError, match="approved support"):
        PracticeRepresentationService(db_session).catalog(learner, task.id)


def test_api_enforces_identity_csrf_and_delivery_only(db_session, context, monkeypatch):
    _, owner, learner, task, _ = context
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: learner
    monkeypatch.setattr(settings, "csrf_enabled", True)
    client = TestClient(app)
    path = f"/api/v1/practice-representations/tasks/{task.id}"
    try:
        listed = client.get(path)
        assert listed.status_code == 200 and listed.headers["cache-control"] == "no-store"
        payload = dict(
            revision_id=listed.json()["revision_id"],
            representation_id="brief",
            preference_version=0,
            request_key="api",
            selection="preference",
        )
        assert client.get(path + "?student_id=someone-else").status_code == 422
        client.cookies.set(settings.csrf_cookie_name, "synthetic-csrf")
        assert client.post(path + "/deliver", json=payload).status_code == 403
        headers = {settings.csrf_header_name: "synthetic-csrf", "Origin": settings.frontend_origin}
        result = client.post(path + "/deliver", json=payload, headers=headers)
        assert result.status_code == 200, result.text
        assert client.post(path + "/deliver", json=payload, headers=headers).json() == result.json()
        outsider = User(
            email="outsider@example.invalid",
            full_name="Synthetic outsider",
            role=UserRole.STUDENT,
            password_hash="unused",
        )
        db_session.add(outsider)
        db_session.commit()
        app.dependency_overrides[get_current_user] = lambda: outsider
        assert client.get(path).status_code == 403
        assert client.post(path + "/deliver", json=payload, headers=headers).status_code == 403
        app.dependency_overrides[get_current_user] = lambda: owner
        assert client.get(path).status_code == 403
    finally:
        client.close()
        app.dependency_overrides.clear()
