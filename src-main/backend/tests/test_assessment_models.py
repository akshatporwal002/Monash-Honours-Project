from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.domain.assessment import AssessmentPurpose, BloomKnowledge, BloomProcess
from app.models.assessment import (
    AssessmentApprovalState,
    AssessmentDefinition,
    AssessmentDefinitionVersion,
    BloomTarget,
    BloomTargetVersion,
    Criterion,
    CriterionEvaluatorType,
    CriterionVersion,
    ImmutableAssessmentVersionError,
    OutcomeVersion,
    PassRule,
    PassRuleVersion,
    TaskApproval,
    TaskForm,
    TaskFormVersion,
)
from app.models.enums import TaskType
from app.models.lms import Course, CourseModule, CourseState, LearningOutcome, OutcomeKind
from app.models.persistence import LearningTask
from app.models.user import User, UserRole

NOW = datetime(2026, 8, 15, 3, 0, tzinfo=UTC)


def _blueprint(
    session: Session,
) -> tuple[
    AssessmentDefinitionVersion,
    BloomTargetVersion,
    CriterionVersion,
    PassRuleVersion,
    TaskFormVersion,
    User,
]:
    owner = User(
        email="assessor@example.edu",
        password_hash=hash_password("assessment-model-test-password"),
        full_name="Assessment Owner",
        role=UserRole.EDUCATOR,
    )
    session.add(owner)
    session.flush()
    course = Course(
        educator_id=owner.id,
        code="QNT301",
        title="Assessment model course",
        state=CourseState.DRAFT,
    )
    session.add(course)
    session.flush()
    module = CourseModule(course_id=course.id, title="Quantum evidence", position=1)
    session.add(module)
    session.flush()
    outcome = LearningOutcome(
        module_id=module.id,
        title="Explain interference evidence",
        statement="Explain how interference supports a quantum claim.",
        kind=OutcomeKind.WEEKLY,
        week_number=1,
        position=1,
    )
    session.add(outcome)
    session.flush()
    task = LearningTask(
        slug="assessment-model-task",
        title="Interference explanation",
        module="Quantum evidence",
        description="Provide an evidence-based explanation.",
        instructions="Explain the observed interference pattern.",
        task_type=TaskType.QUIZ,
        difficulty="intermediate",
        points=0,
        position=1,
        course_id=course.id,
        module_id=module.id,
        learning_outcome_id=outcome.id,
    )
    session.add(task)
    session.flush()

    outcome_version = OutcomeVersion(
        course_id=course.id,
        learning_outcome_id=outcome.id,
        version=1,
        owner_user_id=owner.id,
        created_by_user_id=owner.id,
        title=outcome.title,
        statement=outcome.statement,
        source_version="course-source.v1",
    )
    definition = AssessmentDefinition(
        course_id=course.id,
        learning_outcome_id=outcome.id,
        created_by_user_id=owner.id,
    )
    session.add_all([outcome_version, definition])
    session.flush()
    definition_version = AssessmentDefinitionVersion(
        course_id=course.id,
        assessment_definition_id=definition.id,
        outcome_version_id=outcome_version.id,
        version=1,
        owner_user_id=owner.id,
        created_by_user_id=owner.id,
        claim="The learner can explain how the observed pattern supports the claim.",
        supporting_evidence={"observable": ["links the pattern to the claim"]},
        contradicting_evidence={"observable": ["claims the pattern proves the opposite"]},
        insufficient_evidence={"observable": ["names the pattern without reasoning"]},
        task_conditions={"response_mode": "written"},
        next_action_contract={"when_incomplete": "issue a fresh approved task"},
        purpose=AssessmentPurpose.SUMMATIVE,
        permitted_tools={"allowed": ["notes"]},
        instructional_support={"maximum_level": 1},
        access_conditions={"equivalent_modes": ["screen_reader"]},
        transfer_rule={"required": True, "new_context": "different circuit"},
        evidence_sufficiency={"requires": ["criterion evidence"]},
    )
    session.add(definition_version)
    session.flush()
    bloom_target = BloomTarget(assessment_definition_id=definition.id)
    criterion = Criterion(
        assessment_definition_id=definition.id,
        stable_key="target_bloom_action",
    )
    pass_rule = PassRule(assessment_definition_id=definition.id)
    task_form = TaskForm(assessment_definition_id=definition.id)
    session.add_all([bloom_target, criterion, pass_rule, task_form])
    session.flush()
    bloom_version = BloomTargetVersion(
        course_id=course.id,
        bloom_target_id=bloom_target.id,
        assessment_definition_version_id=definition_version.id,
        version=1,
        owner_user_id=owner.id,
        created_by_user_id=owner.id,
        bloom_process=BloomProcess.ANALYSE,
        knowledge_dimension=BloomKnowledge.CONCEPTUAL,
    )
    criterion_version = CriterionVersion(
        course_id=course.id,
        criterion_id=criterion.id,
        assessment_definition_version_id=definition_version.id,
        version=1,
        owner_user_id=owner.id,
        created_by_user_id=owner.id,
        learner_description="Explain the relationship between evidence and claim.",
        evidence_description="States a valid evidence-to-claim relationship.",
        mandatory=True,
        evidence_source_types=["learner_response"],
        met_rule="The response makes the required relationship explicit.",
        not_met_rule="The response lacks the relationship.",
        not_evaluable_rule="The response is missing or invalid.",
        approved_anchors={"met": ["valid explanation"]},
        critical_error_rules={"errors": ["reverses the relationship"]},
        evaluator_type=CriterionEvaluatorType.RULES,
    )
    session.add_all([bloom_version, criterion_version])
    session.flush()
    rule_version = PassRuleVersion(
        course_id=course.id,
        pass_rule_id=pass_rule.id,
        assessment_definition_version_id=definition_version.id,
        version=1,
        owner_user_id=owner.id,
        created_by_user_id=owner.id,
        expression={
            "operator": "ALL_OF",
            "clauses": [{"criterion_version_id": criterion_version.id}],
        },
    )
    form_version = TaskFormVersion(
        course_id=course.id,
        task_form_id=task_form.id,
        assessment_definition_version_id=definition_version.id,
        learning_task_id=task.id,
        version=1,
        owner_user_id=owner.id,
        created_by_user_id=owner.id,
        source_version="learning-task.v1",
        source_digest="sha256:assessment-model-task",
        task_family="written_explanation",
        context={"scenario": "interference experiment"},
        constraints={"response_format": "text"},
    )
    session.add_all([rule_version, form_version])
    session.commit()
    return definition_version, bloom_version, criterion_version, rule_version, form_version, owner


def test_approved_assessment_versions_are_immutable(db_session: Session) -> None:
    definition_version, _, _, _, form_version, owner = _blueprint(db_session)
    definition_version.approval_state = AssessmentApprovalState.APPROVED
    definition_version.approved_at = NOW
    definition_version.approved_by_user_id = owner.id
    db_session.commit()

    definition_version.claim = "A later draft must use a new version."
    with pytest.raises(ImmutableAssessmentVersionError, match="immutable"):
        db_session.commit()
    db_session.rollback()

    definition_version.retirement_reason = "The approved task form was superseded."
    definition_version.retired_at = NOW
    definition_version.retired_by_user_id = owner.id
    definition_version.approval_state = AssessmentApprovalState.RETIRED
    db_session.commit()
    definition_version.claim = "A retired version cannot change."
    with pytest.raises(ImmutableAssessmentVersionError, match="immutable"):
        db_session.commit()
    db_session.rollback()

    approval = TaskApproval(
        course_id=definition_version.course_id,
        assessment_definition_version_id=definition_version.id,
        task_form_version_id=form_version.id,
        actor_user_id=owner.id,
        approval_reason="The form matches the approved definition.",
        approval_state=AssessmentApprovalState.APPROVED,
        approved_at=NOW,
        approved_by_user_id=owner.id,
    )
    db_session.add(approval)
    db_session.commit()
    approval.approval_state = AssessmentApprovalState.RETIRED
    with pytest.raises(ImmutableAssessmentVersionError, match="immutable"):
        db_session.commit()


def test_definition_versions_keep_exact_outcome_bloom_criteria_rule_and_source_links(
    db_session: Session,
) -> None:
    definition_version, bloom_version, criterion_version, rule_version, form_version, _ = (
        _blueprint(db_session)
    )

    assert definition_version.outcome_version_id
    assert bloom_version.assessment_definition_version_id == definition_version.id
    assert criterion_version.assessment_definition_version_id == definition_version.id
    assert rule_version.assessment_definition_version_id == definition_version.id
    assert form_version.assessment_definition_version_id == definition_version.id
    assert form_version.source_version == "learning-task.v1"
    assert form_version.source_digest == "sha256:assessment-model-task"
    assert definition_version.formal_result_eligible is None

    definition_version.formal_result_eligible = True
    with pytest.raises(IntegrityError, match="result_eligibility"):
        db_session.commit()


@pytest.mark.parametrize(
    "expression",
    [
        {"operator": "SCORE_AT_LEAST", "clauses": [{"criterion_id": "criterion-1"}]},
        {"operator": "ALL_OF", "clauses": [{"criterion_id": "criterion-1"}]},
        {"operator": "ALL_OF", "clauses": [{"criterion_version_id": "criterion-1", "weight": 1}]},
        {"operator": "ALL_OF", "clauses": [{"criterion_version_id": "criterion-1", "score": 100}]},
        {"operator": "ALL_OF", "operands": [{"criterion_version_id": "criterion-1"}]},
    ],
)
def test_pass_rule_storage_rejects_scores_weights_and_unknown_operators(
    db_session: Session,
    expression: dict[str, object],
) -> None:
    _, _, _, rule_version, _, _ = _blueprint(db_session)

    with pytest.raises(ValueError, match="pass-rule"):
        rule_version.expression = expression


def test_draft_version_numbers_are_immutable(db_session: Session) -> None:
    definition_version, _, _, _, _, _ = _blueprint(db_session)

    definition_version.version = 2
    with pytest.raises(ImmutableAssessmentVersionError, match="version numbers"):
        db_session.commit()


def test_draft_version_row_identifiers_are_immutable(db_session: Session) -> None:
    definition_version, _, _, _, _, _ = _blueprint(db_session)

    definition_version.id = "different-version-row-id"
    with pytest.raises(ImmutableAssessmentVersionError, match="row identifiers"):
        db_session.commit()


def test_pass_rule_accepts_a_nested_boolean_expression(db_session: Session) -> None:
    _, _, criterion_version, rule_version, _, _ = _blueprint(db_session)

    rule_version.expression = {
        "operator": "NOT",
        "clauses": [
            {
                "operator": "ANY_OF",
                "clauses": [{"criterion_version_id": criterion_version.id}],
            }
        ],
    }
    db_session.commit()


def test_pass_rule_cannot_reference_a_missing_criterion_version(db_session: Session) -> None:
    _, _, _, rule_version, _, _ = _blueprint(db_session)

    rule_version.expression = {
        "operator": "ANY_OF",
        "clauses": [{"criterion_version_id": "missing-criterion-version"}],
    }
    with pytest.raises(ValueError, match="same course and definition version"):
        db_session.commit()


def test_referenced_criterion_version_cannot_be_reassigned_or_deleted(db_session: Session) -> None:
    _, _, criterion_version, _, _, _ = _blueprint(db_session)

    criterion_version.course_id = "other-course"
    with pytest.raises(ImmutableAssessmentVersionError, match="referenced criterion"):
        db_session.commit()
    db_session.rollback()

    db_session.delete(criterion_version)
    with pytest.raises(ImmutableAssessmentVersionError, match="referenced criterion"):
        db_session.commit()


def test_pass_rule_can_reference_a_pending_criterion_version(db_session: Session) -> None:
    definition_version, _, _, rule_version, _, owner = _blueprint(db_session)
    criterion = Criterion(
        id="pending-criterion",
        assessment_definition_id=definition_version.assessment_definition_id,
        stable_key="pending-criterion",
    )
    criterion_version = CriterionVersion(
        id="pending-criterion-v1",
        course_id=definition_version.course_id,
        criterion_id=criterion.id,
        assessment_definition_version_id=definition_version.id,
        version=1,
        owner_user_id=owner.id,
        created_by_user_id=owner.id,
        learner_description="Explain the pending criterion.",
        evidence_description="Provides the pending evidence.",
        mandatory=True,
        evidence_source_types=["learner_response"],
        met_rule="The evidence satisfies the pending criterion.",
        not_met_rule="The evidence does not satisfy the pending criterion.",
        not_evaluable_rule="The evidence cannot be evaluated.",
        approved_anchors={"met": ["pending evidence"]},
        critical_error_rules={"errors": []},
        evaluator_type=CriterionEvaluatorType.RULES,
    )
    next_rule_version = PassRuleVersion(
        id="pending-pass-rule-v2",
        course_id=definition_version.course_id,
        pass_rule_id=rule_version.pass_rule_id,
        assessment_definition_version_id=definition_version.id,
        version=2,
        owner_user_id=owner.id,
        created_by_user_id=owner.id,
        expression={
            "operator": "ALL_OF",
            "clauses": [{"criterion_version_id": criterion_version.id}],
        },
    )
    db_session.add_all([criterion, criterion_version, next_rule_version])

    db_session.commit()


def test_access_and_instructional_support_are_separate(db_session: Session) -> None:
    definition_version, _, _, _, _, _ = _blueprint(db_session)

    assert definition_version.instructional_support == {"maximum_level": 1}
    assert definition_version.access_conditions == {"equivalent_modes": ["screen_reader"]}
    assert definition_version.instructional_support != definition_version.access_conditions


def test_criterion_evaluator_type_is_constrained(db_session: Session) -> None:
    _, _, criterion_version, _, _, _ = _blueprint(db_session)

    criterion_version.evaluator_type = "unapproved"  # type: ignore[assignment]
    with pytest.raises((IntegrityError, StatementError), match="criterion_evaluator_type"):
        db_session.commit()
