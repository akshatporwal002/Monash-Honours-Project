"""Course-scoped learning progress; all reads are side-effect free."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentEducator, CurrentUser
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.progress import (
    LearningProgressPage,
    ProfileReviewReceipt,
    ProfileReviewRequest,
    ProgressEvidenceDetail,
    ProgressTrendPage,
)
from app.services.learner_model.profile_reviews import review_profile
from app.services.learner_model.safety import LearnerModelConflictError, LearnerModelSafetyError
from app.services.learning_progress import LearningProgressService
from app.services.progress_evidence import read_progress_evidence
from app.services.progress_trends import contributing_records, records_query

router = APIRouter(prefix="/progress", tags=["learning progress"])


@router.post(
    "/{course_id}/learners/{learner_id}/outcomes/{outcome_id}/reviews",
    response_model=ProfileReviewReceipt,
)
async def record_profile_review(
    course_id: str,
    learner_id: int,
    outcome_id: str,
    payload: ProfileReviewRequest,
    actor: CurrentEducator,
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    response.headers["Cache-Control"] = "no-store"
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(actor.id), role=actor.role.value),
        "learner-model-corrections",
        mutating=True,
    )
    try:
        return review_profile(
            session, actor, course_id, learner_id, outcome_id, payload, request.state.correlation_id
        )
    except LearnerModelConflictError:
        session.rollback()
        raise HTTPException(409, "The profile changed; refresh before reviewing it") from None
    except LearnerModelSafetyError:
        session.rollback()
        raise HTTPException(422, "The profile review could not be recorded") from None
    except HTTPException:
        session.rollback()
        raise


@router.get("/{course_id}/records", response_model=ProgressTrendPage)
def trend_records(
    course_id: str,
    kind: str,
    actor: CurrentUser,
    response: Response,
    learner_id: int | None = Query(default=None, gt=0),
    outcome_id: str | None = None,
    week: date | None = None,
    response_id: str | None = None,
    limit: int = Query(default=25, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    _, roster = LearningProgressService(session).scope(actor, course_id, learner_id=learner_id)
    return contributing_records(
        session,
        records_query(course_id, roster, outcome_id),
        course_id=course_id,
        kind=kind,
        week=week,
        response_id=response_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{course_id}/evidence/{evidence_id}", response_model=ProgressEvidenceDetail)
def inspect_evidence(
    course_id: str,
    evidence_id: str,
    actor: CurrentUser,
    response: Response,
    session: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    return read_progress_evidence(session, actor, course_id, evidence_id)


@router.get("/{course_id}", response_model=LearningProgressPage)
def read_progress(
    course_id: str,
    actor: CurrentUser,
    response: Response,
    learner_id: int | None = Query(default=None, gt=0),
    outcome_id: str | None = None,
    limit: int = Query(default=10, ge=1, le=25),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    return LearningProgressService(session).read(
        actor, course_id, learner_id=learner_id, outcome_id=outcome_id, limit=limit, offset=offset
    )
