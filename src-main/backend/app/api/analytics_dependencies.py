from __future__ import annotations

from typing import NoReturn

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.feedback_dependencies import FeedbackApiException
from app.core.config import settings
from app.db.session import get_db_session
from app.services.access import (
    SqlAlchemyAnalyticsAccessPolicy,
    SqlAlchemyRosterAdapter,
)
from app.services.analytics import (
    AnalyticsAccessPolicy,
    AnalyticsApplication,
    AnalyticsPseudonymizer,
    RosterAdapter,
    SqlAlchemyAnalyticsRepository,
)
from app.services.learning_events import HmacSha256Pseudonymizer


class UnavailableAnalyticsPseudonymizer:
    def pseudonymize(self, namespace: str, reference: str) -> str:
        del namespace, reference
        _unavailable(
            "pseudonymization_unavailable",
            "Pseudonymization is not configured.",
        )


def get_analytics_access_policy(
    session: Session = Depends(get_db_session),
) -> AnalyticsAccessPolicy:
    return SqlAlchemyAnalyticsAccessPolicy(session)


def get_roster_adapter(
    session: Session = Depends(get_db_session),
) -> RosterAdapter:
    return SqlAlchemyRosterAdapter(session)


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
