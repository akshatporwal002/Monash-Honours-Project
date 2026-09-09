"""Real persistence, ownership, concurrency and task policy for explicit choices."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from test_lms_core_api import lms_context as lms_context
from test_lms_core_api import login

from app.models.learner_preferences import LearnerPreferenceRevision
from app.models.user import User, UserRole
from app.schemas.learner_preferences import (
    PreferenceRead,
    PreferenceReset,
    PreferenceUpdate,
    PreferenceValues,
)
from app.services.learner_preferences import (
    LearnerPreferenceService,
    PreferenceConflict,
    PreferenceUnavailable,
    effective_preferences,
)


def learner(session, email="preferences@example.test", role=UserRole.STUDENT):
    actor = User(email=email, full_name="Preference fixture", password_hash="unused", role=role)
    session.add(actor)
    session.commit()
    return actor


def command(version=0, key="save-1", **values):
    return PreferenceUpdate(
        expected_version=version, request_key=key, values=PreferenceValues(**values)
    )


def test_choices_restore_in_new_session_and_reset_keeps_history(db_session):
    actor = learner(db_session)
    service = LearnerPreferenceService(db_session)
    assert service.read(actor).version == 0
    first = service.save(
        actor,
        command(
            pace="stepwise",
            format="stepwise",
            explanation_detail="detailed",
            breaks=True,
            repeat_practice=True,
            support_amount="on_request",
            feedback_form="expandable",
        ),
    )
    assert (
        service.save(
            actor,
            command(
                pace="stepwise",
                format="stepwise",
                explanation_detail="detailed",
                breaks=True,
                repeat_practice=True,
                support_amount="on_request",
                feedback_form="expandable",
            ),
        )
        == first
    )
    with Session(db_session.get_bind()) as other:
        restored = LearnerPreferenceService(other).read(other.get(User, actor.id))
        assert restored == first
    service.save(actor, command(1, "opt-out", personalisation_enabled=False))
    result = service.save(actor, PreferenceReset(expected_version=2, request_key="reset"))
    assert result.values == PreferenceValues()
    assert service.history(actor).items[-1].values == first.values
    assert [item.action for item in service.history(actor).items] == ["reset", "save", "save"]
    assert service.history(actor, limit=1).next_offset == 1
    assert service.history(actor, offset=1, limit=2).next_offset is None
    with pytest.raises(ValueError):
        service.history(actor, limit=0)


@pytest.mark.parametrize(
    "values",
    [
        {"diagnosis": "x"},
        {"learner_id": 10},
        {"format": "audio"},
        {"breaks": "true"},
        {"pace": "fast learner"},
    ],
)
def test_unknown_sensitive_and_invalid_fields_rejected(values):
    with pytest.raises(ValidationError):
        PreferenceValues(**values)


def test_scope_and_stale_writes(db_session):
    first = learner(db_session)
    second = learner(db_session, "other@example.test")
    educator = learner(db_session, "educator@example.test", UserRole.EDUCATOR)
    service = LearnerPreferenceService(db_session)
    service.save(first, command())
    assert service.read(second).version == 0
    assert not service.history(second).items
    with pytest.raises(PreferenceConflict):
        service.save(first, command(key="stale"))
    with pytest.raises(PreferenceConflict):
        service.save(first, command(pace="stepwise"))
    with pytest.raises(PermissionError):
        service.read(educator)
    first.is_active = False
    db_session.commit()
    with pytest.raises(PermissionError):
        service.save(first, command(1, "inactive"))


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE learner_preference_revisions SET pace='stepwise'",
        "DELETE FROM learner_preference_revisions",
        "INSERT OR REPLACE INTO learner_preference_revisions SELECT * FROM learner_preference_revisions",
    ],
)
def test_database_protects_history(db_session, sql):
    LearnerPreferenceService(db_session).save(learner(db_session), command())
    with pytest.raises(IntegrityError):
        db_session.execute(text(sql))
    db_session.rollback()
    assert db_session.scalar(select(func.count()).select_from(LearnerPreferenceRevision)) == 1


def test_concurrent_saves_have_one_winner(db_session):
    actor_id = learner(db_session).id
    db_session.commit()
    engine = db_session.get_bind()

    def save(key):
        with Session(engine) as session:
            try:
                LearnerPreferenceService(session).save(
                    session.get(User, actor_id), command(key=key)
                )
                return "saved"
            except (PreferenceConflict, PreferenceUnavailable):
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(save, ["one", "two"])) == ["conflict", "saved"]
    assert db_session.scalar(select(func.count()).select_from(LearnerPreferenceRevision)) == 1


def test_failed_commit_rolls_back_and_same_request_can_retry(db_session, monkeypatch):
    actor = learner(db_session)
    service = LearnerPreferenceService(db_session)
    original = db_session.commit

    def fail():
        db_session.flush()
        raise OperationalError("synthetic", {}, Exception("busy"))

    monkeypatch.setattr(db_session, "commit", fail)
    with pytest.raises(PreferenceUnavailable):
        service.save(actor, command())
    monkeypatch.setattr(db_session, "commit", original)
    assert service.read(actor).version == 0
    assert service.save(actor, command()).version == 1


def test_concurrent_exact_replay_returns_original_receipt(db_session, monkeypatch):
    actor = learner(db_session)
    actor_id = actor.id
    original_commit = db_session.commit
    competing = []

    def commit_after_competing_request():
        with Session(db_session.get_bind()) as other:
            competing.append(
                LearnerPreferenceService(other).save(other.get(User, actor_id), command())
            )
        original_commit()

    monkeypatch.setattr(db_session, "commit", commit_after_competing_request)
    receipt = LearnerPreferenceService(db_session).save(actor, command())
    assert receipt == competing[0]
    assert db_session.scalar(select(func.count()).select_from(LearnerPreferenceRevision)) == 1


def test_opt_out_and_transfer_policy_preserve_requested_choices():
    values = PreferenceValues(
        pace="stepwise",
        format="stepwise",
        explanation_detail="detailed",
        breaks=True,
        repeat_practice=True,
        support_amount="on_request",
        feedback_form="expandable",
        personalisation_enabled=False,
    )
    saved = PreferenceRead(version=5, values=values)
    effective = effective_preferences(saved, transfer=False, repeat_allowed=True)
    assert effective.values == PreferenceValues(personalisation_enabled=False)
    assert effective.requested == values
    transfer = effective_preferences(
        PreferenceRead(
            version=5, values=values.model_copy(update={"personalisation_enabled": True})
        ),
        transfer=True,
        repeat_allowed=True,
    )
    assert transfer.values.pace == "self_paced"
    assert not transfer.values.repeat_practice
    assert not transfer.repeat_allowed
    assert transfer.values.breaks


def test_authenticated_save_reload_session_history_and_denials(lms_context):
    client, session = lms_context
    endpoint = "/api/v1/learner-preferences/me"
    assert client.get(endpoint).status_code == 401
    login(client, "student")
    headers = {"X-CSRF-Token": client.cookies.get("ql_csrf"), "Origin": "http://localhost:5173"}
    payload = command(pace="stepwise").model_dump()
    assert client.put(endpoint, json=payload).status_code == 403
    response = client.put(endpoint, json=payload, headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert client.get(endpoint).json() == response.json()
    assert client.put(endpoint, json=payload, headers=headers).json() == response.json()
    assert (
        client.put(endpoint, json={**payload, "learner_id": 999}, headers=headers).status_code
        == 422
    )
    assert client.get(endpoint + "?learner_id=999").status_code == 422
    assert client.get(endpoint + "/history?course_id=999").status_code == 422
    assert client.get("/api/v1/learner-preferences/999").status_code == 404
    client.cookies.clear()
    login(client, "student")
    assert client.get(endpoint).json()["values"]["pace"] == "stepwise"
    assert len(client.get(endpoint + "/history").json()["items"]) == 1
    client.cookies.clear()
    login(client, "educator")
    assert client.get(endpoint).status_code == 403


def test_frozen_episode_effective_policy_and_protected_records(db_session):
    from test_task14_lifecycle import complete, setup_episode

    from app.models.assessment import AssessmentDecision
    from app.models.assessment_work import AssessmentWorkStart
    from app.models.learner_model import LearnerModelSnapshot
    from app.models.learning_evidence import LearningEvidence

    lms, actor, task, started = setup_episode(db_session)
    service = LearnerPreferenceService(db_session)
    original_work = {
        key: value
        for key, value in db_session.get(
            AssessmentWorkStart, started.assessment_work_start_id
        ).__dict__.items()
        if not key.startswith("_")
    }
    counts = [
        db_session.scalar(select(func.count()).select_from(table))
        for table in (LearningEvidence, LearnerModelSnapshot, AssessmentDecision)
    ]
    service.save(actor, command(pace="stepwise", repeat_practice=True, support_amount="on_request"))
    supported_view = lms.effective_preferences(actor, task.id)
    assert not supported_view.transfer
    assert supported_view.values.support_amount == "on_request"
    assert not supported_view.repeat_allowed
    assert not supported_view.values.repeat_practice
    assert counts == [
        db_session.scalar(select(func.count()).select_from(table))
        for table in (LearningEvidence, LearnerModelSnapshot, AssessmentDecision)
    ]
    assert {
        key: value
        for key, value in db_session.get(
            AssessmentWorkStart, started.assessment_work_start_id
        ).__dict__.items()
        if not key.startswith("_")
    } == original_work
    complete(lms, actor, task, started)
    transfer = lms.effective_preferences(actor, task.id)
    assert transfer.transfer
    assert transfer.values.pace == "self_paced"
    assert transfer.values.support_amount == "standard"
    assert lms.episode_state(actor, task.id)["accessibility_support"]
    assert not lms.episode_state(actor, task.id)["supported_hints"]
    service.save(actor, command(1, "disable", personalisation_enabled=False))
    assert lms.episode_state(actor, task.id)["accessibility_support"]
    other = learner(db_session, "out-of-course@example.test")
    from app.services.lms import LmsServiceError

    with pytest.raises(LmsServiceError):
        lms.effective_preferences(other, task.id)


def test_migration_preserves_preferences_and_refuses_destructive_downgrade(tmp_path):
    from alembic import command as migration
    from test_migrations import migration_config

    from app.db.session import create_db_engine

    engine = create_db_engine(f"sqlite:///{(tmp_path / 'preferences.db').as_posix()}")
    config = migration_config(str(engine.url))
    migration.upgrade(config, "head")
    # Simulate interrupted DDL after the table exists but before all guards exist.
    with engine.begin() as connection:
        connection.execute(text("DROP TRIGGER learner_preference_revisions_no_delete"))
    migration.stamp(config, "20260908_0032")
    migration.upgrade(config, "head")
    with Session(engine) as session:
        actor = learner(session)
        LearnerPreferenceService(session).save(actor, command(pace="stepwise"))
    migration.upgrade(config, "head")
    with pytest.raises(RuntimeError, match="history is protected"):
        migration.downgrade(config, "20260908_0032")
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT pace FROM learner_preference_revisions")).scalar_one()
            == "stepwise"
        )
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "20260909_0035"
        )
        with pytest.raises(IntegrityError):
            connection.execute(text("DELETE FROM learner_preference_revisions"))
    engine.dispose()
