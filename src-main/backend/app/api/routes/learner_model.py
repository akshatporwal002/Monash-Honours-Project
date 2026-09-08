"""Scoped learner-model correction endpoints."""

import base64
import json
from datetime import UTC
from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentEducator, CurrentStudent
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db
from app.models.learner_model import LearnerModelAnnotation, LearnerModelCorrectionReview
from app.models.learning_evidence import LearningEvidence
from app.schemas.feedback_api import AuthenticatedActor
from app.services.learner_model.correction_contracts import (
    CorrectionTarget,
    EducatorCorrectionReviewCommand,
    EducatorCorrectionReviewPayload,
    EducatorCorrectionReviewRequest,
    LearnerAnnotationCommand,
    LearnerAnnotationPayload,
    LearnerAnnotationRequest,
    LearnerModelTimelineCorrection,
    LearnerModelTimelineEntry,
    LearnerModelTimelineEstimate,
    LearnerModelTimelineEvidence,
    LearnerModelTimelineResponse,
    LearnerModelTimelineSnapshot,
)
from app.services.learner_model.correction_repository import (
    SqlAlchemyLearnerModelCorrectionRepository,
)
from app.services.learner_model.corrections import LearnerModelCorrectionService
from app.services.learner_model.repository import SqlAlchemyLearnerModelRepository
from app.services.learner_model.safety import (
    LearnerModelConflictError,
    LearnerModelCorrectionNotFoundError,
    LearnerModelPersistenceError,
)

router = APIRouter(prefix="/learner-model", tags=["learner model"])

_CORRECTION_REQUEST_NAMESPACE = UUID("91bb4900-d5e5-414f-b12c-506007603a28")


def _service(session: Session) -> LearnerModelCorrectionService:
    return LearnerModelCorrectionService(SqlAlchemyLearnerModelCorrectionRepository(session))


def _headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _request_identity(kind: str, actor_id: str, idempotency_key: str) -> tuple[str, str]:
    """Stable server identifiers make an HTTP retry an exact command replay."""
    seed = f"{kind}:{actor_id}:{idempotency_key}"
    return (
        str(uuid5(_CORRECTION_REQUEST_NAMESPACE, f"record:{seed}")),
        str(uuid5(_CORRECTION_REQUEST_NAMESPACE, f"correlation:{seed}")),
    )


def _timeline(
    session: Session,
    *,
    actor_id: str,
    course_id: str,
    learner_id: str,
    outcome_id: str,
    cursor: str | None,
    limit: int,
) -> LearnerModelTimelineResponse:
    """Metadata-only projection; protected evidence artefacts are never included."""
    corrections = _service(session).history(
        actor_reference=actor_id, course_id=course_id, learner_id=learner_id, outcome_id=outcome_id
    )
    evidence = (
        session.query(LearningEvidence)
        .filter_by(course_id=course_id, learner_id=int(learner_id), outcome_id=outcome_id)
        .order_by(LearningEvidence.occurred_at, LearningEvidence.id)
        .all()
    )
    snapshots = SqlAlchemyLearnerModelRepository(session).timeline(
        course_id=course_id, learner_id=learner_id, outcome_id=outcome_id
    )
    entries = [
        LearnerModelTimelineEntry(
            entry_type="OBSERVATION", reference_id=item.id, occurred_at=item.occurred_at
        )
        for item in evidence
    ]
    entries.extend(
        LearnerModelTimelineEntry(
            entry_type="INFERENCE", reference_id=item.snapshot_id, occurred_at=item.occurred_at
        )
        for item in snapshots
    )
    for item in corrections:
        entries.append(
            LearnerModelTimelineEntry(
                entry_type="ANNOTATION",
                reference_id=item.annotation.annotation_id,
                occurred_at=item.annotation.occurred_at,
            )
        )
        entries.extend(
            LearnerModelTimelineEntry(
                entry_type="REVIEW", reference_id=review.review_id, occurred_at=review.occurred_at
            )
            for review in item.reviews
        )
    entries.sort(
        key=lambda item: (
            item.occurred_at.astimezone(UTC).isoformat(),
            item.entry_type,
            item.reference_id,
        )
    )
    if cursor is not None:
        cursor_key = _decode_cursor(cursor)
        entries = [item for item in entries if _entry_key(item) > cursor_key]
    page = entries[:limit]
    next_cursor = _encode_cursor(_entry_key(page[-1])) if len(entries) > limit else None
    page_ids = {entry.reference_id for entry in page}
    return LearnerModelTimelineResponse(
        evidence=[
            LearnerModelTimelineEvidence(
                id=item.id,
                type=item.evidence_type.value,
                provenance=item.provenance.value,
                occurred_at=item.occurred_at,
            )
            for item in evidence
            if item.id in page_ids
        ],
        snapshots=[
            LearnerModelTimelineSnapshot(
                snapshot_id=snapshot.snapshot_id,
                prior_snapshot_id=snapshot.prior_snapshot_id,
                record_version=snapshot.record_version,
                model_source=snapshot.model_source,
                model_version=snapshot.model_version,
                rule_version=snapshot.rule_version,
                occurred_at=snapshot.occurred_at,
                validation_classification=snapshot.validation_classification,
                estimates=[
                    LearnerModelTimelineEstimate(
                        estimate_id=estimate.estimate_id,
                        dimension=estimate.dimension,
                        inference_status=estimate.inference_status,
                        uncertainty=estimate.uncertainty,
                        reason_code=estimate.reason_code,
                        evidence_observed_at=estimate.evidence_observed_at,
                        evidence_links=[list(link) for link in estimate.evidence_links],
                    )
                    for estimate in snapshot.estimates
                ],
            )
            for snapshot in snapshots
            if snapshot.snapshot_id in page_ids
        ],
        corrections=[
            LearnerModelTimelineCorrection(
                annotation=item.annotation,
                reviews=[review for review in item.reviews if review.review_id in page_ids],
            )
            for item in corrections
            if item.annotation.annotation_id in page_ids
            or any(review.review_id in page_ids for review in item.reviews)
        ],
        entries=page,
        next_cursor=next_cursor,
    )


def _entry_key(entry: LearnerModelTimelineEntry) -> tuple[str, str, str]:
    return (entry.occurred_at.astimezone(UTC).isoformat(), entry.entry_type, entry.reference_id)


def _encode_cursor(key: tuple[str, str, str]) -> str:
    return (
        base64.urlsafe_b64encode(json.dumps(key, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )


def _decode_cursor(cursor: str) -> tuple[str, str, str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded).decode())
        if (
            not isinstance(value, list)
            or len(value) != 3
            or not all(isinstance(item, str) for item in value)
        ):
            raise ValueError
        return (value[0], value[1], value[2])
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(422, "The timeline cursor is invalid.") from None


@router.get("/me/timeline", response_model=LearnerModelTimelineResponse)
def my_timeline(
    course_id: str,
    outcome_id: str,
    response: Response,
    student: CurrentStudent,
    session: Session = Depends(get_db),
    cursor: str | None = None,
    limit: int = 50,
):
    _headers(response)
    try:
        return _timeline(
            session,
            actor_id=str(student.id),
            course_id=course_id,
            learner_id=str(student.id),
            outcome_id=outcome_id,
            cursor=cursor,
            limit=min(max(limit, 1), 100),
        )
    except LearnerModelCorrectionNotFoundError:
        raise HTTPException(404, "Learner-model history was not found.") from None


@router.post("/me/annotations", status_code=201, response_model=LearnerAnnotationPayload)
async def annotate(
    payload: LearnerAnnotationRequest,
    request: Request,
    response: Response,
    student: CurrentStudent,
    session: Session = Depends(get_db),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    _headers(response)
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(student.id), role=student.role.value),
        "learner-model-corrections",
        mutating=True,
    )
    annotation_id, correlation_id = _request_identity(
        "annotation", str(student.id), payload.idempotency_key
    )
    command = LearnerAnnotationCommand(
        annotation_id=annotation_id,
        learner_id=str(student.id),
        actor_reference=str(student.id),
        correlation_id=correlation_id,
        record_version=1,
        **payload.model_dump(),
    )
    try:
        result = _service(session).annotate(command)
    except LearnerModelConflictError:
        raise HTTPException(
            409, "The annotation request conflicts with existing history."
        ) from None
    except LearnerModelCorrectionNotFoundError:
        raise HTTPException(404, "Learner-model record was not found.") from None
    except LearnerModelPersistenceError:
        raise HTTPException(503, "Learner-model corrections are temporarily unavailable.") from None
    if not result.created:
        response.status_code = 200
    return result.annotation


@router.get(
    "/courses/{course_id}/learners/{learner_id}/timeline",
    response_model=LearnerModelTimelineResponse,
)
def educator_timeline(
    course_id: str,
    learner_id: str,
    outcome_id: str,
    response: Response,
    educator: CurrentEducator,
    session: Session = Depends(get_db),
    cursor: str | None = None,
    limit: int = 50,
):
    _headers(response)
    try:
        return _timeline(
            session,
            actor_id=str(educator.id),
            course_id=course_id,
            learner_id=learner_id,
            outcome_id=outcome_id,
            cursor=cursor,
            limit=min(max(limit, 1), 100),
        )
    except LearnerModelCorrectionNotFoundError:
        raise HTTPException(404, "Learner-model history was not found.") from None


@router.post(
    "/courses/{course_id}/learners/{learner_id}/annotations/{annotation_id}/reviews",
    status_code=201,
    response_model=EducatorCorrectionReviewPayload,
)
async def review(
    course_id: str,
    learner_id: str,
    annotation_id: str,
    outcome_id: str,
    payload: EducatorCorrectionReviewRequest,
    response: Response,
    request: Request,
    educator: CurrentEducator,
    session: Session = Depends(get_db),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    _headers(response)
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(educator.id), role=educator.role.value),
        "learner-model-corrections",
        mutating=True,
    )
    if payload.annotation_id != annotation_id:
        raise HTTPException(404, "Learner-model record was not found.")
    annotation = session.get(LearnerModelAnnotation, annotation_id)
    if annotation is None:
        raise HTTPException(404, "Learner-model record was not found.")
    latest = (
        session.query(LearnerModelCorrectionReview)
        .filter(LearnerModelCorrectionReview.annotation_id == annotation_id)
        .order_by(LearnerModelCorrectionReview.review_version.desc())
        .first()
    )
    review_id, correlation_id = _request_identity(
        "review", str(educator.id), payload.idempotency_key
    )
    command = EducatorCorrectionReviewCommand(
        review_id=review_id,
        annotation_id=annotation_id,
        course_id=course_id,
        learner_id=learner_id,
        outcome_id=outcome_id,
        target=CorrectionTarget(
            target_kind=annotation.target_kind,
            evidence_id=annotation.evidence_id,
            estimate_id=annotation.estimate_id,
        ),
        actor_reference=str(educator.id),
        correlation_id=correlation_id,
        review_version=payload.expected_latest_review_version + 1,
        prior_review_id=None if latest is None else latest.id,
        **payload.model_dump(exclude={"annotation_id"}),
    )
    try:
        result = _service(session).review(command)
    except LearnerModelConflictError:
        raise HTTPException(
            409, "The review is stale; refresh history before resubmitting."
        ) from None
    except LearnerModelCorrectionNotFoundError:
        raise HTTPException(404, "Learner-model record was not found.") from None
    if not result.created:
        response.status_code = 200
    return result.review
