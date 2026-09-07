"""Server-owned observation construction; every write joins its source transaction."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.platform_enums import (
    AccessSupportState,
    EvidenceLinkRelation,
    EvidenceProvenance,
    EvidenceType,
    InstructionalSupportLevel,
    ObservationType,
)
from app.models.assessment import TaskApproval, TaskFormVersion
from app.models.assessment_work import AssessmentWorkStart
from app.models.episode import EpisodeCheckpoint, EpisodeHelpUse, EpisodeStageStart
from app.models.learning_evidence import LearningEvidence
from app.models.lms import PlatformAuditEvent, SubmissionAttempt
from app.models.persistence import LearningTask
from app.models.simulation import CircuitVersion, SimulationOutcome, SimulationRun
from app.models.task_review import TaskReviewEvent, TaskRevision
from app.schemas.evidence import EvidenceArtifact, EvidenceLink, EvidenceRecord
from app.services.evidence.repository import EvidenceCapture, SqlAlchemyEvidenceRepository
from app.services.evidence.safety import opaque_fingerprint


def evidence_id(source: str, field: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"learnlens.live-evidence.v1:{source}:{field}"))


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def serialized(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


class LiveEvidenceCapture:
    """Use only records already validated by the owning learner command service.

    Never commits. A failure aborts the owning command transaction. Existing
    source records remain intact and simulation recovery can retry its final write.
    """

    def __init__(self, session: Session):
        self.session = session
        self.repository = SqlAlchemyEvidenceRepository(session)

    def _write(
        self,
        *,
        task,
        learner_id,
        source,
        field,
        kind,
        value,
        occurred_at,
        work_id=None,
        response_id=None,
        parents=(),
        provenance=EvidenceProvenance.LEARNER,
        observation=ObservationType.DIRECT,
        support=InstructionalSupportLevel.INDEPENDENT,
        access=AccessSupportState.NOT_DECLARED,
    ):
        # Unscoped sandbox circuits are not course learning observations.
        if not task.course_id or not task.learning_outcome_id:
            return None
        identity = evidence_id(source, field)
        existing = self.session.get(LearningEvidence, identity)
        if existing is not None:
            return identity
        work = self.session.get(AssessmentWorkStart, work_id) if work_id else None
        if work and (work.student_id, work.task_id, work.course_id) != (
            learner_id,
            task.id,
            task.course_id,
        ):
            raise ValueError("Evidence work scope differs from source")
        form = self.session.get(TaskFormVersion, work.task_form_version_id) if work else None
        approval = self.session.get(TaskApproval, work.task_approval_id) if work else None
        review = (
            self.session.get(TaskReviewEvent, approval.task_review_event_id)
            if approval and approval.task_review_event_id
            else None
        )
        if not work:
            review = self.session.scalar(
                select(TaskReviewEvent)
                .join(TaskRevision, TaskReviewEvent.task_revision_id == TaskRevision.id)
                .where(
                    TaskRevision.task_id == task.id,
                    TaskReviewEvent.state == "APPROVED",
                    TaskReviewEvent.created_at <= occurred_at,
                )
                .order_by(TaskReviewEvent.created_at.desc(), TaskReviewEvent.id.desc())
                .limit(1)
            )
        source_approval_ids = set(review.source_approvals.values()) if review else set()
        source_version = next(iter(source_approval_ids)) if len(source_approval_ids) == 1 else None
        context = {
            "task_review_event_id": review.id if review else None,
            "source_approvals": review.source_approvals if review else {},
            "source_version": form.source_version if form else None,
            "source_record": source,
            "field": field,
            "assessment_work_start_id": work.id if work else None,
            "task_form_version_id": work.task_form_version_id if work else None,
            "task_approval_id": work.task_approval_id if work else None,
            "source_references": work.source_references if work else [],
            "declared_conditions": work.declared_conditions if work else None,
        }
        content = serialized({"context": context, "value": value})
        # Large immutable responses remain available through their exact source.
        if len(content) > 65_536:
            content = serialized(
                {
                    "context": context,
                    "value_reference": source,
                    "value_digest": "sha256:" + sha256(serialized(value).encode()).hexdigest(),
                }
            )
        digest = "sha256:" + sha256(content.encode()).hexdigest()
        artifact_id = evidence_id(source, field + ":artifact")
        when = utc(occurred_at)
        actor = str(learner_id)
        record = EvidenceRecord(
            evidence_id=identity,
            course_id=task.course_id,
            learner_id=actor,
            outcome_id=task.learning_outcome_id,
            activity_id=work.id if work else task.id,
            task_id=task.id,
            response_version_id=response_id,
            source_interaction_id=source,
            source_version=source_version,
            task_conditions_version=form.version if form else None,
            evidence_type=kind,
            provenance=provenance,
            observation_type=observation,
            instructional_support_level=support,
            access_support_state=access,
            artifact_id=artifact_id,
            content_digest=digest,
            actor_reference=actor,
            agent_reference="live-evidence.v1",
            correlation_id=identity,
            schema_version="learnlens.live-evidence.v1",
            record_version=1,
            idempotency_key=identity,
            occurred_at=when,
        )
        links = tuple(
            EvidenceLink(
                evidence_id=identity,
                linked_evidence_id=parent,
                relation=EvidenceLinkRelation.DERIVES_FROM,
                actor_reference=actor,
                correlation_id=identity,
                occurred_at=when,
            )
            for parent in dict.fromkeys(parents)
            if parent and parent != identity
        )
        result = self.repository.capture(
            EvidenceCapture(
                record=record,
                artifact=EvidenceArtifact(
                    artifact_id=artifact_id,
                    course_id=task.course_id,
                    learner_id=actor,
                    content=content,
                    content_digest=digest,
                    content_format="application.json",
                    record_version=1,
                    occurred_at=when,
                ),
                links=links,
            ),
            commit=False,
        )
        if result.created:
            self.session.add(
                PlatformAuditEvent(
                    id=evidence_id(source, field + ":audit"),
                    actor_id=None,
                    action="learning_evidence.created",
                    resource_type="learning_evidence",
                    resource_id=opaque_fingerprint(identity),
                    correlation_id=identity,
                    outcome="success",
                    occurred_at=when,
                    details={
                        "actor_fingerprint": opaque_fingerprint(actor),
                        "schema_version": record.schema_version,
                        "evidence_type": kind.value,
                    },
                )
            )
            self.session.flush()
        return identity

    def checkpoint(self, checkpoint):
        task = self.session.get(LearningTask, checkpoint.task_id)
        support, access, parents = self._support_for(
            checkpoint.assessment_work_start_id, checkpoint.created_at, checkpoint.stage_start_id
        )
        return self._write(
            task=task,
            learner_id=checkpoint.student_id,
            source=checkpoint.id,
            support=support,
            access=access,
            parents=parents,
            field="prediction",
            kind=EvidenceType.PREDICTION,
            value={
                "prediction": checkpoint.prediction,
                "input": checkpoint.input_content,
                "part_id": checkpoint.part_id,
                "stage_start_id": checkpoint.stage_start_id,
            },
            work_id=checkpoint.assessment_work_start_id,
            occurred_at=checkpoint.created_at,
        )

    def support(self, receipt):
        record = receipt["record"]
        task = self.session.get(LearningTask, self.session.get(EpisodeHelpUse, record.id).task_id)
        work = self.session.get(AssessmentWorkStart, record.assessment_work_start_id)
        conceptual = record.kind == "conceptual_hint"
        return self._write(
            task=task,
            learner_id=work.student_id,
            source=record.id,
            field="support",
            kind=EvidenceType.HINT if conceptual else EvidenceType.SCAFFOLD,
            value=record.model_dump(mode="json"),
            work_id=work.id,
            occurred_at=record.created_at,
            observation=ObservationType.SYSTEM_CAPTURED,
            support=InstructionalSupportLevel.CONCEPT_CUE
            if conceptual
            else InstructionalSupportLevel.INDEPENDENT,
            access=AccessSupportState.NOT_DECLARED if conceptual else AccessSupportState.PROVIDED,
        )

    def submission(self, response):
        if self.session.get(LearningEvidence, evidence_id(response.id, "response")) is not None:
            return
        task = self.session.get(LearningTask, response.task_id)
        common = dict(
            task=task,
            learner_id=response.student_id,
            source=response.id,
            work_id=response.assessment_work_start_id,
            response_id=response.id,
            occurred_at=response.submitted_at,
        )
        previous = self.session.scalar(
            select(SubmissionAttempt)
            .where(
                SubmissionAttempt.student_id == response.student_id,
                SubmissionAttempt.task_id == response.task_id,
                SubmissionAttempt.attempt_number < response.attempt_number,
            )
            .order_by(SubmissionAttempt.attempt_number.desc())
            .limit(1)
        )
        parents = ()
        if previous:
            prior_id = evidence_id(previous.id, "response")
            if self.session.get(LearningEvidence, prior_id):
                parents = (prior_id,)
        episode = response.episode or {}
        supported_process = episode.get("supported", {})
        parents = (*parents, *self._sources(supported_process))
        support, access, support_parents = self._support_for(
            response.assessment_work_start_id, response.submitted_at
        )
        parents = (*parents, *support_parents)
        common.update(support=support, access=access)
        root = self._write(
            **common,
            field="response",
            kind=EvidenceType.RESPONSE,
            value={"answer": response.answer, "code": response.code, "circuit": response.circuit},
            parents=parents,
        )
        if previous:
            self._write(
                **common,
                field="revision",
                kind=EvidenceType.REVISION,
                value={"previous_response_version_id": previous.id},
                parents=(root, *parents),
            )
        episode = response.episode or {}
        self._process(common, episode.get("supported", {}), "supported", root)
        transfer = episode.get("transfer")
        if transfer:
            transfer_support, transfer_access, transfer_parents = self._support_for(
                response.assessment_work_start_id, response.submitted_at, transfer["stage_start_id"]
            )
            common = {**common, "support": transfer_support, "access": transfer_access}
            ref = self._write(
                **common,
                field="transfer",
                kind=EvidenceType.TRANSFER,
                value={
                    "content": transfer["content"],
                    "stage_start_id": transfer["stage_start_id"],
                    "part_id": transfer["part_id"],
                },
                parents=(root, *transfer_parents, *self._sources(transfer.get("process", {}))),
            )
            self._process(common, transfer.get("process", {}), "transfer", ref)

    def _support_for(self, work_id, when, stage_id=None):
        if not work_id:
            return InstructionalSupportLevel.INDEPENDENT, AccessSupportState.NOT_DECLARED, ()
        uses = list(
            self.session.scalars(
                select(EpisodeHelpUse).where(
                    EpisodeHelpUse.assessment_work_start_id == work_id,
                    (EpisodeHelpUse.stage_start_id == stage_id)
                    | (EpisodeHelpUse.kind == "accessibility"),
                    EpisodeHelpUse.created_at <= when,
                )
            )
        )
        from app.services.episode_support import EpisodeSupportService

        parents = tuple(self.support({"record": EpisodeSupportService.read(use)}) for use in uses)
        kinds = {use.kind for use in uses}
        return (
            InstructionalSupportLevel.CONCEPT_CUE
            if "conceptual_hint" in kinds
            else InstructionalSupportLevel.INDEPENDENT,
            AccessSupportState.PROVIDED
            if "accessibility" in kinds
            else AccessSupportState.NOT_DECLARED,
            parents,
        )

    def _sources(self, process):
        parents = []
        if process.get("prediction_checkpoint_id"):
            checkpoint = self.session.get(EpisodeCheckpoint, process["prediction_checkpoint_id"])
            if checkpoint:
                parents.append(self.checkpoint(checkpoint))
        for reference in process.get("simulation_references", []):
            run = self.session.get(SimulationRun, reference["run_id"])
            outcome = self.session.get(SimulationOutcome, reference["run_id"])
            if run and outcome:
                self.simulation(run, outcome)
                parents.append(evidence_id(run.id, "simulation"))
        return tuple(parents)

    def _process(self, common, process, stage, parent):
        checkpoint = (
            self.session.get(EpisodeCheckpoint, process.get("prediction_checkpoint_id"))
            if process.get("prediction_checkpoint_id")
            else None
        )
        parents = (parent, self.checkpoint(checkpoint)) if checkpoint else (parent,)
        for field in ("prediction", "reasoning", "explanation", "reflection", "revision"):
            value = process.get(field)
            if value is not None and not (field == "prediction" and checkpoint):
                field_parents = parents
                if field == "revision":
                    earlier = evidence_id(value["previous_response_version_id"], "response")
                    if self.session.get(LearningEvidence, earlier):
                        field_parents = (*parents, earlier)
                self._write(
                    **common,
                    field=stage + ":" + field,
                    kind=EvidenceType(field.upper()),
                    value=value,
                    parents=field_parents,
                )

    def simulation(self, run, outcome):
        circuit = self.session.get(CircuitVersion, run.circuit_version_id)
        if not circuit.task_id:
            return
        task = self.session.get(LearningTask, circuit.task_id)
        checkpoint = (
            self.session.get(EpisodeCheckpoint, run.prediction_checkpoint_id)
            if run.prediction_checkpoint_id
            else None
        )
        parent = self.checkpoint(checkpoint) if checkpoint else None
        response = (
            self.session.get(SubmissionAttempt, run.submission_id) if run.submission_id else None
        )
        stage = (
            self.session.get(EpisodeStageStart, run.episode_stage_start_id)
            if run.episode_stage_start_id
            else None
        )
        work = self.session.scalar(
            select(AssessmentWorkStart).where(
                AssessmentWorkStart.student_id == run.owner_id,
                AssessmentWorkStart.task_id == circuit.task_id,
                AssessmentWorkStart.started_at <= run.created_at,
            )
        )
        work_id = (
            checkpoint.assessment_work_start_id
            if checkpoint
            else response.assessment_work_start_id
            if response
            else work.id
            if work
            else None
        )
        support, access, support_parents = self._support_for(
            work_id, run.created_at, run.episode_stage_start_id
        )
        self._write(
            task=task,
            learner_id=run.owner_id,
            support=support,
            access=access,
            source=run.id,
            field="simulation",
            kind=EvidenceType.SIMULATION
            if outcome.status == "completed"
            else EvidenceType.SYSTEM_FAULT,
            value={
                "episode_stage_start_id": run.episode_stage_start_id,
                "part_id": stage.part_id if stage else None,
                "run_id": run.id,
                "circuit_version_id": circuit.id,
                "circuit": circuit.circuit,
                "status": outcome.status,
                "error_code": outcome.error_code,
                "result": outcome.result,
                "seed": run.seed,
                "shots": run.shots,
                "engine_versions": run.engine_versions,
                "policy_version": run.policy_version,
                "purpose": run.purpose,
            },
            occurred_at=outcome.created_at,
            parents=(parent, *support_parents),
            response_id=run.submission_id,
            work_id=work_id,
            provenance=EvidenceProvenance.SIMULATOR,
            observation=ObservationType.SYSTEM_CAPTURED,
        )

    def acknowledge_feedback(self, response, feedback_id, workflow_id):
        from datetime import datetime

        self.submission(response)
        task = self.session.get(LearningTask, response.task_id)
        return self._write(
            task=task,
            learner_id=response.student_id,
            source=feedback_id,
            field="acknowledgement",
            kind=EvidenceType.FEEDBACK_INTERACTION,
            value={
                "action": "acknowledged",
                "feedback_id": feedback_id,
                "workflow_run_id": workflow_id,
            },
            work_id=response.assessment_work_start_id,
            response_id=response.id,
            occurred_at=datetime.now(UTC),
            parents=(evidence_id(response.id, "response"),),
            observation=ObservationType.SELF_REPORTED,
        )
