"""Deterministic continuation, using the shared model and approved curriculum."""

from dataclasses import asdict
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException
from sqlalchemy import select, update

from app.domain.platform_enums import (
    EvidenceLinkRelation,
    EvidenceType,
    InferenceStatus,
    LearnerModelDimension,
)
from app.models.activity_continuation import ActivityChoice, ActivityProgress, ActivitySuggestion
from app.models.continuation import ContinuationJob
from app.models.curriculum import PathwayVersion
from app.models.enums import (
    ContinuationState,
    FeedbackStatus,
    JudgeDecision,
    JudgeEvaluationStatus,
    WorkflowOutcome,
    WorkflowStage,
)
from app.models.learning_evidence import LearningEvidence
from app.models.lms import Course, SubmissionAttempt
from app.models.persistence import FeedbackRecord, LearningTask, WorkflowRun
from app.models.user import User, UserRole
from app.schemas.activity_continuation import ActivityAction, ActivityHistory, ActivityRead
from app.schemas.category_review import CategoryReviewRecord, CategoryReviewRequest
from app.services.category_review import require_approved
from app.services.category_selection_review import review_selection
from app.services.curriculum import CurriculumService, pathway_progress
from app.services.learner_model.builder import (
    DeterministicLearnerModelBuilder,
    LearnerModelBuildService,
    LearnerModelBuildState,
)
from app.services.learner_model.contracts import (
    LearnerModelEvidenceSignal,
    LearnerModelSnapshotPayload,
    LearnerModelUpdateCommand,
    LearnerOutcomeEstimatePayload,
)
from app.services.learner_model.correction_repository import (
    SqlAlchemyLearnerModelCorrectionRepository,
)
from app.services.learner_model.repository import SqlAlchemyLearnerModelRepository
from app.services.learner_preferences import LearnerPreferenceService
from app.services.lms import LmsService, LmsServiceError
from app.services.task_review import TaskReviewError
from app.services.validation_reads import validation_read_scope

RULE = "approved-activity.v1"
MODEL_RULE = "continuation-observations.v2"


def utc_now():
    return datetime.now(UTC)


class ObservationBuilder(DeterministicLearnerModelBuilder):
    """New event occurrence is uncertain evidence, never proof of learning success."""

    def __init__(self, new_ids, head=None):
        self.new_ids = set(new_ids)
        self.previous = {item.dimension: item for item in head.estimates} if head else {}

    def build(self, command, observations):
        result = super().build(command, observations)
        estimates = list(result.estimates) if result else []
        represented = {signal.evidence_id for item in estimates for signal in item.evidence_signals}
        missing = [item for item in observations if item.evidence_id not in represented]
        # A supported response is still an observation. It cannot support independence.
        if missing:
            dimension = LearnerModelDimension.INDEPENDENCE
            prior = next((item for item in estimates if item.dimension == dimension), None)
            estimates = [item for item in estimates if item.dimension != dimension]
            signals = list(prior.evidence_signals) if prior else []
            signals.extend(
                LearnerModelEvidenceSignal(evidence_id=item.evidence_id, relation=item.relation)
                for item in missing
            )
            estimates.append(
                LearnerOutcomeEstimatePayload(
                    estimate_id=str(uuid5(NAMESPACE_URL, f"{command.snapshot_id}:independence")),
                    dimension=dimension,
                    inference_status=InferenceStatus.UNCERTAIN,
                    uncertainty=1,
                    reason_code="observation.independence-unchecked.v1",
                    evidence_observed_at=max(item.occurred_at for item in observations),
                    evidence_signals=tuple(signals),
                )
            )
        estimates = tuple(
            item.model_copy(
                update={
                    "inference_status": InferenceStatus.UNCERTAIN,
                    "uncertainty": 1.0,
                    "reason_code": "observation.learning-success-unchecked.v1",
                }
            )
            if any(signal.evidence_id in self.new_ids for signal in item.evidence_signals)
            else item
            for item in estimates
        )
        preserved = []
        for item in estimates:
            previous = self.previous.get(item.dimension)
            if previous and (
                previous.inference_status == InferenceStatus.NEEDS_REVIEW
                or set(previous.evidence_links)
                == {(signal.evidence_id, signal.relation) for signal in item.evidence_signals}
            ):
                item = item.model_copy(
                    update={
                        "inference_status": previous.inference_status,
                        "uncertainty": previous.uncertainty,
                        "reason_code": previous.reason_code,
                    }
                )
            preserved.append(item)
        estimates = tuple(preserved)
        return LearnerModelSnapshotPayload(
            **{
                key: getattr(command, key)
                for key in (
                    "snapshot_id",
                    "course_id",
                    "learner_id",
                    "outcome_id",
                    "prior_snapshot_id",
                    "model_source",
                    "model_version",
                    "rule_version",
                    "record_version",
                    "actor_reference",
                    "agent_reference",
                    "correlation_id",
                    "idempotency_key",
                    "occurred_at",
                )
            },
            estimates=estimates,
        )


def lock_claim(session, request, now):
    """Take the SQLite writer lock and fence all side effects before reading inputs."""
    result = session.execute(
        update(ContinuationJob)
        .where(
            ContinuationJob.workflow_run_id == request.workflow_run_id,
            ContinuationJob.execution_token == request.execution_token,
            ContinuationJob.execution_token.is_not(None),
            ContinuationJob.state == ContinuationState.RUNNING,
            ContinuationJob.lease_expires_at > now(),
        )
        .values(execution_token=ContinuationJob.execution_token)
    )
    if result.rowcount != 1:
        raise RuntimeError("Continuation claim expired or was replaced")


def workflow_scope(session, identity):
    workflow = session.get(WorkflowRun, identity)
    attempt = session.get(SubmissionAttempt, workflow.submission_id) if workflow else None
    task = session.get(LearningTask, attempt.task_id) if attempt else None
    learner = session.get(User, attempt.student_id) if attempt else None
    if not task or not learner:
        raise HTTPException(404, "Activity continuation is unavailable")
    return workflow, attempt, task, learner


def response_observations(session, attempt, task, learner):
    """Read the submitted episode and its exact pre-result prediction checkpoints.

    Checkpoints precede submission and therefore have no response_version_id.
    Do not collect other drafts or checkpoints merely because they share a task.
    """
    episode = attempt.episode or {}
    stages = [episode.get("supported", {})]
    if episode.get("transfer"):
        stages.append(episode["transfer"].get("process", {}))
    checkpoints = [
        stage["prediction_checkpoint_id"]
        for stage in stages
        if stage.get("prediction_checkpoint_id")
    ]
    scope = (
        LearningEvidence.learner_id == learner.id,
        LearningEvidence.course_id == task.course_id,
        LearningEvidence.outcome_id == task.learning_outcome_id,
        LearningEvidence.task_id == task.id,
    )
    submitted = (
        LearningEvidence.response_version_id == attempt.id
    ) & LearningEvidence.evidence_type.in_(
        [
            EvidenceType.RESPONSE,
            EvidenceType.REASONING,
            EvidenceType.PREDICTION,
            EvidenceType.REVISION,
            EvidenceType.EXPLANATION,
            EvidenceType.REFLECTION,
            EvidenceType.TRANSFER,
        ]
    )
    checkpoint = (
        LearningEvidence.response_version_id.is_(None)
        & (LearningEvidence.evidence_type == EvidenceType.PREDICTION)
        & LearningEvidence.source_interaction_id.in_(checkpoints)
        & (LearningEvidence.activity_id == attempt.assessment_work_start_id)
    )
    return list(
        session.scalars(
            select(LearningEvidence)
            .where(*scope, submitted | checkpoint)
            .order_by(LearningEvidence.id)
        )
    )


class ApprovedActivityAdapter:
    def __init__(self, session_factory=None, *, now=utc_now):
        self.session_factory = session_factory
        self.now = now

    def bind(self, session_factory, now):
        return ApprovedActivityAdapter(session_factory, now=now)

    def _scope(self, session, request):
        scope = workflow_scope(session, request.workflow_run_id)
        workflow, _, task, learner = scope
        if (workflow.task_id, workflow.course_id) != (task.id, task.course_id):
            raise RuntimeError("Continuation workflow scope changed")
        job = session.get(ContinuationJob, request.workflow_run_id)
        if (task.id, task.course_id, job.correlation_id, job.pseudonymous_actor_reference) != (
            request.completed_task_reference,
            request.course_reference,
            request.correlation_id,
            request.pseudonymous_actor_reference,
        ):
            raise RuntimeError("Continuation scope does not match its workflow")
        CurriculumService(session)._access(learner, task.course_id)
        return scope

    async def record_terminal_feedback(self, request):
        if request.idempotency_key != request.workflow_run_id:
            raise RuntimeError("Continuation idempotency key must identify its workflow")
        with self.session_factory() as session:
            try:
                lock_claim(session, request, self.now)
                workflow, attempt, task, learner = self._scope(session, request)
                if session.get(ActivityProgress, workflow.id):
                    session.rollback()
                    return
                feedback = session.scalar(
                    select(FeedbackRecord).where(
                        FeedbackRecord.workflow_run_id == workflow.id,
                        FeedbackRecord.status == FeedbackStatus.ACCEPTED,
                    )
                )
                judge = feedback.judge_evaluation if feedback else None
                eligible = (
                    workflow.current_stage == WorkflowStage.COMPLETED
                    and workflow.final_outcome
                    in {WorkflowOutcome.FIRST_PASS, WorkflowOutcome.SECOND_PASS}
                    and workflow.completed_at is not None
                    and judge is not None
                    and judge.evaluation_status == JudgeEvaluationStatus.VALID
                    and judge.decision == JudgeDecision.PASS
                )
                evidence = (
                    response_observations(session, attempt, task, learner) if eligible else []
                )
                state = "feedback_not_eligible" if not eligible else "insufficient_evidence"
                snapshot_id = None
                preferences = LearnerPreferenceService(session).read(learner)
                if eligible and not preferences.values.personalisation_enabled:
                    state = "personalisation_disabled"
                elif eligible and evidence:
                    repository = SqlAlchemyLearnerModelRepository(session, caller_transaction=True)
                    head = repository.current(
                        course_id=task.course_id,
                        learner_id=str(learner.id),
                        outcome_id=task.learning_outcome_id,
                    )
                    old_relations = (
                        {
                            identity: relation
                            for item in head.estimates
                            for identity, relation in item.evidence_links
                        }
                        if head
                        else {}
                    )
                    result = LearnerModelBuildService(
                        repository,
                        ObservationBuilder([item.id for item in evidence], head),
                        SqlAlchemyLearnerModelCorrectionRepository(session),
                    ).update(
                        LearnerModelUpdateCommand(
                            course_id=task.course_id,
                            learner_id=str(learner.id),
                            outcome_id=task.learning_outcome_id,
                            model_version=DeterministicLearnerModelBuilder.model_version,
                            rule_version=MODEL_RULE,
                            actor_reference=str(learner.id),
                            agent_reference=RULE,
                            adjudicator_reference="learner-model-rule-engine.v1",
                            adjudication_rule_version=MODEL_RULE,
                            correlation_id=request.correlation_id,
                            evidence_signals=tuple(
                                LearnerModelEvidenceSignal(
                                    evidence_id=item.id,
                                    relation=old_relations.get(
                                        item.id, EvidenceLinkRelation.SUPPORTS
                                    ),
                                )
                                for item in evidence
                            ),
                        )
                    )
                    if result.state != LearnerModelBuildState.STORED:
                        raise RuntimeError("Learner model update could not be stored")
                    snapshot_id = result.snapshot.snapshot_id
                    state = "observations_recorded"
                session.add(
                    ActivityProgress(
                        workflow_id=workflow.id,
                        learner_id=learner.id,
                        course_id=task.course_id,
                        outcome_id=task.learning_outcome_id,
                        snapshot_id=snapshot_id,
                        state=state,
                        evidence_ids=[item.id for item in evidence],
                    )
                )
                session.flush()
                lock_claim(session, request, self.now)
                session.commit()
            except Exception:
                session.rollback()
                raise

    async def recommend_next_task(self, request):
        with self.session_factory() as session:
            try:
                lock_claim(session, request, self.now)
                workflow, _, task, learner = self._scope(session, request)
                existing = session.get(ActivitySuggestion, workflow.id)
                if existing:
                    session.rollback()
                    return existing.task_id
                receipt = session.get(ActivityProgress, workflow.id)
                if receipt is None:
                    raise RuntimeError("The model receipt must be durable first")
                decision, path = ActivityService(session).decide(receipt, task, learner)
                quality_input, quality = review_selection(decision, receipt, path)
                decision["quality_review_required"] = True
                decision["quality_review_input"] = quality_input.model_dump(mode="json")
                decision["quality_review"] = quality.model_dump(mode="json")
                try:
                    require_approved(quality, quality_input)
                except ValueError:
                    decision.update(
                        state="quality_review_required",
                        reason="The activity suggestion needs educator quality review. Your course activities remain available.",
                        options=[],
                    )
                selected = (
                    decision["options"][0]["task_id"] if decision["state"] == "suggested" else None
                )
                session.add(
                    ActivitySuggestion(
                        workflow_id=workflow.id,
                        pathway_id=path.id if path else None,
                        task_id=selected,
                        decision=decision,
                    )
                )
                session.flush()
                lock_claim(session, request, self.now)
                session.commit()
                return selected
            except Exception:
                session.rollback()
                raise


class ActivityService:
    def __init__(self, session):
        self.session = session

    def options(self, path, task, learner):
        curriculum = CurriculumService(self.session)
        curriculum._access(learner, task.course_id)
        curriculum._current(path)
        from app.services.progress_activity import completed_practice_tasks

        completed = completed_practice_tasks(
            self.session, learner.id, [step["task_id"] for step in path.payload["steps"]]
        )
        options = []
        for step in path.payload["steps"]:
            if step["task_id"] == task.id or step["task_id"] in completed:
                continue
            candidate = self.session.get(LearningTask, step["task_id"])
            try:
                LmsService(self.session)._require_student_task(learner, candidate.id)
                LmsService(self.session)._require_unlocked(learner, candidate)
            except LmsServiceError:
                continue
            _, _, support = pathway_progress(self.session, learner.id, candidate)
            options.append(dict(task_id=candidate.id, title=candidate.title, support_level=support))
        return options

    @validation_read_scope
    def decide(self, receipt, task, learner):
        prefs = LearnerPreferenceService(self.session).read(learner)
        head = (
            SqlAlchemyLearnerModelRepository(self.session).current(
                course_id=receipt.course_id,
                learner_id=str(learner.id),
                outcome_id=receipt.outcome_id,
            )
            if receipt.outcome_id
            else None
        )
        path = (
            CurriculumService(self.session)._latest(receipt.outcome_id)
            if receipt.outcome_id
            else None
        )
        decision = dict(
            state=receipt.state,
            reason="There is not enough checked learning evidence for a suggestion.",
            uncertainty=1.0,
            snapshot_id=head.snapshot_id if head else None,
            model_snapshot=asdict(head) if head else None,
            rule_version=RULE,
            evidence_ids=receipt.evidence_ids,
            preference_version=prefs.version,
            preferences=prefs.values.model_dump(),
            options=[],
        )
        # JSON contains only strings, numbers, lists, and maps; dates are serialized below.
        if head:
            decision["model_snapshot"] = {
                **decision["model_snapshot"],
                "occurred_at": head.occurred_at.isoformat(),
                "estimates": [
                    {**asdict(item), "evidence_observed_at": item.evidence_observed_at.isoformat()}
                    for item in head.estimates
                ],
            }
        if receipt.state == "feedback_not_eligible":
            decision["reason"] = (
                "Fallback or unchecked feedback cannot support a learning update. Your work and feedback remain available."
            )
        elif (
            not prefs.values.personalisation_enabled or receipt.state == "personalisation_disabled"
        ):
            decision.update(
                state="personalisation_disabled",
                reason="Personalisation is off. Use the course workspace to choose approved activities.",
            )
        elif not path:
            decision.update(
                state="no_eligible_activity",
                reason="The educator has not published an approved pathway for this outcome.",
            )
        else:
            try:
                options = self.options(path, task, learner)
            except (HTTPException, TaskReviewError):
                decision.update(
                    state="stale_approval",
                    reason="Pathway approval changed. The educator must review and publish the pathway again.",
                )
                return decision, path
            decision["options"] = options
            if self.needs_review(head):
                decision.update(
                    state="conflicting_evidence",
                    reason="The learner record needs educator review before an automatic suggestion.",
                )
            elif not receipt.evidence_ids or not head:
                decision["state"] = "insufficient_evidence"
            elif not options:
                decision.update(
                    state="no_eligible_activity",
                    reason="No new approved activity meets the current prerequisites. Your completed work remains available.",
                )
            else:
                decision.update(
                    state="suggested",
                    options=options,
                    reason="Your checked feedback and saved response are recorded. This is the next approved activity with completed prerequisites. Learning success remains uncertain.",
                )
        return decision, path

    def needs_review(self, head):
        if not head:
            return False
        return any(
            item.inference_status in {InferenceStatus.NEEDS_REVIEW, InferenceStatus.CONTRADICTED}
            or len({relation for _, relation in item.evidence_links}) > 1
            for item in head.estimates
        ) or bool(
            SqlAlchemyLearnerModelCorrectionRepository(self.session).accepted_targets(
                course_id=head.course_id,
                learner_id=head.learner_id,
                outcome_id=head.outcome_id,
                evidence_ids=tuple(
                    {identity for item in head.estimates for identity, _ in item.evidence_links}
                ),
                snapshot_id=head.snapshot_id,
            )
        )

    def _access(self, actor, identity):
        workflow, attempt, task, learner = workflow_scope(self.session, identity)
        course = CurriculumService(self.session)._access(actor, task.course_id)
        current = self.session.get(User, actor.id, populate_existing=True)
        educator = current.role == UserRole.EDUCATOR and course.educator_id == current.id
        if actor.id != learner.id and not educator:
            raise HTTPException(404, "Activity continuation is unavailable")
        return workflow, attempt, task, learner, educator

    def read(self, actor, identity):
        _, _, task, learner, educator = self._access(actor, identity)
        row = self.session.get(ActivitySuggestion, identity)
        if row is None:
            job = self.session.get(ContinuationJob, identity)
            failed = job and job.state == ContinuationState.FAILED
            return ActivityRead(
                workflow_id=identity,
                state="unavailable" if failed else "processing",
                reason="The suggestion is unavailable. Your work and feedback remain available."
                if failed
                else "The learning record and approved activity suggestion are being prepared.",
            )
        decisions = list(
            self.session.scalars(
                select(ActivityChoice)
                .where(ActivityChoice.workflow_id == identity)
                .order_by(ActivityChoice.version)
            )
        )
        data = row.decision
        history = [
            ActivityHistory(
                version=item.version,
                action=item.payload["action"],
                task_id=item.payload.get("selected_task_id"),
                reason=item.payload["reason"],
                educator=item.payload["action"] == "educator_override",
                created_at=item.created_at,
            )
            for item in decisions
        ]
        selected = history[-1].task_id if history else row.task_id
        state, reason, options = data["state"], data["reason"], data["options"]
        quality_blocked = False
        if data.get("quality_review_required"):
            try:
                quality_input = CategoryReviewRequest.model_validate(
                    data.get("quality_review_input")
                )
                quality = CategoryReviewRecord.model_validate(data.get("quality_review"))
                require_approved(quality, quality_input)
                if quality_input.output != {
                    key: data[key] for key in ("state", "reason", "uncertainty", "options")
                }:
                    raise ValueError("Suggestion differs from its quality review")
            except (ValueError, TypeError):
                quality_blocked = True
        if history:
            state = history[-1].action
        prefs = LearnerPreferenceService(self.session).read(learner)
        if not prefs.values.personalisation_enabled:
            state, reason, selected, options = (
                "personalisation_disabled",
                "Personalisation is off. Your course activities remain available.",
                None,
                [],
            )
        elif row.pathway_id:
            try:
                current_options = self.options(
                    self.session.get(PathwayVersion, row.pathway_id), task, learner
                )
                allowed = {item["task_id"] for item in current_options}
                options = [item for item in options if item["task_id"] in allowed]
                if selected and selected not in allowed:
                    selected, state, reason = (
                        None,
                        "unavailable",
                        "This activity is no longer eligible. Use the course workspace.",
                    )
            except (HTTPException, LmsServiceError, TaskReviewError):
                state, reason, selected, options = (
                    "stale_approval",
                    "Approval or access changed. Ask the educator to review the pathway.",
                    None,
                    [],
                )
        if selected and state not in {"replace", "educator_override"}:
            head = SqlAlchemyLearnerModelRepository(self.session).current(
                course_id=task.course_id,
                learner_id=str(learner.id),
                outcome_id=task.learning_outcome_id,
            )
            if self.needs_review(head):
                state, reason, selected = (
                    "conflicting_evidence",
                    "The learner record needs review. Choose an allowed activity or ask the educator.",
                    None,
                )
        if quality_blocked:
            state, reason, selected, options = (
                "quality_review_required",
                "The activity suggestion needs educator quality review. Your course activities remain available.",
                None,
                [],
            )
        return ActivityRead(
            learner_label=learner.full_name,
            workflow_id=identity,
            state=state,
            reason=reason,
            uncertainty=data["uncertainty"],
            snapshot_id=data["snapshot_id"],
            rule_version=data["rule_version"],
            evidence_ids=data["evidence_ids"],
            preference_version=data["preference_version"],
            pathway_id=row.pathway_id,
            next_task_id=selected,
            options=options,
            history=history,
            version=history[-1].version if history else 0,
            can_override=educator,
        )

    def act(self, actor, identity, payload: ActivityAction):
        try:
            _, _, task, learner, educator = self._access(actor, identity)
            self.session.execute(
                update(Course)
                .where(Course.id == task.course_id)
                .values(id=Course.id, updated_at=Course.updated_at)
            )
            self._access(actor, identity)
            if (payload.action == "educator_override") != educator:
                raise HTTPException(403, "This action is unavailable for your role")
            prior = self.session.scalar(
                select(ActivityChoice).where(
                    ActivityChoice.workflow_id == identity,
                    ActivityChoice.actor_id == actor.id,
                    ActivityChoice.request_key == payload.request_key,
                )
            )
            if prior:
                if {
                    key: prior.payload[key] for key in payload.model_dump()
                } != payload.model_dump():
                    raise HTTPException(409, "Request key was already used for another choice")
                self.session.rollback()
                return self.read(actor, identity)
            current = self.read(actor, identity)
            if current.version != payload.expected_version:
                raise HTTPException(409, "A newer choice was saved. Refresh before choosing again")
            if current.state in {
                "processing",
                "unavailable",
                "stale_approval",
                "personalisation_disabled",
                "feedback_not_eligible",
                "quality_review_required",
            }:
                raise HTTPException(409, "A current approved suggestion is required")
            selected = current.next_task_id if payload.action == "accept" else payload.task_id
            if payload.action != "defer" and selected not in {
                item.task_id for item in current.options
            }:
                raise HTTPException(409, "Choose a currently permitted activity")
            self.session.add(
                ActivityChoice(
                    workflow_id=identity,
                    actor_id=actor.id,
                    version=current.version + 1,
                    request_key=payload.request_key,
                    payload={**payload.model_dump(), "selected_task_id": selected},
                )
            )
            self.session.commit()
            return self.read(actor, identity)
        except Exception:
            self.session.rollback()
            raise
