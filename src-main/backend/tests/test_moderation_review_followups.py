"""Focused regressions from review of the live moderation delivery."""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from test_live_assessment_moderation import context, evidence, policy, record, reviewer
from test_task15_human_review import request_for
from test_task15_migrated_review import migrated  # noqa: F401

from app.api.dependencies.authentication import get_current_user
from app.api.routes.assessment import get_human_assessment_service
from app.api.routes.assessment import router as assessment_router
from app.api.routes.assessment_moderation import router
from app.db.session import get_db
from app.domain.assessment import AssessmentResult, CriterionDecision
from app.models.assessment import AssessmentDecision
from app.models.assessment_moderation import ModerationPolicy, ModerationReview
from app.models.lms import PlatformAuditEvent
from app.models.user import UserRole
from app.services.assessment.moderation import ModerationService
from app.services.assessment.review import (
    AssessmentReviewConflictError,
    AssessmentReviewValidationError,
)

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def client_for(session, actors, human):
    app = FastAPI()
    app.include_router(router)
    app.include_router(assessment_router)
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: actors[0]
    app.dependency_overrides[get_human_assessment_service] = lambda: human

    @app.middleware("http")
    async def correlate(request, call_next):
        request.state.correlation_id = request.headers.get("X-Correlation-ID", str(uuid4()))
        return await call_next(request)

    return TestClient(app)


def test_sampled_confirmed_results_support_repeated_independent_correction_cycles(request):
    session, _config = request.getfixturevalue("migrated")
    from test_task15_migrated_review import request as frozen_request
    from test_task15_migrated_review import setup_human

    human, owner, attempt, _ = setup_human(session)

    def decision_request(actor, judgement, key):
        return frozen_request(human, actor, attempt.id, key=key, decision=judgement)

    second = reviewer(session, owner, attempt.course_id, "second")
    policy(session, owner, attempt)
    moderation = ModerationService(session)
    for stage, actor in (("ORIGINAL", owner), ("SECOND", second)):
        moderation.record(
            actor, attempt, stage, decision_request(actor, CriterionDecision.NOT_MET, stage), human
        )
        session.commit()
    first = human.finalise(
        owner,
        assessment_attempt_id=attempt.id,
        request=decision_request(owner, CriterionDecision.NOT_MET, "first-confirmation"),
    )
    assert first["result_state"] == "CONFIRMED" and first["result"] == AssessmentResult.INCOMPLETE

    moderation = ModerationService(session)
    for cycle, judgement, expected in (
        (2, CriterionDecision.MET, AssessmentResult.PASS),
        (3, CriterionDecision.NOT_MET, AssessmentResult.INCOMPLETE),
    ):
        original_result = session.get(AssessmentDecision, first["decision_id"]).result
        proposed = decision_request(owner, judgement, f"correction-{cycle}")
        saved = moderation.record(owner, attempt, "CORRECTION", proposed, human)
        session.commit()
        assert saved.cycle == cycle and saved.stage == "ORIGINAL"
        assert moderation.record(owner, attempt, "CORRECTION", proposed, human).id == saved.id
        with pytest.raises(AssessmentReviewConflictError, match="SECOND_REQUIRED"):
            human.finalise(
                owner,
                assessment_attempt_id=attempt.id,
                request=decision_request(owner, judgement, f"confirm-{cycle}"),
            )
        assert session.get(AssessmentDecision, first["decision_id"]).result == original_result
        moderation.record(
            second,
            attempt,
            "SECOND",
            decision_request(second, judgement, f"second-{cycle}"),
            human,
        )
        session.commit()
        corrected = human.finalise(
            owner,
            assessment_attempt_id=attempt.id,
            request=decision_request(owner, judgement, f"confirm-{cycle}"),
        )
        assert corrected["result_state"] == "OVERRIDDEN" and corrected["result"] == expected
    assert [
        (row.cycle, row.stage)
        for row in session.scalars(
            select(ModerationReview).order_by(ModerationReview.cycle, ModerationReview.stage)
        )
    ] == [
        (1, "ORIGINAL"),
        (1, "SECOND"),
        (2, "ORIGINAL"),
        (2, "SECOND"),
        (3, "ORIGINAL"),
        (3, "SECOND"),
    ]


def test_prospective_second_reviewer_receives_no_prior_judgements_until_commit(db_session):
    attempt, response, criterion, owner, human, _ = context(db_session)
    second = reviewer(db_session, owner, attempt.course_id, "second")
    policy(db_session, owner, attempt)
    record(db_session, human, owner, attempt, response, criterion, "ORIGINAL")
    client = client_for(db_session, [second], human)
    queue = client.get(f"/assessment/courses/{attempt.course_id}/moderation")
    assert queue.status_code == 200
    row = queue.json()["records"][0]
    assert row["history_withheld"] is True and row["history"] == [] and row["result"] is None
    detail = client.get(f"/assessment/attempts/{attempt.id}/human-review").json()
    assert detail["history"] == []
    assert all(
        entry["decision"] is None and entry["reason"] is None for entry in detail["criteria"]
    )
    assert detail["response"] and detail["criteria"][0]["approved_anchors"]
    receipt = client.post(
        f"/assessment/attempts/{attempt.id}/moderation/SECOND",
        json=asdict(
            request_for(human, second, attempt, response, criterion, key="independent-second")
        ),
    )
    assert receipt.status_code == 200
    row = client.get(f"/assessment/courses/{attempt.course_id}/moderation").json()["records"][0]
    assert row["history_withheld"] is False
    assert {entry["stage"] for entry in row["history"]} == {"ORIGINAL", "SECOND"}


def test_drift_reviewer_cannot_resolve_their_own_disagreement(db_session):
    attempt, response, criterion, owner, human, _ = context(db_session)
    second = reviewer(db_session, owner, attempt.course_id, "second")
    drift = reviewer(db_session, owner, attempt.course_id, "drift")
    resolver = reviewer(db_session, owner, attempt.course_id, "resolver")
    policy(db_session, owner, attempt, drift_interval=1)
    record(db_session, human, owner, attempt, response, criterion, "ORIGINAL")
    record(db_session, human, second, attempt, response, criterion, "SECOND")
    record(
        db_session, human, drift, attempt, response, criterion, "DRIFT", CriterionDecision.NOT_MET
    )
    moderation = ModerationService(db_session)
    assert moderation.queue(drift, attempt.course_id)["records"][0]["next_stage"] is None
    with pytest.raises(AssessmentReviewValidationError, match="outside the disagreement"):
        record(db_session, human, drift, attempt, response, criterion, "DRIFT_RESOLUTION")
    record(db_session, human, resolver, attempt, response, criterion, "DRIFT_RESOLUTION")
    assert moderation.status(moderation.select_attempt(attempt)) == ("READY", "PASS")


def test_correlated_governance_audits_are_atomic_and_responses_are_typed(db_session):
    attempt, response, criterion, owner, human, _ = context(db_session)
    actors = [owner]
    client = client_for(db_session, actors, human)
    base = f"/assessment/courses/{attempt.course_id}"
    cid = str(uuid4())
    headers = {"X-Correlation-ID": cid}
    payload = dict(
        initial_count=1,
        later_percent=0,
        drift_interval=7,
        approval_reference="SYNTHETIC approval",
        training_reference="SYNTHETIC training",
        expires_at=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
    )
    assert (
        client.post(base + "/moderation-policy", json=payload, headers=headers).status_code == 200
    )
    review = client.post(
        f"/assessment/attempts/{attempt.id}/moderation/ORIGINAL",
        json=asdict(request_for(human, owner, attempt, response, criterion)),
        headers=headers,
    )
    assert review.status_code == 200
    status = client.get(base + "/evaluator-validation", headers=headers).json()
    actors[0] = reviewer(db_session, owner, attempt.course_id, "admin", UserRole.ADMINISTRATOR)
    assert (
        client.post(
            base + "/evaluator-validation",
            json={
                "expected_fingerprint": status["fingerprint"],
                "evidence": evidence(),
                "expires_at": payload["expires_at"],
            },
            headers=headers,
        ).status_code
        == 200
    )
    events = list(
        db_session.scalars(
            select(PlatformAuditEvent).where(PlatformAuditEvent.correlation_id == cid)
        )
    )
    assert {event.action for event in events} == {
        "assessment_moderation.policy_recorded",
        "assessment_moderation.review_recorded",
        "assessment_evaluator.validated",
    }
    for event in events:
        assert event.occurred_at and event.outcome == "success" and event.actor_id
        assert event.details["result"]
    assert (
        next(event for event in events if event.action.endswith("review_recorded")).details[
            "pass_rule_version_id"
        ]
        == attempt.pass_rule_version_id
    )
    assert (
        "model_version"
        in next(event for event in events if event.action.endswith("validated")).details
    )
    actors[0] = owner
    db_session.execute(
        text(
            "CREATE TRIGGER reject_test_policy_audit BEFORE INSERT ON platform_audit_events WHEN NEW.action = 'assessment_moderation.policy_recorded' BEGIN SELECT RAISE(ABORT, 'synthetic audit failure'); END"
        )
    )
    db_session.commit()
    assert (
        client.post(base + "/moderation-policy", json=payload, headers=headers).status_code == 409
    )
    assert len(list(db_session.scalars(select(ModerationPolicy)))) == 1
    schema = client.get("/openapi.json").json()
    for path, method, expected in (
        ("/assessment/courses/{course_id}/moderation", "get", "ModerationQueueRead"),
        ("/assessment/courses/{course_id}/moderation-policy", "post", "ModerationPolicyReceipt"),
        ("/assessment/attempts/{attempt_id}/moderation/{stage}", "post", "ModerationReviewReceipt"),
        (
            "/assessment/courses/{course_id}/evaluator-validation",
            "get",
            "EvaluatorValidationStatusRead",
        ),
        (
            "/assessment/courses/{course_id}/evaluator-validation",
            "post",
            "EvaluatorValidationReceipt",
        ),
    ):
        assert schema["paths"][path][method]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]["$ref"].endswith("/" + expected)
