"""Read exact assessor context and revision evidence without recovery writes."""

from sqlalchemy import select

from app.models.assessment import (
    AssessmentApprovalState,
    AssessmentAttempt,
    OutcomeVersion,
    TaskApproval,
)
from app.models.task_review import TaskReviewEvent, TaskRevision
from app.schemas.assessment_review import (
    FrozenAssessmentContextRead,
    HistoricalResponseEvidenceRead,
)
from app.services.assessment.evaluation import (
    AssessmentEvaluationConflictError,
    AssessmentEvaluationService,
    UnavailableCriterionEvaluationPort,
    UnavailableQualityReviewPort,
)
from app.services.assessment.response_evidence import ResponseEvidenceResolver
from app.services.episode_contract import FrozenResponseError, validate_reviewed_episode_plan
from app.services.task_review import snapshot_digest


class FrozenReviewEvidenceReader:
    def __init__(self, session, reader):
        self.session = session
        self.reader = reader
        self.resolver = ResponseEvidenceResolver(reader, session)

    def bundle(self, attempt):
        return AssessmentEvaluationService(
            self.session,
            criterion_port=UnavailableCriterionEvaluationPort(),
            quality_port=UnavailableQualityReviewPort(),
        ).load_review_bundle(attempt)

    def context(self, bundle):
        form = bundle.form
        revision = (
            self.session.get(TaskRevision, form.task_revision_id) if form.task_revision_id else None
        )
        approval = self.session.scalar(
            select(TaskApproval).where(
                TaskApproval.task_form_version_id == form.id,
                TaskApproval.assessment_definition_version_id == bundle.definition.id,
                TaskApproval.course_id == form.course_id,
                TaskApproval.approval_state == AssessmentApprovalState.APPROVED,
            )
        )
        review = (
            self.session.get(TaskReviewEvent, approval.task_review_event_id) if approval else None
        )
        if (
            revision is None
            or review is None
            or (
                revision.task_id != form.learning_task_id
                or revision.course_id != form.course_id
                or revision.content_digest != snapshot_digest(revision.snapshot)
                or form.source_digest != revision.content_digest
                or form.source_version != f"task-revision:{revision.id}"
                or review.task_revision_id != revision.id
                or review.course_id != form.course_id
                or review.state != "APPROVED"
            )
        ):
            raise FrozenResponseError("The exact reviewed task context is unavailable or stale")
        snapshot = revision.snapshot
        frozen_plan = (
            form.constraints.get("episode_plan") if isinstance(form.constraints, dict) else None
        )
        plan = validate_reviewed_episode_plan(snapshot.get("marking_criteria"), frozen_plan)
        if plan and frozen_plan is None:
            raise FrozenResponseError("The reviewed episode plan is absent from the frozen form")
        transfer = plan.transfer if plan else None
        outcome = self.session.get(OutcomeVersion, bundle.definition.outcome_version_id)
        return FrozenAssessmentContextRead(
            task_revision_id=revision.id,
            task_title=snapshot["title"],
            supported_prompt=snapshot["description"],
            supported_instructions=snapshot["instructions"],
            starter_code=snapshot.get("starter_code"),
            starter_circuit=snapshot.get("starter_circuit"),
            transfer_prompt=transfer.prompt if transfer else None,
            transfer_instructions=transfer.instructions if transfer else None,
            transfer_starter_code=transfer.starter_code if transfer else None,
            transfer_starter_circuit=transfer.starter_circuit if transfer else None,
            outcome_title=outcome.title,
            outcome_statement=outcome.statement,
            bloom_process=bundle.bloom.bloom_process.value,
            knowledge_dimension=bundle.bloom.knowledge_dimension.value,
            pass_rule_expression=bundle.rule.expression,
        )

    def read(self, attempt):
        result = {
            "response": None,
            "response_history": (),
            "simulations": (),
            "historical_evidence": (),
            "frozen_context": None,
            "issues": [],
        }
        try:
            bundle = self.bundle(attempt)
            result["frozen_context"] = self.context(bundle)
            response = self.reader.read(assessment=bundle.reference)
            result["response"] = response
            result["simulations"] = self.resolver.simulations(bundle.reference, response)
            if any(run["status"] != "completed" for run in result["simulations"]):
                result["issues"].append(
                    "Required simulation evidence is pending or has a technical fault. Do not issue an incomplete result."
                )
            result["historical_evidence"] = self.history(attempt, response)
            result["response_history"] = tuple(
                entry.response for entry in result["historical_evidence"] if entry.response
            )
        except (AssessmentEvaluationConflictError, FrozenResponseError, ValueError, KeyError):
            result["issues"].append(
                "Frozen evidence or approved task context is unavailable or stale. Technical review is required."
            )
        return result

    def history(self, attempt, response):
        history, pending, seen = [], [response], {attempt.response_version_id}
        while pending:
            current = pending.pop()
            if current.episode is None:
                continue
            stages = [current.episode.supported]
            if current.episode.transfer:
                stages.append(current.episode.transfer.process)
            for response_id in sorted(
                {stage.revision.previous_response_version_id for stage in stages if stage.revision}
            ):
                if response_id in seen:
                    continue
                if len(seen) >= 100:
                    raise FrozenResponseError(
                        "Response revision history exceeds the inspection limit"
                    )
                seen.add(response_id)
                entry = HistoricalResponseEvidenceRead(response_version_id=response_id)
                try:
                    prior = self.session.scalar(
                        select(AssessmentAttempt).where(
                            AssessmentAttempt.response_version_id == response_id
                        )
                    )
                    if prior is None or (prior.student_id, prior.task_id, prior.course_id) != (
                        attempt.student_id,
                        attempt.task_id,
                        attempt.course_id,
                    ):
                        raise FrozenResponseError(
                            "Earlier response is outside the learner task scope"
                        )
                    bundle = self.bundle(prior)
                    entry.response = self.reader.read(assessment=bundle.reference)
                    entry.simulations = list(
                        self.resolver.simulations(bundle.reference, entry.response)
                    )
                    if any(run["status"] != "completed" for run in entry.simulations):
                        entry.issues.append(
                            "Recorded simulation evidence is pending or has a technical fault."
                        )
                    pending.append(entry.response)
                except (AssessmentEvaluationConflictError, FrozenResponseError, ValueError):
                    entry.issues.append(
                        "Earlier evidence is unavailable, foreign, or stale. Technical review is required."
                    )
                history.append(entry)
        return tuple(history)
