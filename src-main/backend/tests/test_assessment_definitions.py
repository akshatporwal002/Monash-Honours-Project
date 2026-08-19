from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.domain.assessment import AssessmentPurpose, BloomKnowledge, BloomProcess
from app.models.assessment import (
    AssessmentApprovalState,
    AssessmentDefinitionVersion,
    OutcomeVersion,
    TaskApproval,
)
from app.models.enums import TaskType
from app.models.lms import Course, CourseModule, LearningOutcome, OutcomeKind
from app.models.persistence import LearningTask
from app.models.user import User, UserRole
from app.services.assessment.definitions import (
    AssessmentDefinitionConflictError,
    AssessmentDefinitionDraft,
    AssessmentDefinitionService,
    AssessmentDefinitionValidationError,
    CriterionDraft,
    TaskFormDraft,
)

NOW = datetime(2026, 8, 16, 1, 0, tzinfo=UTC)


def _service(session: Session) -> AssessmentDefinitionService:
    return AssessmentDefinitionService(
        session,
        correlation_id="00000000-0000-4000-8000-000000000601",
        now=lambda: NOW,
    )


def _setup(session: Session) -> tuple[str, str, int, str]:
    owner = User(
        email="definition-assessor@example.edu",
        password_hash=hash_password("definition-test-password"),
        full_name="Definition Assessor",
        role=UserRole.EDUCATOR,
    )
    session.add(owner)
    session.flush()
    course = Course(educator_id=owner.id, code="QNT601", title="Definition service course")
    session.add(course)
    session.flush()
    module = CourseModule(course_id=course.id, title="Quantum evidence", position=1)
    session.add(module)
    session.flush()
    outcome = LearningOutcome(
        module_id=module.id,
        title="Analyse interference evidence",
        statement="Analyse how interference evidence supports a quantum claim.",
        kind=OutcomeKind.WEEKLY,
        week_number=1,
        position=1,
    )
    session.add(outcome)
    session.flush()
    session.add(
        LearningTask(
            slug="definition-service-task",
            title="Interference analysis",
            module="Quantum evidence",
            description="Analyse an interference observation.",
            instructions="Use the observed pattern to justify the claim.",
            task_type=TaskType.QUIZ,
            difficulty="intermediate",
            points=0,
            position=1,
            course_id=course.id,
            module_id=module.id,
            learning_outcome_id=outcome.id,
        )
    )
    source = OutcomeVersion(
        course_id=course.id,
        learning_outcome_id=outcome.id,
        version=1,
        owner_user_id=owner.id,
        created_by_user_id=owner.id,
        title=outcome.title,
        statement=outcome.statement,
        source_version="course-source.v1",
        approval_state=AssessmentApprovalState.APPROVED,
        approved_at=NOW,
        approved_by_user_id=owner.id,
    )
    session.add(source)
    session.commit()
    return course.id, outcome.id, owner.id, source.id


def _draft(
    *,
    outcome_version_id: str,
    task_id: str,
    task_processes: list[str] | None = None,
    access_preserves_construct: bool = True,
    claim: str = "The learner can analyse interference evidence to support a claim.",
) -> AssessmentDefinitionDraft:
    return AssessmentDefinitionDraft(
        outcome_version_id=outcome_version_id,
        claim=claim,
        supporting_evidence={"observable": ["links evidence to the claim"]},
        contradicting_evidence={"observable": ["reverses the evidence relationship"]},
        insufficient_evidence={"observable": ["names evidence without analysis"]},
        task_conditions={"response_mode": "written"},
        next_action_contract={"when_incomplete": "offer reassessment when approved"},
        purpose=AssessmentPurpose.SUMMATIVE,
        permitted_tools={"allowed": ["course notes"]},
        instructional_support={"maximum_level": "approved"},
        access_conditions={
            "modes": [
                {
                    "mode": "screen_reader",
                    "preserves_construct": access_preserves_construct,
                }
            ]
        },
        transfer_rule={"required": True, "new_context": "another quantum circuit"},
        evidence_sufficiency={"requires": ["criterion evidence"]},
        formal_result_eligible=False,
        bloom_process=BloomProcess.ANALYSE,
        knowledge_dimension=BloomKnowledge.CONCEPTUAL,
        criteria=[
            CriterionDraft(
                stable_key="evidence_to_claim",
                learner_description="Explain how the evidence supports the claim.",
                evidence_description="Connects the observed pattern to the claim.",
                mandatory=True,
                evidence_source_types=["learner_response"],
                met_rule="The response makes the relationship explicit.",
                not_met_rule="The response omits the relationship.",
                not_evaluable_rule="The response is unavailable or invalid.",
                approved_anchors={"met": ["valid evidence-to-claim explanation"]},
                critical_error_rules={"errors": ["reverses the evidence relationship"]},
            )
        ],
        pass_rule_expression={
            "operator": "ALL_OF",
            "clauses": [{"criterion": "evidence_to_claim"}],
        },
        task_forms=[
            TaskFormDraft(
                learning_task_id=task_id,
                source_version="learning-task.v1",
                source_digest="sha256:definition-service-task",
                task_family="written_analysis",
                context={"scenario": "interference observation"},
                constraints={
                    "response_format": "text",
                    "elicited_bloom_processes": task_processes or ["ANALYSE"],
                },
            )
        ],
    )


def _task_id(session: Session) -> str:
    return session.scalar(select(LearningTask.id))  # type: ignore[return-value]


def test_stale_definition_update_returns_conflict(db_session: Session) -> None:
    course_id, outcome_id, owner_id, outcome_version_id = _setup(db_session)
    service = _service(db_session)
    created = service.create_draft(
        course_id=course_id,
        learning_outcome_id=outcome_id,
        actor_user_id=owner_id,
        draft=_draft(outcome_version_id=outcome_version_id, task_id=_task_id(db_session)),
    )

    with pytest.raises(AssessmentDefinitionConflictError) as error:
        service.update_draft(
            course_id=course_id,
            assessment_definition_id=created.assessment_definition_id,
            expected_version=2,
            actor_user_id=owner_id,
            draft=_draft(outcome_version_id=outcome_version_id, task_id=_task_id(db_session)),
        )

    assert error.value.status_code == 409
    assert (
        len(
            service.repository.list_versions(
                course_id=course_id,
                assessment_definition_id=created.assessment_definition_id,
            )
        )
        == 1
    )
    other_course = Course(
        educator_id=owner_id,
        code="QNT602",
        title="Other definition service course",
    )
    db_session.add(other_course)
    db_session.commit()
    with pytest.raises(AssessmentDefinitionConflictError):
        service.approve(
            course_id=other_course.id,
            assessment_definition_id=created.assessment_definition_id,
            expected_version=1,
            actor_user_id=owner_id,
            approval_reason="This cross-course action must not leak a definition.",
        )


def test_incomplete_blueprint_cannot_be_approved(db_session: Session) -> None:
    course_id, outcome_id, owner_id, outcome_version_id = _setup(db_session)
    service = _service(db_session)
    created = service.create_draft(
        course_id=course_id,
        learning_outcome_id=outcome_id,
        actor_user_id=owner_id,
        draft=_draft(
            outcome_version_id=outcome_version_id,
            task_id=_task_id(db_session),
            claim="",
        ),
    )

    with pytest.raises(AssessmentDefinitionValidationError, match="claim is required"):
        service.approve(
            course_id=course_id,
            assessment_definition_id=created.assessment_definition_id,
            expected_version=1,
            actor_user_id=owner_id,
            approval_reason="Ready for formal assessment.",
        )

    stored = db_session.get(AssessmentDefinitionVersion, created.id)
    assert stored is not None
    assert stored.approval_state is AssessmentApprovalState.DRAFT
    assert all(
        row.approval_state is AssessmentApprovalState.DRAFT
        for row in [
            *stored.bloom_target_versions,
            *stored.criterion_versions,
            *stored.pass_rule_versions,
            *stored.task_form_versions,
        ]
    )
    assert db_session.scalars(select(TaskApproval)).all() == []


def test_analyse_target_rejects_recall_only_task_form(db_session: Session) -> None:
    course_id, outcome_id, owner_id, outcome_version_id = _setup(db_session)
    service = _service(db_session)
    created = service.create_draft(
        course_id=course_id,
        learning_outcome_id=outcome_id,
        actor_user_id=owner_id,
        draft=_draft(
            outcome_version_id=outcome_version_id,
            task_id=_task_id(db_session),
            task_processes=["REMEMBER"],
        ),
    )

    with pytest.raises(AssessmentDefinitionValidationError, match="target Bloom process"):
        service.approve(
            course_id=course_id,
            assessment_definition_id=created.assessment_definition_id,
            expected_version=1,
            actor_user_id=owner_id,
            approval_reason="Ready for formal assessment.",
        )


def test_access_mode_must_preserve_the_construct(db_session: Session) -> None:
    course_id, outcome_id, owner_id, outcome_version_id = _setup(db_session)
    service = _service(db_session)
    created = service.create_draft(
        course_id=course_id,
        learning_outcome_id=outcome_id,
        actor_user_id=owner_id,
        draft=_draft(
            outcome_version_id=outcome_version_id,
            task_id=_task_id(db_session),
            access_preserves_construct=False,
        ),
    )

    with pytest.raises(AssessmentDefinitionValidationError, match="changes the intended construct"):
        service.approve(
            course_id=course_id,
            assessment_definition_id=created.assessment_definition_id,
            expected_version=1,
            actor_user_id=owner_id,
            approval_reason="Ready for formal assessment.",
        )


def test_approval_is_atomic_and_keeps_prior_versions(db_session: Session) -> None:
    course_id, outcome_id, owner_id, outcome_version_id = _setup(db_session)
    service = _service(db_session)
    first = service.create_draft(
        course_id=course_id,
        learning_outcome_id=outcome_id,
        actor_user_id=owner_id,
        draft=_draft(outcome_version_id=outcome_version_id, task_id=_task_id(db_session)),
    )
    service.approve(
        course_id=course_id,
        assessment_definition_id=first.assessment_definition_id,
        expected_version=1,
        actor_user_id=owner_id,
        approval_reason="The first version is ready.",
    )
    with pytest.raises(AssessmentDefinitionConflictError):
        service.approve(
            course_id=course_id,
            assessment_definition_id=first.assessment_definition_id,
            expected_version=1,
            actor_user_id=owner_id,
            approval_reason="A second approval must conflict.",
        )
    second = service.update_draft(
        course_id=course_id,
        assessment_definition_id=first.assessment_definition_id,
        expected_version=1,
        actor_user_id=owner_id,
        draft=_draft(outcome_version_id=outcome_version_id, task_id=_task_id(db_session)),
    )
    service.approve(
        course_id=course_id,
        assessment_definition_id=first.assessment_definition_id,
        expected_version=2,
        actor_user_id=owner_id,
        approval_reason="The revised version is ready.",
    )

    versions = service.repository.list_versions(
        course_id=course_id,
        assessment_definition_id=first.assessment_definition_id,
    )
    assert [(row.version, row.approval_state) for row in versions] == [
        (1, AssessmentApprovalState.APPROVED),
        (2, AssessmentApprovalState.APPROVED),
    ]
    assert second.version == 2
    assert db_session.scalars(select(TaskApproval)).all()
    assert len(db_session.scalars(select(TaskApproval)).all()) == 2
