"""Course-scoped learning progress; all reads are side-effect free."""

from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentUser
from app.db.session import get_db
from app.schemas.progress import LearningProgressPage, ProgressEvidenceDetail, ProgressTrendPage
from app.services.learning_progress import LearningProgressService
from app.services.progress_evidence import read_progress_evidence
from app.services.progress_trends import contributing_records, records_query

router = APIRouter(prefix="/progress", tags=["learning progress"])


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
