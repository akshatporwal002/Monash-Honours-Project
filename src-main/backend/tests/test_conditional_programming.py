"""D-11 reuse checks. All identities, source approvals and decisions are synthetic."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from support.assessment import assign_assessor
from support.task_review import approve_sourced_fixture_task
from test_assessment_definitions import _draft
from test_task14_lifecycle import assessment_reference

from app.domain.assessment import AssessmentResult, BloomProcess, CriterionDecision
from app.models import LearningTask, User, UserRole
from app.models.assessment import (
    AssessmentApprovalState,
    CriterionEvaluatorType,
    OutcomeVersion,
    TaskFormVersion,
)
from app.models.lms import CourseState, Enrollment
from app.schemas.episode import EpisodePayloadV1, ResponseContent
from app.schemas.lms import DraftWrite, SubmissionCreate
from app.services import conditional_programming as module
from app.services.assessment.definitions import AssessmentDefinitionService
from app.services.assessment.evaluators import (
    CriterionEvaluationRequest,
    HumanCriterionEvaluator,
    HumanCriterionInput,
)
from app.services.assessment.pass_rules import (
    CriterionRuleOutcome,
    PassRuleEngine,
    PassRuleEvaluationRequest,
)
from app.services.assessment.publication import learner_task_available
from app.services.episode_contract import FrozenResponseStale, learner_episode_plan
from app.services.episode_responses import SqlAlchemyFrozenResponseReader
from app.services.lms import LmsService, LmsServiceError
from app.services.task_review import TaskReviewError
from app.services.task_types import UnsupportedTaskTypeError, build_default_task_type_registry


@pytest.fixture
def content(db_session):
    owner = User(
        email="conditional-owner@example.edu",
        full_name="Synthetic Owner",
        password_hash="unused",
        role=UserRole.EDUCATOR,
    )
    student = User(
        email="conditional-student@example.edu",
        full_name="Synthetic Student",
        password_hash="unused",
        role=UserRole.STUDENT,
    )
    db_session.add_all([owner, student])
    db_session.commit()
    lms = LmsService(db_session)
    course = lms.create_course(owner, module.course_draft())
    section = lms.create_module(owner, course.id, module.module_draft())
    outcome = lms.create_outcome(owner, section.id, module.outcome_draft())
    tasks = [
        lms.create_task(owner, course.id, draft)
        for draft in module.task_drafts(module_id=section.id, outcome_id=outcome.id)
    ]
    return lms, owner, student, course, outcome, tasks


def test_creates_separate_unpublished_content_without_sources_or_approvals(db_session, content):
    lms, owner, _, course, _, tasks = content
    assert course.state == CourseState.DRAFT
    assert not course.enrollment_open
    for task in tasks:
        stored = db_session.get(LearningTask, task.id)
        assert stored.course_id == course.id
        assert stored.source_references == []
        assert not learner_task_available(db_session, stored)
    with pytest.raises(LmsServiceError, match="review|approv|source"):
        lms.set_course_state(owner, course.id, CourseState.PUBLISHED)


@pytest.mark.parametrize(
    "index, answer, correct",
    [
        (0, "cool", True),
        (0, " WARM ", False),
        (0, "", False),
        (0, '["cool", "warm"]', False),
        (0, " COOL ", True),
        (1, "inclusive", True),
        (1, "strict", False),
        (1, "equal", False),
        (1, "", False),
        (1, "__import__('os')", False),
    ],
)
def test_existing_choice_handler_marks_trace_and_correction(index, answer, correct):
    drafts = module.task_drafts(
        module_id="00000000-0000-4000-8000-000000000001",
        outcome_id="00000000-0000-4000-8000-000000000002",
    )
    task = drafts[index]
    registry = build_default_task_type_registry()
    assert registry.is_correct(task.task_type, task, ResponseContent(answer=answer)) is correct
    episode = drafts[2]
    with pytest.raises(UnsupportedTaskTypeError, match="criterion review"):
        registry.is_correct(episode.task_type, episode, ResponseContent(answer="warm"))


def test_contract_rejects_malformed_input_and_keeps_transfer_private():
    with pytest.raises(ValidationError):
        ResponseContent(answer={"output": "cool"})
    visible = learner_episode_plan(module.episode_plan())
    assert "solution" not in str(visible)
    assert module.TRANSFER_CODE not in str(visible)
    assert module.episode_plan().transfer.prompt not in str(visible)
    drafts = module.criterion_drafts()
    assert all(
        c.evaluator_type is CriterionEvaluatorType.HUMAN and c.approved_anchors == {}
        for c in drafts
    )


def test_episode_freezes_conditional_evidence_and_reuses_assessment(db_session, content):
    lms, owner, student, course, outcome, tasks = content
    for item in tasks:
        approve_sourced_fixture_task(db_session, db_session.get(LearningTask, item.id))
    assign_assessor(db_session, owner, course.id, owner)
    version = OutcomeVersion(
        course_id=course.id,
        learning_outcome_id=outcome.id,
        version=1,
        owner_user_id=owner.id,
        created_by_user_id=owner.id,
        title=outcome.title,
        statement=outcome.statement,
        source_version="synthetic-conditional-source.v1",
        approval_state=AssessmentApprovalState.APPROVED,
        approved_by_user_id=owner.id,
        approved_at=datetime.now(UTC),
    )
    db_session.add(version)
    db_session.commit()
    task = tasks[2]
    criteria = module.criterion_drafts()
    draft = replace(
        _draft(outcome_version_id=version.id, task_id=task.id, task_processes=["APPLY"]),
        claim=outcome.statement,
        bloom_process=BloomProcess.APPLY,
        formal_result_eligible=True,
        criteria=criteria,
        supporting_evidence={"observable": [c.met_rule for c in criteria]},
        contradicting_evidence={"observable": [c.not_met_rule for c in criteria]},
        transfer_rule={"required": True, "independence": "unaided delivery example"},
        pass_rule_expression={
            "operator": "ALL_OF",
            "clauses": [{"criterion": c.stable_key} for c in criteria],
        },
    )
    draft = replace(
        draft,
        task_forms=[
            replace(
                draft.task_forms[0],
                task_family="conditional_programming",
                context={"scenario": "temperature boundary and delivery fee"},
            )
        ],
    )
    definitions = AssessmentDefinitionService(db_session)
    definition = definitions.create_draft(
        course_id=course.id, learning_outcome_id=outcome.id, actor_user_id=owner.id, draft=draft
    )
    definitions.approve(
        course_id=course.id,
        assessment_definition_id=definition.assessment_definition_id,
        expected_version=1,
        actor_user_id=owner.id,
        approval_reason="Synthetic D-11 integration fixture only",
    )
    form = db_session.scalar(
        select(TaskFormVersion).where(
            TaskFormVersion.assessment_definition_version_id == definition.id
        )
    )
    assert form.constraints["episode_plan"] == module.episode_plan().model_dump(mode="json")
    lms.set_course_state(owner, course.id, CourseState.PUBLISHED)
    db_session.add(Enrollment(course_id=course.id, student_id=student.id))
    db_session.commit()
    started = lms.start_assessment_work(student, task.id, form.id)
    payload = DraftWrite(
        assessment_work_start_id=started.assessment_work_start_id,
        answer="19: cool; 20: warm; 21: warm\n" + module.BUGGY_CODE.replace("> 20", ">= 20"),
        episode=EpisodePayloadV1(
            supported={
                "prediction": {"answer": "cool"},
                "reasoning": "> excludes equality",
                "explanation": ">= includes 20",
                "reflection": "Check both sides and equality.",
            }
        ),
    )
    saved = lms.episode_checkpoint(student, task.id, payload, "supported", None)
    payload = DraftWrite.model_validate(
        saved["draft"].model_dump(exclude={"id", "task_id", "updated_at"})
    )
    with pytest.raises(TaskReviewError, match="Complete the fresh application before submitting"):
        lms.submit(
            student,
            task.id,
            SubmissionCreate(**payload.model_dump(), idempotency_key="missing-transfer"),
        )
    db_session.rollback()
    transfer = lms.episode_transfer(student, task.id, payload)["transfer"]
    assert transfer["starter_code"] == module.TRANSFER_CODE
    assert "solution" not in transfer
    raw = payload.episode.model_dump(mode="json")
    raw["transfer"] = {
        "stage_start_id": transfer["stage_start_id"],
        "part_id": transfer["part_id"],
        "content": {"answer": "2: 5; 3: 0; 4: 0", "code": module.TRANSFER_CODE},
        "process": {
            "reasoning": "At least includes equality",
            "explanation": ">= includes 3",
            "reflection": "The same boundary rule applies.",
        },
    }
    payload = payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(raw)})
    lms.save_draft(student, task.id, payload)
    assert lms.get_draft(student, task.id).episode == payload.episode
    request = SubmissionCreate(**payload.model_dump(), idempotency_key="conditional-first")
    submitted = lms.submit(student, task.id, request)
    assert lms.submit(student, task.id, request).id == submitted.id
    assert not hasattr(submitted, "score")
    reference = assessment_reference(db_session, submitted.id)
    reader = SqlAlchemyFrozenResponseReader(db_session)
    frozen = reader.read(assessment=reference)
    assert frozen.content.answer == payload.answer
    assert frozen.content.code is None
    assert frozen.episode == payload.episode
    revised = payload.episode.model_dump(mode="json")
    revised["supported"]["revision"] = {
        "previous_response_version_id": submitted.id,
        "reason": "Clarify that equality takes the warm branch after correction.",
    }
    revised["supported"]["explanation"] = "At 20 the corrected >= condition is true."
    revision = payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(revised)})
    second = lms.submit(
        student,
        task.id,
        SubmissionCreate(**revision.model_dump(), idempotency_key="conditional-revision"),
    )
    assert second.id != submitted.id
    assert reader.read(assessment=reference) == frozen
    assert (
        reader.read(
            assessment=assessment_reference(db_session, second.id)
        ).episode.supported.revision.previous_response_version_id
        == submitted.id
    )
    with pytest.raises(FrozenResponseStale):
        reader.read(assessment=reference.model_copy(update={"course_id": "different-course"}))
    evaluator = HumanCriterionEvaluator()
    decision = evaluator.evaluate(
        CriterionEvaluationRequest(
            frozen.content.answer, BloomProcess.APPLY, {}, (frozen.reference,)
        ),
        HumanCriterionInput(CriterionDecision.MET, "Synthetic reviewer input for adapter check"),
    )
    assert decision.evidence == (frozen.reference,)
    # This exercises the engine with synthetic decisions, not educational validation.
    keys = frozenset(c.stable_key for c in criteria)
    for transfer_decision, expected in [
        (CriterionDecision.MET, AssessmentResult.PASS),
        (CriterionDecision.NOT_EVALUABLE, AssessmentResult.INCOMPLETE),
        (CriterionDecision.NOT_MET, AssessmentResult.INCOMPLETE),
    ]:
        result = PassRuleEngine().evaluate(
            PassRuleEvaluationRequest(
                expression={
                    "operator": "ALL_OF",
                    "clauses": [{"criterion_version_id": k} for k in sorted(keys)],
                },
                approved_criterion_version_ids=keys,
                mandatory_criterion_version_ids=keys,
                criterion_outcomes=tuple(
                    CriterionRuleOutcome(
                        k, transfer_decision if k == "transfer" else decision.decision
                    )
                    for k in sorted(keys)
                ),
            )
        )
        assert result.result is expected
