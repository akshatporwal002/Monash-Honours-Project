"""Historical inspection preserves validated responses without approving old context."""

from dataclasses import replace

import pytest
from sqlalchemy import event, update
from support.assessment import assign_assessor, seed_review_decision
from test_task15_migrated_review import request, setup_human

from app.domain.assessment import AssessmentResult, AssessorReviewAction, ResultState
from app.models.assessment import AssessmentAttempt, AssessmentDefinitionVersion, BloomTargetVersion
from app.models.lms import SubmissionAttempt
from app.schemas.episode import ResponseContent
from app.services.assessment.access import RoleAssignmentService
from app.services.assessment.frozen_review import FrozenReviewEvidenceReader
from app.services.assessment.review import (
    AssessmentReviewActionRequest,
    AssessmentReviewConflictError,
    AssessmentReviewService,
)
from app.services.episode_contract import FrozenResponseError
from app.services.episode_evidence import canonical_response_digest
from app.services.episode_responses import SqlAlchemyFrozenResponseReader

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


@pytest.mark.parametrize("action", [AssessorReviewAction.CONFIRM, AssessorReviewAction.OVERRIDE])
def test_legacy_valid_response_remains_readable_without_approved_context(db_session, action):
    attempt, response, decision, actor = seed_review_decision(db_session)
    # The old fixture uses a placeholder digest. Model a genuinely preserved v1 response.
    digest = canonical_response_digest(
        content=ResponseContent(
            answer=response.answer, code=response.code, circuit=response.circuit
        ),
        episode=None,
        schema_version=response.response_schema_version,
        assessment_work_start_id=response.assessment_work_start_id,
        task_form_version_id=response.task_form_version_id,
        declared_conditions=response.declared_conditions,
    )
    db_session.execute(
        update(SubmissionAttempt)
        .where(SubmissionAttempt.id == response.id)
        .values(content_digest=digest)
    )
    assign_assessor(db_session, actor, attempt.course_id, actor)
    db_session.commit()
    statements = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(db_session.bind, "before_cursor_execute", observe)
    try:
        detail = AssessmentReviewService(
            db_session,
            assignments=RoleAssignmentService(db_session),
            reader=SqlAlchemyFrozenResponseReader(db_session),
        ).get_detail(actor, decision_id=decision.id)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", observe)
    assert detail.response is not None
    assert detail.response_text == "The response links the observation to the claim."
    assert detail.response.reference.evidence_id == response.id
    assert detail.frozen_context is None
    assert detail.response_issues
    assert not {"INSERT", "UPDATE", "DELETE", "REPLACE"} & set(statements)
    service = AssessmentReviewService(
        db_session,
        assignments=RoleAssignmentService(db_session),
        reader=SqlAlchemyFrozenResponseReader(db_session),
    )
    with pytest.raises(AssessmentReviewConflictError, match="Frozen evidence"):
        service.act(
            actor,
            decision_id=decision.id,
            request=AssessmentReviewActionRequest(
                action=action,
                reason="Inspect historical work without inventing approval.",
                expected_result_state=ResultState.PROVISIONAL,
                expected_review_revision=0,
                new_result=AssessmentResult.INCOMPLETE
                if action is AssessorReviewAction.OVERRIDE
                else None,
            ),
        )
    assert decision.result_state is ResultState.PROVISIONAL


def test_legacy_invalid_digest_is_still_rejected(db_session):
    attempt, _, _, _ = seed_review_decision(db_session)
    detail = FrozenReviewEvidenceReader(
        db_session, SqlAlchemyFrozenResponseReader(db_session)
    ).read(attempt)
    assert detail["response"] is None
    assert detail["issues"]


@pytest.mark.parametrize("missing", ["bundle", "context"])
def test_missing_context_preserves_valid_history_and_blocks_confirmation(
    db_session, missing, monkeypatch
):
    service, actor, attempt, first_id = setup_human(
        db_session, revision=True, simulation_status="completed"
    )
    action = request(service, actor, attempt.id)
    if missing == "bundle":
        db_session.execute(
            update(AssessmentDefinitionVersion)
            .where(AssessmentDefinitionVersion.id == attempt.assessment_definition_version_id)
            .values(formal_result_eligible=False)
        )
    else:

        def unavailable_context(self, bundle):
            raise FrozenResponseError("The exact reviewed task context is unavailable or stale")

        monkeypatch.setattr(FrozenReviewEvidenceReader, "context", unavailable_context)
    db_session.commit()
    detail = service.detail(actor, assessment_attempt_id=attempt.id)
    assert detail["response"] is not None
    assert detail["frozen_context"] is None
    assert detail["response_history"][0].reference.evidence_id == first_id
    assert detail["historical_evidence"][0].simulations[0]["status"] == "completed"
    assert detail["historical_evidence"][0].issues
    assert detail["issues"] and not detail["can_finalise"]
    with pytest.raises(AssessmentReviewConflictError):
        service.finalise(
            actor,
            assessment_attempt_id=attempt.id,
            request=replace(action, expected_token=detail["expected_token"]),
        )


@pytest.mark.parametrize("broken", ["digest", "scope", "version"])
def test_invalid_current_response_is_not_exposed(db_session, broken, monkeypatch):
    service, actor, attempt, _ = setup_human(db_session)
    if broken == "digest":
        db_session.execute(
            update(SubmissionAttempt)
            .where(SubmissionAttempt.id == attempt.response_version_id)
            .values(answer="Tampered response must stay hidden")
        )
    elif broken == "scope":
        db_session.execute(
            update(AssessmentAttempt)
            .where(AssessmentAttempt.id == attempt.id)
            .values(student_id=actor.id)
        )
    else:
        original_get = db_session.get

        def missing_version(model, key, *args, **kwargs):
            if model is BloomTargetVersion:
                return None
            return original_get(model, key, *args, **kwargs)

        monkeypatch.setattr(db_session, "get", missing_version)
    db_session.commit()
    detail = service.detail(actor, assessment_attempt_id=attempt.id)
    assert detail["response"] is None
    assert detail["response_history"] == ()
    assert detail["issues"] and not detail["can_finalise"]


def test_current_simulation_failure_keeps_valid_earlier_evidence(db_session, monkeypatch):
    service, actor, attempt, first_id = setup_human(
        db_session, revision=True, simulation_status="completed"
    )
    from app.services.assessment.response_evidence import ResponseEvidenceResolver

    original = ResponseEvidenceResolver.simulations

    def unavailable_current(self, assessment, response):
        if assessment.assessment_attempt_id == attempt.id:
            raise FrozenResponseError("Required current simulation is missing")
        return original(self, assessment, response)

    monkeypatch.setattr(ResponseEvidenceResolver, "simulations", unavailable_current)
    detail = service.detail(actor, assessment_attempt_id=attempt.id)
    assert detail["response"] is not None
    assert detail["historical_evidence"][0].response.reference.evidence_id == first_id
    assert detail["historical_evidence"][0].simulations[0]["status"] == "completed"
    assert detail["issues"] and not detail["can_finalise"]
