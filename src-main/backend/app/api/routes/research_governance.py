"""Restricted preparation, self-consent and explicitly authorized research controls."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.feedback_dependencies import require_actor
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db_session
from app.models.lms import Enrollment, EnrollmentStatus
from app.models.user import User, UserRole
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.research_governance import (
    Code,
    DisposalExecute,
    DisposalPreview,
    GovernanceCommand,
    GovernanceHistoryEntry,
    GovernanceReceipt,
    ParticipationRead,
)
from app.services.research.governance import (
    GovernanceConflict,
    GovernanceDenied,
    ResearchGovernanceService,
    utc,
)

router = APIRouter(prefix="/research/governance", tags=["research"])


@router.post("/{study_id}/disposal/preview")
async def disposal_preview(
    study_id: Code,
    payload: DisposalPreview,
    request: Request,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    from app.api.research_study_dependencies import invoke
    from app.services.research.disposal import custodian, inventory

    await security.enforce(request, actor, "research-governance", mutating=True)
    response.headers["Cache-Control"] = "no-store"
    policy = ResearchGovernanceService(session)

    def prepare():
        custodian(policy, int(actor.actor_reference))
        return inventory(policy, study_id, payload.record_ids)

    return invoke(prepare)


@router.post("/{study_id}/disposal/execute")
async def disposal_execute(
    study_id: Code,
    payload: DisposalExecute,
    request: Request,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    from app.api.research_study_dependencies import invoke
    from app.services.research.disposal import execute

    await security.enforce(request, actor, "research-governance", mutating=True)
    response.headers["Cache-Control"] = "no-store"
    return invoke(
        lambda: execute(
            ResearchGovernanceService(session), int(actor.actor_reference), study_id, payload
        )
    )


@router.post("/{study_id}/decisions", response_model=GovernanceReceipt, status_code=201)
async def record_decision(
    study_id: Code,
    payload: GovernanceCommand,
    request: Request,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    await security.enforce(request, actor, "research-governance", mutating=True)
    response.headers["Cache-Control"] = "no-store"
    try:
        event = ResearchGovernanceService(session).record(
            int(actor.actor_reference), study_id, payload
        )
    except GovernanceDenied as error:
        raise HTTPException(403, str(error)) from None
    except GovernanceConflict as error:
        raise HTTPException(409, str(error)) from None
    return GovernanceReceipt(
        id=event.id,
        study_id=study_id,
        revision=event.revision,
        kind=event.kind,
        recorded_at=utc(event.recorded_at),
        production_active=ResearchGovernanceService(session).release_active(study_id),
    )


@router.get("/{study_id}/decisions", response_model=list[GovernanceHistoryEntry])
def read_decisions(
    study_id: Code,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
):
    response.headers["Cache-Control"] = "no-store"
    user = session.get(User, int(actor.actor_reference))
    if not user or not user.is_active or user.role != UserRole.ADMINISTRATOR:
        raise HTTPException(403, "governance_custodian_required")
    return [
        GovernanceHistoryEntry(
            id=e.id,
            study_id=study_id,
            revision=e.revision,
            kind=e.kind,
            recorded_at=utc(e.recorded_at),
            command=e.command,
            actor_user_id=e.actor_user_id,
        )
        for e in ResearchGovernanceService(session).events(study_id)
    ]


@router.get("/{study_id}/participation/{course_id}", response_model=ParticipationRead)
def read_participation(
    study_id: Code,
    course_id: Code,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
):
    response.headers["Cache-Control"] = "no-store"
    user_id = int(actor.actor_reference)
    user = session.get(User, user_id, populate_existing=True)
    enrollment = session.scalar(
        select(Enrollment.id).where(
            Enrollment.student_id == user_id,
            Enrollment.course_id == course_id,
            Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
        )
    )
    policy = ResearchGovernanceService(session)
    events = policy.events(study_id)
    scope = next((e for e in reversed(events) if e.kind == "scope"), None)
    if (
        user is None
        or not user.is_active
        or enrollment is None
        or scope is None
        or course_id not in policy.decision(scope).course_ids
    ):
        raise HTTPException(403, "participation_scope_denied")
    consent = policy._subject_event(events, "consent", course_id, user_id)
    return ParticipationRead(
        study_id=study_id,
        scope_id=scope.id,
        revision=events[-1].revision,
        scope=policy.decision(scope),
        consent=policy.decision(consent) if consent else None,
        production_active=policy.release_active(study_id),
    )
