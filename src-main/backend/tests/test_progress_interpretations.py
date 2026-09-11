"""Synthetic scoped associations and human-reviewed, versioned interpretations."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from test_evidence_repository import _seed_scope
from test_learner_model import _service, _store_evidence, _update_command

from app.domain.platform_enums import EvidenceType
from app.models.learner_model import LearnerModelSnapshot
from app.models.lms import Course, Enrollment, EnrollmentStatus, PlatformAuditEvent
from app.models.persistence import LearningTask
from app.models.user import User
from app.schemas.progress import ProfileReviewRequest
from app.services.evidence.live import LiveEvidenceCapture
from app.services.learner_model.profile_reviews import review_profile
from app.services.learning_progress import LearningProgressService
from app.services.progress_indicators import indicators


def setup(session):
    scope = _seed_scope(session)
    course = session.get(Course, scope["course_one"])
    owner = session.get(User, course.educator_id)
    learner = session.get(User, int(scope["learner_id"]))
    session.add(Enrollment(course_id=course.id, student_id=learner.id))
    session.commit()
    return scope, owner, learner


def request(evidence_id="reasoning", **changes):
    values = dict(
        expected_version=0,
        dimension="SUCCESSFUL_STRATEGY",
        status="UNCERTAIN",
        uncertainty=0.6,
        reason="Self-explanation connected the stated observation to the claim.",
        evidence=[{"evidence_id": evidence_id, "relation": "SUPPORTS"}],
        idempotency_key="review-1",
    )
    values.update(changes)
    return ProfileReviewRequest(**values)


def save(session, scope, owner, payload):
    return review_profile(
        session,
        owner,
        scope["course_one"],
        int(scope["learner_id"]),
        scope["outcome_one"],
        payload,
        "synthetic-review-correlation",
    )


def test_review_is_reachable_versioned_idempotent_and_retained_by_rules(db_session):
    scope, owner, learner = setup(db_session)
    _store_evidence(
        db_session, scope, evidence_id="reasoning", evidence_type=EvidenceType.REASONING
    )
    payload = request()
    first = save(db_session, scope, owner, payload)
    assert first.version == 1 and first.created
    assert save(db_session, scope, owner, payload).created is False
    assert (
        len(
            list(
                db_session.scalars(
                    select(PlatformAuditEvent).where(
                        PlatformAuditEvent.action == "learner_profile.reviewed"
                    )
                )
            )
        )
        == 1
    )
    with pytest.raises(HTTPException) as reused:
        save(
            db_session,
            scope,
            owner,
            payload.model_copy(
                update={"reason": "A different interpretation of the same observation."}
            ),
        )
    assert reused.value.status_code == 409
    db_session.rollback()
    with pytest.raises(HTTPException) as stale:
        save(db_session, scope, owner, request(idempotency_key="stale"))
    assert stale.value.status_code == 409
    db_session.rollback()
    _store_evidence(
        db_session, scope, evidence_id="prediction", evidence_type=EvidenceType.PREDICTION
    )
    update = _service(db_session).update(
        _update_command(scope, tuple(request("prediction").evidence))
    )
    assert update.snapshot.created and update.view.record_version == 2
    dimensions = {item.dimension.value: item for item in update.view.estimates}
    assert "SUCCESSFUL_STRATEGY" in dimensions and "PRIOR_KNOWLEDGE" in dimensions
    assert "REASONING_STRENGTH" not in dimensions  # Human strategy relation is not rule evidence.
    assert dimensions["SUCCESSFUL_STRATEGY"].uncertainty == 0.6
    assert update.view.occurred_at >= db_session.get(
        LearnerModelSnapshot, first.snapshot_id
    ).occurred_at.replace(tzinfo=UTC)
    page = LearningProgressService(db_session).read(owner, scope["course_one"])
    selected = next(item for item in page.items if item.learner_id == learner.id)
    assert selected.snapshot_version == 2
    assert any(item.reason == payload.reason for item in selected.estimates)


def test_review_denies_learner_foreign_evidence_and_withdrawn_enrolment(db_session):
    scope, owner, learner = setup(db_session)
    _store_evidence(
        db_session, scope, evidence_id="reasoning", evidence_type=EvidenceType.REASONING
    )
    with pytest.raises(HTTPException):
        save(db_session, scope, learner, request())
    with pytest.raises(HTTPException):
        save(db_session, scope, owner, request("missing"))
    db_session.rollback()
    enrolment = db_session.scalar(select(Enrollment))
    enrolment.status = EnrollmentStatus.WITHDRAWN
    db_session.commit()
    with pytest.raises(HTTPException):
        save(db_session, scope, owner, request())
    assert list(db_session.scalars(select(LearnerModelSnapshot))) == []


def test_indicators_require_exact_lineage_time_and_scoped_original_text(db_session):
    scope, _, learner = setup(db_session)
    task = db_session.get(LearningTask, scope["task_one"])
    capture = LiveEvidenceCapture(db_session)
    now = datetime.now(UTC) - timedelta(hours=1)

    def emit(source, kind, offset, parents=(), value=None):
        return capture._write(
            task=task,
            learner_id=learner.id,
            source=source,
            field="synthetic",
            kind=kind,
            value=value or {},
            occurred_at=now + timedelta(minutes=offset),
            parents=parents,
        )

    original = emit("first", EvidenceType.RESPONSE, 0)
    ack = emit("ack", EvidenceType.FEEDBACK_INTERACTION, 1, (original,))
    revised = emit("revision", EvidenceType.REVISION, 2, (original,))
    transfer = emit("transfer", EvidenceType.TRANSFER, 3, (revised,))
    emit("unlinked", EvidenceType.REVISION, 4)
    emit("too-early", EvidenceType.TRANSFER, 0, (original,))
    clarification = emit(
        "clarification",
        EvidenceType.SCAFFOLD,
        5,
        value={"message": "The question wording is unclear to me."},
    )
    emit(
        "answer-not-question",
        EvidenceType.SCAFFOLD,
        6,
        value={"message": "I do not know the answer."},
    )
    db_session.commit()
    result, truncated = indicators(
        db_session, scope["course_one"], learner.id, scope["outcome_one"]
    )
    assert not truncated
    assert {item.kind for item in result} == {
        "feedback_revision",
        "feedback_transfer",
        "question_clarification",
    }
    assert len(result) == 3 and all(item.uncertainty == 1 for item in result)
    assert next(item for item in result if item.kind == "feedback_revision").evidence_ids == [
        ack,
        original,
        revised,
    ]
    assert next(item for item in result if item.kind == "feedback_transfer").evidence_ids == [
        ack,
        original,
        transfer,
    ]
    assert next(item for item in result if item.kind == "question_clarification").evidence_ids == [
        clarification
    ]
    assert indicators(db_session, scope["course_two"], learner.id, scope["outcome_one"])[0] == []
    assert indicators(db_session, scope["course_one"], learner.id, scope["outcome_one"], limit=2)[1]


def test_profile_review_rejects_trait_claims_and_duplicate_links():
    with pytest.raises(ValueError, match="banned trait"):
        request(reason="This shows a fixed learning style.")
    with pytest.raises(ValueError, match="distinct"):
        request(evidence=[{"evidence_id": "same", "relation": "SUPPORTS"}] * 2)


def test_profile_dimension_migration_preserves_populated_history_and_replays(tmp_path):
    from alembic import command
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session
    from test_migrations import migration_config

    from scripts.verify_sqlite_backup import database_manifest

    path = tmp_path / "profiles.db"
    config = migration_config(f"sqlite:///{path.as_posix()}")
    command.upgrade(config, "20260911_0051")
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    with Session(engine) as session:
        from support.assessment import build_assessment_attempt

        attempt, _, _, _, owner = build_assessment_attempt(session)
        scope = {
            "course_one": attempt.course_id,
            "learner_id": str(attempt.student_id),
            "actor_reference": str(attempt.student_id),
            "outcome_one": session.get(LearningTask, attempt.task_id).learning_outcome_id,
            "task_one": attempt.task_id,
        }
        session.add(Enrollment(course_id=attempt.course_id, student_id=attempt.student_id))
        session.commit()
        owner_id = owner.id
        _store_evidence(
            session, scope, evidence_id="reasoning", evidence_type=EvidenceType.REASONING
        )
        save(session, scope, owner, request(dimension="FEEDBACK_USE"))
    before = database_manifest(path)
    command.upgrade(config, "20260911_0052")
    after = database_manifest(path)
    assert (
        next(
            column["type"].length
            for column in inspect(engine).get_columns("learner_outcome_estimates")
            if column["name"] == "dimension"
        )
        == 23
    )
    assert all(after[key] == value for key, value in before.items() if key != "alembic_version")
    with Session(engine) as session:
        owner = session.get(User, owner_id)
        save(session, scope, owner, request(expected_version=1, idempotency_key="after-upgrade"))
    populated = database_manifest(path)
    command.stamp(config, "20260911_0051")
    command.upgrade(config, "20260911_0052")
    assert database_manifest(path) == populated
    with pytest.raises(RuntimeError, match="history is protected"):
        command.downgrade(config, "20260911_0051")
    assert database_manifest(path) == populated
    with engine.begin() as connection:
        with pytest.raises(IntegrityError, match="append-only"):
            connection.execute(text("UPDATE learner_outcome_estimates SET uncertainty=0"))
    engine.dispose()


def test_profile_review_http_requires_csrf_and_educator_and_publishes_receipt(
    db_session, monkeypatch
):
    from fastapi.testclient import TestClient

    from app.api.dependencies.authentication import get_current_user
    from app.core.config import settings
    from app.db.session import get_db
    from app.main import create_app

    scope, owner, learner = setup(db_session)
    _store_evidence(
        db_session, scope, evidence_id="reasoning", evidence_type=EvidenceType.REASONING
    )
    monkeypatch.setattr(settings, "csrf_enabled", True)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: owner
    path = f"/api/v1/progress/{scope['course_one']}/learners/{learner.id}/outcomes/{scope['outcome_one']}/reviews"
    with TestClient(app) as client:
        payload = request().model_dump(mode="json")
        client.cookies.set(settings.csrf_cookie_name, "profile-csrf")
        assert client.post(path, json=payload).status_code == 403
        client.cookies.set(settings.csrf_cookie_name, "profile-csrf")
        headers = {
            settings.csrf_header_name: "profile-csrf",
            "Origin": settings.allowed_cors_origins[0],
            "X-Correlation-ID": "profile-review-http",
        }
        result = client.post(path, json=payload, headers=headers)
        assert result.status_code == 200, result.text
        assert result.headers["Cache-Control"] == "no-store"
        assert result.json()["created"] is True
        assert client.post(path, json=payload, headers=headers).json()["created"] is False
        app.dependency_overrides[get_current_user] = lambda: learner
        assert client.post(path, json=payload, headers=headers).status_code == 403


def test_supported_feedback_interpretation_requires_linked_revision(db_session):
    scope, owner, _ = setup(db_session)
    _store_evidence(
        db_session, scope, evidence_id="reasoning", evidence_type=EvidenceType.FEEDBACK_INTERACTION
    )
    with pytest.raises(HTTPException) as error:
        save(db_session, scope, owner, request(dimension="FEEDBACK_USE", status="SUPPORTED"))
    assert error.value.status_code == 422
    assert list(db_session.scalars(select(LearnerModelSnapshot))) == []
