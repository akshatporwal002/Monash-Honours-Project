"""Synthetic policy and reviewer records exercise live BP9/BP11 gates only."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from support.assessment import assign_assessor
from test_task15_human_review import context, request_for

from app.core.config import settings
from app.domain.assessment import AssessmentResult, CriterionDecision, ResultState
from app.models.assessment import AssessmentDecision
from app.models.assessment_moderation import EvaluatorValidationEvent, ModerationReview
from app.models.lms import SystemSetting
from app.models.persistence import LearningTask
from app.models.user import User, UserRole
from app.services.assessment.access import ScopedRoleAccessDeniedError
from app.services.assessment.evaluator_release import EvaluatorReleaseService
from app.services.assessment.moderation import ModerationService
from app.services.assessment.review import (
    AssessmentReviewConflictError,
    AssessmentReviewValidationError,
)

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def reviewer(session, owner, course_id, suffix, role=UserRole.EDUCATOR):
    actor = User(
        email=f"moderator-{suffix}@example.test",
        password_hash="test-only",
        full_name=f"Reviewer {suffix}",
        role=role,
    )
    session.add(actor)
    session.commit()
    if role == UserRole.EDUCATOR:
        assign_assessor(session, actor, course_id, owner)
    return actor


def policy(session, actor, attempt, **overrides):
    values = dict(
        initial_count=2,
        later_percent=0,
        drift_interval=7,
        approval_reference="SYNTHETIC policy approval",
        training_reference="SYNTHETIC assessor calibration",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    values.update(overrides)
    row = ModerationService(session).configure(actor, attempt.course_id, **values)
    session.commit()
    return row


def record(
    session, service, actor, attempt, response, criterion, stage, decision=CriterionDecision.MET
):
    row = ModerationService(session).record(
        actor,
        attempt,
        stage,
        request_for(
            service, actor, attempt, response, criterion, decision, key=f"{stage}-{actor.id}"
        ),
        service,
    )
    session.commit()
    return row


def test_no_policy_is_explicit_and_preserves_unmoderated_human_path(db_session):
    attempt, response, criterion, actor, human, _ = context(db_session)
    assert ModerationService(db_session).queue(actor, attempt.course_id) == {
        "policy_status": "POLICY_REQUIRED",
        "records": [],
    }
    receipt = human.finalise(
        actor,
        assessment_attempt_id=attempt.id,
        request=request_for(human, actor, attempt, response, criterion),
    )
    assert receipt["result_state"] == "CONFIRMED"
    assert list(db_session.scalars(select(ModerationReview))) == []


@pytest.mark.parametrize(
    "initial,percent,interval,selected,drift",
    [
        (0, 0, 9, False, False),
        (2, 0, 9, True, False),
        (0, 100, 9, True, False),
        (0, 0, 1, True, True),
    ],
)
def test_only_explicit_policy_numbers_determine_durable_eligibility(
    db_session, initial, percent, interval, selected, drift
):
    attempt, _, _, actor, _, _ = context(db_session)
    policy(
        db_session,
        actor,
        attempt,
        initial_count=initial,
        later_percent=percent,
        drift_interval=interval,
    )
    service = ModerationService(db_session)
    sampled = service.select_attempt(attempt)
    db_session.commit()
    assert (sampled.selected, sampled.drift_check, sampled.sequence) == (selected, drift, 1)
    frozen_policy = sampled.policy_id
    policy(db_session, actor, attempt, initial_count=0, later_percent=0, drift_interval=999)
    assert service.select_attempt(attempt).policy_id == frozen_policy


def test_second_reviewer_and_explicit_resolution_block_every_confirmation(db_session):
    attempt, response, criterion, actor, human, _ = context(db_session)
    second = reviewer(db_session, actor, attempt.course_id, "second")
    third = reviewer(db_session, actor, attempt.course_id, "third")
    policy(db_session, actor, attempt)
    moderation = ModerationService(db_session)
    record(db_session, human, actor, attempt, response, criterion, "ORIGINAL")
    with pytest.raises(AssessmentReviewValidationError, match="different authorised"):
        record(db_session, human, actor, attempt, response, criterion, "SECOND")
    with pytest.raises(AssessmentReviewConflictError, match="SECOND_REQUIRED"):
        human.finalise(
            actor,
            assessment_attempt_id=attempt.id,
            request=request_for(human, actor, attempt, response, criterion),
        )
    assert db_session.scalar(select(AssessmentDecision)) is None
    record(
        db_session, human, second, attempt, response, criterion, "SECOND", CriterionDecision.NOT_MET
    )
    assert moderation.status(moderation.select_attempt(attempt))[0] == "DISAGREEMENT"
    with pytest.raises(AssessmentReviewConflictError, match="DISAGREEMENT"):
        human.finalise(
            actor,
            assessment_attempt_id=attempt.id,
            request=request_for(human, actor, attempt, response, criterion),
        )
    with pytest.raises(AssessmentReviewValidationError, match="third authorised"):
        record(db_session, human, second, attempt, response, criterion, "RESOLUTION")
    record(db_session, human, third, attempt, response, criterion, "RESOLUTION")
    with pytest.raises(AssessmentReviewConflictError, match="match the resolved"):
        human.finalise(
            actor,
            assessment_attempt_id=attempt.id,
            request=request_for(
                human, actor, attempt, response, criterion, CriterionDecision.NOT_MET
            ),
        )
    receipt = human.finalise(
        actor,
        assessment_attempt_id=attempt.id,
        request=request_for(human, actor, attempt, response, criterion),
    )
    assert receipt["result_state"] == ResultState.CONFIRMED.value
    assert receipt["result"] == AssessmentResult.PASS
    assert {row.stage for row in db_session.scalars(select(ModerationReview))} == {
        "ORIGINAL",
        "SECOND",
        "RESOLUTION",
    }


def test_agreement_drift_check_and_expired_policy_preserve_selected_requirements(
    db_session, monkeypatch
):
    attempt, response, criterion, actor, human, _ = context(db_session)
    second = reviewer(db_session, actor, attempt.course_id, "second")
    saved_policy = policy(db_session, actor, attempt, drift_interval=1)
    moderation = ModerationService(db_session)
    selection = moderation.select_attempt(attempt)
    db_session.commit()
    # Advance only the policy clock; approved immutable history remains untouched.
    import app.services.assessment.moderation as module

    real_datetime = datetime

    class Later:
        @staticmethod
        def now(zone):
            return real_datetime.now(zone) + timedelta(days=2)

    monkeypatch.setattr(module, "datetime", Later)
    queue = moderation.queue(actor, attempt.course_id)
    assert queue["policy_status"] == "POLICY_REQUIRED"
    assert queue["records"][0]["policy_id"] == saved_policy.id
    record(db_session, human, actor, attempt, response, criterion, "ORIGINAL")
    record(db_session, human, second, attempt, response, criterion, "SECOND")
    with pytest.raises(AssessmentReviewConflictError, match="DRIFT_REQUIRED"):
        moderation.require_ready(actor, attempt, AssessmentResult.PASS)
    record(db_session, human, second, attempt, response, criterion, "DRIFT")
    assert moderation.status(selection) == ("READY", "PASS")


def test_scope_stale_evidence_and_append_only_history(db_session):
    attempt, response, criterion, actor, human, reader = context(db_session)
    policy(db_session, actor, attempt)
    stranger = User(
        email="stranger@example.test",
        password_hash="test",
        full_name="Stranger",
        role=UserRole.EDUCATOR,
    )
    db_session.add(stranger)
    db_session.commit()
    with pytest.raises(ScopedRoleAccessDeniedError):
        ModerationService(db_session).queue(stranger, attempt.course_id)
    request = request_for(human, actor, attempt, response, criterion)
    with pytest.raises(AssessmentReviewConflictError):
        ModerationService(db_session).record(
            actor, attempt, "ORIGINAL", replace(request, expected_token="f" * 64), human
        )
    row = record(db_session, human, actor, attempt, response, criterion, "ORIGINAL")
    with pytest.raises(IntegrityError, match="append-only"):
        db_session.execute(
            text("UPDATE assessment_moderation_reviews SET reason = 'changed' WHERE id = :id"),
            {"id": row.id},
        )
    db_session.rollback()
    reader.stale = True
    with pytest.raises(AssessmentReviewConflictError):
        human.finalise(
            actor,
            assessment_attempt_id=attempt.id,
            request=request_for(human, actor, attempt, response, criterion),
        )


def evidence():
    return {
        **{
            key: f"SYNTHETIC {key} reference"
            for key in (
                "release_approval",
                "expert_review",
                "approved_cases",
                "human_agreement",
                "fairness_review",
                "revalidation_policy",
                "threshold_approval",
            )
        },
        "false_pass": 0.01,
        "max_false_pass": 0.02,
        "false_incomplete": 0.02,
        "max_false_incomplete": 0.03,
    }


def validated(session):
    attempt, response, criterion, owner, human, _ = context(session)
    admin = reviewer(session, owner, attempt.course_id, "admin", UserRole.ADMINISTRATOR)
    release = EvaluatorReleaseService(session)
    status = release.status(attempt.course_id)
    assert status["state"] == "PENDING" and status["ai_activation"] == "PENDING"
    row = release.validate(
        admin,
        attempt.course_id,
        expected_fingerprint=status["fingerprint"],
        evidence=evidence(),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    session.commit()
    return attempt, admin, release, row


@pytest.mark.parametrize("change", ["task", "configuration", "model", "retrieval"])
def test_material_changes_invalidate_and_require_fresh_approved_revalidation(
    db_session, monkeypatch, change
):
    attempt, admin, release, original = validated(db_session)
    old_fingerprint = original.fingerprint
    if change == "task":
        db_session.get(LearningTask, attempt.task_id).title = "Materially changed task"
        db_session.commit()
        assert release.latest(attempt.course_id).state == "INVALIDATED"
    elif change == "configuration":
        db_session.add(
            SystemSetting(
                key="assessment_prompt_version",
                value="changed",
                description="Synthetic material prompt change",
            )
        )
        db_session.commit()
        assert release.latest(attempt.course_id).state == "INVALIDATED"
    else:
        monkeypatch.setattr(
            settings,
            "llm_model" if change == "model" else "rag_default_top_k",
            "changed-model" if change == "model" else settings.rag_default_top_k + 1,
        )
    status = release.status(attempt.course_id)
    db_session.commit()
    assert status["state"] == "INVALIDATED" and status["ai_activation"] == "PENDING"
    assert db_session.get(EvaluatorValidationEvent, original.id).state == "VALIDATED"
    with pytest.raises(AssessmentReviewConflictError, match="repeat validation"):
        release.validate(
            admin,
            attempt.course_id,
            expected_fingerprint=old_fingerprint,
            evidence=evidence(),
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    revised = release.validate(
        admin,
        attempt.course_id,
        expected_fingerprint=status["fingerprint"],
        evidence=evidence(),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db_session.commit()
    assert revised.revision == 3
    assert release.status(attempt.course_id)["state"] == "VALIDATED"
    assert release.status(attempt.course_id)["ai_activation"] == "PENDING"


@pytest.mark.parametrize(
    "invalid", [{}, {**evidence(), "false_pass": 0.5}, {**evidence(), "threshold_approval": ""}]
)
def test_validation_never_invents_approvals_or_error_limits(db_session, invalid):
    attempt, _, _, actor, _, _ = context(db_session)
    admin = reviewer(db_session, actor, attempt.course_id, "admin", UserRole.ADMINISTRATOR)
    service = EvaluatorReleaseService(db_session)
    fingerprint = service.status(attempt.course_id)["fingerprint"]
    with pytest.raises(AssessmentReviewValidationError):
        service.validate(
            admin,
            attempt.course_id,
            expected_fingerprint=fingerprint,
            evidence=invalid,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    assert service.latest(attempt.course_id) is None


def test_unchanged_validation_and_repeated_invalidation_are_stable(db_session):
    attempt, _admin, release, original = validated(db_session)
    for _ in range(3):
        status = release.status(attempt.course_id)
        db_session.commit()
        assert status["fingerprint"] == original.fingerprint
        assert status["state"] == "VALIDATED"
    assert len(list(db_session.scalars(select(EvaluatorValidationEvent)))) == 1
    db_session.get(LearningTask, attempt.task_id).title = "New assessed prompt"
    db_session.commit()
    for _ in range(3):
        assert release.status(attempt.course_id)["state"] == "INVALIDATED"
        db_session.commit()
    assert len(list(db_session.scalars(select(EvaluatorValidationEvent)))) == 2


def test_drift_disagreement_has_a_resolution_path_and_invalidates_validation(db_session):
    attempt, response, criterion, owner, human, _ = context(db_session)
    second = reviewer(db_session, owner, attempt.course_id, "second")
    third = reviewer(db_session, owner, attempt.course_id, "third")
    admin = reviewer(db_session, owner, attempt.course_id, "admin", UserRole.ADMINISTRATOR)
    policy(db_session, owner, attempt, drift_interval=1)
    release = EvaluatorReleaseService(db_session)
    release.validate(
        admin,
        attempt.course_id,
        expected_fingerprint=release.status(attempt.course_id)["fingerprint"],
        evidence=evidence(),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db_session.commit()
    record(db_session, human, owner, attempt, response, criterion, "ORIGINAL")
    record(db_session, human, second, attempt, response, criterion, "SECOND")
    record(
        db_session, human, second, attempt, response, criterion, "DRIFT", CriterionDecision.NOT_MET
    )
    moderation = ModerationService(db_session)
    assert moderation.status(moderation.select_attempt(attempt))[0] == "DRIFT_DISAGREEMENT"
    assert release.status(attempt.course_id)["state"] == "INVALIDATED"
    with pytest.raises(AssessmentReviewConflictError, match="DRIFT_DISAGREEMENT"):
        moderation.require_ready(owner, attempt, AssessmentResult.PASS)
    record(db_session, human, third, attempt, response, criterion, "DRIFT_RESOLUTION")
    assert moderation.status(moderation.select_attempt(attempt)) == ("READY", "PASS")
    assert release.status(attempt.course_id)["state"] == "INVALIDATED"


def test_existing_provisional_review_actions_cannot_bypass_sampling(db_session):
    from support.assessment import build_provisional_decision

    from app.domain.assessment import AssessorReviewAction
    from app.services.assessment.access import RoleAssignmentService
    from app.services.assessment.review import (
        AssessmentReviewActionRequest,
        AssessmentReviewService,
    )

    attempt, _, _, owner, _, _ = context(db_session)
    decision = build_provisional_decision(db_session, attempt)
    db_session.commit()
    policy(db_session, owner, attempt)
    service = AssessmentReviewService(db_session, assignments=RoleAssignmentService(db_session))
    for action in (AssessorReviewAction.CONFIRM, AssessorReviewAction.OVERRIDE):
        with pytest.raises(AssessmentReviewConflictError, match="ORIGINAL_REQUIRED"):
            service.act(
                owner,
                decision_id=decision.id,
                request=AssessmentReviewActionRequest(
                    action=action,
                    reason="Reviewed",
                    expected_result_state=ResultState.PROVISIONAL,
                    expected_review_revision=0,
                    new_result=AssessmentResult.INCOMPLETE
                    if action == AssessorReviewAction.OVERRIDE
                    else None,
                ),
            )
        db_session.rollback()
    assert db_session.get(AssessmentDecision, decision.id).result_state == ResultState.PROVISIONAL


def test_routes_enforce_scoped_reviewer_and_admin_release_roles(db_session):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.dependencies.authentication import get_current_user
    from app.api.routes.assessment import get_human_assessment_service
    from app.api.routes.assessment_moderation import router
    from app.db.session import get_db

    attempt, response, criterion, actor, human, _ = context(db_session)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[get_human_assessment_service] = lambda: human
    client = TestClient(app)
    base = f"/assessment/courses/{attempt.course_id}"
    assert client.get(base + "/moderation").json()["policy_status"] == "POLICY_REQUIRED"
    policy(db_session, actor, attempt)
    from dataclasses import asdict

    payload = asdict(request_for(human, actor, attempt, response, criterion))
    invalid_payload = {
        **payload,
        "criteria": [{**payload["criteria"][0], "evidence_ids": ["foreign-evidence"]}],
    }
    assert (
        client.post(
            f"/assessment/attempts/{attempt.id}/moderation/ORIGINAL", json=invalid_payload
        ).status_code
        == 409
    )
    assert list(db_session.scalars(select(ModerationReview))) == []
    first = client.post(f"/assessment/attempts/{attempt.id}/moderation/ORIGINAL", json=payload)
    assert first.status_code == 200
    assert (
        client.post(f"/assessment/attempts/{attempt.id}/moderation/ORIGINAL", json=payload).json()
        == first.json()
    )
    assert (
        client.post(
            f"/assessment/attempts/{attempt.id}/moderation/SECOND",
            json={**payload, "idempotency_key": "independent-second-attempt"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            base + "/evaluator-validation",
            json={
                "expected_fingerprint": "a" * 64,
                "evidence": evidence(),
                "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            },
        ).status_code
        == 403
    )
    actor.is_active = False
    db_session.commit()
    assert client.get(base + "/moderation").status_code == 403
    assert client.get(base + "/evaluator-validation").status_code == 403


def test_forward_migration_preserves_history_and_live_submission_sampling(tmp_path):
    from alembic import command
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from test_migrations import migration_config
    from test_task14_lifecycle import complete, setup_episode

    from app.models.assessment import AssessmentAttempt
    from app.models.assessment_moderation import ModerationSelection
    from app.models.lms import Course
    from app.schemas.lms import SubmissionCreate
    from scripts.verify_sqlite_backup import database_manifest

    path = tmp_path / "m.db"
    url = f"sqlite:///{path.as_posix()}"
    config = migration_config(url)
    command.upgrade(config, "20260910_0046")
    engine = create_engine(url)
    with Session(engine) as session:
        # Populate pre-migration protected records, then compare exact row counts.
        from support.assessment import build_assessment_attempt

        old_attempt, _, _, _, _ = build_assessment_attempt(session)
        session.commit()
        old_id = old_attempt.id
        old_course_id = old_attempt.course_id
    before = database_manifest(path)
    command.upgrade(config, "20260911_0049")
    after = database_manifest(path)
    assert all(after[key] == value for key, value in before.items() if key != "alembic_version")
    with Session(engine) as session:
        from support.assessment import assign_assessor

        owner = session.get(User, session.get(Course, old_course_id).educator_id)
        assign_assessor(session, owner, old_course_id, owner)
        ModerationService(session).configure(
            owner,
            old_course_id,
            initial_count=1,
            later_percent=100,
            drift_interval=3,
            approval_reference="SYNTHETIC historical migration policy",
            training_reference="SYNTHETIC training",
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        session.commit()
    populated = database_manifest(path)
    with pytest.raises(RuntimeError, match="populated"):
        command.downgrade(config, "20260910_0046")
    assert database_manifest(path) == populated

    # Today's publication and scanner runtime requires the complete current schema.
    command.upgrade(config, "head")
    with Session(engine) as session:
        assert (
            session.execute(text("SELECT count(*) FROM assessment_attempts")).scalar_one()
            == before["assessment_attempts"].row_count
        )
        assert session.get(AssessmentAttempt, old_id)
        lms, student, task, started = setup_episode(session)
        owner = session.get(User, session.get(Course, task.course_id).educator_id)
        ModerationService(session).configure(
            owner,
            task.course_id,
            initial_count=1,
            later_percent=100,
            drift_interval=3,
            approval_reference="SYNTHETIC migration policy",
            training_reference="SYNTHETIC training",
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        session.commit()
        payload = complete(lms, student, task, started)
        submission = lms.submit(
            student,
            task.id,
            SubmissionCreate(**payload.model_dump(), idempotency_key="moderated-live-submission"),
        )
        attempt = session.scalar(
            select(AssessmentAttempt).where(AssessmentAttempt.response_version_id == submission.id)
        )
        selection = session.get(ModerationSelection, attempt.id)
        assert selection and selection.selected
        assert (
            session.scalar(
                select(AssessmentDecision).where(
                    AssessmentDecision.assessment_attempt_id == attempt.id
                )
            )
            is None
        )
        with pytest.raises(IntegrityError, match="append-only"):
            session.execute(
                text("DELETE FROM assessment_moderation_selections WHERE attempt_id = :id"),
                {"id": attempt.id},
            )
        session.rollback()
    populated_head = database_manifest(path)
    with pytest.raises(RuntimeError, match="Intake history is protected"):
        command.downgrade(config, "20260910_0046")
    assert database_manifest(path) == populated_head
    engine.dispose()


@pytest.mark.parametrize("kind", ["revision", "passage", "approval"])
def test_exact_source_history_changes_invalidate_validation(db_session, kind):
    from uuid import uuid4

    from app.models.source_history import SourceApproval, SourcePassage, SourceRevision

    attempt, _, release, original = validated(db_session)
    model = {"revision": SourceRevision, "passage": SourcePassage, "approval": SourceApproval}[kind]
    source = db_session.scalars(select(model)).first()
    assert source is not None
    values = {column.name: getattr(source, column.name) for column in model.__table__.columns}
    values["id"] = str(uuid4())
    if kind == "revision":
        values["version"] += 1
    elif kind == "passage":
        values["chunk_index"] += 100
        values["chunk_text"] = "A new approved-source passage requires revalidation"
    else:
        values["sequence"] += 1
        values["state"] = "REVOKED"
    db_session.add(model(**values))
    db_session.commit()
    invalidated = release.latest(attempt.course_id)
    assert invalidated.state == "INVALIDATED"
    assert "source" in invalidated.evidence["changed_dependencies"]
    assert db_session.get(EvaluatorValidationEvent, original.id).state == "VALIDATED"


def test_later_policy_does_not_relabel_or_block_preexisting_human_corrections(db_session):
    attempt, response, criterion, actor, human, _ = context(db_session)
    human.finalise(
        actor,
        assessment_attempt_id=attempt.id,
        request=request_for(human, actor, attempt, response, criterion),
    )
    policy(db_session, actor, attempt)
    receipt = human.finalise(
        actor,
        assessment_attempt_id=attempt.id,
        request=request_for(
            human,
            actor,
            attempt,
            response,
            criterion,
            CriterionDecision.NOT_MET,
            key="later-correction",
        ),
    )
    assert receipt["result_state"] == "OVERRIDDEN"
    assert ModerationService(db_session).queue(actor, attempt.course_id)["records"] == []


def test_validation_expiry_is_durable_and_cannot_reactivate_ai(db_session, monkeypatch):
    import app.services.assessment.evaluator_release as module

    attempt, _, release, original = validated(db_session)

    class Later:
        @staticmethod
        def now(zone):
            return datetime.now(zone) + timedelta(days=2)

    monkeypatch.setattr(module, "datetime", Later)
    status = release.status(attempt.course_id)
    db_session.commit()
    assert status["state"] == "INVALIDATED" and status["reason"] == "Validation expired"
    assert status["ai_activation"] == "PENDING"
    assert release.latest(attempt.course_id).evidence["prior_validation_id"] == original.id


def test_upload_mount_relocation_preserves_validation_but_retrieval_policy_does_not(
    db_session, monkeypatch
):
    attempt, _, release, original = validated(db_session)
    for location in ("D:/relocated/uploads", "/srv/learnlens/uploads"):
        monkeypatch.setattr(settings, "rag_upload_dir", location)
        status = release.status(attempt.course_id)
        db_session.commit()
        assert status["fingerprint"] == original.fingerprint
        assert status["state"] == "VALIDATED"
        assert status["validation_id"] == original.id
    assert len(list(db_session.scalars(select(EvaluatorValidationEvent)))) == 1

    monkeypatch.setattr(settings, "rag_default_top_k", settings.rag_default_top_k + 1)
    status = release.status(attempt.course_id)
    db_session.commit()
    assert status["fingerprint"] != original.fingerprint
    assert status["state"] == "INVALIDATED"
    assert release.latest(attempt.course_id).evidence["changed_dependencies"] == [
        "retrieval_settings"
    ]
