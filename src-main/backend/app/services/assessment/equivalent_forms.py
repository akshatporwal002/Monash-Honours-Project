"""Publish additional reviewed forms without revising the assessment standard."""

from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, update

from app.models.assessment import (
    AssessmentApprovalState,
    AssessmentDefinitionVersion,
    OutcomeVersion,
    TaskApproval,
    TaskForm,
    TaskFormVersion,
)
from app.models.lms import Course, PlatformAuditEvent
from app.models.persistence import LearningTask
from app.schemas.reassessment import EquivalentFormRead, FreshTaskRead
from app.services.assessment.access import RoleAssignmentService
from app.services.assessment.alignment import (
    AssessmentAlignmentError,
    validate_definition_alignment,
)
from app.services.assessment.publication import current_form_review
from app.services.episode_contract import validate_reviewed_episode_plan
from app.services.lms import LmsServiceError
from app.services.task_review import TaskReviewError, TaskReviewService


class EquivalentFormService:
    def __init__(self, session):
        self.session = session

    def candidates(self, definition_id):
        definition = self.session.get(AssessmentDefinitionVersion, definition_id)
        outcome = self.session.get(OutcomeVersion, definition.outcome_version_id)
        bound = select(TaskFormVersion.learning_task_id)
        tasks = self.session.scalars(
            select(LearningTask)
            .where(
                LearningTask.course_id == definition.course_id,
                LearningTask.learning_outcome_id == outcome.learning_outcome_id,
                LearningTask.id.not_in(bound),
            )
            .order_by(LearningTask.position, LearningTask.id)
        )
        review = TaskReviewService(self.session)
        result = []
        for task in tasks:
            try:
                review.require_available(task)
                review.validate_ready(task, require_sources=True)
            except TaskReviewError:
                continue
            revision = review.latest_revision(task.id)
            if revision:
                result.append(
                    FreshTaskRead(
                        task_id=task.id,
                        title=task.title,
                        prompt=task.description,
                        instructions=task.instructions,
                        revision_id=revision.id,
                    )
                )
        return result

    def publish(self, actor, definition_id, command):
        definition = self.session.get(AssessmentDefinitionVersion, definition_id)
        if definition is None:
            raise LmsServiceError(404, "Standard not found")
        self.session.execute(
            update(Course)
            .where(Course.id == definition.course_id)
            .values(id=Course.id, updated_at=Course.updated_at)
        )
        RoleAssignmentService(self.session).require_assessor_access(actor, definition.course_id)
        if (
            definition.approval_state is not AssessmentApprovalState.APPROVED
            or not definition.formal_result_eligible
        ):
            raise LmsServiceError(409, "The original standard must remain approved")
        template = self.session.get(TaskFormVersion, command.template_form_id)
        if (
            template is None
            or template.assessment_definition_version_id != definition_id
            or template.approval_state is not AssessmentApprovalState.APPROVED
        ):
            raise LmsServiceError(422, "Choose an approved template from this standard")
        current_form_review(self.session, template)
        existing = self.session.scalar(
            select(TaskFormVersion).where(TaskFormVersion.learning_task_id == command.task_id)
        )
        if existing:
            approval = self.session.scalar(
                select(TaskApproval).where(TaskApproval.task_form_version_id == existing.id)
            )
            if (
                existing.assessment_definition_version_id == definition_id
                and existing.task_revision_id == command.revision_id
                and existing.context.get("equivalent_to_form_id") == command.template_form_id
                and approval
                and approval.actor_user_id == actor.id
                and approval.approval_reason == command.reason
            ):
                self.session.rollback()
                return EquivalentFormRead(
                    id=existing.id,
                    task_id=command.task_id,
                    task_title=self.session.get(LearningTask, command.task_id).title,
                )
            raise LmsServiceError(409, "This task already has an assessment form")
        candidate = next(
            (item for item in self.candidates(definition_id) if item.task_id == command.task_id),
            None,
        )
        if candidate is None or candidate.revision_id != command.revision_id:
            raise LmsServiceError(
                409, "The fresh task changed or needs teaching and source approval"
            )
        task = self.session.get(LearningTask, command.task_id)
        original = self.session.get(LearningTask, template.learning_task_id)
        if task.task_type != original.task_type:
            raise LmsServiceError(422, "The equivalent form must preserve the response mode")
        review = TaskReviewService(self.session)
        revision = review.latest_revision(task.id)
        now = datetime.now(UTC)
        form = TaskForm(assessment_definition_id=definition.assessment_definition_id)
        self.session.add(form)
        self.session.flush()
        row = TaskFormVersion(
            task_form_id=form.id,
            assessment_definition_version_id=definition_id,
            course_id=definition.course_id,
            learning_task_id=task.id,
            task_revision_id=revision.id,
            version=1,
            owner_user_id=actor.id,
            created_by_user_id=actor.id,
            source_version=f"task-revision:{revision.id}",
            source_digest=revision.content_digest,
            task_family=template.task_family,
            context={"scenario": task.description, "equivalent_to_form_id": template.id},
            constraints=deepcopy(template.constraints),
        )
        plan = validate_reviewed_episode_plan(task.marking_criteria)
        if plan:
            row.constraints = {**row.constraints, "episode_plan": plan.model_dump(mode="json")}
        elif "episode_plan" in row.constraints:
            raise LmsServiceError(422, "The fresh form needs its own reviewed episode plan")
        try:
            validate_definition_alignment(
                claim=definition.claim,
                supporting_evidence=definition.supporting_evidence,
                contradicting_evidence=definition.contradicting_evidence,
                insufficient_evidence=definition.insufficient_evidence,
                task_conditions=definition.task_conditions,
                next_action_contract=definition.next_action_contract,
                permitted_tools=definition.permitted_tools,
                instructional_support=definition.instructional_support,
                access_conditions=definition.access_conditions,
                transfer_rule=definition.transfer_rule,
                evidence_sufficiency=definition.evidence_sufficiency,
                bloom_process=definition.bloom_target_versions[0].bloom_process,
                criteria=definition.criterion_versions,
                task_forms=[row],
            )
        except AssessmentAlignmentError as error:
            raise LmsServiceError(422, str(error)) from error
        self.session.add(row)
        self.session.flush()
        teaching = current_form_review(self.session, row)
        row.approval_state = AssessmentApprovalState.APPROVED
        row.approved_at = now
        row.approved_by_user_id = actor.id
        self.session.add(
            TaskApproval(
                course_id=definition.course_id,
                assessment_definition_version_id=definition_id,
                task_form_version_id=row.id,
                task_review_event_id=teaching.id,
                actor_user_id=actor.id,
                approval_reason=command.reason,
                approval_state=AssessmentApprovalState.APPROVED,
                approved_at=now,
                approved_by_user_id=actor.id,
            )
        )
        self.session.add(
            PlatformAuditEvent(
                actor_id=actor.id,
                action="assessment.equivalent_form_published",
                resource_type="task_form_version",
                resource_id=row.id,
                correlation_id=str(uuid4()),
                details={"definition_version_id": definition_id},
            )
        )
        self.session.commit()
        return EquivalentFormRead(id=row.id, task_id=task.id, task_title=task.title)
