"""Stable assessment graph builders shared by tests and browser seeding."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.domain.assessment import (
    AssessmentAttemptState,
    AssessmentPurpose,
    AssessmentResult,
    BloomKnowledge,
    BloomProcess,
    CriterionDecision,
    ResultState,
)
from app.models.assessment import (
    AssessmentAttempt,
    AssessmentDecision,
    AssessmentDefinition,
    AssessmentDefinitionVersion,
    BloomTarget,
    BloomTargetVersion,
    Criterion,
    CriterionEvaluation,
    CriterionEvaluatorType,
    CriterionVersion,
    OutcomeVersion,
    PassRule,
    PassRuleVersion,
    TaskForm,
    TaskFormVersion,
)
from app.models.enums import TaskType
from app.models.lms import (
    AttemptStatus,
    Course,
    CourseModule,
    CourseState,
    LearningOutcome,
    OutcomeKind,
    PlatformAuditEvent,
    SubmissionAttempt,
    SubmissionDraft,
)
from app.models.persistence import LearningTask
from app.models.user import RoleAssignment, ScopedRole, User, UserRole

NOW = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)
DIGEST = "sha256:" + "a" * 64


def _lms_scope(session: Session) -> tuple[User, Course, LearningOutcome, LearningTask]:
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
    return owner, course, outcome, task


def _definition_version(
    session: Session,
    owner: User,
    course: Course,
    outcome: LearningOutcome,
) -> tuple[AssessmentDefinition, AssessmentDefinitionVersion]:
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
    version = AssessmentDefinitionVersion(
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
    session.add(version)
    session.flush()
    return definition, version


def _assessment_versions(
    session: Session,
    owner: User,
    course: Course,
    task: LearningTask,
    definition: AssessmentDefinition,
    definition_version: AssessmentDefinitionVersion,
) -> tuple[BloomTargetVersion, CriterionVersion, PassRuleVersion, TaskFormVersion]:
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
    session.flush()
    return bloom_version, criterion_version, rule_version, form_version


def build_assessment_blueprint(
    session: Session,
) -> tuple[
    AssessmentDefinitionVersion,
    BloomTargetVersion,
    CriterionVersion,
    PassRuleVersion,
    TaskFormVersion,
    User,
]:
    owner, course, outcome, task = _lms_scope(session)
    definition, definition_version = _definition_version(session, owner, course, outcome)
    bloom, criterion, rule, form = _assessment_versions(
        session,
        owner,
        course,
        task,
        definition,
        definition_version,
    )
    session.commit()
    return definition_version, bloom, criterion, rule, form, owner


def build_assessment_attempt(
    session: Session,
) -> tuple[AssessmentAttempt, SubmissionAttempt, CriterionVersion, PassRuleVersion, User]:
    definition, bloom, criterion, rule, form, owner = build_assessment_blueprint(session)
    student = User(
        email="attempt-student@example.edu",
        password_hash=hash_password("attempt-model-test-password"),
        full_name="Attempt Student",
        role=UserRole.STUDENT,
    )
    session.add(student)
    session.flush()
    draft = SubmissionDraft(student_id=student.id, task_id=form.learning_task_id)
    session.add(draft)
    session.flush()
    response = SubmissionAttempt(
        draft_id=draft.id,
        student_id=student.id,
        task_id=form.learning_task_id,
        attempt_number=1,
        status=AttemptStatus.SUBMITTED,
        answer="The response links the observation to the claim.",
        score=None,
        feedback="Response recorded.",
        task_form_version_id=form.id,
        response_schema_version="assessment.response.v1",
        content_digest=DIGEST,
        idempotency_key="response-key-1",
        declared_conditions={"tools": ["notes"]},
    )
    session.add(response)
    session.flush()
    attempt = AssessmentAttempt(
        course_id=definition.course_id,
        student_id=student.id,
        task_id=form.learning_task_id,
        response_version_id=response.id,
        assessment_definition_version_id=definition.id,
        task_form_version_id=form.id,
        bloom_target_version_id=bloom.id,
        pass_rule_version_id=rule.id,
        state=AssessmentAttemptState.PENDING,
    )
    session.add(attempt)
    session.commit()
    return attempt, response, criterion, rule, owner


def build_provisional_decision(
    session: Session,
    attempt: AssessmentAttempt,
) -> AssessmentDecision:
    decision = AssessmentDecision(
        assessment_attempt_id=attempt.id,
        bloom_target_version_id=attempt.bloom_target_version_id,
        pass_rule_version_id=attempt.pass_rule_version_id,
        evaluation_idempotency_key="evaluation-key-1",
        result=AssessmentResult.PASS,
        result_state=ResultState.PROVISIONAL,
        evidence_references={"criterion_evaluations": []},
        system_reason="TARGET_EVIDENCE_MET",
    )
    session.add(decision)
    session.commit()
    return decision


def build_external_criterion(
    session: Session,
    attempt: AssessmentAttempt,
    frozen_criterion: CriterionVersion,
    owner: User,
) -> CriterionVersion:
    criterion = Criterion(
        assessment_definition_id=frozen_criterion.criterion.assessment_definition_id,
        stable_key="later-criterion",
    )
    session.add(criterion)
    session.flush()
    version = CriterionVersion(
        course_id=attempt.course_id,
        criterion_id=criterion.id,
        assessment_definition_version_id=attempt.assessment_definition_version_id,
        version=1,
        owner_user_id=owner.id,
        created_by_user_id=owner.id,
        learner_description="A later criterion that the frozen rule does not include.",
        evidence_description="Evidence for a later criterion.",
        mandatory=True,
        evidence_source_types=["learner_response"],
        met_rule="The response satisfies the later criterion.",
        not_met_rule="The response does not satisfy the later criterion.",
        not_evaluable_rule="The response cannot be evaluated for the later criterion.",
        approved_anchors={"met": ["later evidence"]},
        critical_error_rules={"errors": []},
        evaluator_type=CriterionEvaluatorType.RULES,
    )
    session.add(version)
    session.commit()
    return version


def assign_assessor(
    session: Session,
    assessor: User,
    course_id: str,
    assigned_by: User,
) -> None:
    session.add(
        RoleAssignment(
            subject_user_id=assessor.id,
            course_id=course_id,
            role=ScopedRole.ASSESSOR,
            version=1,
            assigned_by_user_id=assigned_by.id,
            reason="The assessor is assigned to review formal assessment decisions.",
            assigned_at=NOW,
            valid_from=NOW,
        )
    )
    session.commit()


def seed_review_decision(
    session: Session,
) -> tuple[AssessmentAttempt, SubmissionAttempt, AssessmentDecision, User]:
    attempt, response, criterion, _, owner = build_assessment_attempt(session)
    decision = build_provisional_decision(session, attempt)
    evaluation = CriterionEvaluation(
        assessment_attempt_id=attempt.id,
        criterion_version_id=criterion.id,
        decision=CriterionDecision.MET,
        evidence_references={"evidence": ["frozen-evidence-1"]},
        evaluator_reference="rules.v1",
        model_version="model.v1",
        prompt_version="prompt.v1",
        retrieval_version="retrieval.v1",
        reason="The exact response contains the required explanation.",
    )
    audit = PlatformAuditEvent(
        actor_id=None,
        action="assessment_evaluation.provisional",
        resource_type="assessment_attempt",
        resource_id=attempt.id,
        correlation_id="00000000-0000-4000-8000-000000000012",
        details={"quality_review_status": "REJECTED"},
    )
    session.add_all([evaluation, audit])
    session.commit()
    return attempt, response, decision, owner
