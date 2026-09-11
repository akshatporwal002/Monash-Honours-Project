"""Scoped synthetic instrument preparation and closed production collection routes."""

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.feedback_dependencies import require_actor
from app.api.research_study_dependencies import invoke
from app.api.routes import research_study
from app.api.security_dependencies import RequestSecurityGuard, get_request_security_guard
from app.db.session import get_db_session
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.research_governance import Code
from app.schemas.research_instruments import (
    ExportField,
    FormFreeze,
    FormRead,
    FormWrite,
    InstrumentExportRequest,
    InstrumentReceipt,
    InstrumentRecordWrite,
)
from app.services.research.instruments import ResearchInstrumentService

router = APIRouter(
    prefix="/research/instruments/{study_id}/{course_id}", tags=["research instruments"]
)


@router.post("/forms/{instrument_key}", response_model=FormRead, status_code=201)
async def save_form(
    study_id: Code,
    course_id: Code,
    instrument_key: Code,
    payload: FormWrite,
    request: Request,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    await security.enforce(request, actor, "research-instruments", mutating=True)
    response.headers["Cache-Control"] = "no-store"
    return invoke(
        lambda: ResearchInstrumentService(session).save_form(
            int(actor.actor_reference), study_id, course_id, instrument_key, payload
        )
    )


@router.get("/forms/{form_id}", response_model=FormRead)
def read_form(
    study_id: Code,
    course_id: Code,
    form_id: Code,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
):
    response.headers["Cache-Control"] = "no-store"
    return invoke(
        lambda: ResearchInstrumentService(session).read_form(
            int(actor.actor_reference), study_id, course_id, form_id
        )
    )


@router.post("/forms/{form_id}/freeze", response_model=FormRead)
async def freeze_form(
    study_id: Code,
    course_id: Code,
    form_id: Code,
    payload: FormFreeze,
    request: Request,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    await security.enforce(request, actor, "research-instruments", mutating=True)
    response.headers["Cache-Control"] = "no-store"
    return invoke(
        lambda: ResearchInstrumentService(session).freeze_form(
            int(actor.actor_reference), study_id, course_id, form_id, payload
        )
    )


@router.post("/records", response_model=InstrumentReceipt, status_code=201)
async def collect(
    study_id: Code,
    course_id: Code,
    payload: InstrumentRecordWrite,
    request: Request,
    response: Response,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    await security.enforce(request, actor, "research-instruments", mutating=True)
    response.headers["Cache-Control"] = "no-store"
    return invoke(
        lambda: ResearchInstrumentService(session).collect(
            int(actor.actor_reference), study_id, course_id, payload
        )
    )


@router.get("/records/{record_id}", response_model=list[dict[str, str | int | None]])
def read_record(
    study_id: Code,
    course_id: Code,
    record_id: Code,
    response: Response,
    fields: list[ExportField] = Query(min_length=1, max_length=24),
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
):
    response.headers["Cache-Control"] = "no-store"
    return invoke(
        lambda: ResearchInstrumentService(session).read(
            int(actor.actor_reference), study_id, course_id, record_id, fields
        )
    )


@router.post("/exports")
async def export(
    study_id: Code,
    course_id: Code,
    payload: InstrumentExportRequest,
    request: Request,
    actor: AuthenticatedActor = Depends(require_actor),
    session: Session = Depends(get_db_session),
    security: RequestSecurityGuard = Depends(get_request_security_guard),
):
    await security.enforce(request, actor, "exports", mutating=True)
    prepared = invoke(
        lambda: ResearchInstrumentService(session).export(
            int(actor.actor_reference), study_id, course_id, payload
        )
    )
    return StreamingResponse(
        prepared.body,
        media_type=prepared.media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="study-instruments.{payload.format}"',
            "X-Research-Export-Id": prepared.export_id,
        },
    )


router.include_router(research_study.router)
