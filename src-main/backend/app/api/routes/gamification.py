"""Persistent learner control over optional rewards."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentStudent
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.gamification import GamificationPreferenceRead, GamificationPreferenceWrite
from app.services.gamification import GamificationService

router = APIRouter(prefix="/students/me/gamification", tags=["gamification"])


@router.get("", response_model=GamificationPreferenceRead)
def read(response: Response, learner: CurrentStudent, session: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    return GamificationService(session).preference(learner.id)


@router.put("", response_model=GamificationPreferenceRead)
async def save(
    payload: GamificationPreferenceWrite,
    request: Request,
    response: Response,
    learner: CurrentStudent,
    session: Session = Depends(get_db),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    response.headers["Cache-Control"] = "no-store"
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(learner.id), role=learner.role.value),
        "gamification",
        mutating=True,
    )
    try:
        return GamificationService(session).save_preference(learner.id, payload)
    except (ValueError, IntegrityError, OperationalError) as error:
        session.rollback()
        raise HTTPException(
            409, "Gamification preferences changed or are busy. Reload before retrying."
        ) from error
