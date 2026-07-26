from __future__ import annotations

from typing import Protocol

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, get_db_session
from app.schemas.feedback_api import AuthenticatedActor
from app.services.access import SqlAlchemyResearchExportAccessPolicy
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


def get_research_export_access_policy(
    session: Session = Depends(get_db_session),
) -> ResearchExportAccessPolicy:
    return SqlAlchemyResearchExportAccessPolicy(session)


def get_research_export_service(
    session: Session = Depends(get_db_session),
) -> ResearchExportService:
    return ResearchExportService(
        SqlAlchemyResearchExportRepository(session),
        IndependentAuditRecorder(SessionLocal),  # type: ignore[arg-type]
        row_limit=settings.research_export_row_limit,
        batch_size=settings.research_export_batch_size,
    )
