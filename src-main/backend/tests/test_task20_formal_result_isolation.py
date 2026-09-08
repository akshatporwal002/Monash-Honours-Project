"""Preferences are learner-owned support choices, never formal-result input."""

from __future__ import annotations

import inspect

from sqlalchemy import func, select
from test_assessment_evaluation_api import _ready_attempt, _service

from app.domain.platform_enums import ExplanationDetail, PreferenceFormat, PreferencePace
from app.models.assessment import AssessmentDecision, CriterionEvaluation
from app.services.assessment.evaluation import AssessmentEvaluationService
from app.services.learner_preferences.contracts import LearnerPreferencesWrite
from app.services.learner_preferences.repository import SqlAlchemyLearnerPreferencesRepository
from app.services.learner_preferences.service import LearnerPreferencesService


def _preferences(*, expected_revision: int, key: str, slower: bool) -> LearnerPreferencesWrite:
    return LearnerPreferencesWrite(
        pace=PreferencePace.SLOWER if slower else PreferencePace.FASTER,
        format=PreferenceFormat.WORKED_EXAMPLE if slower else PreferenceFormat.CIRCUIT,
        explanation_detail=ExplanationDetail.DETAILED if slower else ExplanationDetail.BRIEF,
        optional_breaks_enabled=slower,
        repeat_practice_enabled=slower,
        personalisation_enabled=slower,
        expected_revision=expected_revision,
        idempotency_key=key,
    )


def test_preference_corrections_cannot_change_a_frozen_formal_result(db_session) -> None:
    """A correction before and after evaluation leaves formal assessment inputs/results intact."""
    attempt, response, _, _, owner = _ready_attempt(db_session)
    preferences = LearnerPreferencesService(SqlAlchemyLearnerPreferencesRepository(db_session))

    preferences.save(owner.id, _preferences(expected_revision=0, key="before-work", slower=True))
    frozen_before = (response.content_digest, response.task_form_version_id, attempt.id)
    preferences.save(
        owner.id, _preferences(expected_revision=1, key="before-evaluation", slower=False)
    )
    assert (response.content_digest, response.task_form_version_id, attempt.id) == frozen_before

    result = _service(db_session).evaluate(
        assessment_attempt_id=attempt.id, evaluation_idempotency_key="preference-isolation"
    )
    decisions_before = db_session.scalar(select(func.count()).select_from(AssessmentDecision))
    criteria_before = db_session.scalar(select(func.count()).select_from(CriterionEvaluation))
    preferences.save(owner.id, _preferences(expected_revision=2, key="after-decision", slower=True))

    assert (response.content_digest, response.task_form_version_id, attempt.id) == frozen_before
    assert (
        db_session.scalar(select(func.count()).select_from(AssessmentDecision)) == decisions_before
    )
    assert (
        db_session.scalar(select(func.count()).select_from(CriterionEvaluation)) == criteria_before
    )
    assert result.result.value == "PASS"


def test_assessment_runtime_does_not_depend_on_learner_preferences() -> None:
    """The formal-result boundary must not accept preferences as evaluator input."""
    source = inspect.getsource(AssessmentEvaluationService)
    assert "learner_preferences" not in source
    assert "preference" not in inspect.signature(AssessmentEvaluationService.evaluate).parameters
