"""Learner-self endpoints for non-essential support preferences."""

from hashlib import sha256
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentStudent
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db
from app.models.lms import PlatformAuditEvent
from app.schemas.feedback_api import AuthenticatedActor
from app.services.learner_preferences.contracts import (
    LearnerPreferencesRead,
    LearnerPreferencesWrite,
)
from app.services.learner_preferences.repository import SqlAlchemyLearnerPreferencesRepository
from app.services.learner_preferences.service import (
    LearnerPreferencesConflictError,
    LearnerPreferencesService,
)

router = APIRouter(prefix="/students/me/preferences", tags=["learner preferences"])


def _service(session: Session):
    return LearnerPreferencesService(SqlAlchemyLearnerPreferencesRepository(session))


def _no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"


def _audit_fingerprint(value: str) -> str:
    return sha256(f"learner-preferences:{value}".encode()).hexdigest()


@router.get("", response_model=LearnerPreferencesRead)
def read_preferences(
    response: Response, student: CurrentStudent, session: Session = Depends(get_db)
):
    _no_store(response)
    return _service(session).read(student.id)


@router.put("", response_model=LearnerPreferencesRead, status_code=201)
async def save_preferences(
    payload: LearnerPreferencesWrite,
    request: Request,
    response: Response,
    student: CurrentStudent,
    session: Session = Depends(get_db),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    _no_store(response)
    await security.enforce(
        request,
        AuthenticatedActor(actor_reference=str(student.id), role=student.role.value),
        "learner-preferences",
        mutating=True,
    )
    repository = SqlAlchemyLearnerPreferencesRepository(session)
    replay = repository.by_key(student.id, payload.idempotency_key) is not None
    try:
        result = LearnerPreferencesService(repository).save(student.id, payload)
    except LearnerPreferencesConflictError as error:
        raise HTTPException(
            409, "The preference request conflicts with a newer revision."
        ) from error
    if replay:
        response.status_code = 200
    # The revision has already committed. Audit is deliberately best effort and
    # contains only opaque references, never preference values or identity claims.
    try:
        session.add(
            PlatformAuditEvent(
                actor_id=student.id,
                action="learner_preferences.saved",
                resource_type="learner_preference_revision",
            resource_id=_audit_fingerprint(str(result.revision)),
                correlation_id=str(uuid4()),
                outcome="success",
                details={
                    "outcome": "replayed" if replay else "created",
                    "schema_version": result.schema_version,
                },
            )
        )
        session.commit()
    except Exception:
        session.rollback()
    return result


@router.get("/history", response_model=list[LearnerPreferencesRead])
def preference_history(
    response: Response,
    student: CurrentStudent,
    session: Session = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
):
    _no_store(response)
    return _service(session).history(student.id, min(max(limit, 1), 100), max(offset, 0))
