"""Course-owner interpretations of scoped evidence, separate from assessment results."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException
from sqlalchemy import select

from app.domain.platform_enums import (
    EvidenceLinkRelation,
    InferenceStatus,
    LearnerModelDimension,
    ModelSource,
)
from app.models.learner_model import LearnerModelSnapshot
from app.models.learning_evidence import LearningEvidence
from app.models.lms import PlatformAuditEvent
from app.models.user import UserRole
from app.schemas.progress import ProfileReviewReceipt
from app.services.course_history import lock_course
from app.services.learner_model.contracts import (
    LearnerModelEvidenceSignal,
    LearnerModelSnapshotPayload,
    LearnerOutcomeEstimatePayload,
)
from app.services.learner_model.repository import SqlAlchemyLearnerModelRepository
from app.services.learning_progress import LearningProgressService

VERSION = "reviewed-profile.v1"


def clone_estimate(estimate, snapshot_id):
    return LearnerOutcomeEstimatePayload(
        estimate_id=str(uuid5(NAMESPACE_URL, f"{snapshot_id}:{estimate.dimension.value}")),
        dimension=estimate.dimension,
        inference_status=estimate.inference_status,
        uncertainty=estimate.uncertainty,
        reason_code=estimate.reason_code,
        evidence_observed_at=estimate.evidence_observed_at,
        evidence_signals=tuple(
            LearnerModelEvidenceSignal(evidence_id=key, relation=relation)
            for key, relation in estimate.evidence_links
        ),
    )


def review_profile(session, actor, course_id, learner_id, outcome_id, request, correlation_id):
    if actor.role != UserRole.EDUCATOR:
        raise HTTPException(404, "Learning profile is unavailable")
    course, roster = LearningProgressService(session).scope(actor, course_id, learner_id=learner_id)
    if learner_id not in session.scalars(roster).all():
        raise HTTPException(404, "Learning profile is unavailable")
    lock_course(session, course)
    # Recheck the actor/enrolment after serializing writers.
    session.refresh(actor)
    _, roster = LearningProgressService(session).scope(actor, course_id, learner_id=learner_id)
    if learner_id not in session.scalars(roster).all():
        raise HTTPException(404, "Learning profile is unavailable")
    identity = str(
        uuid5(
            NAMESPACE_URL,
            f"{VERSION}:{course_id}:{learner_id}:{outcome_id}:{actor.id}:{request.idempotency_key}",
        )
    )
    digest = sha256(request.model_dump_json().encode()).hexdigest()
    existing = session.get(LearnerModelSnapshot, identity)
    if existing:
        audit = session.scalar(
            select(PlatformAuditEvent).where(
                PlatformAuditEvent.resource_id == identity,
                PlatformAuditEvent.action == "learner_profile.reviewed",
            )
        )
        if not audit or audit.details.get("request_digest") != digest:
            raise HTTPException(409, "This request key was already used for another review")
        return ProfileReviewReceipt(
            snapshot_id=identity, version=existing.record_version, created=False
        )

    repository = SqlAlchemyLearnerModelRepository(session, caller_transaction=True)
    head = repository.current(
        course_id=course_id, learner_id=str(learner_id), outcome_id=outcome_id
    )
    if request.expected_version != (head.record_version if head else 0):
        raise HTTPException(409, "The profile changed; refresh before reviewing it")
    rows = session.scalars(
        select(LearningEvidence).where(
            LearningEvidence.id.in_([item.evidence_id for item in request.evidence]),
            LearningEvidence.course_id == course_id,
            LearningEvidence.learner_id == learner_id,
            LearningEvidence.outcome_id == outcome_id,
        )
    ).all()
    if len(rows) != len(request.evidence):
        raise HTTPException(404, "Review evidence is unavailable in this outcome")
    expected_relation = {
        InferenceStatus.SUPPORTED: EvidenceLinkRelation.SUPPORTS,
        InferenceStatus.CONTRADICTED: EvidenceLinkRelation.CONTRADICTS,
    }.get(request.status)
    if expected_relation and not any(
        item.relation == expected_relation for item in request.evidence
    ):
        raise HTTPException(422, "The interpretation needs evidence with the matching relationship")
    if (
        request.dimension == LearnerModelDimension.FEEDBACK_USE
        and request.status == InferenceStatus.SUPPORTED
    ):
        from app.services.progress_indicators import indicators

        linked, _ = indicators(session, course_id, learner_id, outcome_id)
        selected = {item.evidence_id for item in request.evidence}
        if not any(
            item.kind.startswith("feedback_") and set(item.evidence_ids) <= selected
            for item in linked
        ):
            raise HTTPException(
                422,
                "Useful feedback review requires its acknowledgement, original response and linked later revision or transfer",
            )
    now = datetime.now(UTC)
    observed = max(
        row.occurred_at.replace(tzinfo=UTC)
        if row.occurred_at.tzinfo is None
        else row.occurred_at.astimezone(UTC)
        for row in rows
    )
    if observed > now:
        raise HTTPException(422, "Review evidence cannot be in the future")
    estimates = (
        [
            clone_estimate(item, identity)
            for item in head.estimates
            if item.dimension != request.dimension
        ]
        if head
        else []
    )
    prior = (
        next((item for item in head.estimates if item.dimension == request.dimension), None)
        if head
        else None
    )
    links = dict(prior.evidence_links) if prior else {}
    links.update({item.evidence_id: item.relation for item in request.evidence})
    reason_code = f"reviewed-profile.{digest[:24]}"
    estimates.append(
        LearnerOutcomeEstimatePayload(
            estimate_id=str(uuid5(NAMESPACE_URL, f"{identity}:{request.dimension.value}")),
            dimension=request.dimension,
            inference_status=request.status,
            uncertainty=request.uncertainty,
            reason_code=reason_code,
            evidence_observed_at=max(observed, prior.evidence_observed_at) if prior else observed,
            evidence_signals=tuple(
                LearnerModelEvidenceSignal(evidence_id=key, relation=value)
                for key, value in sorted(links.items())
            ),
        )
    )
    payload = LearnerModelSnapshotPayload(
        snapshot_id=identity,
        course_id=course_id,
        learner_id=str(learner_id),
        outcome_id=outcome_id,
        prior_snapshot_id=head.snapshot_id if head else None,
        model_source=ModelSource.EDUCATOR,
        model_version=VERSION,
        rule_version=VERSION,
        record_version=request.expected_version + 1,
        actor_reference=str(actor.id),
        correlation_id=correlation_id,
        idempotency_key=identity,
        occurred_at=now,
        estimates=tuple(estimates),
    )
    repository.store(payload)
    session.add(
        PlatformAuditEvent(
            actor_id=actor.id,
            action="learner_profile.reviewed",
            resource_type="learner_model_snapshot",
            resource_id=identity,
            correlation_id=correlation_id,
            details={
                "request_digest": digest,
                "reason_code": reason_code,
                "reason": request.reason,
                "dimension": request.dimension.value,
                "course_id": course_id,
            },
        )
    )
    session.commit()
    return ProfileReviewReceipt(snapshot_id=identity, version=payload.record_version, created=True)
