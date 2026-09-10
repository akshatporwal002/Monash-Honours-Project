"""A reviewed teaching cycle that preserves observations and uncertain hypotheses."""

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, update

from app.domain.platform_enums import (
    AccessSupportState,
    EvidenceLinkRelation,
    EvidenceProvenance,
    EvidenceType,
    InferenceStatus,
    InstructionalSupportLevel,
    LearnerModelDimension,
    ModelSource,
    ObservationType,
)
from app.models.learning_evidence import EvidenceArtifact, LearningEvidence
from app.models.lms import (
    Course,
    CourseState,
    Enrollment,
    EnrollmentStatus,
    PlatformAuditEvent,
    SubmissionAttempt,
)
from app.models.misconceptions import (
    MisconceptionClosure,
    MisconceptionHypothesis,
    MisconceptionResponse,
    MisconceptionReviewRecord,
)
from app.models.persistence import FeedbackRecord, LearningTask
from app.models.user import User, UserRole
from app.schemas.misconceptions import (
    MisconceptionCandidateRead,
    MisconceptionEvidenceRead,
    MisconceptionRead,
    MisconceptionResponseRead,
    MisconceptionReviewRead,
)
from app.services.curriculum import CurriculumService
from app.services.escalation_sources import record_signal, source_for
from app.services.evidence.live import LiveEvidenceCapture
from app.services.learner_model.contracts import (
    LearnerModelEvidenceSignal,
    LearnerModelSnapshotPayload,
    LearnerOutcomeEstimatePayload,
)
from app.services.learner_model.correction_repository import (
    SqlAlchemyLearnerModelCorrectionRepository,
)
from app.services.learner_model.repository import SqlAlchemyLearnerModelRepository
from app.services.learner_model.safety import require_safe_claim_text
from app.services.lms import LmsServiceError
from app.services.misconception_state import active_assessed_transfer
from app.services.task_review import TaskReviewService

STAGES = ("PROBE", "REVISION", "TRANSFER")
RULE = "misconception-review.v1"


class MisconceptionService:
    def __init__(self, session):
        self.session = session

    def _lock(self, actor):
        self.session.execute(
            update(User).where(User.id == actor.id).values(is_active=User.is_active)
        )

    def candidates(self, actor, offset=0):
        current = self.session.get(User, actor.id, populate_existing=True)
        if not current or not current.is_active or current.role != UserRole.EDUCATOR:
            raise LmsServiceError(404, "Teaching records are unavailable")
        rows = self.session.execute(
            select(FeedbackRecord, SubmissionAttempt, LearningTask, User, Course)
            .join(SubmissionAttempt, SubmissionAttempt.id == FeedbackRecord.submission_id)
            .join(LearningTask, LearningTask.id == SubmissionAttempt.task_id)
            .join(User, User.id == SubmissionAttempt.student_id)
            .join(Course, Course.id == LearningTask.course_id)
            .where(Course.educator_id == actor.id)
            .order_by(FeedbackRecord.created_at.desc(), FeedbackRecord.id)
            .limit(20)
            .offset(offset)
        )
        result = []
        for feedback, response, task, student, course in rows:
            evidence = list(
                self.session.scalars(
                    select(LearningEvidence)
                    .where(
                        LearningEvidence.response_version_id == response.id,
                        LearningEvidence.learner_id == student.id,
                        LearningEvidence.course_id == course.id,
                        LearningEvidence.outcome_id == task.learning_outcome_id,
                    )
                    .order_by(LearningEvidence.occurred_at, LearningEvidence.id)
                )
            )
            result.append(
                MisconceptionCandidateRead(
                    feedback_id=feedback.id,
                    task_id=task.id,
                    student_id=student.id,
                    student_name=student.full_name,
                    course_title=course.title,
                    task_title=task.title,
                    response=response.answer,
                    evidence=[
                        MisconceptionEvidenceRead(
                            id=item.id,
                            kind=item.evidence_type.value,
                            content=self._evidence_content(item),
                        )
                        for item in evidence
                    ],
                )
            )
        return result

    def _evidence_content(self, evidence):
        artifact = (
            self.session.get(EvidenceArtifact, evidence.artifact_id)
            if evidence.artifact_id
            else None
        )
        if artifact is None:
            return "Content remains in the saved source record."
        try:
            value = json.loads(artifact.content)
            return json.dumps(value.get("value", value), ensure_ascii=False, indent=2)
        except (ValueError, AttributeError):
            return artifact.content

    def list_owned(self, actor, offset=0):
        current = self.session.get(User, actor.id, populate_existing=True)
        if not current or not current.is_active:
            raise LmsServiceError(404, "Learning checks are unavailable")
        query = select(MisconceptionHypothesis).join(
            Course, Course.id == MisconceptionHypothesis.course_id
        )
        if current.role == UserRole.STUDENT:
            query = query.join(
                Enrollment,
                (Enrollment.course_id == Course.id) & (Enrollment.student_id == current.id),
            ).where(
                MisconceptionHypothesis.student_id == current.id,
                Enrollment.status == EnrollmentStatus.ACTIVE,
                Course.state == CourseState.PUBLISHED,
            )
        elif current.role == UserRole.EDUCATOR:
            query = query.where(Course.educator_id == current.id)
        else:
            return []
        rows = self.session.scalars(
            query.order_by(MisconceptionHypothesis.created_at.desc(), MisconceptionHypothesis.id)
            .limit(20)
            .offset(offset)
        )
        return [self.read(actor, row.id) for row in rows]

    def _access(self, actor, row, *, educator=False):
        CurriculumService(self.session)._access(actor, row.course_id, owner=educator)
        if actor.role == UserRole.STUDENT and actor.id != row.student_id:
            raise LmsServiceError(404, "Learning check is unavailable")

    def _get(self, actor, identity, *, educator=False):
        row = self.session.get(MisconceptionHypothesis, identity)
        if row is None:
            raise LmsServiceError(404, "Learning check is unavailable")
        self._access(actor, row, educator=educator)
        return row

    def _history(self, row):
        responses = list(
            self.session.scalars(
                select(MisconceptionResponse)
                .where(
                    MisconceptionResponse.hypothesis_id == row.id,
                )
                .order_by(MisconceptionResponse.version)
            )
        )
        reviews = list(
            self.session.scalars(
                select(MisconceptionReviewRecord)
                .where(
                    MisconceptionReviewRecord.hypothesis_id == row.id,
                )
                .order_by(MisconceptionReviewRecord.version)
            )
        )
        return responses, reviews

    def read(self, actor, identity):
        row = self._get(actor, identity)
        responses, reviews = self._history(row)
        fresh = len(responses) == 2 and actor.role == UserRole.STUDENT
        staff = actor.role != UserRole.STUDENT
        assessment_active = (
            not staff
            and active_assessed_transfer(self.session, row.student_id, row.task_id) is not None
        )
        closure = self.session.scalar(
            select(MisconceptionClosure).where(MisconceptionClosure.hypothesis_id == row.id)
        )
        hidden = (fresh and not closure) or assessment_active
        return MisconceptionRead(
            id=row.id,
            task_id=row.task_id,
            course_id=row.course_id,
            outcome_id=row.outcome_id,
            student_id=row.student_id,
            hypothesis=row.payload["hypothesis"]
            if not assessment_active
            else "Teaching check paused during assessed fresh application.",
            evidence_ids=row.payload["evidence_ids"],
            selection_reason=row.payload["selection_reason"]
            if not assessment_active
            else "Teaching details are withheld during this assessed stage.",
            content_approval_reason=row.payload["content_approval_reason"]
            if not assessment_active
            else "Approval remains recorded.",
            approved_by=row.actor_id,
            approved_at=row.created_at,
            version=reviews[-1].version if reviews else len(responses),
            state=reviews[-1].state if reviews else "UNCERTAIN",
            confidence=reviews[-1].payload["confidence"] if reviews else row.payload["confidence"],
            next_stage=STAGES[len(responses)] if len(responses) < 3 and not closure else None,
            probe=row.payload["probe"] if not hidden else None,
            explanation=row.payload["explanation"] if (staff or responses) and not hidden else None,
            fresh_question=row.payload["fresh_question"]
            if (staff or len(responses) >= 2) and not assessment_active
            else None,
            responses=[]
            if hidden
            else [
                MisconceptionResponseRead(
                    id=item.id,
                    evidence_id=item.evidence_id,
                    version=item.version,
                    stage=item.stage,
                    created_at=item.created_at,
                    **{
                        key: item.payload[key]
                        for key in ("answer", "reasoning", "confidence", "help_used")
                    },
                )
                for item in responses
            ],
            reviews=[
                MisconceptionReviewRead(
                    id=item.id,
                    version=item.version,
                    actor_id=item.actor_id,
                    state=item.state,
                    created_at=item.created_at,
                    evidence_id=item.evidence_id,
                    snapshot_id=item.snapshot_id,
                    escalation_id=item.escalation_id,
                    **{
                        key: item.payload[key]
                        for key in (
                            "confidence",
                            "supports",
                            "contradicts",
                            "reason",
                            "next_action",
                        )
                    },
                )
                for item in (reviews if not assessment_active else [])
            ],
            persistence_stages=row.payload["persistence_stages"],
            closure={
                "disposition": closure.disposition,
                "reason": closure.payload["reason"]
                if not assessment_active
                else "Teaching details are withheld during this assessed stage.",
                "actor_id": closure.actor_id,
                "created_at": closure.created_at.isoformat(),
            }
            if closure
            else None,
            teaching_available=not assessment_active,
            initial_evidence=[]
            if hidden
            else [
                MisconceptionEvidenceRead(
                    id=item.id, kind=item.evidence_type.value, content=self._evidence_content(item)
                )
                for item in self._evidence(
                    row.course_id,
                    row.outcome_id,
                    row.student_id,
                    row.payload["evidence_ids"],
                )
            ],
        )

    def list_for(self, actor, task_id, student_id):
        task = self.session.get(LearningTask, task_id)
        if task is None:
            raise LmsServiceError(404, "Learning checks are unavailable")
        CurriculumService(self.session)._access(actor, task.course_id)
        if actor.role == UserRole.STUDENT and actor.id != student_id:
            raise LmsServiceError(404, "Learning checks are unavailable")
        return [
            self.read(actor, identity)
            for identity in self.session.scalars(
                select(MisconceptionHypothesis.id)
                .where(
                    MisconceptionHypothesis.task_id == task_id,
                    MisconceptionHypothesis.student_id == student_id,
                )
                .order_by(MisconceptionHypothesis.created_at.desc(), MisconceptionHypothesis.id)
                .limit(50)
            )
        ]

    def _evidence(self, course_id, outcome_id, student_id, identities):
        if len(set(identities)) != len(identities):
            raise LmsServiceError(422, "Choose distinct evidence references")
        rows = list(
            self.session.scalars(
                select(LearningEvidence)
                .where(
                    LearningEvidence.id.in_(identities),
                    LearningEvidence.course_id == course_id,
                    LearningEvidence.outcome_id == outcome_id,
                    LearningEvidence.learner_id == student_id,
                )
                .order_by(LearningEvidence.occurred_at, LearningEvidence.id)
            )
        )
        if len(rows) != len(identities):
            raise LmsServiceError(
                422, "Every evidence reference must belong to this learner and outcome"
            )
        return rows

    @staticmethod
    def _replay(row, command, actor):
        if row.actor_id != actor.id or row.payload != command.model_dump(mode="json"):
            raise LmsServiceError(409, "This request key already has different details")

    def open(self, actor, command):
        self._lock(actor)
        source = source_for(self.session, "FEEDBACK", command.feedback_id)
        if source is None:
            raise LmsServiceError(404, "Saved feedback is unavailable")
        task = source.task
        CurriculumService(self.session)._access(actor, task.course_id, owner=True)
        prior = self.session.scalar(
            select(MisconceptionHypothesis).where(
                MisconceptionHypothesis.actor_id == actor.id,
                MisconceptionHypothesis.request_key == command.request_key,
            )
        )
        if prior:
            self._replay(prior, command, actor)
            self.session.rollback()
            return self.read(actor, prior.id)
        if not self.session.scalar(
            select(Enrollment.id).where(
                Enrollment.course_id == task.course_id,
                Enrollment.student_id == source.student_id,
                Enrollment.status == EnrollmentStatus.ACTIVE,
            )
        ):
            raise LmsServiceError(404, "The learner is unavailable in this course")
        reviewer = TaskReviewService(self.session)
        reviewer.require_available(task)
        sources = reviewer.source_approvals(task, required=True)
        self._evidence(
            task.course_id, task.learning_outcome_id, source.student_id, command.evidence_ids
        )
        require_safe_claim_text(command.hypothesis)
        for previous in self.session.scalars(
            select(MisconceptionHypothesis).where(
                MisconceptionHypothesis.student_id == source.student_id,
                MisconceptionHypothesis.outcome_id == task.learning_outcome_id,
            )
        ):
            if (
                previous.payload["fresh_question"].strip().casefold()
                == command.fresh_question.strip().casefold()
            ):
                raise LmsServiceError(
                    422, "Choose a new approved fresh question for a replacement cycle"
                )
        finished = (
            select(MisconceptionResponse.id)
            .where(
                MisconceptionResponse.hypothesis_id == MisconceptionHypothesis.id,
                MisconceptionResponse.stage == "TRANSFER",
            )
            .exists()
        )
        closed = (
            select(MisconceptionClosure.id)
            .where(
                MisconceptionClosure.hypothesis_id == MisconceptionHypothesis.id,
            )
            .exists()
        )
        if self.session.scalar(
            select(MisconceptionHypothesis.id)
            .where(
                MisconceptionHypothesis.task_id == task.id,
                MisconceptionHypothesis.student_id == source.student_id,
                ~finished,
                ~closed,
            )
            .limit(1)
        ):
            raise LmsServiceError(409, "Finish the existing learning check before opening another")
        row = MisconceptionHypothesis(
            id=str(uuid4()),
            task_id=task.id,
            course_id=task.course_id,
            outcome_id=task.learning_outcome_id,
            student_id=source.student_id,
            actor_id=actor.id,
            feedback_id=command.feedback_id,
            task_revision_id=reviewer.latest_revision(task.id).id,
            request_key=command.request_key,
            payload=command.model_dump(mode="json"),
            source_approvals=sources,
        )
        self.session.add(row)
        self._audit(actor, row.id, "opened")
        self.session.commit()
        return self.read(actor, row.id)

    def exit(self, actor, identity, command):
        self._lock(actor)
        row = self._get(
            actor,
            identity,
            educator=actor.role != UserRole.STUDENT or command.disposition == "INVALIDATED",
        )
        prior = self.session.scalar(
            select(MisconceptionClosure).where(MisconceptionClosure.hypothesis_id == identity)
        )
        if prior:
            self._replay(prior, command, actor)
            self.session.rollback()
            return self.read(actor, identity)
        responses, reviews = self._history(row)
        if reviews or len(responses) == 3:
            raise LmsServiceError(
                409, "This cycle is complete. Add an educator review to correct it"
            )
        if command.expected_version != len(responses):
            raise LmsServiceError(409, "The check changed. Refresh before leaving")
        self.session.add(
            MisconceptionClosure(
                hypothesis_id=identity,
                actor_id=actor.id,
                disposition=command.disposition,
                payload=command.model_dump(mode="json"),
            )
        )
        self._audit(actor, identity, command.disposition.lower())
        self.session.commit()
        return self.read(actor, identity)

    def answer(self, learner, identity, command):
        self._lock(learner)
        row = self._get(learner, identity)
        if learner.role != UserRole.STUDENT or learner.id != row.student_id:
            raise LmsServiceError(404, "Learning check is unavailable")
        if self.session.scalar(
            select(MisconceptionClosure.id).where(MisconceptionClosure.hypothesis_id == row.id)
        ):
            raise LmsServiceError(409, "This check has ended. Your saved work remains available")
        if active_assessed_transfer(self.session, row.student_id, row.task_id):
            raise LmsServiceError(
                409,
                "Finish or leave the assessed fresh application before using this teaching check",
            )
        responses, reviews = self._history(row)
        prior = next((item for item in responses if item.request_key == command.request_key), None)
        if prior:
            self._replay(prior, command, learner)
            self.session.rollback()
            return self.read(learner, identity)
        if reviews or command.expected_version != len(responses):
            raise LmsServiceError(409, "The learning check changed. Refresh before saving")
        if len(responses) >= 3 or command.stage != STAGES[len(responses)]:
            raise LmsServiceError(422, "Complete the probe, revision and fresh check in order")
        task = self.session.get(LearningTask, row.task_id)
        reviewer = TaskReviewService(self.session)
        reviewer.require_available(task)
        if (
            reviewer.latest_revision(task.id).id != row.task_revision_id
            or reviewer.source_approvals(task, required=True) != row.source_approvals
        ):
            raise LmsServiceError(
                409, "Teaching approval changed. Ask your educator to review this check"
            )
        response_id = str(uuid4())
        when = datetime.now(UTC)
        support = InstructionalSupportLevel(
            max(
                row.payload["explanation_support_level"] if command.stage == "REVISION" else 0,
                InstructionalSupportLevel.DIRECT_ANSWER if command.help_used else 0,
            )
        )
        evidence = LiveEvidenceCapture(self.session)._write(
            task=task,
            learner_id=learner.id,
            source=response_id,
            field="misconception_response",
            kind=EvidenceType.MISCONCEPTION_CHECK,
            value={
                "hypothesis_id": row.id,
                "stage": command.stage,
                **command.model_dump(mode="json"),
            },
            occurred_at=when,
            support=support,
            access=AccessSupportState.NOT_DECLARED,
            parents=[item.evidence_id for item in responses],
        )
        response = MisconceptionResponse(
            id=response_id,
            hypothesis_id=row.id,
            actor_id=learner.id,
            version=len(responses) + 1,
            stage=command.stage,
            request_key=command.request_key,
            payload=command.model_dump(mode="json"),
            evidence_id=evidence,
            created_at=when,
        )
        self.session.add(response)
        if command.stage == "PROBE":
            source = source_for(self.session, "FEEDBACK", row.feedback_id)
            original = self.session.get(SubmissionAttempt, source.record.submission_id)
            LiveEvidenceCapture(self.session)._write(
                task=task,
                learner_id=learner.id,
                source=response.id,
                field="misconception_teaching",
                kind=EvidenceType.SCAFFOLD,
                value={
                    "hypothesis_id": row.id,
                    "explanation": row.payload["explanation"],
                    "approved_by": row.actor_id,
                    "source_approvals": row.source_approvals,
                },
                occurred_at=when,
                work_id=original.assessment_work_start_id,
                parents=(response.evidence_id,),
                support=InstructionalSupportLevel(row.payload["explanation_support_level"]),
                observation=ObservationType.SYSTEM_CAPTURED,
            )
        self._audit(learner, row.id, command.stage.lower())
        self.session.commit()
        return self.read(learner, identity)

    def review(self, actor, identity, command):
        self._lock(actor)
        row = self._get(actor, identity, educator=True)
        responses, reviews = self._history(row)
        prior = next((item for item in reviews if item.request_key == command.request_key), None)
        if prior:
            self._replay(prior, command, actor)
            self.session.rollback()
            return self.read(actor, identity)
        version = reviews[-1].version if reviews else len(responses)
        if command.expected_version != version:
            raise LmsServiceError(409, "This review is stale. Refresh before saving")
        if len(responses) != 3:
            raise LmsServiceError(
                422, "Review the probe, revision and fresh check before recording a state"
            )
        candidates = set(row.payload["evidence_ids"]) | {item.evidence_id for item in responses}
        if not set(command.supports + command.contradicts) <= candidates:
            raise LmsServiceError(422, "Review only the evidence retained by this cycle")
        if command.state == "PERSISTED" and not set(row.payload["persistence_stages"]) <= {
            item.stage for item in responses if item.evidence_id in command.supports
        }:
            raise LmsServiceError(
                422, "Persistence requires the supporting stages approved for this cycle"
            )
        if command.state == "WEAKENED" and not command.contradicts:
            raise LmsServiceError(422, "A weakened hypothesis needs contradicting evidence")
        fresh = responses[-1]
        if command.state == "CORRECTED" and (
            fresh.evidence_id not in command.contradicts or fresh.payload["help_used"]
        ):
            raise LmsServiceError(
                422, "Correction requires contradicting evidence from an unaided fresh check"
            )
        review_id = str(uuid4())
        when = datetime.now(UTC)
        evidence_id = self._review_evidence(actor, row, review_id, command, when)
        snapshot_id = self._snapshot(actor, row, review_id, evidence_id, when)
        escalation = None
        if command.state in {"UNCERTAIN", "PERSISTED"}:
            escalation = record_signal(
                self.session,
                source_kind="FEEDBACK",
                source_id=row.feedback_id,
                trigger="UNRESOLVED_MISCONCEPTION",
                queue_kind="ASSESSOR",
                reason="A completed learning check needs human follow-up. Inspect its retained review and evidence.",
                request_key=f"misconception:{row.id}",
            )
        record = MisconceptionReviewRecord(
            id=review_id,
            hypothesis_id=row.id,
            actor_id=actor.id,
            version=version + 1,
            state=command.state,
            request_key=command.request_key,
            payload=command.model_dump(mode="json"),
            evidence_id=evidence_id,
            snapshot_id=snapshot_id,
            escalation_id=escalation.id if escalation else None,
            created_at=when,
        )
        self.session.add(record)
        self._audit(actor, row.id, "reviewed")
        self.session.commit()
        return self.read(actor, identity)

    def _review_evidence(self, actor, row, identity, command, when):
        return LiveEvidenceCapture(self.session)._write(
            task=self.session.get(LearningTask, row.task_id),
            learner_id=row.student_id,
            source=identity,
            field="misconception_review",
            kind=EvidenceType.MISCONCEPTION_CHECK,
            value={
                "hypothesis_id": row.id,
                "reviewed_by": actor.id,
                **command.model_dump(mode="json"),
            },
            occurred_at=when,
            provenance=EvidenceProvenance.EDUCATOR,
            observation=ObservationType.EDUCATOR_RECORDED,
            actor_reference=str(actor.id),
            parents=command.supports + command.contradicts,
        )

    def _snapshot(self, actor, row, identity, evidence_id, when):
        repository = SqlAlchemyLearnerModelRepository(self.session, caller_transaction=True)
        head = repository.current(
            course_id=row.course_id, learner_id=str(row.student_id), outcome_id=row.outcome_id
        )
        snapshot_id = str(uuid4())
        estimates = (
            [
                LearnerOutcomeEstimatePayload(
                    estimate_id=str(uuid4()),
                    dimension=item.dimension,
                    inference_status=item.inference_status,
                    uncertainty=item.uncertainty,
                    reason_code=item.reason_code,
                    evidence_observed_at=item.evidence_observed_at,
                    evidence_signals=tuple(
                        LearnerModelEvidenceSignal(evidence_id=reference, relation=relation)
                        for reference, relation in item.evidence_links
                    ),
                )
                for item in head.estimates
            ]
            if head
            else []
        )
        prior = next(
            (
                item
                for item in estimates
                if item.dimension == LearnerModelDimension.POSSIBLE_MISCONCEPTION
            ),
            None,
        )
        estimates = [
            item
            for item in estimates
            if item.dimension != LearnerModelDimension.POSSIBLE_MISCONCEPTION
        ]
        signals = list(prior.evidence_signals) if prior else []
        signals.append(
            LearnerModelEvidenceSignal(
                evidence_id=evidence_id, relation=EvidenceLinkRelation.SUPPORTS
            )
        )
        estimates.append(
            LearnerOutcomeEstimatePayload(
                estimate_id=str(uuid4()),
                dimension=LearnerModelDimension.POSSIBLE_MISCONCEPTION,
                inference_status=InferenceStatus.NEEDS_REVIEW
                if prior and prior.inference_status == InferenceStatus.NEEDS_REVIEW
                else InferenceStatus.UNCERTAIN,
                uncertainty=1,
                reason_code="observation.educator-misconception-review.v1",
                evidence_observed_at=when,
                evidence_signals=tuple(signals),
            )
        )
        accepted = SqlAlchemyLearnerModelCorrectionRepository(self.session).accepted_targets(
            course_id=row.course_id,
            learner_id=str(row.student_id),
            outcome_id=row.outcome_id,
            evidence_ids=tuple(
                signal.evidence_id for item in estimates for signal in item.evidence_signals
            ),
            snapshot_id=head.snapshot_id if head else None,
        )
        affected = {item.dimension for item in accepted}
        estimates = [
            item.model_copy(update={"inference_status": InferenceStatus.NEEDS_REVIEW})
            if item.dimension.value in affected
            else item
            for item in estimates
        ]
        repository.store(
            LearnerModelSnapshotPayload(
                snapshot_id=snapshot_id,
                course_id=row.course_id,
                learner_id=str(row.student_id),
                outcome_id=row.outcome_id,
                prior_snapshot_id=head.snapshot_id if head else None,
                model_source=ModelSource.EDUCATOR,
                model_version=RULE,
                rule_version=RULE,
                record_version=head.record_version + 1 if head else 1,
                actor_reference=str(actor.id),
                correlation_id=identity,
                idempotency_key=identity,
                occurred_at=when,
                estimates=tuple(estimates),
            ),
            accepted_review_ids=tuple(dict.fromkeys(item.review_id for item in accepted)),
        )
        return snapshot_id

    def _audit(self, actor, identity, action):
        self.session.add(
            PlatformAuditEvent(
                actor_id=actor.id,
                action=f"misconception.{action}",
                resource_type="misconception",
                resource_id=identity,
                correlation_id=str(uuid4()),
                details={"rule_version": RULE},
            )
        )
