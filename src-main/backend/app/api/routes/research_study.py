"""Dedicated study workflows and full study export, separate from technical-v2."""

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.feedback_dependencies import require_actor
from app.api.research_study_dependencies import invoke
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db_session
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.research_governance import Code
from app.schemas.research_instruments import InstrumentReceipt
from app.schemas.research_study import (
    StudyAssignmentRead,
    StudyCommand,
    StudyExportRequest,
    StudyPacketRead,
    StudyPlanRead,
    StudyReceipt,
    StudyReconciliationRead,
    StudySelfResponse,
)
from app.services.research.reconciliation import reconcile
from app.services.research.study import ResearchStudyService

router = APIRouter(prefix="/study", tags=["study workflows"])


@router.get("/reconciliation", response_model=StudyReconciliationRead)
def reconciliation(
    study_id: Code,
    course_id: Code,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
):
    response.headers["Cache-Control"] = "no-store"
    return invoke(
        lambda: reconcile(
            ResearchStudyService(session), int(actor.actor_reference), study_id, course_id
        )
    )


@router.get("/plan", response_model=StudyPlanRead | None)
def plan(
    study_id: Code,
    course_id: Code,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
):
    response.headers["Cache-Control"] = "no-store"
    return invoke(
        lambda: ResearchStudyService(session).read_plan(
            int(actor.actor_reference), study_id, course_id
        )
    )


@router.post("/decisions", response_model=StudyReceipt, status_code=201)
async def decision(
    study_id: Code,
    course_id: Code,
    payload: StudyCommand,
    request: Request,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    await security.enforce(request, actor, "research-instruments", mutating=True)
    response.headers["Cache-Control"] = "no-store"
    return invoke(
        lambda: ResearchStudyService(session).record(
            int(actor.actor_reference), study_id, course_id, payload
        )
    )


@router.get("/records", response_model=list[dict[str, str | None]])
def records(
    study_id: Code,
    course_id: Code,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
):
    response.headers["Cache-Control"] = "no-store"
    return invoke(
        lambda: ResearchStudyService(session).read_events(
            int(actor.actor_reference), study_id, course_id
        )
    )


@router.get("/my-forms", response_model=list[StudyAssignmentRead])
def my_forms(
    study_id: Code,
    course_id: Code,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
):
    response.headers["Cache-Control"] = "no-store"
    return invoke(
        lambda: ResearchStudyService(session).participant_forms(
            int(actor.actor_reference), study_id, course_id
        )
    )


@router.post("/my-responses", response_model=InstrumentReceipt, status_code=201)
async def self_response(
    study_id: Code,
    course_id: Code,
    payload: StudySelfResponse,
    request: Request,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    await security.enforce(request, actor, "research-instruments", mutating=True)
    response.headers["Cache-Control"] = "no-store"
    return invoke(
        lambda: ResearchStudyService(session).submit_self(
            int(actor.actor_reference), study_id, course_id, payload
        )
    )


@router.get("/packets/{packet_id}", response_model=StudyPacketRead)
def packet(
    study_id: Code,
    course_id: Code,
    packet_id: Code,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
):
    response.headers["Cache-Control"] = "no-store"
    return invoke(
        lambda: ResearchStudyService(session).packet(
            int(actor.actor_reference), study_id, course_id, packet_id
        )
    )


@router.post("/exports")
async def export(
    study_id: Code,
    course_id: Code,
    payload: StudyExportRequest,
    request: Request,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    await security.enforce(request, actor, "exports", mutating=True)
    prepared = invoke(
        lambda: ResearchStudyService(session).export(
            int(actor.actor_reference), study_id, course_id, payload
        )
    )
    return StreamingResponse(
        prepared.body,
        media_type=prepared.media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="full-study.{payload.format}"',
            "X-Research-Export-Id": prepared.export_id,
        },
    )


from fastapi import Query  # noqa: E402

from app.schemas.research_governance import OperationalField  # noqa: E402
from app.schemas.research_operational import (  # noqa: E402
    OperationalCapture,
    OperationalFieldRead,
    OperationalPreview,
    OperationalSelection,
)
from app.services.research.operational import OperationalCollector  # noqa: E402


@router.post("/operational/preview", response_model=OperationalPreview)
async def operational_preview(
    study_id: Code,
    course_id: Code,
    payload: OperationalSelection,
    request: Request,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    await security.enforce(request, actor, "research-instruments", mutating=True)
    response.headers["Cache-Control"] = "no-store"
    return invoke(
        lambda: OperationalCollector(ResearchStudyService(session)).preview(
            int(actor.actor_reference), study_id, course_id, payload
        )
    )


@router.post("/operational/snapshots", response_model=StudyReceipt, status_code=201)
async def operational_capture(
    study_id: Code,
    course_id: Code,
    payload: OperationalCapture,
    request: Request,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    await security.enforce(request, actor, "research-instruments", mutating=True)
    response.headers["Cache-Control"] = "no-store"
    return invoke(
        lambda: OperationalCollector(ResearchStudyService(session)).capture(
            int(actor.actor_reference), study_id, course_id, payload
        )
    )


@router.get("/operational/snapshots/{snapshot_id}", response_model=dict[str, OperationalFieldRead])
def operational_read(
    study_id: Code,
    course_id: Code,
    snapshot_id: Code,
    response: Response,
    fields: list[OperationalField] = Query(min_length=1, max_length=32),
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
):
    response.headers["Cache-Control"] = "no-store"
    return invoke(
        lambda: OperationalCollector(ResearchStudyService(session)).read(
            int(actor.actor_reference), study_id, course_id, snapshot_id, fields
        )
    )


@router.post("/responses", response_model=InstrumentReceipt, status_code=201)
async def researcher_response(
    study_id: Code,
    course_id: Code,
    payload: StudySelfResponse,
    request: Request,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    await security.enforce(request, actor, "research-instruments", mutating=True)
    response.headers["Cache-Control"] = "no-store"
    return invoke(
        lambda: ResearchStudyService(session).submit_researcher(
            int(actor.actor_reference), study_id, course_id, payload
        )
    )
