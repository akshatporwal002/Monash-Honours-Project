from __future__ import annotations

from typing import NoReturn

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.feedback_dependencies import FeedbackApiException
from app.core.config import settings
from app.db.session import get_db_session
from app.services.analytics import (
    AnalyticsAccessPolicy,
    AnalyticsApplication,
    AnalyticsPseudonymizer,
    RosterAdapter,
    SqlAlchemyAnalyticsRepository,
)
from app.services.learning_events import HmacSha256Pseudonymizer


class UnavailableRosterAdapter:
    async def learner_references(self, course_ids: set[str]) -> list[str]:
        del course_ids
        _unavailable("roster_unavailable", "Roster access is not configured.")


class UnavailableAnalyticsPseudonymizer:
    def pseudonymize(self, namespace: str, reference: str) -> str:
        del namespace, reference
        _unavailable(
            "pseudonymization_unavailable",
            "Pseudonymization is not configured.",
        )


def get_analytics_access_policy() -> AnalyticsAccessPolicy:
    _unavailable(
        "analytics_authorization_unavailable",
        "Analytics authorization is not configured.",
    )


def get_roster_adapter() -> RosterAdapter:
    return UnavailableRosterAdapter()


def get_analytics_pseudonymizer() -> AnalyticsPseudonymizer:
    secret = settings.learning_event_pseudonym_secret
    if secret is None:
        return UnavailableAnalyticsPseudonymizer()
    try:
        return HmacSha256Pseudonymizer(secret.get_secret_value())
    except Exception:
        return UnavailableAnalyticsPseudonymizer()


def get_analytics_application(
    session: Session = Depends(get_db_session),
    roster_adapter: RosterAdapter = Depends(get_roster_adapter),
    pseudonymizer: AnalyticsPseudonymizer = Depends(get_analytics_pseudonymizer),
) -> AnalyticsApplication:
    return AnalyticsApplication(
        SqlAlchemyAnalyticsRepository(session),
        roster_adapter,
        pseudonymizer,
    )


def _unavailable(code: str, message: str) -> NoReturn:
    raise FeedbackApiException(503, code, message)
