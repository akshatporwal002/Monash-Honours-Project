from __future__ import annotations

from typing import NoReturn, Protocol

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.feedback_dependencies import FeedbackApiException
from app.core.config import settings
from app.db.session import SessionLocal, get_db_session
from app.schemas.feedback_api import AuthenticatedActor
from app.services.audit import IndependentAuditRecorder
from app.services.research_export import ResearchExportService
from app.services.research_export_repository import (
    SqlAlchemyResearchExportRepository,
)


class ResearchExportAccessPolicy(Protocol):
    async def authorized_course_ids(
        self,
        actor: AuthenticatedActor,
    ) -> set[str]: ...


def get_research_export_access_policy() -> ResearchExportAccessPolicy:
    _unavailable(
        "research_export_authorization_unavailable",
        "Research export authorization is not configured.",
    )


def get_research_export_service(
    session: Session = Depends(get_db_session),
) -> ResearchExportService:
    return ResearchExportService(
        SqlAlchemyResearchExportRepository(session),
        IndependentAuditRecorder(SessionLocal),  # type: ignore[arg-type]
        row_limit=settings.research_export_row_limit,
        batch_size=settings.research_export_batch_size,
    )


def _unavailable(code: str, message: str) -> NoReturn:
    raise FeedbackApiException(503, code, message)
