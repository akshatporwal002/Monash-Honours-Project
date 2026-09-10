"""Inspect a single scoped observation without exposing internal artifact context."""

import json
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy import select

from app.domain.platform_enums import EvidenceType
from app.models.learning_evidence import EvidenceArtifact, EvidenceLink, LearningEvidence
from app.models.persistence import LearningTask
from app.models.user import UserRole
from app.schemas.progress import ProgressEvidenceDetail
from app.services.learning_progress import LearningProgressService
from app.services.misconception_state import active_assessed_transfer, active_fresh_check
from app.services.task_review import TaskReviewError

# Only learner-facing observation fields are projected. Internal versions, protected
# task conditions, tutor context, request keys and source approvals stay private.
DISPLAY_FIELDS = {
    "answer",
    "code",
    "circuit",
    "prediction",
    "input",
    "content",
    "reason",
    "reasoning",
    "explanation",
    "reflection",
    "confidence",
    "help_used",
    "stage",
    "state",
    "next_action",
    "message",
    "reply",
    "kind",
    "action",
    "item_index",
    "previous_response_version_id",
    "status",
    "result",
    "error_code",
    "shots",
    "seed",
    "prior_knowledge",
    "concept_uncertainty",
    "requested_support",
    "independent_conditions_met",
}


def read_progress_evidence(session, actor, course_id, evidence_id):
    evidence = session.get(LearningEvidence, evidence_id)
    if evidence is None or evidence.course_id != course_id:
        raise HTTPException(404, "This observation is unavailable")
    LearningProgressService(session).scope(actor, course_id, learner_id=evidence.learner_id)
    task = session.get(LearningTask, evidence.task_id)
    # Do not follow moved task content across the frozen course boundary.
    if task is None or task.course_id != course_id:
        raise HTTPException(404, "This observation is unavailable under current task access")
    if actor.role == UserRole.STUDENT and (
        active_fresh_check(session, actor.id, task.id)
        or active_assessed_transfer(session, actor.id, task.id)
    ):
        raise HTTPException(409, "Saved observation content is unavailable during a fresh check")
    if actor.role == UserRole.STUDENT and evidence.evidence_type == EvidenceType.SIMULATION:
        from app.models.simulation import CircuitVersion, SimulationRun
        from app.services.episodes import EpisodeService

        run = session.get(SimulationRun, evidence.source_interaction_id)
        circuit = session.get(CircuitVersion, run.circuit_version_id) if run else None
        if (
            not run
            or not circuit
            or (run.owner_id, circuit.course_id, circuit.task_id) != (actor.id, course_id, task.id)
        ):
            raise HTTPException(404, "The recorded simulation is unavailable")
        try:
            EpisodeService(session).require_run_reveal(run, circuit)
        except TaskReviewError as error:
            raise HTTPException(error.status_code, error.detail) from error
    artifact = session.get(EvidenceArtifact, evidence.artifact_id) if evidence.artifact_id else None
    fields = []
    status = (
        "The original content is unavailable in this view. Its evidence reference is preserved."
    )
    if (
        artifact
        and (artifact.course_id, artifact.learner_id, artifact.content_digest)
        == (course_id, evidence.learner_id, evidence.content_digest)
        and evidence.content_digest == "sha256:" + sha256(artifact.content.encode()).hexdigest()
    ):
        try:
            payload = json.loads(artifact.content)
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            if evidence.schema_version == "learnlens.live-evidence.v1":
                value = payload.get("value")
            elif evidence.schema_version == "learnlens.diagnostic.v1":
                value = payload.get("response")
            else:
                value = None
            if isinstance(value, str):
                fields = [{"label": "Recorded observation", "text": value}]
            elif isinstance(value, dict):
                fields = [
                    {
                        "label": key.replace("_", " ").capitalize(),
                        "text": item
                        if isinstance(item, str)
                        else json.dumps(item, ensure_ascii=False, indent=2),
                    }
                    for key, item in value.items()
                    if key in DISPLAY_FIELDS and item is not None
                ]
            if fields:
                status = "Original recorded observation. This content does not determine a formal result."
    related = list(
        session.scalars(
            select(EvidenceLink.linked_evidence_id)
            .join(LearningEvidence, LearningEvidence.id == EvidenceLink.linked_evidence_id)
            .where(
                EvidenceLink.evidence_id == evidence.id,
                LearningEvidence.course_id == course_id,
                LearningEvidence.learner_id == evidence.learner_id,
                LearningEvidence.outcome_id == evidence.outcome_id,
            )
            .order_by(EvidenceLink.linked_evidence_id)
        )
    )
    return ProgressEvidenceDetail(
        evidence_id=evidence.id,
        course_id=course_id,
        learner_id=evidence.learner_id,
        outcome_id=evidence.outcome_id,
        task_id=evidence.task_id,
        response_id=evidence.response_version_id,
        kind=evidence.evidence_type.value,
        support_level=evidence.instructional_support_level,
        occurred_at=evidence.occurred_at,
        status=status,
        fields=fields,
        related_evidence_ids=related,
        confidence=LearningProgressService(session)._confidence(evidence),
    )
