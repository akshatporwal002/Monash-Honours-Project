"""Authorise a new equivalent form without changing an existing result."""

from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.domain.assessment import ResultState
from app.models.assessment import (
    AssessmentApprovalState,
    AssessmentAttempt,
    AssessmentDecision,
    AssessmentDefinitionVersion,
    AssessorReview,
    ReassessmentLink,
    TaskFormVersion,
)
from app.models.assessment_work import AssessmentWorkStart
from app.models.lms import PlatformAuditEvent, SubmissionAttempt, SubmissionDraft
from app.models.persistence import LearningTask
from app.models.reassessment import OutcomeResultPolicy, ReassessmentAuthorisation
from app.models.user import User
from app.schemas.reassessment import (
    EquivalentFormRead,
    OutcomePolicyRead,
    OutcomePolicyWrite,
    ReassessmentRead,
    ReassessmentSetup,
    ReassessmentWrite,
)
from app.services.assessment.access import RoleAssignmentService, ScopedRoleAccessDeniedError
from app.services.assessment.publication import require_learner_task_available
from app.services.assessment.submissions import AssessmentSubmissionService
from app.services.lms import LmsService, LmsServiceError
from app.services.task_review import TaskReviewError


class ReassessmentService:
    def __init__(self, session: Session):
        self.session = session
        self.assignments = RoleAssignmentService(session)

    def policy(self, definition_id):
        return self.session.scalar(
            select(OutcomeResultPolicy).where(
                OutcomeResultPolicy.definition_version_id == definition_id
            )
        )

    def publish_policy(self, actor: User, definition_id: str, command: OutcomePolicyWrite):
        self._lock(actor.id)
        definition = self.session.get(AssessmentDefinitionVersion, definition_id)
        if definition is None:
            raise LmsServiceError(404, "Assessment definition not found")
        self.assignments.require_assessor_access(actor, definition.course_id)
        if (
            definition.approval_state is not AssessmentApprovalState.APPROVED
            or not definition.formal_result_eligible
        ):
            raise LmsServiceError(409, "Publish the assessment standard before its outcome rule")
        prior = self.policy(definition.id)
        if prior:
            if (prior.selection_rule, sorted(prior.required_form_ids), prior.reason) != (
                command.selection_rule,
                sorted(command.required_form_ids),
                command.reason,
            ):
                raise LmsServiceError(
                    409,
                    "This standard already has a published outcome rule; preserve it and approve a new standard version for a policy change",
                )
            self.session.rollback()
            return OutcomePolicyRead.model_validate(prior)
        for form_id in command.required_form_ids:
            form = self.session.get(TaskFormVersion, form_id)
            if form is None or form.assessment_definition_version_id != definition.id:
                raise LmsServiceError(422, "Every required form must belong to this exact standard")
            self._current_form(form)
        policy = OutcomeResultPolicy(
            definition_version_id=definition.id,
            approved_by_user_id=actor.id,
            **command.model_dump(),
        )
        self.session.add(policy)
        self.session.flush()
        self._audit(actor.id, policy.id, "assessment.outcome_policy_published")
        self._commit()
        return OutcomePolicyRead.model_validate(policy)

    def setup(self, actor: User, decision_id: str):
        from app.services.assessment.equivalent_forms import EquivalentFormService

        decision, attempt = self._decision(actor, decision_id)
        policy = self.policy(attempt.assessment_definition_version_id)
        forms = []
        policy_forms = []
        for form in self.session.scalars(
            select(TaskFormVersion)
            .where(
                TaskFormVersion.assessment_definition_version_id
                == attempt.assessment_definition_version_id
            )
            .order_by(TaskFormVersion.id)
        ):
            try:
                task = self._current_form(form)
                policy_forms.append(
                    EquivalentFormRead(id=form.id, task_id=task.id, task_title=task.title)
                )
                task = self._fresh_target(attempt, form)
            except (LmsServiceError, TaskReviewError):
                continue
            forms.append(EquivalentFormRead(id=form.id, task_id=task.id, task_title=task.title))
        grant = self._latest_grant(attempt.id)
        return ReassessmentSetup(
            definition_version_id=attempt.assessment_definition_version_id,
            policy=OutcomePolicyRead.model_validate(policy) if policy else None,
            forms=forms,
            policy_forms=policy_forms,
            fresh_tasks=EquivalentFormService(self.session).candidates(
                attempt.assessment_definition_version_id
            ),
            authorisation=self.read_grant(grant) if grant else None,
        )

    def authorise(self, actor: User, decision_id: str, command: ReassessmentWrite):
        self._lock(actor.id)
        decision, attempt = self._decision(actor, decision_id)
        policy = self.policy(attempt.assessment_definition_version_id)
        if policy is None:
            raise LmsServiceError(
                409, "Publish an outcome selection rule before authorising reassessment"
            )
        existing = self._latest_grant(attempt.id)
        if existing:
            if (
                existing.task_form_version_id,
                existing.reason,
                existing.learner_notice,
                existing.decision_revision,
                existing.approved_by_user_id,
            ) == (
                command.task_form_version_id,
                command.reason,
                command.learner_notice,
                command.expected_decision_revision,
                actor.id,
            ):
                self.session.rollback()
                return self.read_grant(existing)
            retained = self.read_grant(existing)
            if retained.available or retained.replacement_response_id:
                raise LmsServiceError(
                    409, "A different reassessment is already authorised for this attempt"
                )
        if self._revision(decision.id) != command.expected_decision_revision:
            raise LmsServiceError(
                409,
                "The decision changed; review its current history before authorising reassessment",
            )
        self._eligible(decision)
        form = self.session.get(TaskFormVersion, command.task_form_version_id)
        task = self._fresh_target(attempt, form)
        # A learner may have retained unrelated work even when no formal start exists.
        draft = self.session.scalar(
            select(SubmissionDraft).where(
                SubmissionDraft.student_id == attempt.student_id, SubmissionDraft.task_id == task.id
            )
        )
        if draft and (draft.answer or draft.code or draft.circuit or draft.episode):
            raise LmsServiceError(
                409, "Choose a fresh task; the learner already has saved work on this form"
            )
        learner = self.session.get(User, attempt.student_id)
        LmsService(self.session).get_draft(learner, attempt.task_id)
        grant = ReassessmentAuthorisation(
            prior_attempt_id=attempt.id,
            prior_decision_id=decision.id,
            decision_revision=command.expected_decision_revision,
            revision=existing.revision + 1 if existing else 1,
            student_id=attempt.student_id,
            task_id=task.id,
            task_form_version_id=form.id,
            policy_id=policy.id,
            approved_by_user_id=actor.id,
            reason=command.reason,
            learner_notice=command.learner_notice,
        )
        self.session.add(grant)
        self.session.flush()
        self._audit(actor.id, grant.id, "assessment.reassessment_authorised")
        self._commit()
        return self.read_grant(grant)

    def for_task(self, student_id, task_id):
        return self.session.scalar(
            select(ReassessmentAuthorisation).where(
                ReassessmentAuthorisation.student_id == student_id,
                ReassessmentAuthorisation.task_id == task_id,
            )
        )

    def require_start(self, student_id, task, versions):
        grant = self.for_task(student_id, task.id)
        if grant is None:
            return
        self._active_grant(grant)
        if versions is None or versions.task_form_version_id != grant.task_form_version_id:
            raise LmsServiceError(
                409, "The authorised reassessment form changed; ask your assessor to review it"
            )
        linked = self.session.scalar(
            select(ReassessmentLink.id).where(
                ReassessmentLink.prior_assessment_attempt_id == grant.prior_attempt_id
            )
        )
        if linked:
            raise LmsServiceError(
                409,
                "This fresh reassessment has already been submitted; request another authorised form if needed",
            )

    def link_attempt(self, attempt):
        grant = self.for_task(attempt.student_id, attempt.task_id)
        if grant is None:
            return
        self._active_grant(grant)
        policy = self.session.get(OutcomeResultPolicy, grant.policy_id)
        if (attempt.task_form_version_id, attempt.assessment_definition_version_id) != (
            grant.task_form_version_id,
            policy.definition_version_id,
        ):
            raise LmsServiceError(409, "The new attempt must preserve the authorised standard")
        self.session.add(
            ReassessmentLink(
                prior_assessment_attempt_id=grant.prior_attempt_id,
                replacement_assessment_attempt_id=attempt.id,
                approved_by_user_id=grant.approved_by_user_id,
                reason=grant.reason,
            )
        )
        self.session.flush()

    def bypass_prerequisites(self, student_id, task_id):
        grant = self.for_task(student_id, task_id)
        if grant is None:
            return False
        try:
            self._active_grant(grant)
        except (LmsServiceError, TaskReviewError, ScopedRoleAccessDeniedError):
            return False
        return True

    def read_grant(self, grant):
        task = self.session.get(LearningTask, grant.task_id)
        replacement = self.session.scalar(
            select(AssessmentAttempt)
            .join(
                ReassessmentLink,
                ReassessmentLink.replacement_assessment_attempt_id == AssessmentAttempt.id,
            )
            .where(
                ReassessmentLink.prior_assessment_attempt_id == grant.prior_attempt_id,
                AssessmentAttempt.task_form_version_id == grant.task_form_version_id,
            )
        )
        available = replacement is None
        try:
            self._active_grant(grant)
        except (LmsServiceError, TaskReviewError, ScopedRoleAccessDeniedError):
            available = False
        return ReassessmentRead(
            id=grant.id,
            task_id=grant.task_id,
            task_title=task.title,
            learner_notice=grant.learner_notice,
            created_at=grant.created_at,
            replacement_response_id=replacement.response_version_id if replacement else None,
            available=available,
        )

    def _active_grant(self, grant):
        if self._latest_grant(grant.prior_attempt_id).id != grant.id:
            raise LmsServiceError(409, "A later authorisation supersedes this reassessment")
        prior = self.session.get(AssessmentAttempt, grant.prior_attempt_id)
        actor = self.session.get(User, grant.approved_by_user_id)
        try:
            self.assignments.require_assessor_access(actor, prior.course_id)
        except ScopedRoleAccessDeniedError as error:
            raise LmsServiceError(
                409, "The reassessment authorisation needs review by a currently assigned assessor"
            ) from error
        decision = self.session.get(AssessmentDecision, grant.prior_decision_id)
        self._eligible(decision)
        if self._revision(decision.id) != grant.decision_revision:
            raise LmsServiceError(
                409, "The original decision changed after reassessment was authorised"
            )
        self._current_form(self.session.get(TaskFormVersion, grant.task_form_version_id))

    def _fresh_target(self, attempt, form):
        if (
            form is None
            or form.assessment_definition_version_id != attempt.assessment_definition_version_id
            or form.id == attempt.task_form_version_id
            or form.learning_task_id == attempt.task_id
        ):
            raise LmsServiceError(
                422, "Choose a fresh equivalent form under the same approved standard"
            )
        task = self._current_form(form)
        if (
            self.session.scalar(
                select(AssessmentWorkStart.id).where(
                    AssessmentWorkStart.student_id == attempt.student_id,
                    AssessmentWorkStart.task_id == task.id,
                )
            )
            or self.session.scalar(
                select(ReassessmentAuthorisation.id).where(
                    ReassessmentAuthorisation.student_id == attempt.student_id,
                    ReassessmentAuthorisation.task_id == task.id,
                )
            )
            or self.session.scalar(
                select(SubmissionAttempt.id).where(
                    SubmissionAttempt.student_id == attempt.student_id,
                    SubmissionAttempt.task_id == task.id,
                )
            )
        ):
            raise LmsServiceError(
                409,
                "Choose a fresh task that the learner has not already attempted or been assigned for reassessment",
            )
        return task

    def _current_form(self, form):
        task = self.session.get(LearningTask, form.learning_task_id) if form else None
        if task is None:
            raise LmsServiceError(409, "The approved task is unavailable")
        require_learner_task_available(self.session, task)
        versions = AssessmentSubmissionService(self.session).frozen_versions_for_task(task)
        if versions is None or versions.task_form_version_id != form.id:
            raise LmsServiceError(409, "The equivalent form is not currently published")
        return task

    def _decision(self, actor, decision_id):
        decision = self.session.get(AssessmentDecision, decision_id)
        if decision is None:
            raise LmsServiceError(404, "Assessment decision not found")
        attempt = self.session.get(AssessmentAttempt, decision.assessment_attempt_id)
        self.assignments.require_assessor_access(actor, attempt.course_id)
        return decision, attempt

    def _latest_grant(self, attempt_id):
        return self.session.scalar(
            select(ReassessmentAuthorisation)
            .where(ReassessmentAuthorisation.prior_attempt_id == attempt_id)
            .order_by(ReassessmentAuthorisation.revision.desc())
            .limit(1)
        )

    @staticmethod
    def _eligible(decision):
        if decision.result_state is not ResultState.VOID and not (
            decision.result_state in {ResultState.CONFIRMED, ResultState.OVERRIDDEN}
            and decision.result
            and decision.result.value == "INCOMPLETE"
        ):
            raise LmsServiceError(
                409, "Reassessment requires a confirmed incomplete result or an authorised void"
            )

    def _revision(self, decision_id):
        return (
            self.session.scalar(
                select(AssessorReview.review_revision)
                .where(AssessorReview.assessment_decision_id == decision_id)
                .order_by(AssessorReview.review_revision.desc())
                .limit(1)
            )
            or 0
        )

    def _lock(self, actor_id):
        self.session.execute(
            update(User).where(User.id == actor_id).values(id=User.id, updated_at=User.updated_at)
        )

    def _audit(self, actor_id, record_id, action):
        self.session.add(
            PlatformAuditEvent(
                actor_id=actor_id,
                action=action,
                resource_type="assessment",
                resource_id=record_id,
                correlation_id=str(uuid4()),
                details={},
            )
        )

    def _commit(self):
        try:
            self.session.commit()
        except (IntegrityError, OperationalError) as error:
            self.session.rollback()
            raise LmsServiceError(
                409, "The assessment changed concurrently; refresh before retrying"
            ) from error
