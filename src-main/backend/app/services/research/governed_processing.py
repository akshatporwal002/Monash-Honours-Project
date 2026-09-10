"""Adapters for the activation seam; legacy pairs never acquire retrospective consent."""

from dataclasses import replace

from sqlalchemy import select

from app.core.config import settings
from app.models.lms import SubmissionAttempt
from app.models.persistence import LearningTask, WorkflowRun
from app.models.research_governance import ResearchCaseGovernance
from app.services.learning_events import HmacSha256Pseudonymizer
from app.services.research.governance import (
    GovernanceDenied,
    ResearchGovernanceService,
    lock_governance_write,
    utc,
)
from app.services.research.repository import SqlAlchemyResearchJobRepository
from app.services.research.worker import BaselineJobExecutor


class GovernedResearchJobRepository(SqlAlchemyResearchJobRepository):
    def create_pair(self, seed):
        try:
            lock_governance_write(self._session)
            self._create_governed_pair(seed)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def _create_governed_pair(self, seed):
        governance = ResearchGovernanceService(self._session, now=self._now)
        workflow = self._session.get(WorkflowRun, seed.workflow_run_id)
        attempt = self._session.get(SubmissionAttempt, workflow.submission_id) if workflow else None
        task = self._session.get(LearningTask, attempt.task_id) if attempt else None
        if (
            not attempt
            or not task
            or task.course_id != seed.course_id
            or task.id != seed.task_id
            or workflow.task_id != task.id
            or workflow.course_id != task.course_id
        ):
            raise GovernanceDenied("case_scope_mismatch")
        scope, consent = governance.processing_scope(task.course_id, attempt.student_id)
        if min(utc(workflow.started_at), utc(attempt.submitted_at)) < utc(consent.recorded_at):
            raise GovernanceDenied("historical_use_not_approved")
        secret = settings.learning_event_pseudonym_secret
        if secret is None:
            raise GovernanceDenied("pseudonym_key_unavailable")
        pseudonyms = HmacSha256Pseudonymizer(secret.get_secret_value())
        seed = replace(
            seed,
            pseudonymous_user_id=pseudonyms.pseudonymize(
                f"study:{scope.study_id}:actor", str(attempt.student_id)
            ),
            pseudonymous_submission_reference=pseudonyms.pseudonymize(
                f"study:{scope.study_id}:submission", attempt.id
            ),
        )
        binding = self._session.scalar(
            select(ResearchCaseGovernance).where(ResearchCaseGovernance.case_id == seed.case_id)
        )
        if binding:
            governance.require_case(seed.case_id)
            if binding.scope_id != scope.id or binding.consent_id != consent.id:
                raise GovernanceDenied("case_scope_mismatch")
        else:
            if self._case_rows(seed.case_id):
                raise GovernanceDenied("legacy_case_unapproved")
            self._session.add(
                ResearchCaseGovernance(
                    case_id=seed.case_id,
                    scope_id=scope.id,
                    consent_id=consent.id,
                    course_id=task.course_id,
                    pseudonymous_user_id=seed.pseudonymous_user_id,
                )
            )
        # Binding and both condition rows commit together using the existing replay guard.
        super().create_pair(seed)

    def complete(self, claim, completion, *, completed_at):
        try:
            lock_governance_write(self._session)
            ResearchGovernanceService(self._session, now=self._now).require_case(claim.case_id)
            return super().complete(claim, completion, completed_at=completed_at)
        except Exception:
            self._session.rollback()
            raise


def governed_baseline_executor(session, context_provider, generator, judge, **kwargs):
    """Later activation must use this factory, after institutional and release review."""
    governance = ResearchGovernanceService(session, now=kwargs.get("now"))
    return BaselineJobExecutor(
        GovernedResearchJobRepository(session, now=governance.now),
        GovernedBaselineContext(session, context_provider, governance),
        generator,
        judge,
        check_eligibility=lambda claim: governance.require_case(claim.case_id),
        **kwargs,
    )


class GovernedBaselineContext:
    """Prevent an adapter from crossing workflow, course, task, or learner boundaries."""

    def __init__(self, session, provider, governance):
        self.session = session
        self.provider = provider
        self.governance = governance

    async def get_context(self, workflow_id):
        binding = self.governance.require_case(workflow_id)
        workflow = self.session.get(WorkflowRun, workflow_id)
        attempt = self.session.get(SubmissionAttempt, workflow.submission_id) if workflow else None
        context = await self.provider.get_context(workflow_id)
        if (
            context is None
            or attempt is None
            or context.submission.submission_id != attempt.id
            or context.submission.student_id != str(attempt.student_id)
            or context.submission.task_id != attempt.task_id
            or context.task.task_id != attempt.task_id
            or context.submission.course_id != binding.course_id
            or context.task.course_id != binding.course_id
        ):
            raise GovernanceDenied("baseline_context_scope_mismatch")
        self.governance.require_case(workflow_id)
        return context
