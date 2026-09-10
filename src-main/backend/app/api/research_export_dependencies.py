from __future__ import annotations

from typing import Protocol

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.api.feedback_dependencies import require_actor
from app.core.config import settings
from app.db.session import get_db_session
from app.schemas.feedback_api import AuthenticatedActor
from app.schemas.research_governance import TechnicalPairField
from app.services.access import SqlAlchemyResearchExportAccessPolicy
from app.services.research.governed_export import GovernedResearchExportService


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
    actor: AuthenticatedActor = Depends(require_actor),
    study_id: str | None = Query(default=None, min_length=1, max_length=128),
    fields: list[TechnicalPairField] | None = Query(default=None, max_length=64),
) -> GovernedResearchExportService:
    return GovernedResearchExportService(
        session,
        int(actor.actor_reference),
        study_id,
        fields,
        row_limit=settings.research_export_row_limit,
    )
