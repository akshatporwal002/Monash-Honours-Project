"""Focused service tests for learner preference revisions."""

import pytest
from sqlalchemy import func, select

from app.domain.platform_enums import ExplanationDetail, PreferenceFormat, PreferencePace
from app.models.learner_preferences import LearnerPreferenceRevision
from app.models.user import User, UserRole
from app.services.learner_preferences.contracts import LearnerPreferencesWrite
from app.services.learner_preferences.repository import SqlAlchemyLearnerPreferencesRepository
from app.services.learner_preferences.service import (
    LearnerPreferencesConflictError,
    LearnerPreferencesService,
)


def _write(expected_revision: int, key: str, *, pace=PreferencePace.SLOWER):
    return LearnerPreferencesWrite(
        pace=pace,
        format=PreferenceFormat.WORKED_EXAMPLE,
        explanation_detail=ExplanationDetail.DETAILED,
        optional_breaks_enabled=True,
        repeat_practice_enabled=True,
        personalisation_enabled=True,
        expected_revision=expected_revision,
        idempotency_key=key,
    )


def test_defaults_are_side_effect_free_and_revisions_are_learner_scoped(db_session):
    learners = [
        User(
            email=f"preferences-{number}@test.example",
            password_hash="unused",
            full_name=f"Learner {number}",
            role=UserRole.STUDENT,
        )
        for number in (1, 2)
    ]
    db_session.add_all(learners)
    db_session.commit()
    service = LearnerPreferencesService(SqlAlchemyLearnerPreferencesRepository(db_session))

    assert service.read(learners[0].id).revision == 0
    assert db_session.scalar(select(func.count()).select_from(LearnerPreferenceRevision)) == 0
    first = service.save(learners[0].id, _write(0, "first"))

    assert first.revision == 1
    assert service.read(learners[1].id).revision == 0
    assert service.history(learners[1].id) == []


def test_exact_replay_correction_and_conflicts_preserve_history(db_session):
    learner = User(
        email="preference-replay@test.example",
        password_hash="unused",
        full_name="Learner",
        role=UserRole.STUDENT,
    )
    db_session.add(learner)
    db_session.commit()
    service = LearnerPreferencesService(SqlAlchemyLearnerPreferencesRepository(db_session))

    first = service.save(learner.id, _write(0, "first"))
    assert service.save(learner.id, _write(0, "first")) == first
    second = service.save(learner.id, _write(1, "second", pace=PreferencePace.FASTER))
    with pytest.raises(LearnerPreferencesConflictError):
        service.save(learner.id, _write(1, "stale"))
    with pytest.raises(LearnerPreferencesConflictError):
        service.save(learner.id, _write(0, "first", pace=PreferencePace.FASTER))

    assert [item.revision for item in service.history(learner.id)] == [2, 1]
    assert second.pace is PreferencePace.FASTER
