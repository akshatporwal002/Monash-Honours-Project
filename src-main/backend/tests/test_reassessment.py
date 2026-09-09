"""Fresh authorised work preserves the standard and prior released evidence."""

from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from support.assessment import build_provisional_decision
from support.assessment_review import ANSWER, seed_review_context
from test_assessor_review_api import _request

from app.domain.assessment import AssessmentResult, AssessorReviewAction, ResultState
from app.models.assessment import AssessmentAttempt, AssessmentDecision, ReassessmentLink
from app.models.lms import SubmissionAttempt
from app.models.user import User
from app.schemas.lms import SubmissionCreate
from app.schemas.reassessment import OutcomePolicyWrite, ReassessmentWrite
from app.services.assessment.access import RoleAssignmentService
from app.services.assessment.outcome_results import OutcomeResultService
from app.services.assessment.reassessment import ReassessmentService
from app.services.assessment.review import AssessmentReviewService
from app.services.lms import LmsService, LmsServiceError


def context(session, *, rule="LATEST_VALID"):
    fixture = seed_review_context(session, reassessment=True)
    owner = session.scalar(select(User).where(User.email == fixture["educator_email"]))
    student = session.scalar(select(User).where(User.email == fixture["student_email"]))
    reviews = AssessmentReviewService(session, assignments=RoleAssignmentService(session))
    reviews.act(
        owner,
        decision_id=fixture["decision_id"],
        request=_request(
            AssessorReviewAction.OVERRIDE,
            new_result=AssessmentResult.INCOMPLETE,
        ),
    )
    service = ReassessmentService(session)
    setup = service.setup(owner, fixture["decision_id"])
    service.publish_policy(
        owner,
        fixture["definition_id"],
        OutcomePolicyWrite(
            selection_rule=rule,
            reason="Assessor approved whole-attempt evidence sufficiency.",
            required_form_ids=[form.id for form in setup.policy_forms]
            if rule == "ALL_REQUIRED_FORMS"
            else [],
        ),
    )
    command = ReassessmentWrite(
        task_form_version_id=setup.forms[0].id,
        expected_decision_revision=1,
        reason="PRIVATE: fresh equivalent form reviewed.",
        learner_notice="Use the fresh form to explain the relationship again.",
    )
    return fixture, owner, student, reviews, service, command


@pytest.mark.parametrize("rule", ["LATEST_VALID", "ANY_VALID_PASS", "ALL_REQUIRED_FORMS"])
def test_authorised_fresh_attempt_and_outcome_selection(db_session, rule):
    fixture, owner, student, reviews, service, command = context(db_session, rule=rule)
    projection = OutcomeResultService(db_session)
    before = projection.read(student, fixture["response_id"])
    assert before.result is AssessmentResult.INCOMPLETE
    grant = service.authorise(owner, fixture["decision_id"], command)
    assert service.authorise(owner, fixture["decision_id"], command).id == grant.id
    assert "PRIVATE" not in projection.read(student, fixture["response_id"]).model_dump_json()
    lms = LmsService(db_session)
    work = lms.start_assessment_work(student, grant.task_id, command.task_form_version_id)
    request = SubmissionCreate(
        answer=ANSWER,
        assessment_work_start_id=work.assessment_work_start_id,
        idempotency_key="fresh-response",
    )
    response = lms.submit(student, grant.task_id, request)
    assert lms.submit(student, grant.task_id, request).id == response.id
    link = db_session.scalar(select(ReassessmentLink))
    assert link.prior_assessment_attempt_id == fixture["attempt_id"]
    replacement = db_session.get(AssessmentAttempt, link.replacement_assessment_attempt_id)
    assert replacement.assessment_definition_version_id == fixture["definition_id"]
    assert (
        projection.read(student, response.id).evidence_response_ids == before.evidence_response_ids
    )
    decision = build_provisional_decision(db_session, replacement, suffix="replacement")
    db_session.commit()
    reviews.act(owner, decision_id=decision.id, request=_request(AssessorReviewAction.CONFIRM))
    current = projection.read(student, response.id)
    # Both originally required forms must have their own evidence; one replacement
    # cannot satisfy two required forms at once.
    assert current.result is (
        AssessmentResult.INCOMPLETE if rule == "ALL_REQUIRED_FORMS" else AssessmentResult.PASS
    )
    assert response.id in current.evidence_response_ids
    assert not current.authorisations[0].available
    assert (
        db_session.get(AssessmentDecision, fixture["decision_id"]).result
        is AssessmentResult.INCOMPLETE
    )
    assert db_session.get(SubmissionAttempt, fixture["response_id"]).answer == ANSWER
    with pytest.raises(LmsServiceError, match="already been submitted"):
        lms.submit(
            student, grant.task_id, request.model_copy(update={"idempotency_key": "another"})
        )
    db_session.rollback()


def test_reassessment_rejects_stale_decision_and_mutation(db_session):
    fixture, owner, student, reviews, service, command = context(db_session)
    with pytest.raises(LmsServiceError, match="decision changed"):
        service.authorise(
            owner,
            fixture["decision_id"],
            command.model_copy(update={"expected_decision_revision": 0}),
        )
    db_session.rollback()
    grant = service.authorise(owner, fixture["decision_id"], command)
    with pytest.raises(LmsServiceError, match="different reassessment"):
        service.authorise(
            owner, fixture["decision_id"], command.model_copy(update={"reason": "Changed"})
        )
    db_session.rollback()
    for table in ("reassessment_authorisations", "outcome_result_policies"):
        with pytest.raises(IntegrityError, match="immutable"):
            db_session.execute(text(f"DELETE FROM {table}"))
        db_session.rollback()
    reviews.act(
        owner,
        decision_id=fixture["decision_id"],
        request=_request(
            AssessorReviewAction.VOID,
            expected_state=ResultState.OVERRIDDEN,
            expected_revision=1,
        ),
    )
    assert (
        not OutcomeResultService(db_session)
        .read(student, fixture["response_id"])
        .authorisations[0]
        .available
    )
    with pytest.raises(LmsServiceError, match="changed after"):
        LmsService(db_session).start_assessment_work(
            student, grant.task_id, command.task_form_version_id
        )


def test_policy_requires_assessor_and_is_immutable(db_session):
    fixture, owner, student, _, service, _ = context(db_session)
    from app.services.assessment.access import ScopedRoleAccessDeniedError

    with pytest.raises(ScopedRoleAccessDeniedError):
        service.setup(student, fixture["decision_id"])
    with pytest.raises(LmsServiceError, match="published outcome rule"):
        service.publish_policy(
            owner,
            fixture["definition_id"],
            OutcomePolicyWrite(selection_rule="ANY_VALID_PASS", reason="Changed rule"),
        )
    db_session.rollback()
    with pytest.raises(LmsServiceError) as error:
        OutcomeResultService(db_session).read(owner, fixture["response_id"])
    assert error.value.status_code == 404


def test_assessor_can_add_equivalent_forms_without_revising_the_standard(db_session):
    from support.task_review import approve_sourced_fixture_task

    from app.models.assessment import AssessmentDefinitionVersion, TaskFormVersion
    from app.models.persistence import LearningTask
    from app.schemas.reassessment import EquivalentFormWrite
    from app.services.assessment.equivalent_forms import EquivalentFormService

    fixture, owner, student, reviews, service, original_command = context(db_session)
    original = db_session.get(LearningTask, fixture["task_id"])
    fresh = LearningTask(
        slug=f"another-form-{uuid4().hex}",
        title="Another reviewed scenario",
        module=original.module,
        description="Explain how this new observation supports the claim.",
        instructions=original.instructions,
        expected_answer=ANSWER,
        task_type=original.task_type,
        difficulty=original.difficulty,
        points=original.points,
        position=original.position + 2,
        course_id=original.course_id,
        module_id=original.module_id,
        learning_outcome_id=original.learning_outcome_id,
        source_references=list(original.source_references),
        marking_criteria=dict(original.marking_criteria or {}),
    )
    db_session.add(fresh)
    db_session.commit()
    approve_sourced_fixture_task(db_session, fresh)
    setup = service.setup(owner, fixture["decision_id"])
    candidate = next(item for item in setup.fresh_tasks if item.task_id == fresh.id)
    command = EquivalentFormWrite(
        task_id=fresh.id,
        revision_id=candidate.revision_id,
        template_form_id=setup.forms[0].id,
        reason="The assessor reviewed the fresh scenario against the same criteria and conditions.",
    )
    forms = EquivalentFormService(db_session)
    added = forms.publish(owner, fixture["definition_id"], command)
    assert forms.publish(owner, fixture["definition_id"], command).id == added.id
    form = db_session.get(TaskFormVersion, added.id)
    definition = db_session.get(AssessmentDefinitionVersion, fixture["definition_id"])
    assert form.assessment_definition_version_id == definition.id
    assert definition.version == 1
    assert added.id in {item.id for item in service.setup(owner, fixture["decision_id"]).forms}
    earlier = service.authorise(owner, fixture["decision_id"], original_command)
    reviews.act(
        owner,
        decision_id=fixture["decision_id"],
        request=_request(
            AssessorReviewAction.VOID, expected_state=ResultState.OVERRIDDEN, expected_revision=1
        ),
    )
    renewed = service.authorise(
        owner,
        fixture["decision_id"],
        original_command.model_copy(
            update={
                "task_form_version_id": added.id,
                "expected_decision_revision": 2,
                "reason": "A new assessor decision requires a fresh authorisation.",
            }
        ),
    )
    assert renewed.available
    grants = OutcomeResultService(db_session).read(student, fixture["response_id"]).authorisations
    assert len(grants) == 2
    assert not next(item for item in grants if item.id == earlier.id).available
    assert next(item for item in grants if item.id == renewed.id).available
