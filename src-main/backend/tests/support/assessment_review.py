"""Private, newly reviewed work for one browser review-action execution."""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.domain.assessment import AssessmentPurpose, BloomKnowledge, BloomProcess, CriterionDecision
from app.models.assessment import AssessmentAttempt, CriterionEvaluation, TaskFormVersion
from app.models.lms import CourseState, LearningOutcome, PlatformAuditEvent
from app.models.persistence import LearningTask
from app.models.user import User, UserRole
from app.schemas.lms import SubmissionCreate
from app.services.assessment.definitions import (
    AssessmentDefinitionDraft,
    AssessmentDefinitionService,
    CriterionDraft,
    TaskFormDraft,
)
from app.services.lms import LmsService
from support.assessment import build_provisional_decision
from support.assessment_authoring import seed_authoring_context
from support.task_review import approve_sourced_fixture_task

ANSWER = "The response links the observation to the claim."


def seed_review_context(session: Session) -> dict[str, str]:
    context = seed_authoring_context(session)
    actor = session.scalar(select(User).where(User.email == context["educator_email"]))
    task = session.get(LearningTask, context["task_id"])
    outcome = session.get(LearningOutcome, context["outcome_id"])
    task.title = "Interference explanation"
    task.description = "Explain how an interference observation supports a quantum claim."
    task.instructions = "Link the observation to the claim."
    task.expected_answer = ANSWER
    outcome.title = "Explain the evidence relationship"
    outcome.statement = "Explain how the observation supports the claim."
    session.commit()
    approve_sourced_fixture_task(session, task)
    lms = LmsService(session)
    source = lms.create_assessment_outcome_version(actor, context["course_id"], outcome.id)
    definition_service = AssessmentDefinitionService(session)
    definition = definition_service.create_draft(
        course_id=context["course_id"],
        learning_outcome_id=outcome.id,
        actor_user_id=actor.id,
        draft=AssessmentDefinitionDraft(
            outcome_version_id=source.id,
            claim="Explain how the observation supports the claim.",
            supporting_evidence={"observable": ["links the observation to the claim"]},
            contradicting_evidence={"observable": ["reverses the relationship"]},
            insufficient_evidence={"observable": ["names the observation without explanation"]},
            task_conditions={"response_mode": "written"},
            next_action_contract={"when_incomplete": "request a fresh approved task"},
            purpose=AssessmentPurpose.SUMMATIVE,
            permitted_tools={"allowed": ["course notes"]},
            instructional_support={"allowed": ["approved conceptual hints"]},
            access_conditions={"modes": [{"mode": "screen_reader", "preserves_construct": True}]},
            transfer_rule={
                "required": False,
                "reason": "This fixture isolates existing decision review.",
            },
            evidence_sufficiency={"requires": ["criterion evidence"]},
            formal_result_eligible=True,
            bloom_process=BloomProcess.UNDERSTAND,
            knowledge_dimension=BloomKnowledge.CONCEPTUAL,
            criteria=[
                CriterionDraft(
                    stable_key="evidence_to_claim",
                    learner_description="Explain how the evidence supports the claim.",
                    evidence_description="Connect the observation to the claim.",
                    mandatory=True,
                    evidence_source_types=["learner_response"],
                    met_rule="The response makes the relationship explicit.",
                    not_met_rule="The response omits the relationship.",
                    not_evaluable_rule="The response is unavailable or invalid.",
                    approved_anchors={"met": [ANSWER]},
                    critical_error_rules={"errors": ["reverses the relationship"]},
                )
            ],
            pass_rule_expression={
                "operator": "ALL_OF",
                "clauses": [{"criterion": "evidence_to_claim"}],
            },
            task_forms=[
                TaskFormDraft(
                    learning_task_id=task.id,
                    source_version="synthetic-review-fixture.v1",
                    source_digest="synthetic-review-fixture",
                    task_family="written_explanation",
                    context={"scenario": "interference observation"},
                    constraints={
                        "response_format": "text",
                        "elicited_bloom_processes": ["UNDERSTAND"],
                    },
                )
            ],
        ),
    )
    definition = definition_service.approve(
        course_id=context["course_id"],
        assessment_definition_id=definition.assessment_definition_id,
        expected_version=1,
        actor_user_id=actor.id,
        approval_reason="New synthetic assessment explicitly reviewed for this isolated browser test.",
    )
    form = session.scalar(
        select(TaskFormVersion).where(
            TaskFormVersion.assessment_definition_version_id == definition.id
        )
    )
    student = User(
        email=f"review-student-{uuid4().hex}@example.edu",
        full_name="Review fixture learner",
        password_hash=hash_password("assessment-review-student-test-password"),
        role=UserRole.STUDENT,
    )
    session.add(student)
    session.commit()
    lms.set_course_state(actor, context["course_id"], CourseState.PUBLISHED)
    lms.enroll_student(actor, context["course_id"], student.id)
    started = lms.start_assessment_work(student, task.id, form.id)
    response = lms.submit(
        student,
        task.id,
        SubmissionCreate(
            assessment_work_start_id=started.assessment_work_start_id,
            answer=ANSWER,
            idempotency_key=f"review-response-{uuid4().hex}",
        ),
    )
    attempt = session.scalar(
        select(AssessmentAttempt).where(AssessmentAttempt.response_version_id == response.id)
    )
    decision = build_provisional_decision(session, attempt, suffix=uuid4().hex)
    # Preserve the old synthetic evaluator provenance required by the review journey.
    session.add(
        CriterionEvaluation(
            assessment_attempt_id=attempt.id,
            criterion_version_id=definition.criterion_versions[0].id,
            decision=CriterionDecision.MET,
            evidence_references={"evidence": [response.id]},
            evaluator_reference="rules.v1",
            model_version="model.v1",
            prompt_version="prompt.v1",
            retrieval_version="retrieval.v1",
            reason="The exact response contains the required explanation.",
        )
    )
    session.add(
        PlatformAuditEvent(
            actor_id=None,
            action="assessment_evaluation.provisional",
            resource_type="assessment_attempt",
            resource_id=attempt.id,
            correlation_id=str(uuid4()),
            details={"quality_review_status": "REJECTED"},
        )
    )
    session.commit()
    return {
        "educator_email": context["educator_email"],
        "educator_password": context["educator_password"],
        "course_id": attempt.course_id,
        "attempt_id": attempt.id,
        "response_id": response.id,
        "decision_id": decision.id,
    }
