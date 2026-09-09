"""Select whole, released decisions under an explicitly published outcome rule."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.assessment import AssessmentResult, ResultState
from app.models.assessment import AssessmentAttempt, AssessmentDecision, ReassessmentLink
from app.models.reassessment import ReassessmentAuthorisation
from app.schemas.reassessment import OutcomeResultRead
from app.services.assessment.learner_results import LearnerResultService
from app.services.assessment.reassessment import ReassessmentService


class OutcomeResultService:
    def __init__(self, session: Session):
        self.session = session

    def read(self, learner, response_id):
        owned = LearnerResultService(self.session)._owned_attempt(learner, response_id)
        reassessment = ReassessmentService(self.session)
        policy = reassessment.policy(owned.assessment_definition_version_id)
        attempts = list(
            self.session.scalars(
                select(AssessmentAttempt)
                .where(
                    AssessmentAttempt.student_id == learner.id,
                    AssessmentAttempt.assessment_definition_version_id
                    == owned.assessment_definition_version_id,
                )
                .order_by(AssessmentAttempt.created_at, AssessmentAttempt.id)
            )
        )
        grants = list(
            self.session.scalars(
                select(ReassessmentAuthorisation)
                .where(
                    ReassessmentAuthorisation.prior_attempt_id.in_([item.id for item in attempts])
                )
                .order_by(ReassessmentAuthorisation.created_at, ReassessmentAuthorisation.id)
            )
        )
        result = OutcomeResultRead(
            definition_version_id=owned.assessment_definition_version_id,
            result=None,
            status="Awaiting a published outcome rule",
            selection_rule=policy.selection_rule if policy else None,
            evidence_response_ids=[],
            explanation="Your individual decisions remain available. An assessor must publish the outcome selection rule before an outcome result can be selected.",
            authorisations=[reassessment.read_grant(grant) for grant in grants],
        )
        if policy is None:
            return result
        selected = self._released_chains(attempts, grants, policy.selection_rule)
        result.status = "Awaiting confirmed evidence"
        result.explanation = "Only released assessor decisions count. Pending, returned, withheld and void work cannot replace confirmed evidence. Attempts are never averaged."
        if not selected:
            return result
        if policy.selection_rule == "ALL_REQUIRED_FORMS":
            required = {key: selected.get(key) for key in policy.required_form_ids}
            evidence = [item for item in required.values() if item]
            passed = all(item and item[1] is AssessmentResult.PASS for item in required.values())
            if not evidence:
                return result
            result.result = AssessmentResult.PASS if passed else AssessmentResult.INCOMPLETE
            result.evidence_response_ids = [item[0].response_version_id for item in evidence]
            result.explanation = "Each required form needs a whole confirmed PASS, including any authorised equivalent replacement. Partial criteria from different attempts are not combined."
        else:
            candidates = list(selected.values())
            passes = (
                [item for item in candidates if item[1] is AssessmentResult.PASS]
                if policy.selection_rule == "ANY_VALID_PASS"
                else []
            )
            chosen = max(passes or candidates, key=lambda item: (item[0].created_at, item[0].id))
            result.result = chosen[1]
            result.evidence_response_ids = [chosen[0].response_version_id]
            result.explanation += (
                " Any valid PASS satisfies this outcome."
                if policy.selection_rule == "ANY_VALID_PASS"
                else " The latest released evidence controls the current result. Earlier decisions remain in history."
            )
        result.status = "Current outcome result"
        return result

    def _released_chains(self, attempts, grants, selection_rule):
        by_id = {item.id: item for item in attempts}
        authorised = {item.prior_attempt_id: item for item in grants}
        replacements = {}
        for link in self.session.scalars(
            select(ReassessmentLink).where(ReassessmentLink.prior_assessment_attempt_id.in_(by_id))
        ):
            grant = authorised.get(link.prior_assessment_attempt_id)
            replacement = by_id.get(link.replacement_assessment_attempt_id)
            if (
                grant
                and replacement
                and replacement.task_form_version_id == grant.task_form_version_id
            ):
                replacements[replacement.id] = link.prior_assessment_attempt_id
        decisions = {
            row.assessment_attempt_id: row
            for row in self.session.scalars(
                select(AssessmentDecision).where(
                    AssessmentDecision.assessment_attempt_id.in_(by_id)
                )
            )
        }
        first_forms = {}
        roots = {}
        selected = {}
        for attempt in attempts:
            parent = replacements.get(attempt.id)
            if parent:
                root = roots.get(parent)
                if root is None:
                    continue
            else:
                root = attempt.task_form_version_id
                if root in first_forms:
                    continue
                first_forms[root] = attempt.id
            roots[attempt.id] = root
            decision = decisions.get(attempt.id)
            if not decision or decision.result_state not in {
                ResultState.CONFIRMED,
                ResultState.OVERRIDDEN,
            }:
                continue
            prior = selected.get(root)
            if selection_rule == "ANY_VALID_PASS" and prior and prior[1] is AssessmentResult.PASS:
                continue
            selected[root] = (attempt, decision.result)
        return selected
